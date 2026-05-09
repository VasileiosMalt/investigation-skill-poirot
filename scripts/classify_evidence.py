"""
classify_evidence.py — Phase 2: Evidence classification and question routing.

Usage:
    python classify_evidence.py \
        --manifest case_manifest.json \
        --ckb case_knowledge_base.md \
        --output evidence_manifest.json \
        [--api-key KEY] [--model gpt-4o]

Outputs:
    evidence_manifest.json  — Full classified evidence with relevance scores
                              and priority question lists per file
"""

import os
import sys
import json
import argparse
import re
from pathlib import Path
from typing import Optional

# ── Env bootstrap (loads .env when run standalone) ─────────────────────────────
try:
    _scripts_dir = Path(__file__).parent
    if str(_scripts_dir) not in sys.path:
        sys.path.insert(0, str(_scripts_dir))
    from env_config import get_config as _get_cfg
    _get_cfg()  # populates os.environ from .env
except Exception:
    pass  # env_config unavailable — rely on existing os.environ

# ── Relevance heuristics

EVIDENCE_FOLDERS = {
    "evidence", "exhibits", "suspects", "victims", "witnesses",
    "scene", "photos", "recordings", "documents", "financials",
    "timeline", "communications", "forensics", "autopsy"
}

SYSTEM_JUNK = {
    "__macosx", ".ds_store", "thumbs.db", ".thumbnails", "desktop.ini",
    ".git", ".svn", "node_modules", "temp", "tmp", "cache"
}

GENERIC_NAMES = {
    "img", "image", "photo", "pic", "picture", "untitled", "document",
    "file", "new", "copy", "scan", "screenshot", "capture"
}


def parse_ckb(ckb_text: str) -> dict:
    """Extract entity names and timeline dates from the CKB for relevance scoring."""
    entities = []
    dates = []

    # Extract names from People table rows: | Name | ...
    people_section = re.search(r"### People\n(.*?)(?=###|\Z)", ckb_text, re.DOTALL)
    if people_section:
        for line in people_section.group(1).split("\n"):
            if line.strip().startswith("|") and "---" not in line and "Name" not in line:
                cols = [c.strip() for c in line.split("|") if c.strip()]
                if cols:
                    entities.append(cols[0].lower())

    # Extract places
    places_section = re.search(r"### Places\n(.*?)(?=###|\Z)", ckb_text, re.DOTALL)
    if places_section:
        for line in places_section.group(1).split("\n"):
            if line.strip().startswith("|") and "---" not in line and "Name" not in line:
                cols = [c.strip() for c in line.split("|") if c.strip()]
                if cols:
                    entities.append(cols[0].lower())

    # Extract dates from timeline
    date_pattern = re.compile(r"\d{4}[-/]\d{2}[-/]\d{2}")
    dates = date_pattern.findall(ckb_text)

    return {"entities": entities, "dates": dates}


def score_relevance(entry: dict, ckb_entities: list[str], ckb_dates: list[str]) -> float:
    """
    Heuristic relevance scoring (0.0–1.0).
    LLM call refines this in score_relevance_with_llm().
    """
    score = 0.3  # base score

    name_lower = Path(entry["name"]).stem.lower()
    path_lower = entry["relative_path"].lower()

    # Path contains evidence-type folder
    path_parts = set(path_lower.replace("\\", "/").split("/"))
    if path_parts & EVIDENCE_FOLDERS:
        score += 0.2

    # Name contains a known entity
    for entity in ckb_entities:
        if entity and len(entity) > 2 and entity in name_lower:
            score += 0.25
            break

    # Name contains a known date
    for date in ckb_dates:
        if date.replace("-", "") in name_lower.replace("-", "").replace("_", ""):
            score += 0.15
            break

    # Penalise generic names
    if any(g == name_lower or name_lower.startswith(g + "_") for g in GENERIC_NAMES):
        score -= 0.15

    # Penalise system folders
    if any(j in path_lower for j in SYSTEM_JUNK):
        score = 0.0

    # Penalise duplicates
    if entry.get("duplicate_of"):
        score *= 0.1

    return round(min(max(score, 0.0), 1.0), 2)


# ── Pass 1 neutral prompts (file-type only — NO case context) ─────────────────

