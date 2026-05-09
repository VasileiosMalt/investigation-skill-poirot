"""
run_image_analysis.py — Phase 3: VQA/VLLM image analysis pipeline.

Usage:
    python run_image_analysis.py \
        --evidence evidence_manifest.json \
        --ckb case_knowledge_base.md \
        --output-dir ./output \
        [--api-key KEY] [--model gpt-4o] [--provider openai|anthropic|openrouter]

Outputs:
    image_analysis_report.json   — Machine-readable findings per image
    image_analysis_report.md     — Human-readable report section
"""

import os
import sys
import json
import base64
import argparse
import time
import random
from pathlib import Path
from datetime import datetime
from typing import Optional

# ── Env bootstrap (loads .env when run standalone) ─────────────────────────────
try:
    _scripts_dir = Path(__file__).parent
    if str(_scripts_dir) not in sys.path:
        sys.path.insert(0, str(_scripts_dir))
    from env_config import get_config as _get_cfg
    _get_cfg()
except Exception:
    pass

# ── Optional imports
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import piexif
    HAS_PIEXIF = True
except ImportError:
    HAS_PIEXIF = False


# ── Image pre-processing ───────────────────────────────────────────────────────

MAX_IMAGE_SIDE = 2048
MAX_IMAGE_BYTES = 19 * 1024 * 1024  # 19MB safety margin


def encode_image_to_base64(image_path: Path, max_side: int = MAX_IMAGE_SIDE) -> Optional[str]:
    """Load, resize if needed, and base64-encode an image for API calls."""
    if not HAS_PIL:
        # Fallback: raw bytes
        try:
            data = image_path.read_bytes()
            if len(data) > MAX_IMAGE_BYTES:
                return None  # Cannot resize without PIL
            return base64.b64encode(data).decode()
        except OSError:
            return None

    try:
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (handles RGBA, P, CMYK, etc.)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # Resize if needed
            w, h = img.size
            if max(w, h) > max_side:
                scale = max_side / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

            # Convert to JPEG bytes
            import io
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=90)
            buffer.seek(0)
            return base64.b64encode(buffer.read()).decode()
    except Exception as e:
        print(f"    [WARN] Could not encode {image_path.name}: {e}")
        return None


def extract_exif(image_path: Path) -> dict:
    """Extract EXIF metadata from an image."""
    exif_data = {}

    if not HAS_PIEXIF:
        # Try basic Pillow EXIF
        if HAS_PIL:
            try:
                with Image.open(image_path) as img:
                    raw = img._getexif()
                    if raw:
                        from PIL.ExifTags import TAGS
                        for tag_id, val in raw.items():
                            tag = TAGS.get(tag_id, str(tag_id))
                            if isinstance(val, bytes):
                                try:
                                    val = val.decode("utf-8", errors="replace")
                                except Exception:
                                    val = val.hex()
                            exif_data[tag] = str(val)[:200]  # Cap long values
            except Exception:
                pass
        return exif_data

    try:
        exif_dict = piexif.load(str(image_path))
        interesting_tags = {
            "0th": {piexif.ImageIFD.Make: "Make", piexif.ImageIFD.Model: "Model",
                    piexif.ImageIFD.Software: "Software",
                    piexif.ImageIFD.DateTime: "DateTime"},
            "Exif": {piexif.ExifIFD.DateTimeOriginal: "DateTimeOriginal",
                     piexif.ExifIFD.DateTimeDigitized: "DateTimeDigitized",
                     piexif.ExifIFD.Flash: "Flash"},
            "GPS": {piexif.GPSIFD.GPSLatitude: "GPSLatitude",
                    piexif.GPSIFD.GPSLongitude: "GPSLongitude",
                    piexif.GPSIFD.GPSAltitude: "GPSAltitude"}
        }
        for ifd_name, tags in interesting_tags.items():
            if ifd_name in exif_dict:
                for tag_id, label in tags.items():
                    val = exif_dict[ifd_name].get(tag_id)
                    if val is not None:
                        if isinstance(val, bytes):
                            try:
                                val = val.decode("ascii", errors="replace").strip("\x00")
                            except Exception:
                                val = val.hex()
                        exif_data[label] = str(val)[:200]
    except Exception:
        pass

    # Tampering indicators
    tampering = []
    dt_orig = exif_data.get("DateTimeOriginal", "")
    dt_mod = exif_data.get("DateTime", "")
    software = exif_data.get("Software", "")

    if dt_orig and dt_mod and dt_orig != dt_mod:
        tampering.append(f"ModifyDate ({dt_mod}) differs from OriginalDate ({dt_orig})")
    if any(kw in software.lower() for kw in ["photoshop", "gimp", "lightroom", "affinity", "capture one"]):
        tampering.append(f"Image editing software detected: {software}")

    exif_data["_tampering_indicators"] = tampering

    return exif_data


