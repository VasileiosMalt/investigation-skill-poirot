"""
synthesize_report.py — Phase 5: Cross-modal synthesis and final Poirot report.

Usage:
    python synthesize_report.py \
        --ckb case_knowledge_base.md \
        --image-report image_analysis_report.json \
        --av-report av_analysis_report.json \
        --output-dir ./output \
        [--api-key KEY] [--model claude-opus-4-5] [--provider openai|anthropic|openrouter]

Outputs:
    poirot_report.md        — Final investigation report (human-readable)
    poirot_report.json      — Machine-readable structured report
    synthesis_notes.md      — Working cross-modal correlation notes
"""

import os
import sys
import json
import argparse
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


# ── Data loading

def load_json_safe(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_bytes())
    except Exception as e:
        print(f"  [WARN] Could not load {path}: {e}")
        return {}


def extract_established_image_findings(image_report: dict) -> list[dict]:
    """Extract [E] and [S] findings from the adaptive VQA loop image report."""
    findings = []
    for result in image_report.get("results", []):
        # Gather Pass 1 response, Pass 2 findings, deep drill log
        pass1 = result.get("pass1_response", "")
        pass2 = [f for f in result.get("pass2_findings", []) if f.get("question") is not None]
        drills = [d for d in result.get("deep_drill_log", []) if d.get("rounds")]
        exif = result.get("exif", {})

        if not pass1 and not pass2 and not drills:
            continue  # Skip if no analysis was run

        findings.append({
            "file": result["relative_path"],
            "path": result["path"],
            "relevance_score": result["relevance_score"],
            "exif": exif,
            "pass1_summary": pass1[:600] if pass1 else "",
            "pass2_findings": pass2,
            "deep_drill_rounds": drills
        })
    return findings


def extract_established_av_findings(av_report: dict) -> list[dict]:
    """Extract [E] findings from the adaptive AV loop report."""
    results = []
    for result in av_report.get("results", []):
        transcript = result.get("transcript", {})
        adaptive = result.get("adaptive_analysis", {})
        if transcript.get("success") or adaptive.get("pass2_findings"):
            results.append(result)
    return results


# ── Synthesis prompt ───────────────────────────────────────────────────────────

