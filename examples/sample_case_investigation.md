# Example Investigation — "The Vanishing at Harwick Manor"

A complete walkthrough of a mock investigation case using the Poirot skill.

---

## Case Directory Structure

```
/cases/harwick_manor/
├── description.txt
├── documents/
│   ├── police_report.pdf
│   ├── witness_alice.txt
│   ├── witness_butler.txt
│   └── estate_inventory.xlsx
├── photos/
│   ├── scene_library.jpg
│   ├── scene_garden.jpg
│   ├── suspect_portrait.jpg
│   └── document_note.jpg
├── recordings/
│   ├── phone_call_march14.mp3
│   └── cctv_entrance.mp4
└── financials/
    └── transactions_q1.csv
```

---

## Phase 1 — Ingest Case

**Command:**
```bash
python scripts/ingest_case.py \
  --case-dir /cases/harwick_manor \
  --output-dir /cases/harwick_manor/_poirot_output
```

**Output — `case_manifest.json` (excerpt):**
```json
{
  "case_root": "/cases/harwick_manor/",
  "total_files": 11,
  "modality_counts": { "text": 3, "document": 2, "data": 1, "image": 4, "audio": 1, "video": 1 },
  "files": [
    { "relative_path": "description.txt", "modality": "text", "analysis_lane": "phase1" },
    { "relative_path": "photos/scene_library.jpg", "modality": "image", "analysis_lane": "phase3" },
    { "relative_path": "recordings/phone_call_march14.mp3", "modality": "audio", "analysis_lane": "phase4" }
  ]
}
```

**Output — `case_knowledge_base.md` (after LLM generation):**

```markdown
## Case Summary
Lord Harwick disappeared from his manor on the night of March 14, 2024. He was last seen
by his butler at 9 PM in the library. His niece, Victoria Harwick, was visiting at the time.
The estate safe was found open and empty the following morning.

## Known Entities
### People
| Name | Role | Key Facts | First Mentioned In |
|---|---|---|---|
| Lord Edmund Harwick | Victim | Disappeared March 14, 2024 | description.txt |
| Victoria Harwick | Suspect / Niece | Present on night of disappearance | witness_butler.txt |
| Thomas Briggs | Witness / Butler | Last to see Lord Harwick | witness_butler.txt |
| Alice Moorfield | Witness / Housemaid | Heard argument at 10 PM | witness_alice.txt |

### Timeline
| Date/Time | Event | Source | Confidence |
|---|---|---|---|
| 2024-03-14 21:00 | Lord Harwick last seen in library | witness_butler.txt | HIGH |
| 2024-03-14 ~22:00 | Argument heard | witness_alice.txt | MEDIUM |
| 2024-03-15 07:30 | Safe found open, Lord Harwick missing | police_report.pdf | HIGH |

## Contradictions & Inconsistencies
- witness_butler.txt states Victoria "retired early before 9 PM"
- witness_alice.txt states she heard "Victoria's voice" in the argument at 10 PM

## Pattern Observations
- Safe emptied + disappearance on same night suggests planned event
- Both witnesses agree Lord Harwick was in the library — corroborated location
```

---

## Phase 2 — Classify Evidence

**Command:**
```bash
python scripts/classify_evidence.py \
  --manifest _poirot_output/case_manifest.json \
  --ckb _poirot_output/case_knowledge_base.md \
  --output _poirot_output/evidence_manifest.json \
  --model gpt-4o-mini
```

**Key output from `evidence_manifest.json`:**

```json
{
  "evidence": [
    {
      "relative_path": "photos/scene_library.jpg",
      "modality": "image",
      "relevance_score": 0.92,
      "priority_questions": [
        {
          "type": "scene_description",
          "question": "Describe this room in detail — note any signs of disturbance, unusual placement of objects, or anything inconsistent with a normal evening."
        },
        {
          "type": "anomaly_detection",
          "question": "Are there any signs of struggle, forced entry, or deliberate staging in this image?"
        },
        {
          "type": "text_extraction",
          "question": "Extract all visible text — books, labels, documents, any written notes."
        }
      ]
    },
    {
      "relative_path": "recordings/phone_call_march14.mp3",
      "modality": "audio",
      "relevance_score": 0.95,
      "priority_questions": [
        { "type": "transcription", "question": "Transcribe all speech with word-level timestamps..." },
        { "type": "emotion_detection", "question": "Analyse emotional state and stress levels..." }
      ]
    },
    {
      "relative_path": "photos/document_note.jpg",
      "modality": "image",
      "relevance_score": 0.88,
      "priority_questions": [
        {
          "type": "text_extraction",
          "question": "Extract ALL text from this document image verbatim, including handwriting."
        },
        {
          "type": "forensic_detail",
          "question": "Describe the document: paper type, handwriting characteristics, ink, any marks or folds, condition."
        }
      ]
    }
  ]
}
```

---

## Phase 3 — Image Analysis