# ── VQA API calls ──────────────────────────────────────────────────────────────

FORENSIC_SYSTEM_PROMPT = (
    "You are a precise visual observer assisting a factual analysis. "
    "Describe only what you see with maximum accuracy and zero speculation. "
    "If you cannot determine a detail, state what you can observe and note the limit explicitly. "
    "Never name people. Never infer intent or emotion. Never assert cause or meaning. "
    "Report observable physical facts only."
)


def call_openai_vision(client, model: str, b64_image: str, question: str,
                       system_prompt: str = FORENSIC_SYSTEM_PROMPT) -> dict:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{b64_image}",
                        "detail": "high"
                    }},
                    {"type": "text", "text": question}
                ]}
            ],
            max_tokens=1500,
            temperature=0
        )
        return {"answer": response.choices[0].message.content, "success": True}
    except Exception as e:
        return {"answer": None, "success": False, "error": str(e)}


def call_anthropic_vision(client, model: str, b64_image: str, question: str) -> dict:
    try:
        response = client.messages.create(
            model=model,
            max_tokens=1500,
            system=FORENSIC_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": "image/jpeg", "data": b64_image
                }},
                {"type": "text", "text": question}
            ]}]
        )
        return {"answer": response.content[0].text, "success": True}
    except Exception as e:
        return {"answer": None, "success": False, "error": str(e)}


def call_vision_model(provider: str, client, model: str,
                      b64_image: str, question: str) -> dict:
    if provider == "anthropic":
        return call_anthropic_vision(client, model, b64_image, question)
    else:
        return call_openai_vision(client, model, b64_image, question)


def call_with_retry(fn, max_retries: int = 3) -> dict:
    for attempt in range(max_retries):
        result = fn()
        if result["success"]:
            return result
        wait = (2 ** attempt) + random.random()
        print(f"      Retry {attempt + 1}/{max_retries} after {wait:.1f}s — {result.get('error', '')}")
        time.sleep(wait)
    return result


# ── Discrete Observable Element (DOE) parser ──────────────────────────────────

DOE_EXTRACTION_PROMPT = (
    "You are parsing a visual observation report into discrete observable elements.\n"
    "Given the following observation text, list every distinct observable element as a "
    "numbered list. Each element must be a single object, spatial relationship, text item, "
    "person/figure, lighting characteristic, or physical state description. "
    "Be exhaustive. Do not merge elements. Do not interpret.\n\n"
    "Observation text:\n{observation}\n\n"
    "Return ONLY a numbered list of discrete elements, one per line."
)

PASS2_QUESTION_GENERATION_PROMPT = (
    "You are generating precise follow-up questions for a visual analysis.\n\n"
    "Rules:\n"
    "- One question per element\n"
    "- Physical, verifiable language only (position, colour, text, shape, dimension, condition)\n"
    "- Never embed the expected answer in the question\n"
    "- Never name people or case-specific entities\n"
    "- The question must be answerable with 'no such element is present'\n"
    "- Only generate a question if Pass 1 did NOT already describe this element with full precision\n\n"
    "Discrete observable element:\n{doe}\n\n"
    "Pass 1 description of this element (may be vague or complete):\n{pass1_description}\n\n"
    "If Pass 1 already described this element fully, respond with: SKIP\n"
    "Otherwise, write a single precise follow-up question."
)