IMAGE_PASS1_PROMPT = (
    "Describe this image completely and objectively. Include:\n"
    "- The type of setting or scene visible\n"
    "- Every distinct object or element you can see, and its position relative to others\n"
    "- The lighting conditions: apparent source direction, shadow angles and lengths, quality\n"
    "- Any text, symbols, numbers, or markings visible anywhere in the image\n"
    "- The physical state of every object: condition, damage, displacement, cleanliness\n"
    "- Any people or animals present: describe only physical appearance, position, and posture\n"
    "- Anything that appears physically inconsistent, unusual in placement, or out of proportion\n\n"
    "Do not interpret. Do not infer. Do not speculate. Describe only what is directly visible."
)

AUDIO_PASS1_PROMPT = (
    "Analyse this audio recording. Provide:\n"
    "- A verbatim transcription of all speech, with timestamps for each speaker turn\n"
    "- The number of distinct voices and a physical description of each (pitch, pace, accent)\n"
    "- A list of all non-speech sounds with timestamps and physical descriptions\n"
    "- Any segments where audio quality degrades, cuts abruptly, or changes character\n"
    "- Any periods of silence lasting more than 2 seconds with timestamps and duration\n\n"
    "Do not interpret speaker intent, emotion, or truthfulness at this stage."
)

VIDEO_PASS1_PROMPT = (
    "Analyse this video. Provide:\n"
    "- A description of the visual content scene by scene, noting changes in setting\n"
    "- A verbatim transcription of all speech with timestamps\n"
    "- A description of all visible human or animal movement: what moves, direction, pace\n"
    "- All visible text, signs, or on-screen information with timestamps\n"
    "- All non-speech sounds with timestamps\n"
    "- Any frame where the image abruptly changes, cuts, freezes, or shows compression artifacts\n"
    "- Any visible timestamps, clocks, or date indicators within the frame\n\n"
    "Do not assess intent, meaning, or significance at this stage."
)

# Seed questions — from file type only, NOT from case context
IMAGE_SEED_QUESTIONS = [
    "Describe the position and orientation of every object visible relative to fixed reference points such as walls, floors, or door frames.",
    "List every area of the image where sharpness, grain, or colour balance differs noticeably from surrounding areas.",
    "Transcribe all text visible in the image, including partial text and characters at the image edge.",
]

AUDIO_SEED_QUESTIONS = [
    "For each speaker turn, describe any change in speaking pace or pitch relative to the immediately preceding turn.",
    "Describe the acoustic environment: is it reverberant, dampened, outdoors? What background sounds are consistent throughout?",
    "Identify any segment where the noise floor changes abruptly. Describe the before and after acoustic character.",
]

VIDEO_SEED_QUESTIONS = [
    "Identify each point in the video where the scene or composition changes. Describe what changes and what remains constant.",
    "For each visible person, describe their movement trajectory from entry to exit of the frame.",
    "Compare the lighting conditions across the full duration of the video. Note any changes.",
]


def build_pass1_and_seeds(entry: dict) -> tuple[str, list[str]]:
    """Return the neutral Pass 1 prompt and seed questions for a file based on modality only."""
    modality = entry["modality"]
    if modality == "image":
        return IMAGE_PASS1_PROMPT, IMAGE_SEED_QUESTIONS[:]
    elif modality == "audio":
        return AUDIO_PASS1_PROMPT, AUDIO_SEED_QUESTIONS[:]
    elif modality == "video":
        return VIDEO_PASS1_PROMPT, VIDEO_SEED_QUESTIONS[:]
    else:
        return "", []


# ── LLM-assisted relevance scoring ────────────────────────────────────────────