**Command:**
```bash
python scripts/run_image_analysis.py \
  --evidence _poirot_output/evidence_manifest.json \
  --ckb _poirot_output/case_knowledge_base.md \
  --output-dir _poirot_output \
  --model gpt-4o \
  --provider openai
```

**Sample finding — `scene_library.jpg`:**

```markdown
### 📸 scene_library.jpg — Relevance: 0.92
**Path:** `photos/scene_library.jpg`
**Link:** [View Image](file:///cases/harwick_manor/photos/scene_library.jpg)
**EXIF:** Date: 2024-03-15 07:45:22 | Device: iPhone 14 | Software: None
**Tampering Indicators:** None detected

**Findings:**

| Question Type | Finding | Relevance |
|---|---|---|
| scene_description | Study/library with large desk. One desk drawer is open and empty. A glass of whisky is half-full on the desk. A book is open on the floor near the fireplace — unusual, books are otherwise neatly shelved. | RELEVANT |
| anomaly_detection | The fireplace has recently burned paper — ash visible with unburned corners suggesting documents were destroyed. A chair near the window is positioned facing away from desk, inconsistent with a reading or working posture. | RELEVANT |
| text_extraction | Book visible on shelf spine: "Harwick Estate 1987–1992 Accounts". Open book on floor: partially visible text "...the arrangement was never to be disclosed to..." | RELEVANT |
```

**Sample finding — `document_note.jpg`:**

```markdown
### 📸 document_note.jpg — Relevance: 0.88
**Link:** [View Image](file:///cases/harwick_manor/photos/document_note.jpg)

| Question Type | Finding | Relevance |
|---|---|---|
| text_extraction | Handwritten note reads: "V — The matter is settled. Destroy this after Thursday. — E.H." | RELEVANT |
| forensic_detail | Blue ballpoint ink on cream stationery. Paper fold marks suggest it was kept in an envelope. Handwriting is aged, consistent with elderly male. Note appears authentic — no signs of forgery. | RELEVANT |
```

---

## Phase 4 — Audio/Video Analysis

**Command:**
```bash
python scripts/run_audio_video_analysis.py \
  --evidence _poirot_output/evidence_manifest.json \
  --ckb _poirot_output/case_knowledge_base.md \
  --output-dir _poirot_output \
  --whisper-model large-v3 \
  --llm-model gpt-4o
```

**Sample transcript — `phone_call_march14.mp3`:**

```
[00:00:08 → 00:00:22] SPEAKER_1: "Victoria. It's done. The papers are signed. I need you to come to the library tonight — there's something I need to give you before I leave."
[00:00:24 → 00:00:31] SPEAKER_2: "Uncle, are you certain about this? What about the arrangement with Calloway?"
[00:00:33 → 00:00:41] SPEAKER_1: "Calloway is no longer a concern. Come at ten. Tell no one."
```

**LLM Analysis excerpt:**

> **Key Statements:** Lord Harwick (SPEAKER_1 — confirmed by voice context) initiates a covert meeting with Victoria at 10 PM. The mention of "papers" and "leaving" is significant.
>
> **Entity Match:** "Calloway" mentioned — not in CKB. **FLAG: New entity requiring investigation.**
>
> **Acoustic Events:** At 00:00:33, brief background sound — possible second voice or door — before SPEAKER_1 continues. Suggests Lord Harwick may not have been alone when making the call.
>
> **Contradictions:** The butler states Victoria "retired early before 9 PM". This call establishes she was summoned to the library at 10 PM — directly contradicting the butler's account.

---

## Phase 5 — Synthesis & Final Report

**Command:**
```bash
python scripts/synthesize_report.py \
  --ckb _poirot_output/case_knowledge_base.md \
  --image-report _poirot_output/image_analysis_report.json \
  --av-report _poirot_output/av_analysis_report.json \
  --manifest _poirot_output/case_manifest.json \
  --output-dir _poirot_output \
  --model claude-opus-4-5 \
  --provider anthropic
```

**Output excerpt — `poirot_report.md`:**

---