DEEP_DRILL_EVALUATION_PROMPT = (
    "Evaluate whether the following observed element meets all three conditions for a deep-drill.\n\n"
    "CONDITION A — Specificity: Is the element described precisely enough to form a targeted question?\n"
    "CONDITION B — Anomaly: Is the element objectively anomalous by one of:\n"
    "  B1: It contradicts another element within the same image\n"
    "  B2: It contradicts this established external fact: {external_fact}\n"
    "  B3: It is physically implausible in the described context\n"
    "CONDITION C — Materiality: Does the anomaly relate to the case type: {case_type}\n\n"
    "Element description:\n{element}\n\n"
    "Context (surrounding described scene):\n{context}\n\n"
    "Respond in this exact format:\n"
    "A: PASS or FAIL — [one sentence reason]\n"
    "B: PASS or FAIL — [one sentence reason, specify B1/B2/B3 if PASS]\n"
    "C: PASS or FAIL — [one sentence reason]\n"
    "VERDICT: DRILL or NO_DRILL\n"
    "If DRILL: [Write the single targeted deep-drill question here]"
)


def extract_does_with_llm(pass1_response: str, text_client, model: str) -> list[str]:
    """Use LLM to parse Pass 1 response into discrete observable elements."""
    if text_client is None:
        # Fallback: split on sentences
        import re
        sentences = re.split(r'(?<=[.!?])\s+', pass1_response.strip())
        return [s.strip() for s in sentences if len(s.strip()) > 20]

    try:
        prompt = DOE_EXTRACTION_PROMPT.format(observation=pass1_response)
        resp = text_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=1000
        )
        raw = resp.choices[0].message.content.strip()
        does = []
        for line in raw.split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                # Strip leading number/bullet
                import re
                cleaned = re.sub(r"^[\d\-\.\)]+\s*", "", line).strip()
                if cleaned:
                    does.append(cleaned)
        return does
    except Exception as e:
        print(f"      [WARN] DOE extraction failed: {e}")
        return []


def generate_pass2_question(doe: str, pass1_description: str, text_client, model: str) -> Optional[str]:
    """Generate a Pass 2 question for a DOE, or None if Pass 1 was already precise."""
    if text_client is None:
        # Simple heuristic: if the DOE contains vague qualifiers, ask for precision
        vague_signals = ["some", "appears", "possibly", "unclear", "partial", "angled", "scattered",
                         "various", "something", "certain", "few", "several", "might"]
        if any(v in doe.lower() for v in vague_signals):
            return f"Describe more precisely: {doe}"
        if "text" in doe.lower() or "number" in doe.lower() or "label" in doe.lower():
            return f"Transcribe exactly: {doe}"
        return None

    try:
        prompt = PASS2_QUESTION_GENERATION_PROMPT.format(
            doe=doe,
            pass1_description=pass1_description
        )
        resp = text_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200
        )
        q = resp.choices[0].message.content.strip()
        if q.upper() == "SKIP" or q.startswith("SKIP"):
            return None
        return q
    except Exception as e:
        print(f"      [WARN] Pass 2 question generation failed: {e}")
        return None


def evaluate_deep_drill(doe: str, context: str, case_type: str,
                        external_facts: list[str], text_client, model: str) -> dict:
    """Evaluate DOE against A+B+C conditions and return verdict + question."""
    external_fact_str = "; ".join(external_facts) if external_facts else "No specific external facts provided"

    if text_client is None:
        return {"verdict": "NO_DRILL", "reason": "No LLM available for evaluation", "question": None}

    try:
        prompt = DEEP_DRILL_EVALUATION_PROMPT.format(
            external_fact=external_fact_str,
            case_type=case_type,
            element=doe,
            context=context
        )
        resp = text_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=400
        )
        raw = resp.choices[0].message.content.strip()
        lines = raw.split("\n")
        verdict = "NO_DRILL"
        drill_question = None
        for line in lines:
            if line.startswith("VERDICT:"):
                verdict = "DRILL" if "DRILL" in line and "NO_DRILL" not in line else "NO_DRILL"
            if verdict == "DRILL" and line.startswith("If DRILL:"):
                drill_question = line.replace("If DRILL:", "").strip()
        return {"verdict": verdict, "evaluation": raw, "question": drill_question}
    except Exception as e:
        return {"verdict": "NO_DRILL", "reason": str(e), "question": None}


# ── Adaptive VQA loop ──────────────────────────────────────────────────────────