def build_synthesis_prompt(ckb_text: str, image_findings: list[dict],
                            av_findings: list[dict]) -> str:
    """Build the synthesis prompt enforcing deductive chain reasoning."""

    # Format image findings — pass1 observations + pass2 facts only, no interpretation labels
    image_section = ""
    if image_findings:
        parts = []
        for item in image_findings:
            exif = item.get("exif", {})
            exif_lines = []
            if exif.get("DateTimeOriginal"):
                exif_lines.append(f"  EXIF DateTimeOriginal field: {exif['DateTimeOriginal']}")
            if exif.get("DateTime") and exif.get("DateTime") != exif.get("DateTimeOriginal"):
                exif_lines.append(f"  EXIF ModifyDate field: {exif['DateTime']}")
            if exif.get("Software"):
                exif_lines.append(f"  EXIF Software field: {exif['Software']}")
            for note in exif.get("_tampering_indicators", []):
                exif_lines.append(f"  EXIF field discrepancy note: {note}")

            p2_lines = []
            for f in item.get("pass2_findings", []):
                if f.get("question") and f.get("answer") and f["answer"] != "SKIP — Pass 1 sufficient":
                    p2_lines.append(f"  Q: {f['question'][:120]}")
                    p2_lines.append(f"  A: {f['answer'][:300]}")

            drill_lines = []
            for d in item.get("deep_drill_rounds", []):
                for r in d.get("rounds", []):
                    drill_lines.append(f"  DRILL-Q: {r['question'][:120]}")
                    drill_lines.append(f"  DRILL-A: {r['answer'][:300]}")

            part = (
                f"IMAGE: {item['file']} (relevance: {item['relevance_score']})\n"
                f"EXIF (raw):\n" + ("\n".join(exif_lines) if exif_lines else "  None") + "\n"
                f"PASS 1 neutral observation:\n  {item.get('pass1_summary','')[:400]}\n"
            )
            if p2_lines:
                part += "PASS 2 derived questions and answers:\n" + "\n".join(p2_lines) + "\n"
            if drill_lines:
                part += "DEEP DRILL findings:\n" + "\n".join(drill_lines) + "\n"
            parts.append(part)
        image_section = "\n\n".join(parts)
    else:
        image_section = "No image analysis was performed."

    # Format AV findings — verbatim transcript segments + adaptive pass 2
    av_section = ""
    if av_findings:
        parts = []
        for item in av_findings:
            transcript = item.get("transcript", {})
            adaptive = item.get("adaptive_analysis", {})
            segs = transcript.get("segments", [])
            transcript_text = "\n".join(
                f"  [{s['start']}] {s['text']}"
                for s in segs[:30]
            ) if segs else f"  {transcript.get('full_text','')[:800]}"

            p2_lines = []
            for f in adaptive.get("pass2_findings", []):
                if f.get("question") and f.get("answer") and f["answer"] != "SKIP — transcript already precise":
                    p2_lines.append(f"  Q: {f['question'][:120]}")
                    p2_lines.append(f"  A: {f['answer'][:300]}")

            drill_lines = []
            for d in adaptive.get("deep_drill_log", []):
                for r in d.get("rounds", []):
                    drill_lines.append(f"  DRILL-Q: {r['question'][:120]}")
                    drill_lines.append(f"  DRILL-A: {r['answer'][:300]}")

            indicators = item.get("tampering_indicators", [])
            part = (
                f"AV FILE: {item['relative_path']} ({item['modality']}, relevance: {item['relevance_score']})\n"
                f"Metadata field notes: {'; '.join(indicators) if indicators else 'None'}\n"
                f"PASS 1 transcript (first 30 segments):\n{transcript_text}\n"
            )
            if p2_lines:
                part += "PASS 2 derived questions and answers:\n" + "\n".join(p2_lines) + "\n"
            if drill_lines:
                part += "DEEP DRILL findings:\n" + "\n".join(drill_lines) + "\n"
            parts.append(part)
        av_section = "\n\n".join(parts)
    else:
        av_section = "No audio/video analysis was performed."

    return f"""You are synthesising an investigation report using ONLY the evidence below.

MANDATORY REASONING RULES — THESE ARE NOT OPTIONAL:
1. Every claim must be traceable to a specific source in the evidence below
2. Every non-trivial conclusion must be written in explicit logical chain format:
   PREMISE 1 [E]: [fact] — source
   PREMISE 2 [E]: [fact] — source
   LOGICAL FORM: [why these premises entail the conclusion]
   CONCLUSION [S]: [claim]
3. Every claim must carry an epistemic state: [E] established, [S] supported, [P] possible, [X] excluded
4. NEVER use the words "clearly", "obviously", "must have" to describe human intent
5. NEVER round up [P] claims to [S]
6. NEVER fill gaps with narrative — state gaps explicitly
7. The case description in the CKB is [P] until corroborated by evidence — treat it as a starting frame, not ground truth
8. Absence of evidence is NOT evidence of absence — record it as a gap

══════════════════════════════════
CASE KNOWLEDGE BASE (textual evidence — Phase 1)
══════════════════════════════════
{ckb_text[:5000]}

══════════════════════════════════
IMAGE EVIDENCE (Phase 3 — adaptive VQA loop output)
══════════════════════════════════
{image_section[:6000]}

══════════════════════════════════
AUDIO / VIDEO EVIDENCE (Phase 4 — adaptive AV loop output)
══════════════════════════════════
{av_section[:6000]}

══════════════════════════════════
PRODUCE THE FOLLOWING REPORT SECTIONS IN ORDER:
══════════════════════════════════

## Established Facts [E]
List every directly observable or directly stated fact from the evidence. Group by modality.
Format: - [E-N] Fact text — Source: filename/timestamp

## Contradiction Matrix
List every pair of [E] facts that directly contradict each other.
Format: | ID | [E] Fact A | Source A | [E] Fact B | Source B | Contradiction type |

## Cross-Modal Corroborations
List claims supported by 2+ independent modalities.
Format:
CLAIM: [statement]
CORROBORATING FACTS: [E-N] from [modality] + [E-M] from [modality]
CORROBORATION TYPE: full / partial / circumstantial

## Unified Timeline
Only [E] facts with temporal information. Include precision label.
Format: | Timestamp | [E] Event (exact fact) | Source | Precision |

## Logical Chains and Supported Conclusions [S]
Write out every non-trivial conclusion as a complete logical chain.
Format:
CHAIN-[N]: [Title]
PREMISE 1 [E-ref]: [fact] — source
PREMISE 2 [E-ref]: [fact] — source
LOGICAL FORM: [explicit entailment statement]
CONCLUSION [S]: [precise claim]
WHAT THIS DOES NOT ESTABLISH: [bounded scope]
WHAT WOULD EXTEND THIS: [additional evidence needed]

## Possible Interpretations [P]
List all [P] findings. Each must state what would establish or exclude it.
Format:
[P-N]: [statement]
Would be established by: [specific evidence]
Would be excluded by: [specific evidence]

## Investigative Gaps
What is unknown and what evidence would be most valuable.
Format:
GAP-[N]: [description]
Why it matters: [question it would answer — phrased as a question]
How to address: [specific evidence type or action]

## Conclusion
State ONLY:
- What is established [E]
- What is supported [S] and by which logical chains
- What remains possible [P] and what would resolve it
- What is excluded [X]
- The next investigative steps in priority order

DO NOT state conclusions that exceed what the evidence supports.
DO NOT resolve contradictions by choosing a side without additional evidence.
DO NOT use emotional loading language."""


