"""
run_audio_video_analysis.py — Phase 4: Audio and video evidence analysis.

Usage:
    python run_audio_video_analysis.py \
        --evidence evidence_manifest.json \
        --ckb case_knowledge_base.md \
        --output-dir ./output \
        [--whisper-model large-v3] [--api-key KEY] [--llm-model gpt-4o]

Outputs:
    av_analysis_report.json         — Machine-readable AV findings
    av_analysis_report.md           — Human-readable report section
    transcripts/<filename>.txt      — Full transcript per file
    keyframes/<filename>/           — Extracted video keyframes
"""

import os
import sys
import json
import argparse
import subprocess
import shutil
import time
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
    import whisper
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False

try:
    import ffmpeg  # ffmpeg-python binding
    HAS_FFMPEG_PYTHON = True
except ImportError:
    HAS_FFMPEG_PYTHON = False

# Check for ffmpeg binary
FFMPEG_BIN = shutil.which("ffmpeg")
FFPROBE_BIN = shutil.which("ffprobe")


# ── Media probing ──────────────────────────────────────────────────────────────

def probe_media(file_path: Path) -> dict:
    """Use ffprobe to get media file metadata."""
    if not FFPROBE_BIN:
        return {"error": "ffprobe not found — install ffmpeg"}

    try:
        cmd = [
            FFPROBE_BIN, "-v", "quiet",
            "-print_format", "json",
            "-show_streams", "-show_format",
            str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr}
        return json.loads(result.stdout)
    except Exception as e:
        return {"error": str(e)}


def get_duration_seconds(probe_data: dict) -> float:
    """Extract duration from ffprobe data."""
    try:
        return float(probe_data.get("format", {}).get("duration", 0))
    except (ValueError, TypeError):
        return 0.0


def has_video_stream(probe_data: dict) -> bool:
    return any(s.get("codec_type") == "video"
               for s in probe_data.get("streams", []))


def has_audio_stream(probe_data: dict) -> bool:
    return any(s.get("codec_type") == "audio"
               for s in probe_data.get("streams", []))


def detect_reencode(probe_data: dict) -> list[str]:
    """Detect signs of re-encoding (tampering indicator)."""
    indicators = []
    for stream in probe_data.get("streams", []):
        encoder = stream.get("tags", {}).get("encoder", "")
        if encoder and any(kw in encoder.lower() for kw in ["lavf", "lavc", "ffmpeg"]):
            indicators.append(f"Re-encoded with FFmpeg (stream: {stream.get('codec_type')})")
    fmt = probe_data.get("format", {})
    tags = fmt.get("tags", {})
    if tags.get("comment") and "ffmpeg" in tags["comment"].lower():
        indicators.append("FFmpeg comment tag found in metadata")
    return indicators


# ── Audio extraction from video ───────────────────────────────────────────────

