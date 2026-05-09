# Phase 2 — Classify & Route Evidence

> *"The order. The method. It is everything."*

**Reasoning Protocol:** This phase operates under the full constraints of `00-reasoning-protocol.md`. Classification must be based solely on observable file properties. No question is generated based on what the case description *suggests might be in the file*. Questions are generated based on what the *file type can physically contain*. The case description informs what is *materially relevant* — it does not inform what questions to ask before the evidence has been observed.

## Purpose

Using the `case_manifest.json` from Phase 1, classify every evidence file into an **analysis lane** and determine the **initial neutral observation prompt** for each file. The full question set for each file is *not generated here* — it is derived dynamically in Phases 3 and 4 after the first neutral observation pass returns. This phase only assigns the Pass 1 prompt and a set of observable-property-derived seed questions as a starting scaffold.

---

## Evidence Classification Schema

Each file is assigned:
- `modality`: text | image | audio | video | data | unknown
- `subtype`: a more specific classification (see tables below)
- `relevance_score`: 0.0–1.0 — estimated relevance to the case (from CKB context)
- `analysis_lane`: the processing pipeline to use
- `pass1_prompt`: the neutral observation prompt for this file (generated here)
- `seed_questions`: observable-property-derived scaffold questions (generated here from file type only — NOT from case context)
- `deep_drill_log`: populated during Phases 3/4 when conditional deep-drills are triggered

---

### 2.1 — Classification Rules by Extension

**Text / Document**

| Extension | Subtype | Analysis Lane |
|---|---|---|
| `.txt`, `.md`, `.log` | raw_text | Phase 1 (already done) |
| `.pdf` | document or scanned_image | Phase 1 if text layer; Phase 3 if image-only |
| `.docx`, `.odt` | document | Phase 1 |
| `.csv`, `.tsv` | structured_data | Phase 1 |
| `.json`, `.xml`, `.yaml` | structured_data | Phase 1 |
| `.eml`, `.msg` | email | Phase 1 + entity extraction |
| `.html`, `.htm` | web_content | Phase 1 |

**Image**

| Extension | Subtype | Analysis Lane |
|---|---|---|
| `.jpg`, `.jpeg`, `.png`, `.webp` | photograph | Phase 3 |
| `.tiff`, `.bmp`, `.heic` | photograph | Phase 3 |
| `.gif` | animated_image | Phase 3 (first + key frames) |
| `.svg` | vector_graphic | Phase 3 (render first) |
| `.raw`, `.cr2`, `.nef` | raw_photo | Phase 3 (convert first) |
| Screenshot (detected by name/metadata) | screenshot | Phase 3 |

**Audio**

| Extension | Subtype | Analysis Lane |
|---|---|---|
| `.mp3`, `.wav`, `.flac`, `.aac`, `.ogg`, `.m4a` | audio | Phase 4 |
| `.wma`, `.opus`, `.aiff` | audio | Phase 4 |

**Video**

| Extension | Subtype | Analysis Lane |
|---|---|---|
| `.mp4`, `.mov`, `.avi`, `.mkv`, `.wmv` | video | Phase 4 |
| `.webm`, `.flv`, `.ts`, `.m2ts` | video | Phase 4 |

---

### 2.2 — Relevance Scoring

Assign a **relevance score** (0.0–1.0) to each file using the CKB as context.

**Signals that increase relevance:**
- File name contains a known entity (person, place, date) from the CKB
- File is located in a folder that suggests importance (e.g., `evidence/`, `exhibits/`, `suspects/`)
- File timestamp aligns with the case timeline
- File is referenced by name in any text document

**Signals that decrease relevance:**
- Generic names (`IMG_001.jpg`, `untitled.txt`)
- File is in system/cache folders (`__MACOSX`, `.Thumbs`, `.DS_Store`)
- File predates or postdates the case window by a large margin
- File is a duplicate (hash-matched)

**Thresholds:**
- `0.7–1.0` → High priority — analyse first, full depth
- `0.4–0.69` → Medium priority — standard analysis
- `0.1–0.39` → Low priority — light analysis, flag only if something notable
- `0.0–0.09` → Skip unless nothing else exists

---

---

### 2.3 — Pass 1 Neutral Observation Prompts

These prompts are the **only prompts generated in Phase 2**. They are strictly neutral — no case context, no entity names, no hypotheses. The model is a blind observer. Its output becomes the raw material from which Phase 3/4 derives all further questions.

**For all image files:**
```
Describe this image completely and objectively. Include:
- The type of setting or scene visible
- Every distinct object or element you can see, and its position relative to others
- The lighting conditions — source direction, quality, shadows
- Any text, symbols, numbers, or markings visible anywhere in the image
- The physical state of objects — condition, damage, displacement, cleanliness
- Any people or animals present — describe only their physical appearance and posture
- Anything that appears physically inconsistent, unusual in its placement, or out of proportion

Do not interpret, infer, or speculate. Describe only what is directly visible.
```