# ── LLM synthesis call ─────────────────────────────────────────────────────────

def call_synthesis_llm(prompt: str, provider: str, client, model: str) -> dict:
    """Call the synthesis LLM with retry logic."""
    import time, random

    SYNTHESIS_SYSTEM_PROMPT = (
        "You are a rigorous forensic analyst operating under strict deductive reasoning rules. "
        "You produce only conclusions that are directly entailed by the evidence provided. "
        "You write out every logical chain explicitly. "
        "You assign epistemic states [E/S/P/X] to every claim. "
        "You never use emotional language, narrative gravity, or inductive leaps. "
        "You never state a conclusion that exceeds what the premises establish."
    )

    def _call():
        try:
            if provider == "anthropic":
                response = client.messages.create(
                    model=model,
                    max_tokens=6000,
                    system=SYNTHESIS_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}]
                )
                return {"content": response.content[0].text, "success": True}
            else:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=6000,
                    temperature=0
                )
                return {"content": response.choices[0].message.content, "success": True}
        except Exception as e:
            return {"content": None, "success": False, "error": str(e)}

    for attempt in range(3):
        result = _call()
        if result["success"]:
            return result
        wait = (2 ** attempt) + random.random()
        print(f"  [LLM] Retry {attempt+1}/3 after {wait:.1f}s — {result.get('error', '')}")
        time.sleep(wait)
    return result


# ── Cross-modal correlation builder (heuristic, used without LLM) ─────────────

def build_heuristic_correlations(ckb_text: str, image_findings: list,
                                  av_findings: list) -> str:
    """Build basic cross-modal correlation notes without LLM."""
    lines = [
        "# Synthesis Notes — Cross-Modal Observations",
        "",
        "> Note: This is a heuristic fallback produced without LLM synthesis.",
        "> All items below are [E] observations only — no conclusions are drawn.",
        ""
    ]

    lines.append("## Text Extracted from Images [E]")
    lines.append("")
    for item in image_findings:
        for f in item.get("pass2_findings", []):
            if f.get("answer") and "text" in (f.get("question") or "").lower():
                lines.append(f"- Source: `{item['file']}` — Extracted: _{f['answer'][:200]}_")

    lines.append("")
    lines.append("## Verbatim Transcript Fragments [E]")
    lines.append("")
    for item in av_findings:
        segs = item.get("transcript", {}).get("segments", [])
        for seg in segs[:5]:
            lines.append(f"- Source: `{item['relative_path']}` [{seg['start']}] — \"{seg['text'][:200]}\"")

    lines.append("")
    lines.append("## EXIF and Metadata Field Notes [E]")
    lines.append("")
    for item in image_findings:
        for note in item.get("exif", {}).get("_tampering_indicators", []):
            lines.append(f"- Source: `{item['file']}` — {note}")
    for item in av_findings:
        for note in item.get("tampering_indicators", []):
            lines.append(f"- Source: `{item['relative_path']}` — {note}")
    if not any(
        item.get("exif", {}).get("_tampering_indicators") or item.get("tampering_indicators")
        for item in image_findings + av_findings
    ):
        lines.append("_No field-level discrepancies detected._")

    return "\n".join(lines)


# ── Report assembly ────────────────────────────────────────────────────────────