def extract_audio_from_video(video_path: Path, output_dir: Path) -> Optional[Path]:
    """Extract audio track from video to WAV for Whisper."""
    if not FFMPEG_BIN:
        return None

    audio_out = output_dir / f"{video_path.stem}_audio.wav"
    if audio_out.exists():
        return audio_out

    try:
        cmd = [
            FFMPEG_BIN, "-y", "-i", str(video_path),
            "-vn",          # no video
            "-ar", "16000", # 16kHz for Whisper
            "-ac", "1",     # mono
            "-f", "wav",
            str(audio_out)
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode == 0 and audio_out.exists():
            return audio_out
    except Exception as e:
        print(f"    [WARN] Audio extraction failed: {e}")
    return None


# ── Keyframe extraction ────────────────────────────────────────────────────────

def extract_keyframes(video_path: Path, output_dir: Path,
                      relevance_score: float,
                      duration_seconds: float) -> list[dict]:
    """Extract keyframes from a video based on relevance."""
    if not FFMPEG_BIN:
        return []

    frames_dir = output_dir / "keyframes" / video_path.stem
    frames_dir.mkdir(parents=True, exist_ok=True)

    # Determine max frames and interval
    if relevance_score >= 0.7:
        max_frames = 50
    elif relevance_score >= 0.4:
        max_frames = 20
    else:
        max_frames = 5

    interval = max(1, int(duration_seconds / max_frames)) if duration_seconds > 0 else 30

    keyframes = []

    try:
        # Time-based extraction
        cmd = [
            FFMPEG_BIN, "-y", "-i", str(video_path),
            "-vf", f"fps=1/{interval}",
            "-vsync", "vfr",
            "-frame_pts", "1",
            str(frames_dir / "frame_%06d.jpg")
        ]
        subprocess.run(cmd, capture_output=True, timeout=600)

        # Collect extracted frames with timestamps
        for frame_file in sorted(frames_dir.glob("frame_*.jpg")):
            # Parse frame number to estimate timestamp
            frame_num = int(frame_file.stem.split("_")[1])
            timestamp_s = (frame_num - 1) * interval
            h, m, s = int(timestamp_s // 3600), int((timestamp_s % 3600) // 60), int(timestamp_s % 60)
            timestamp_str = f"{h:02d}:{m:02d}:{s:02d}"

            keyframes.append({
                "frame_path": str(frame_file),
                "relative_frame_path": str(frame_file.relative_to(output_dir)),
                "timestamp": timestamp_str,
                "timestamp_seconds": timestamp_s,
                "extraction_reason": f"time_based_{interval}s_interval",
                "abs_link": frame_file.resolve().as_posix()
            })

    except Exception as e:
        print(f"    [WARN] Keyframe extraction failed: {e}")

    return keyframes[:max_frames]


# ── Transcription ─────────────────────────────────────────────────────────────

def transcribe_audio(audio_path: Path, whisper_model_name: str = "medium",
                     language: Optional[str] = None) -> dict:
    """Transcribe audio using local Whisper."""
    if not HAS_WHISPER:
        return {"error": "whisper not installed — pip install openai-whisper"}

    print(f"    [Whisper] Loading model: {whisper_model_name}...")
    try:
        model = whisper.load_model(whisper_model_name)
        opts = {"word_timestamps": True, "verbose": False}
        if language:
            opts["language"] = language

        result = model.transcribe(str(audio_path), **opts)

        segments = []
        for seg in result.get("segments", []):
            start = seg["start"]
            end = seg["end"]
            h1, m1, s1 = int(start//3600), int((start%3600)//60), int(start%60)
            h2, m2, s2 = int(end//3600), int((end%3600)//60), int(end%60)
            segments.append({
                "start": f"{h1:02d}:{m1:02d}:{s1:02d}",
                "end": f"{h2:02d}:{m2:02d}:{s2:02d}",
                "start_seconds": start,
                "text": seg["text"].strip(),
                "confidence": seg.get("avg_logprob", 0.0)
            })

        return {
            "full_text": result.get("text", ""),
            "language": result.get("language", "unknown"),
            "segments": segments,
            "success": True
        }
    except Exception as e:
        return {"error": str(e), "success": False}


def transcribe_via_api(audio_path: Path, api_key: str,
                       provider: str = "openai") -> dict:
    """Transcribe using cloud Whisper API."""
    if provider == "openai":
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
            with open(audio_path, "rb") as f:
                resp = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )
            segments = []
            for seg in (resp.segments or []):
                start = seg.start
                end = seg.end
                h1, m1, s1 = int(start//3600), int((start%3600)//60), int(start%60)
                h2, m2, s2 = int(end//3600), int((end%3600)//60), int(end%60)
                segments.append({
                    "start": f"{h1:02d}:{m1:02d}:{s1:02d}",
                    "end": f"{h2:02d}:{m2:02d}:{s2:02d}",
                    "start_seconds": start,
                    "text": seg.text.strip(),
                    "confidence": 0.0
                })
            return {"full_text": resp.text, "language": resp.language,
                    "segments": segments, "success": True}
        except Exception as e:
            return {"error": str(e), "success": False}
    return {"error": f"Unsupported provider: {provider}", "success": False}


# ── Adaptive AV analysis: DTE parsing & derived questions ────────────────────

AV_SYSTEM_PROMPT = (
    "You are a precise audio/transcript analyst assisting a factual investigation. "
    "Report only observable acoustic and linguistic facts. "
    "Do not infer intent, emotion, or identity. "
    "If a word is unclear, describe the sounds you hear, not what you think was meant. "
    "Every claim must be directly observable in the audio."
)

DTE_EXTRACTION_PROMPT = (
    "You are parsing a transcript and audio observation into discrete transcript elements.\n"
    "Given the following transcript, list every discrete element as a numbered list.\n"
    "Each element is one of: a named entity or code spoken aloud, an acoustic event, "
    "a silence gap ≥2 seconds, a low-confidence segment, or an abrupt audio transition.\n"
    "Do not include ordinary sentences as DTEs unless they contain a specific named entity, "
    "number, date, code, or address.\n\n"
    "Transcript:\n{transcript}\n\n"
    "Return a numbered list only. One element per line."
)

PASS2_AUDIO_QUESTION_PROMPT = (
    "Generate a single precise follow-up question for the following transcript element.\n\n"
    "Rules:\n"
    "- Target only the specific element described\n"
    "- Physical, verifiable language: sounds, words, pauses, acoustic properties\n"
    "- Never embed the expected answer\n"
    "- Never name suspects or case entities\n"
    "- The question must be answerable with 'no such element is detectable'\n\n"
    "Element:\n{dte}\n\n"
    "Write ONE precise question, or SKIP if the transcript already describes this element fully."
)

AV_DEEP_DRILL_EVALUATION_PROMPT = (
    "Evaluate whether this transcript/audio element meets all three deep-drill conditions.\n\n"
    "CONDITION A — Specificity: Is the element described precisely enough for a targeted question?\n"
    "CONDITION B — Anomaly: Is it objectively anomalous by at least one of:\n"
    "  B1: It directly contradicts another element in the same transcript\n"
    "  B2: It contradicts this established external fact: {external_fact}\n"
    "  B3: It is physically implausible in the described acoustic/situational context\n"
    "CONDITION C — Materiality: Does the anomaly relate to the case type: {case_type}\n\n"
    "Element:\n{element}\n\n"
    "Surrounding context:\n{context}\n\n"
    "Respond exactly:\n"
    "A: PASS or FAIL — [reason]\n"
    "B: PASS or FAIL — [reason, specify B1/B2/B3 if PASS]\n"
    "C: PASS or FAIL — [reason]\n"
    "VERDICT: DRILL or NO_DRILL\n"
    "If DRILL: [Write the single targeted deep-drill question]"
)


def extract_dtes_with_llm(transcript_text: str, client, model: str) -> list[str]:
    """Parse transcript into discrete transcript elements."""
    if client is None:
        import re
        # Fallback: find timestamps and quoted text
        lines = transcript_text.split("\n")
        dtes = []
        for line in lines:
            if re.search(r'\d{2}:\d{2}:\d{2}', line) and len(line.strip()) > 15:
                dtes.append(line.strip())
        return dtes[:30]

    try:
        prompt = DTE_EXTRACTION_PROMPT.format(transcript=transcript_text[:6000])
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=1000
        )
        raw = resp.choices[0].message.content.strip()
        import re
        dtes = []
        for line in raw.split("\n"):
            line = line.strip()
            if line:
                cleaned = re.sub(r"^[\d\-\.\)]+\s*", "", line).strip()
                if cleaned:
                    dtes.append(cleaned)
        return dtes
    except Exception as e:
        print(f"      [WARN] DTE extraction failed: {e}")
        return []


def generate_pass2_audio_question(dte: str, client, model: str) -> Optional[str]:
    """Generate Pass 2 question for an audio DTE."""
    if client is None:
        vague = ["unclear", "inaudible", "[?]", "partial", "possible"]
        if any(v in dte.lower() for v in vague):
            return f"Listen carefully to this segment: {dte[:200]}. Transcribe every audible word. For unclear words, describe the vowel and consonant sounds present."
        return None

    try:
        prompt = PASS2_AUDIO_QUESTION_PROMPT.format(dte=dte)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200
        )
        q = resp.choices[0].message.content.strip()
        if q.upper().startswith("SKIP"):
            return None
        return q
    except Exception as e:
        print(f"      [WARN] Pass 2 audio question failed: {e}")
        return None


def evaluate_av_deep_drill(dte: str, context: str, case_type: str,
                            external_facts: list[str], client, model: str) -> dict:
    """Evaluate DTE against A+B+C conditions."""
    if client is None:
        return {"verdict": "NO_DRILL", "question": None}

    external_fact_str = "; ".join(external_facts[:3]) if external_facts else "No external facts provided"
    try:
        prompt = AV_DEEP_DRILL_EVALUATION_PROMPT.format(
            external_fact=external_fact_str,
            case_type=case_type,
            element=dte,
            context=context[:800]
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=400
        )
        raw = resp.choices[0].message.content.strip()
        verdict = "DRILL" if ("VERDICT: DRILL" in raw and "NO_DRILL" not in raw.split("VERDICT:")[1][:15]) else "NO_DRILL"
        drill_q = None
        if verdict == "DRILL":
            for line in raw.split("\n"):
                if line.startswith("If DRILL:"):
                    drill_q = line.replace("If DRILL:", "").strip()
        return {"verdict": verdict, "evaluation": raw, "question": drill_q}
    except Exception as e:
        return {"verdict": "NO_DRILL", "reason": str(e), "question": None}


def run_adaptive_av_analysis(transcript_text: str, formatted_segments: str,
                              ckb_text: str, established_facts: list[str],
                              case_type: str, source_file: str,
                              client, model: str) -> dict:
    """
    Run the full adaptive AV analysis loop:
    Pass 1 (transcript already done) → DTE parsing → Pass 2 derived questions
    → Deep-drill on A+B+C conditions.
    """
    result = {
        "dtes": [],
        "pass2_findings": [],
        "deep_drill_log": [],
        "analysis_status": "pending"
    }

    if not transcript_text.strip():
        result["analysis_status"] = "empty_transcript"
        return result

    # Parse DTEs from transcript
    dtes = extract_dtes_with_llm(transcript_text, client, model)
    result["dtes"] = dtes
    print(f"    [DTEs] {len(dtes)} discrete transcript elements identified")

    # Pass 2: derived questions per DTE
    for dte in dtes:
        q = generate_pass2_audio_question(dte, client, model)
        if q is None:
            result["pass2_findings"].append({
                "dte": dte, "question": None,
                "answer": "SKIP — transcript already precise",
                "epistemic_state": "E"
            })
            continue

        # For audio Pass 2: re-send transcript segment + question to LLM
        # (we can't re-listen, so we ask the LLM about the transcript text)
        if client:
            try:
                segment_context = f"Transcript context:\n{formatted_segments[:4000]}\n\nQuestion: {q}"
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": AV_SYSTEM_PROMPT},
                        {"role": "user", "content": segment_context}
                    ],
                    temperature=0,
                    max_tokens=500
                )
                answer = resp.choices[0].message.content.strip()
            except Exception as e:
                answer = f"[FAILED: {e}]"
        else:
            answer = "[No LLM available]"

        finding = {"dte": dte, "question": q, "answer": answer, "epistemic_state": "E"}
        result["pass2_findings"].append(finding)

        # Deep-drill evaluation
        evaluation = evaluate_av_deep_drill(
            dte=f"{dte}\n\nPass 2 response: {answer}",
            context=formatted_segments[:800],
            case_type=case_type,
            external_facts=established_facts[:5],
            client=client,
            model=model
        )

        drill_entry = {
            "dte": dte,
            "conditions_evaluation": evaluation.get("evaluation", ""),
            "verdict": evaluation["verdict"],
            "drill_question": evaluation.get("question"),
            "rounds": []
        }

        if evaluation["verdict"] == "DRILL" and evaluation.get("question") and client:
            for round_num in range(1, 4):
                dq = evaluation["question"] if round_num == 1 else None
                if dq is None:
                    break
                try:
                    dr_resp = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": AV_SYSTEM_PROMPT},
                            {"role": "user", "content": f"Transcript:\n{formatted_segments[:4000]}\n\n{dq}"}
                        ],
                        temperature=0,
                        max_tokens=600
                    )
                    dr_answer = dr_resp.choices[0].message.content.strip()
                except Exception as e:
                    dr_answer = f"[FAILED: {e}]"
                    break

                drill_entry["rounds"].append({
                    "round": round_num, "question": dq, "answer": dr_answer
                })
                evaluation["question"] = None  # Stop after 1 round unless extended

        result["deep_drill_log"].append(drill_entry)

    result["analysis_status"] = "complete"
    result["pass2_count"] = sum(1 for f in result["pass2_findings"] if f["question"] is not None)
    result["deep_drill_triggered"] = sum(1 for d in result["deep_drill_log"] if d["verdict"] == "DRILL")
    return result