**For all audio files:**
```
Analyse this audio recording. Provide:
- A verbatim transcription of all speech, with timestamps for each speaker turn
- The number of distinct voices and a physical description of each (pitch range, pace, accent if determinable)
- A list of all non-speech sounds with timestamps and physical descriptions (duration, approximate frequency, source type if identifiable from sound alone)
- Any segments where audio quality degrades, cuts abruptly, or changes character noticeably
- Any periods of silence lasting more than 2 seconds — note their timestamps

Do not interpret speaker intent, emotion, or truthfulness at this stage.
```

**For all video files:**
```
Analyse this video. Provide:
- A description of the visual content, scene by scene, noting any changes in setting or composition
- A verbatim transcription of all speech with timestamps
- A description of all visible human or animal movement — what moves, in which direction, at what pace
- All visible text, signs, or on-screen information at the timestamps where they appear
- All non-speech sounds with timestamps
- Any frame where the image abruptly changes, cuts, freezes, or shows compression artifacts
- Any visible timestamps, clocks, or date indicators within the frame

Do not assess intent, meaning, or significance at this stage.
```

---

### 2.4 — Seed Questions (File-Type Scaffolding Only)

Seed questions are a minimal scaffold generated from **file type and observable metadata alone** — before any model has seen the content. They are starting points for the Pass 2 derived-question loop in Phase 3/4. They are NOT the full question set. They are NOT derived from the case description.

**Image seed questions (from file type only):**
- "Describe the position and orientation of every object visible relative to fixed reference points such as walls, floors, or door frames."
- "List every area of the image where the sharpness, grain, or colour balance differs noticeably from surrounding areas."
- "Transcribe all text visible in the image, including partial text and characters at the image edge."

**Audio seed questions (from file type only):**
- "For each speaker turn, describe any change in speaking pace or pitch relative to the immediately preceding turn."
- "Describe the acoustic environment — is it reverberant, dampened, outdoors? What background sounds are consistent throughout?"
- "Identify any segment where the noise floor changes abruptly — describe the before and after."

**Video seed questions (from file type only):**
- "Identify each point in the video where the scene or composition changes. Describe what changes and what remains constant."
- "For each visible person, describe their movement trajectory from entry to exit of the frame."
- "Compare the lighting conditions across the full duration of the video. Note any changes."

---

### 2.5 — Relevance Scoring

Assign a **relevance score** (0.0–1.0) to each file using the CKB as context.

**Signals that increase relevance:**
- File name contains a known entity (person, place, date) from the CKB
- File is located in a folder that suggests importance (e.g., `evidence/`, `exhibits/`, `suspects/`)
- File timestamp aligns with the case timeline window
- File is explicitly referenced by name in any text document

**Signals that decrease relevance:**
- Entirely generic names with no semantic content (`IMG_001.jpg`, `untitled.txt`)
- File is in system/cache folders (`__MACOSX`, `.Thumbs`, `.DS_Store`)
- File predates or postdates the case window by a large margin with no explanation
- File is a confirmed duplicate (hash-matched)

**Thresholds:**
- `0.7–1.0` → High priority — analyse first, full depth
- `0.4–0.69` → Medium priority — standard analysis
- `0.1–0.39` → Low priority — neutral pass only; escalate only if Pass 1 returns something materially anomalous
- `0.0–0.09` → Skip unless no other evidence of that modality exists

**Important:** A low relevance score does not suppress analysis — it only deprioritises order and depth. The Pass 1 neutral observation always runs regardless of score. A file with a low score may return a Pass 1 observation that independently triggers a deep-drill.

---

### 2.6 — Produce Phase 2 Output

| Output File | Content |
|---|---|
| `evidence_manifest.json` | Full classified evidence with relevance scores, Pass 1 prompts, and seed questions |

**Schema:**
```json
{
  "evidence": [
    {
      "path": "photos/scene_01.jpg",
      "modality": "image",
      "subtype": "photograph",
      "relevance_score": 0.88,
      "analysis_lane": "phase3",
      "pass1_prompt": "Describe this image completely and objectively...",
      "seed_questions": [
        "Describe the position and orientation of every object visible...",
        "List every area where sharpness or colour balance differs noticeably...",
        "Transcribe all visible text including partial characters."
      ],
      "deep_drill_log": [],
      "file_context_note": "Referenced in witness_statement.txt as 'the kitchen photo'"
    }
  ]
}
```

**Pass to Phase 3:** All `phase3` lane items, sorted by relevance score descending.
**Pass to Phase 4:** All `phase4` lane items, sorted by relevance score descending.