```markdown
# 🔍 Poirot Investigation Report

**Case Directory:** `/cases/harwick_manor/`
**Evidence Processed:** 6 text/document files | 4 images | 2 audio/video files

---

## Case Overview
Lord Edmund Harwick disappeared from Harwick Manor on the night of March 14, 2024, along with the contents of his estate safe. The available evidence indicates this was not a random event — Lord Harwick himself arranged a secret meeting with his niece Victoria at 10 PM, contradicting the butler's account of her whereabouts. Documents were burned in the library fireplace. A handwritten note suggests Lord Harwick intended to depart, and a previously unknown associate named "Calloway" is referenced in communications.

## Key Observations
1. Lord Harwick made a phone call to Victoria at ~8 PM arranging a 10 PM meeting "tell no one" — directly contradicts butler's statement that Victoria retired before 9 PM. **[phone_call_march14.mp3 @ 00:00:08]**
2. Library fireplace contains burned document remains — consistent with deliberate destruction of records. **[scene_library.jpg — anomaly_detection]**
3. Handwritten note from Lord Harwick to "V" reads "The matter is settled. Destroy this after Thursday." — suggests preplanned action. **[document_note.jpg — text_extraction]**
4. "Calloway" is referenced by both parties in the phone call but appears in no other document — unexplained entity. **[phone_call_march14.mp3 @ 00:00:24]**
5. financial transactions_q1.csv shows a transfer of £240,000 from the estate account on March 13, 2024 — the day before the disappearance. **[financials/transactions_q1.csv]**

## Cross-Modal Connections
**[CONNECTION-1]** Victoria was present at 10 PM — phone call confirms summoning (audio) ↔ Alice's testimony confirms argument at 10 PM (text) — both contradict the butler's account (text)

**[CONNECTION-2]** "Papers signed" (phone call) + empty safe (police report) + burned documents (library photo) — consistent pattern of deliberate financial/legal record clearance

## Contradictions & Inconsistencies
| # | Claim | Source A | Source B | Nature | Significance |
|---|---|---|---|---|---|
| C1 | Victoria "retired early before 9 PM" | witness_butler.txt | phone_call_march14.mp3 @ 00:00:08 | Direct temporal contradiction | HIGH |
| C2 | "No argument heard" | witness_butler.txt (implied) | witness_alice.txt — argument at 10 PM | Omission contradiction | HIGH |

## Inferences & Hypotheses

### Direct Inferences (High Confidence)
**[INF-01]** Lord Harwick deliberately arranged a secret meeting with Victoria on the night of his disappearance.
*Evidence:* phone_call_march14.mp3 (direct recording), witness_alice.txt (corroborates 10 PM activity)
*Confidence:* HIGH

**[INF-02]** Thomas Briggs (butler) is providing a false account of Victoria's whereabouts.
*Evidence:* phone_call_march14.mp3 contradicts his statement; witness_alice.txt independently corroborates Victoria's presence
*Confidence:* HIGH

### Supported Hypotheses (Medium Confidence)
**[HYP-01]** Lord Harwick planned and executed his own disappearance, with Victoria's assistance.
*Evidence basis:* Pre-arranged meeting, "before I leave" (phone call), signed papers, cleared safe, burned documents, £240k transfer day before
*Missing link:* Destination, identity of "Calloway", whether Victoria was complicit or deceived
*Confidence:* MEDIUM

### Speculative Possibilities (Low Confidence)
**[SPEC-01]** "Calloway" may be a third party whose arrangement conflicted with Lord Harwick's plan — potentially the reason for urgency.
*Evidence basis:* Single audio reference only
*Confidence:* LOW — requires investigation

## Investigative Gaps
- Identity and role of "Calloway" — entirely unknown
- Destination of £240,000 transfer
- Contents of documents destroyed in library
- Victoria Harwick has not been interviewed in available evidence
- Lord Harwick's current whereabouts
- Whether "leaving" was voluntary or coerced

## Conclusion
The evidence strongly indicates Lord Harwick's disappearance was deliberate and preplanned. The sequence of events — financial transfer, signed papers, clandestine meeting, burned documents, cleared safe — forms a coherent pattern of a staged departure rather than foul play. Thomas Briggs's false account of Victoria's whereabouts warrants further questioning. The unknown entity "Calloway" is the most significant gap.

*Recommended next steps:* (1) Identify and locate "Calloway". (2) Trace the £240,000 transfer. (3) Interview Victoria Harwick formally. (4) Forensic analysis of the fireplace ash.
```

---

## Running the Full Pipeline

```bash
# Step 1: Ingest
python scripts/ingest_case.py --case-dir /cases/harwick_manor --output-dir /cases/harwick_manor/_output
# → Send ckb_prompt.txt to your LLM and save response as case_knowledge_base.md

# Step 2: Classify
python scripts/classify_evidence.py \
  --manifest _output/case_manifest.json \
  --ckb _output/case_knowledge_base.md \
  --output _output/evidence_manifest.json

# Step 3: Image analysis
python scripts/run_image_analysis.py \
  --evidence _output/evidence_manifest.json \
  --ckb _output/case_knowledge_base.md \
  --output-dir _output \
  --model gpt-4o

# Step 4: AV analysis
python scripts/run_audio_video_analysis.py \
  --evidence _output/evidence_manifest.json \
  --ckb _output/case_knowledge_base.md \
  --output-dir _output \
  --whisper-model large-v3 \
  --llm-model gpt-4o

# Step 5: Synthesise
python scripts/synthesize_report.py \
  --ckb _output/case_knowledge_base.md \
  --image-report _output/image_analysis_report.json \
  --av-report _output/av_analysis_report.json \
  --manifest _output/case_manifest.json \
  --output-dir _output \
  --model claude-opus-4-5 \
  --provider anthropic
```

**Final report:** `_output/poirot_report.md`