# ── Report formatting ──────────────────────────────────────────────────────────

def format_av_entry(result: dict) -> str:
    """Format a single AV analysis result as Markdown using the adaptive loop schema."""
    path = Path(result["path"])
    rel_path = result["relative_path"]
    score = result["relevance_score"]
    modality = result["modality"]
    probe = result.get("probe_summary", {})
    transcript = result.get("transcript", {})
    adaptive = result.get("adaptive_analysis", {})
    keyframes = result.get("keyframes", [])

    icon = "🎬" if modality == "video" else "🎵"

    lines = [
        f"### {icon} {path.name} — Relevance: {score}",
        f"**Path:** `{rel_path}`",
        f"**Duration:** {probe.get('duration', 'unknown')} | **Type:** {modality.capitalize()} | **Has Audio:** {'Yes' if probe.get('has_audio') else 'No'}",
        "",
        "**Metadata (raw fields):**",
    ]
    for indicator in result.get("tampering_indicators", []):
        lines.append(f"- Field note: {indicator}")
    if not result.get("tampering_indicators"):
        lines.append("- No field-level discrepancies detected")
    lines.append("")

    if transcript.get("success"):
        lang = transcript.get("language", "?")
        segs = transcript.get("segments", [])
        lines.append(f"**PASS 1 — Neutral Transcript:** {len(segs)} segments | Language: {lang}")
        if segs:
            preview = segs[0]["text"][:200] if segs else ""
            lines.append(f"*First segment: {preview}*")
        lines.append(f"**DTEs identified:** {len(adaptive.get('dtes', []))}")
        lines.append("")

    p2 = [f for f in adaptive.get("pass2_findings", []) if f.get("question") is not None]
    if p2:
        lines.append("**PASS 2 — Derived Questions:**")
        lines.append("")
        lines.append("| DTE (summary) | Question | Answer summary | State |")
        lines.append("|---|---|---|---|")
        for f in p2:
            dte_s = f["dte"][:60].replace("|", "/")
            q_s = (f["question"] or "")[:80].replace("|", "/")
            a_s = f["answer"][:150].replace("\n", " ").replace("|", "/")
            lines.append(f"| {dte_s} | {q_s} | {a_s} | {f.get('epistemic_state','E')} |")
        lines.append("")

    drills = [d for d in adaptive.get("deep_drill_log", []) if d["verdict"] == "DRILL"]
    if drills:
        lines.append("**DEEP DRILL LOG:**")
        lines.append("")
        lines.append("| DTE | Round | Question | Answer summary |")
        lines.append("|---|---|---|---|")
        for d in drills:
            dte_s = d["dte"][:60].replace("|", "/")
            for r in d.get("rounds", []):
                q_s = r["question"][:80].replace("|", "/")
                a_s = r["answer"][:150].replace("\n", " ").replace("|", "/")
                lines.append(f"| {dte_s} | {r['round']} | {q_s} | {a_s} |")
        lines.append("")

    if keyframes:
        lines.append("**Keyframes:**")
        lines.append("| Timestamp | Frame | Reason |")
        lines.append("|---|---|---|")
        for kf in keyframes[:10]:
            link = f"[View](file:///{kf['abs_link']})"
            lines.append(f"| {kf['timestamp']} | {link} | {kf['extraction_reason']} |")
        lines.append("")

    lines.append("---")
    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Poirot Phase 4 — Adaptive Audio/Video Analysis")
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--ckb", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--api-key", help="LLM/Whisper API key")
    parser.add_argument("--whisper-model", default="medium",
                        choices=["tiny", "base", "small", "medium", "large-v3"])
    parser.add_argument("--llm-model", default="gpt-4o")
    parser.add_argument("--use-api-whisper", action="store_true")
    parser.add_argument("--min-relevance", type=float, default=0.1)
    parser.add_argument("--case-type", default="general investigation",
                        help="Case type for deep-drill materiality check")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    transcript_dir = output_dir / "transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = output_dir / "_av_temp"
    temp_dir.mkdir(exist_ok=True)

    evidence_data = json.loads(Path(args.evidence).read_bytes())
    ckb_text = Path(args.ckb).read_text(encoding="utf-8") if Path(args.ckb).exists() else ""

    import re
    established_facts = re.findall(r'\[E\][^\n]+', ckb_text)[:20]

    av_files = [
        e for e in evidence_data["evidence"]
        if e["modality"] in ("audio", "video")
        and e["relevance_score"] >= args.min_relevance
        and not e.get("duplicate_of")
    ]
    print(f"[Poirot Phase 4] Analysing {len(av_files)} audio/video files")

    llm_client = None
    if args.api_key or os.environ.get("OPENAI_API_KEY"):
        try:
            import openai
            llm_client = openai.OpenAI(
                api_key=args.api_key or os.environ.get("OPENAI_API_KEY")
            )
        except ImportError:
            print("  [WARN] openai package not installed — adaptive analysis limited")

    all_results = []

    for i, entry in enumerate(av_files):
        path = Path(entry["path"])
        print(f"\n  [{i+1}/{len(av_files)}] {entry['relative_path']} (score: {entry['relevance_score']})")

        result = {
            "path": entry["path"],
            "relative_path": entry["relative_path"],
            "relevance_score": entry["relevance_score"],
            "modality": entry["modality"],
            "probe_summary": {},
            "tampering_indicators": [],
            "transcript": {},
            "adaptive_analysis": {},
            "keyframes": [],
            "status": "pending"
        }

        # Probe media
        print("    [probe] Analysing media metadata...")
        probe_data = probe_media(path)
        if "error" not in probe_data:
            duration = get_duration_seconds(probe_data)
            result["probe_summary"] = {
                "duration": f"{int(duration//3600):02d}:{int((duration%3600)//60):02d}:{int(duration%60):02d}",
                "duration_seconds": duration,
                "has_video": has_video_stream(probe_data),
                "has_audio": has_audio_stream(probe_data),
                "format": probe_data.get("format", {}).get("format_name", "unknown")
            }
            result["tampering_indicators"] = detect_reencode(probe_data)

        # Transcription (Pass 1 — neutral, no case context in Whisper)
        audio_path = path
        if entry["modality"] == "video":
            print("    [audio] Extracting audio track...")
            extracted = extract_audio_from_video(path, temp_dir)
            if extracted:
                audio_path = extracted

        if result["probe_summary"].get("has_audio", True):
            print(f"    [PASS 1] Neutral transcription via {'API' if args.use_api_whisper else 'local'} Whisper...")
            if args.use_api_whisper and (args.api_key or os.environ.get("OPENAI_API_KEY")):
                transcript = transcribe_via_api(
                    audio_path,
                    args.api_key or os.environ.get("OPENAI_API_KEY")
                )
            elif HAS_WHISPER:
                transcript = transcribe_audio(audio_path, args.whisper_model)
            else:
                transcript = {"error": "No transcription method available", "success": False}

            result["transcript"] = transcript

            if transcript.get("success") and transcript.get("full_text"):
                # Save verbatim transcript
                segs = transcript.get("segments", [])
                formatted_segs = "\n".join(
                    f"[{s['start']} → {s['end']}] SPEAKER_A: {s['text']}"
                    for s in segs
                ) if segs else transcript["full_text"]

                transcript_path = transcript_dir / f"{path.stem}.txt"
                transcript_path.write_text(formatted_segs, encoding="utf-8")
                print(f"    [transcript] Saved: {transcript_path.name}")

                # Run adaptive analysis loop
                if llm_client:
                    print(f"    [PASS 2 + DEEP DRILL] Running adaptive AV analysis...")
                    result["adaptive_analysis"] = run_adaptive_av_analysis(
                        transcript_text=transcript["full_text"],
                        formatted_segments=formatted_segs,
                        ckb_text=ckb_text,
                        established_facts=established_facts,
                        case_type=args.case_type,
                        source_file=entry["relative_path"],
                        client=llm_client,
                        model=args.llm_model
                    )
                    aa = result["adaptive_analysis"]
                    print(f"    → DTEs: {len(aa.get('dtes',[]))} | Pass 2 questions: {aa.get('pass2_count',0)} | Deep drills: {aa.get('deep_drill_triggered',0)}")

        # Keyframe extraction for video
        if entry["modality"] == "video" and FFMPEG_BIN:
            duration_s = result["probe_summary"].get("duration_seconds", 60)
            print("    [frames] Extracting keyframes...")
            keyframes = extract_keyframes(path, output_dir,
                                          entry["relevance_score"], duration_s)
            result["keyframes"] = keyframes
            print(f"    → {len(keyframes)} keyframes extracted")

        result["status"] = "complete"
        all_results.append(result)

    # Write JSON report
    json_report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "whisper_model": args.whisper_model,
        "llm_model": args.llm_model,
        "files_analysed": len(all_results),
        "results": all_results
    }
    json_path = output_dir / "av_analysis_report.json"
    json_path.write_text(json.dumps(json_report, indent=2, default=str), encoding="utf-8")
    print(f"\n[Poirot Phase 4] Written: {json_path}")

    # Write Markdown report
    md_lines = [
        "# Phase 4 — Audio / Video Analysis Report",
        f"*Generated: {datetime.utcnow().isoformat()}Z*",
        f"*Files analysed: {len(all_results)} | Whisper: {args.whisper_model} | LLM: {args.llm_model}*",
        "",
        "> Reasoning protocol: Pass 1 is neutral transcription only — no case context.",
        "> Questions were derived from what was actually transcribed.",
        "> Deep-drill follow-ups triggered only when Specificity + Anomaly + Materiality conditions all met.",
        ""
    ]

    for result in all_results:
        md_lines.append(format_av_entry(result))

    md_path = output_dir / "av_analysis_report.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"[Poirot Phase 4] Written: {md_path}")
    print(f"\n[Poirot Phase 4] Complete. Next: synthesize_report.py")


if __name__ == "__main__":
    main()