def assemble_final_report(synthesis_content: str, case_root: str,
                           image_count: int, av_count: int,
                           text_file_count: int) -> str:
    """Wrap the LLM synthesis in the official report header."""
    now = datetime.utcnow().isoformat() + "Z"
    header = f"""# 🔍 Poirot Investigation Report

> *"The impossible could not have happened, therefore the impossible must be possible in spite of appearances."*

**Case Directory:** `{case_root}`
**Report Generated:** {now}
**Evidence Processed:** {text_file_count} text/document files | {image_count} images | {av_count} audio/video files

---

"""
    return header + synthesis_content


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Poirot Phase 5 — Synthesis & Final Report")
    parser.add_argument("--ckb", required=True, help="Path to case_knowledge_base.md")
    parser.add_argument("--image-report", help="Path to image_analysis_report.json")
    parser.add_argument("--av-report", help="Path to av_analysis_report.json")
    parser.add_argument("--manifest", help="Path to case_manifest.json (for counts)")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--api-key", help="LLM API key")
    parser.add_argument("--model", default="gpt-4o",
                        help="LLM model (recommend claude-opus-4-5 or gpt-4o)")
    parser.add_argument("--provider", default="openai",
                        choices=["openai", "anthropic", "openrouter"])
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load all inputs
    ckb_text = Path(args.ckb).read_text(encoding="utf-8") if Path(args.ckb).exists() else ""
    image_report = load_json_safe(Path(args.image_report)) if args.image_report else {}
    av_report = load_json_safe(Path(args.av_report)) if args.av_report else {}
    manifest = load_json_safe(Path(args.manifest)) if args.manifest else {}

    image_findings = extract_established_image_findings(image_report)
    av_findings = extract_established_av_findings(av_report)

    # Stats
    counts = manifest.get("modality_counts", {})
    text_count = counts.get("text", 0) + counts.get("document", 0) + counts.get("data", 0)
    image_count = counts.get("image", len(image_findings))
    av_count = counts.get("audio", 0) + counts.get("video", 0)
    case_root = manifest.get("case_root", str(Path(args.ckb).parent))

    print(f"[Poirot Phase 5] Synthesising investigation report")
    print(f"  Image files with findings: {len(image_findings)}")
    print(f"  AV files with findings: {len(av_findings)}")

    # Build heuristic correlation notes (always — raw [E] facts only)
    synthesis_notes = build_heuristic_correlations(ckb_text, image_findings, av_findings)
    notes_path = output_dir / "logical_chains.md"
    notes_path.write_text(synthesis_notes, encoding="utf-8")
    print(f"  Working notes (pre-LLM): {notes_path}")

    # LLM-powered synthesis
    synthesis_content = None
    api_key = args.api_key or os.environ.get(
        "ANTHROPIC_API_KEY" if args.provider == "anthropic" else "OPENAI_API_KEY"
    )

    if api_key:
        try:
            if args.provider == "anthropic":
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
            else:
                import openai
                kwargs = {"api_key": api_key}
                if args.provider == "openrouter":
                    kwargs["base_url"] = "https://openrouter.ai/api/v1"
                client = openai.OpenAI(**kwargs)

            print(f"  [LLM] Generating deductive synthesis with {args.model}...")
            prompt = build_synthesis_prompt(ckb_text, image_findings, av_findings)
            result = call_synthesis_llm(prompt, args.provider, client, args.model)

            if result["success"]:
                synthesis_content = result["content"]
                print("  [LLM] Synthesis complete")
            else:
                print(f"  [LLM] Synthesis failed: {result.get('error')} — using fallback")

        except ImportError as e:
            print(f"  [LLM] Package not installed: {e} — using fallback report")

    # Fallback: assemble raw [E] facts only, no inferences
    if not synthesis_content:
        print("  [Fallback] Assembling raw [E] facts only (no LLM inference)...")
        parts = [
            "## Case Description (as provided — [P] status until corroborated)",
            ckb_text[:1000], "",
            "## Established Facts from Images [E]", ""
        ]
        for item in image_findings:
            parts.append(f"### {item['file']}")
            if item.get("pass1_summary"):
                parts.append(f"Pass 1 observation: {item['pass1_summary'][:300]}")
            for f in item.get("pass2_findings", []):
                if f.get("question") and f.get("answer") and f["answer"] != "SKIP — Pass 1 sufficient":
                    parts.append(f"- Q: {f['question'][:120]}")
                    parts.append(f"  A: {f['answer'][:300]}")
            parts.append("")

        parts.append("## Established Facts from Audio/Video [E]")
        for item in av_findings:
            parts.append(f"### {item['relative_path']}")
            segs = item.get("transcript", {}).get("segments", [])
            for seg in segs[:10]:
                parts.append(f"- [{seg['start']}] {seg['text']}")
            parts.append("")

        parts.append("## Conclusion")
        parts.append("_LLM synthesis not available. No conclusions are drawn. Review individual phase reports._")
        synthesis_content = "\n".join(parts)

    # Assemble final report
    final_report = assemble_final_report(
        synthesis_content, case_root, image_count, av_count, text_count
    )

    # Write Markdown report
    md_path = output_dir / "poirot_report.md"
    md_path.write_text(final_report, encoding="utf-8")
    print(f"\n[Poirot Phase 5] Final report: {md_path}")

    # Write JSON structured report
    json_report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "model": args.model,
        "case_root": case_root,
        "evidence_counts": {
            "text": text_count, "images": image_count, "av": av_count
        },
        "image_findings_count": len(image_findings),
        "av_findings_count": len(av_findings),
        "report_markdown": final_report,
        "working_notes": synthesis_notes
    }
    json_path = output_dir / "poirot_report.json"
    json_path.write_text(json.dumps(json_report, indent=2, default=str), encoding="utf-8")
    print(f"[Poirot Phase 5] JSON report: {json_path}")

    print("\n" + "="*60)
    print("POIROT INVESTIGATION COMPLETE")
    print(f"Final report: {md_path}")
    print("="*60)


if __name__ == "__main__":
    main()