def build_relevance_prompt(entries_batch: list[dict], ckb_summary: str) -> str:
    files_list = "\n".join(
        f"- {e['relative_path']} (type: {e['modality']}/{e['subtype']}, "
        f"size: {e['size_bytes']} bytes, initial_score: {e.get('relevance_score', '?')})"
        for e in entries_batch
    )
    return f"""You are assisting in an investigation. Based on the Case Knowledge Base summary below,
score the relevance of each listed file on a scale of 0.0 to 1.0, where:
  1.0 = directly relevant to the core case question
  0.5 = possibly relevant, warrants investigation
  0.1 = likely background / incidental
  0.0 = system file, junk, or clearly irrelevant

Case Knowledge Base Summary:
{ckb_summary[:3000]}

Files to score:
{files_list}

Respond with ONLY a JSON object mapping relative_path → score, example:
{{"photos/scene_01.jpg": 0.9, "photos/thumbnail.jpg": 0.2}}

Be decisive. Default to 0.5 for ambiguous files."""


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Poirot Phase 2 — Evidence Classification")
    parser.add_argument("--manifest", required=True, help="Path to case_manifest.json")
    parser.add_argument("--ckb", required=True, help="Path to case_knowledge_base.md")
    parser.add_argument("--output", required=True, help="Output path for evidence_manifest.json")
    parser.add_argument("--api-key", help="LLM API key (or set OPENAI_API_KEY env var)")
    parser.add_argument("--model", default="gpt-4o-mini", help="LLM model for relevance scoring")
    parser.add_argument("--no-llm", action="store_true",
                        help="Use heuristic scoring only (no LLM calls)")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    ckb_path = Path(args.ckb)

    if not manifest_path.exists():
        print(f"ERROR: Manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    manifest = json.loads(manifest_path.read_bytes())
    ckb_text = ckb_path.read_text(encoding="utf-8") if ckb_path.exists() else ""

    ckb_parsed = parse_ckb(ckb_text)
    entities = ckb_parsed["entities"]
    dates = ckb_parsed["dates"]

    print(f"[Poirot Phase 2] Processing {len(manifest['files'])} files")
    print(f"  CKB entities: {entities[:8]}")

    evidence = []
    for entry in manifest["files"]:
        # Skip known-irrelevant
        if entry["modality"] == "unknown" and entry["size_bytes"] == 0:
            continue
        if entry.get("duplicate_of"):
            entry["relevance_score"] = 0.05
        else:
            entry["relevance_score"] = score_relevance(entry, entities, dates)

        # Build Pass 1 prompt and seed questions (file-type only — no case context injected)
        pass1_prompt, seed_questions = build_pass1_and_seeds(entry)
        entry["pass1_prompt"] = pass1_prompt
        entry["seed_questions"] = seed_questions
        entry["deep_drill_log"] = []
        # file_context_note: any textual reference to this file found during Phase 1
        entry["file_context_note"] = entry.pop("referenced_in", "")

        evidence.append(entry)

    # Optional: LLM-assisted relevance refinement (batch to save calls)
    if not args.no_llm and (args.api_key or os.environ.get("OPENAI_API_KEY")):
        try:
            import openai
            api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
            client = openai.OpenAI(api_key=api_key)

            # Process in batches of 20
            batch_size = 20
            for i in range(0, len(evidence), batch_size):
                batch = evidence[i:i + batch_size]
                prompt = build_relevance_prompt(batch, ckb_text[:3000])
                try:
                    resp = client.chat.completions.create(
                        model=args.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0
                    )
                    scores = json.loads(resp.choices[0].message.content)
                    for item in batch:
                        if item["relative_path"] in scores:
                            item["relevance_score"] = float(scores[item["relative_path"]])
                    print(f"  [LLM] Refined scores for batch {i//batch_size + 1}")
                except Exception as e:
                    print(f"  [LLM] Batch {i//batch_size + 1} failed: {e} — using heuristic scores")
        except ImportError:
            print("  [LLM] openai package not installed — using heuristic scores only")

    # Sort by relevance descending within each lane
    evidence.sort(key=lambda x: (-x["relevance_score"], x["relative_path"]))

    output = {
        "case_root": manifest["case_root"],
        "classified_at": manifest["scanned_at"],
        "total_evidence_items": len(evidence),
        "evidence": evidence
    }

    Path(args.output).write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"[Poirot Phase 2] Written: {args.output}")

    # Summary
    phase3_count = sum(1 for e in evidence if e["analysis_lane"] == "phase3")
    phase4_count = sum(1 for e in evidence if e["analysis_lane"] == "phase4")
    high_priority = sum(1 for e in evidence if e["relevance_score"] >= 0.7)
    print(f"  Images → Phase 3: {phase3_count}")
    print(f"  Audio/Video → Phase 4: {phase4_count}")
    print(f"  High-priority items (≥0.7): {high_priority}")
    print(f"\n[Poirot Phase 2] Complete. Next: run_image_analysis.py and/or run_audio_video_analysis.py")


if __name__ == "__main__":
    main()