def analyse_image(entry: dict, ckb_text: str, established_facts: list[str],
                  case_type: str, provider: str, client, model: str,
                  text_client, output_dir: Path) -> dict:
    """Run the two-pass adaptive VQA loop on a single image."""
    path = Path(entry["path"])
    result = {
        "path": entry["path"],
        "relative_path": entry["relative_path"],
        "relevance_score": entry["relevance_score"],
        "exif": {},
        "pass1_response": None,
        "does": [],
        "pass2_findings": [],
        "deep_drill_log": [],
        "epistemic_findings": [],
        "analysis_status": "pending"
    }

    # EXIF extraction
    result["exif"] = extract_exif(path)

    # Encode image
    b64 = encode_image_to_base64(path)
    if not b64:
        result["analysis_status"] = "failed_encoding"
        return result

    # ── PASS 1: Neutral observation ──────────────────────────────────────────
    pass1_prompt = entry.get("pass1_prompt", (
        "Describe this image completely and objectively. Include every distinct object, "
        "its position, lighting conditions, any text or markings, the physical state of all "
        "objects, and anything that appears physically inconsistent or unusual. "
        "Do not interpret, infer, or speculate. Describe only what is directly visible."
    ))

    print(f"    [PASS 1] neutral observation...")
    p1 = call_with_retry(lambda: call_vision_model(provider, client, model, b64, pass1_prompt))
    if not p1["success"]:
        result["analysis_status"] = "pass1_failed"
        return result

    result["pass1_response"] = p1["answer"]
    print(f"    [PASS 1] received {len(p1['answer'])} chars")

    # ── Parse DOEs ───────────────────────────────────────────────────────────
    does = extract_does_with_llm(p1["answer"], text_client, model)
    result["does"] = does
    print(f"    [DOEs] extracted {len(does)} discrete observable elements")

    # ── PASS 2: Derived questions per DOE ────────────────────────────────────
    for doe in does:
        q = generate_pass2_question(doe, p1["answer"], text_client, model)
        if q is None:
            result["pass2_findings"].append({
                "doe": doe, "question": None, "answer": "SKIP — Pass 1 sufficient",
                "epistemic_state": "E"
            })
            continue

        print(f"    [PASS 2] asking: {q[:80]}...")
        p2 = call_with_retry(lambda q=q: call_vision_model(provider, client, model, b64, q))
        answer = p2["answer"] if p2["success"] else "[FAILED]"

        finding = {"doe": doe, "question": q, "answer": answer, "epistemic_state": "E"}
        result["pass2_findings"].append(finding)
        time.sleep(0.3)

        # ── Evaluate for Deep-Drill ──────────────────────────────────────────
        if p2["success"] and answer != "[FAILED]":
            evaluation = evaluate_deep_drill(
                doe=f"{doe}\n\nPass 2 response: {answer}",
                context=p1["answer"][:1000],
                case_type=case_type,
                external_facts=established_facts[:5],
                text_client=text_client,
                model=model
            )
            drill_entry = {
                "doe": doe,
                "conditions_evaluation": evaluation.get("evaluation", ""),
                "verdict": evaluation["verdict"],
                "drill_question": evaluation.get("question"),
                "rounds": []
            }

            if evaluation["verdict"] == "DRILL" and evaluation.get("question"):
                # Execute deep-drill rounds (max 3)
                for round_num in range(1, 4):
                    dq = evaluation["question"] if round_num == 1 else None
                    if dq is None:
                        break

                    print(f"    [DEEP-DRILL round {round_num}] {dq[:80]}...")
                    dr = call_with_retry(
                        lambda dq=dq: call_vision_model(provider, client, model, b64, dq)
                    )
                    dr_answer = dr["answer"] if dr["success"] else "[FAILED]"
                    drill_entry["rounds"].append({
                        "round": round_num,
                        "question": dq,
                        "answer": dr_answer
                    })
                    time.sleep(0.3)

                    # Check if anomaly extends to a further round
                    # Only continue if last answer added new specific information
                    if not dr["success"] or len(dr_answer.strip()) < 30:
                        break
                    # Update question for next round only if warranted
                    evaluation["question"] = None  # Stop after round 1 unless manual escalation

            result["deep_drill_log"].append(drill_entry)

    result["analysis_status"] = "complete"
    result["pass2_count"] = len([f for f in result["pass2_findings"] if f["question"] is not None])
    result["deep_drill_triggered"] = sum(
        1 for d in result["deep_drill_log"] if d["verdict"] == "DRILL"
    )
    return result


def format_image_report_entry(result: dict) -> str:
    """Format a single image analysis result as Markdown using the adaptive loop schema."""
    path = Path(result["path"])
    rel_path = result["relative_path"]
    score = result["relevance_score"]
    exif = result.get("exif", {})
    pass1 = result.get("pass1_response", "")
    pass2 = result.get("pass2_findings", [])
    drills = result.get("deep_drill_log", [])

    abs_path = path.resolve().as_posix()
    lines = [
        f"### 📸 {path.name} — Relevance: {score}",
        f"**Path:** `{rel_path}`  ",
        f"**Link:** [View Image](file:///{abs_path})",
    ]

    # EXIF — raw facts only
    exif_parts = []
    if exif.get("DateTimeOriginal"):
        exif_parts.append(f"DateTimeOriginal: {exif['DateTimeOriginal']}")
    if exif.get("DateTime") and exif.get("DateTime") != exif.get("DateTimeOriginal"):
        exif_parts.append(f"ModifyDate: {exif['DateTime']}")
    if exif.get("Make") or exif.get("Model"):
        exif_parts.append(f"Device: {exif.get('Make','')} {exif.get('Model','')}".strip())
    if exif.get("Software"):
        exif_parts.append(f"Software: {exif['Software']}")
    if exif_parts:
        lines.append("**EXIF (raw fields):**")
        for ep in exif_parts:
            lines.append(f"- {ep}")

    field_notes = exif.get("_tampering_indicators", [])
    if field_notes:
        lines.append("**EXIF field discrepancy notes (raw facts — no interpretation):**")
        for note in field_notes:
            lines.append(f"- {note}")
    lines.append("")

    # Pass 1 summary
    if pass1:
        preview = pass1[:500].replace("\n", " ")
        lines.append(f"**PASS 1 — Neutral Observation (first 500 chars):** {preview}")
        lines.append(f"**DOEs identified:** {len(result.get('does', []))}")
        lines.append("")

    # Pass 2 findings
    substantive_p2 = [f for f in pass2 if f.get("question") is not None and f["answer"] != "SKIP — Pass 1 sufficient"]
    if substantive_p2:
        lines.append("**PASS 2 — Derived Questions:**")
        lines.append("")
        lines.append("| DOE (summary) | Question | Answer summary | State |")
        lines.append("|---|---|---|---|")
        for f in substantive_p2:
            doe_short = f["doe"][:60].replace("|", "/")
            q_short = (f["question"] or "")[:80].replace("|", "/")
            ans_short = f["answer"][:150].replace("\n", " ").replace("|", "/")
            lines.append(f"| {doe_short} | {q_short} | {ans_short} | {f.get('epistemic_state','E')} |")
        lines.append("")

    # Deep-drill log
    triggered = [d for d in drills if d["verdict"] == "DRILL"]
    if triggered:
        lines.append("**DEEP DRILL LOG:**")
        lines.append("")
        lines.append("| DOE | Verdict | Round | Question | Answer summary |")
        lines.append("|---|---|---|---|---|")
        for d in triggered:
            doe_short = d["doe"][:60].replace("|", "/")
            for r in d.get("rounds", []):
                q_short = r["question"][:80].replace("|", "/")
                ans_short = r["answer"][:150].replace("\n", " ").replace("|", "/")
                lines.append(f"| {doe_short} | DRILL | {r['round']} | {q_short} | {ans_short} |")
        lines.append("")

    if not substantive_p2 and not triggered:
        lines.append("*No Pass 2 questions generated — Pass 1 observations were fully precise or no anomalies warranting drill.*")
        lines.append("")

    lines.append("---")
    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Poirot Phase 3 — Adaptive Image Analysis")
    parser.add_argument("--evidence", required=True, help="Path to evidence_manifest.json")
    parser.add_argument("--ckb", required=True, help="Path to case_knowledge_base.md")
    parser.add_argument("--output-dir", required=True, help="Output directory for reports")
    parser.add_argument("--api-key", help="API key (or set OPENAI_API_KEY / ANTHROPIC_API_KEY)")
    parser.add_argument("--model", default="gpt-4o", help="Vision model to use")
    parser.add_argument("--text-model", default=None, help="Text model for DOE parsing and question generation (defaults to --model)")
    parser.add_argument("--provider", default="openai",
                        choices=["openai", "anthropic", "openrouter"],
                        help="API provider")
    parser.add_argument("--min-relevance", type=float, default=0.1,
                        help="Skip images below this relevance threshold")
    parser.add_argument("--case-type", default="general investigation",
                        help="Case type description for deep-drill materiality check")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    evidence_path = Path(args.evidence)
    if not evidence_path.exists():
        print(f"ERROR: Evidence manifest not found: {evidence_path}", file=sys.stderr)
        sys.exit(1)

    evidence_data = json.loads(evidence_path.read_bytes())
    ckb_text = Path(args.ckb).read_text(encoding="utf-8") if Path(args.ckb).exists() else ""

    # Extract established [E] facts from CKB for external inconsistency checks
    import re
    established_facts = re.findall(r'\[E\][^\n]+', ckb_text)[:20]

    # Filter to image files only
    images = [
        e for e in evidence_data["evidence"]
        if e["modality"] == "image"
        and e["relevance_score"] >= args.min_relevance
        and not e.get("duplicate_of")
    ]
    print(f"[Poirot Phase 3] Analysing {len(images)} images (threshold: {args.min_relevance})")

    # Initialise vision API client
    api_key = (args.api_key or
               os.environ.get("ANTHROPIC_API_KEY" if args.provider == "anthropic" else "OPENAI_API_KEY"))
    client = None
    text_client = None
    if api_key:
        if args.provider == "anthropic":
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                text_client = client  # Anthropic client handles text too
            except ImportError:
                print("ERROR: anthropic package not installed.", file=sys.stderr)
                sys.exit(1)
        else:
            try:
                import openai
                kwargs = {"api_key": api_key}
                if args.provider == "openrouter":
                    kwargs["base_url"] = "https://openrouter.ai/api/v1"
                client = openai.OpenAI(**kwargs)
                text_client = client  # Same client handles text completions
            except ImportError:
                print("ERROR: openai package not installed.", file=sys.stderr)
                sys.exit(1)
    else:
        print("WARNING: No API key — metadata-only mode.", file=sys.stderr)

    text_model = args.text_model or args.model

    # Process each image
    all_results = []
    for i, entry in enumerate(images):
        print(f"\n  [{i+1}/{len(images)}] {entry['relative_path']} (score: {entry['relevance_score']})")

        if client:
            result = analyse_image(
                entry=entry,
                ckb_text=ckb_text,
                established_facts=established_facts,
                case_type=args.case_type,
                provider=args.provider,
                client=client,
                model=args.model,
                text_client=text_client,
                output_dir=output_dir
            )
        else:
            result = {
                "path": entry["path"],
                "relative_path": entry["relative_path"],
                "relevance_score": entry["relevance_score"],
                "exif": extract_exif(Path(entry["path"])),
                "pass1_response": None,
                "does": [],
                "pass2_findings": [],
                "deep_drill_log": [],
                "analysis_status": "metadata_only"
            }

        all_results.append(result)
        p2_count = result.get("pass2_count", 0)
        drill_count = result.get("deep_drill_triggered", 0)
        print(f"    → Pass 2 questions: {p2_count} | Deep drills triggered: {drill_count} | Status: {result['analysis_status']}")

    # Write JSON report
    json_report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "model": args.model,
        "provider": args.provider,
        "images_analysed": len(all_results),
        "results": all_results
    }
    json_path = output_dir / "image_analysis_report.json"
    json_path.write_text(json.dumps(json_report, indent=2, default=str), encoding="utf-8")
    print(f"\n[Poirot Phase 3] Written: {json_path}")

    # Write Markdown report
    md_lines = [
        "# Phase 3 — Image Analysis Report",
        f"*Generated: {datetime.utcnow().isoformat()}Z | Model: {args.model}*",
        f"*Images analysed: {len(all_results)}*",
        "",
        "> Reasoning protocol: all findings are derived from neutral Pass 1 observations.",
        "> Questions were generated from what was observed, not from case context.",
        "> Deep-drill follow-ups were only triggered when Specificity + Anomaly + Materiality conditions were all met.",
        ""
    ]

    for result in all_results:
        entry_md = format_image_report_entry(result)
        if entry_md:
            md_lines.append(entry_md)

    md_path = output_dir / "image_analysis_report.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"[Poirot Phase 3] Written: {md_path}")
    total_drills = sum(r.get("deep_drill_triggered", 0) for r in all_results)
    print(f"\n[Poirot Phase 3] Complete. Deep-drills triggered: {total_drills} across {len(all_results)} images.")
    print(f"  Next: run_audio_video_analysis.py (if AV evidence exists)")


if __name__ == "__main__":
    main()
