# Phase 4 — Audio & Video Analysis (Adaptive Loop)

> *"The voice, it tells us much that the words do not."*

**Reasoning Protocol:** This entire phase operates under `00-reasoning-protocol.md`. The agent transcribes and describes first, without case context. It derives questions from what it hears and sees. It triggers deep-drill follow-ups only when a specific, articulable anomaly is found in the content itself.

This phase is **skipped entirely** if the case contains zero audio/video files.

---

## Pipeline Overview

```
evidence_manifest.json (phase4 items)
         │
         ▼
  [4.1] Pre-process & probe media metadata
         │
         ├──► AUDIO PATH ─────────────────────────────────────────────────┐
         │    [4.2] PASS 1: Full neutral transcription (no case context)  │
         │    [4.3] Parse transcript → discrete transcript elements (DTEs) │
         │    [4.4] PASS 2: Derived questions from DTEs                   │
         │    [4.5] Deep-Drill: conditional on A+B+C                      │
         │                                                                 │
         └──► VIDEO PATH ─────────────────────────────────────────────────┤
              [4.6] Audio track extraction → Full Audio Path above        │
              [4.7] PASS 1: Neutral visual description pass               │
              [4.8] Parse visual observations → DVEs                      │
              [4.9] PASS 2: Derived visual questions from DVEs            │
              [4.10] Deep-Drill: conditional on A+B+C                     │
                                                                          │
         ◄────────────────────────────────────────────────────────────────┘
         │
         ▼
  [4.11] Assign epistemic states [E/S/P/X]
         │
         ▼
  [4.12] Filter and produce report
         │
         ▼
  av_analysis_report.json / .md
              [4.9] Motion & behaviour analysis                    │
              [4.10] Scene continuity & timeline analysis          │
                                                                   │
         ◄─────────────────────────────────────────────────────────┘
         │
         ▼
  [4.11] Relevance filtering (against CKB)
         │
         ▼
  av_analysis_report.json / .md
```

---

## 4.1 — Pre-processing & Media Probe

**For all media files:**
1. Verify file is playable — use `ffprobe` to check codec/container integrity; log as `unplayable` and skip if corrupt
2. Record as raw `[E]` facts: duration, codec, bitrate, resolution (video), sample rate (audio), creation date, modification date
3. Record any embedded metadata fields (encoder tag, software tag, comment tag) as raw `[E]` facts
4. Flag files under 1 second or over 8 hours — record this as an objective metadata note, not an interpretation

**Objective metadata discrepancy flags (always `[E]` — never labelled "tampering"):**
- Modification date later than creation date → record the exact delta as a fact
- Encoder/software tag contains a known re-encoding tool → record the exact string value
- These are raw facts to be evaluated in Phase 5, not conclusions

**For video:**
- Extract audio track as `.wav` (16kHz mono) for transcription
- Record whether audio and video stream durations match — exact delta if they differ

---

## 4.2 — PASS 1: Neutral Transcription & Description

### Audio Pass 1

Run Whisper (or equivalent) on the audio file using **only the standard neutral transcription prompt** — no case context, no entity names, no hypotheses.

**Whisper settings:**
- `word_timestamps: true`
- `language: auto-detect`
- Model: `large-v3` for high relevance (≥0.7); `medium` otherwise

**Pass 1 audio output — store verbatim:**
```
[00:00:08 → 00:00:22] SPEAKER_A: "[exact words]"
[PAUSE: 3.2 seconds]
[00:00:25 → 00:00:31] SPEAKER_B: "[exact words]"
[NON-SPEECH: door sound, 0.8s, 00:00:33]
```

**Speaker labels:** Use neutral `SPEAKER_A`, `SPEAKER_B`, etc. Do NOT assign identities at this stage.

**For each segment, also record:**
- Transcription confidence (from Whisper logprob) — flag as `[LOW CONFIDENCE]` if below 0.5
- Presence of non-speech sounds (duration, rough frequency range, qualitative description only)
- Silence gaps ≥2 seconds — record timestamp and duration

**What NOT to do in Pass 1:**
- Do not cross-reference transcript content with the CKB
- Do not flag keywords
- Do not assess speaker emotion or intent
- Do not match speakers to known identities

### Video Pass 1 — Visual

For video files, extract keyframes at regular intervals (every 30 seconds for high-relevance; every 60 seconds for medium) plus at every scene-change boundary detected by ffmpeg.

Each keyframe gets the same Phase 3 **neutral Pass 1 prompt** with no additional case context. The only modification:

```
[Standard Phase 3 Pass 1 prompt]

Additionally: note the timecode visible in the video frame if any clock or timestamp is displayed.
```

Store all keyframe Pass 1 responses indexed by timestamp.

---

## 4.3 — Parse Pass 1: Discrete Transcript Elements (DTEs) and Discrete Visual Elements (DVEs)

### DTEs — from audio/video transcript

Parse the Pass 1 transcript into discrete elements, each of which is a candidate for a derived question:

**DTE types:**
- **Utterance** — a complete spoken segment with timestamp and speaker label
- **Named entity in speech** — any proper noun, number, date, address, or code spoken aloud
- **Acoustic event** — any non-speech sound with timestamp
- **Silence gap** — any silence ≥2 seconds with timestamp and duration
- **Confidence anomaly** — any segment with Whisper confidence below 0.5
- **Abrupt transition** — any sudden change in noise floor, audio level, or recording quality

### DVEs — from video keyframe observations

Parse each keyframe's Pass 1 response into DOEs (same as Phase 3 step 3.3). DVEs are DOEs with their video timestamp attached.

Additional DVE type unique to video:
- **Continuity element** — any object, person, or setting attribute that should persist between frames and can be compared across frames

---

## 4.4 — PASS 2: Derived Questions from DTEs and DVEs

For each DTE or DVE, determine whether a more specific question yields precision beyond Pass 1.

**Generate a Pass 2 question for a DTE when:**
- An utterance contains a word that is inaudible or marked `[UNCLEAR]` — ask for clarification of the specific segment
- A spoken named entity, number, or code was partially captured — ask for the exact transcription of that specific segment
- An acoustic event was described vaguely — ask for a more precise physical description of the sound
- A silence gap is unusually long — ask whether any ambient sound is present during it
- An audio transition was described — ask for the specific nature of the change in acoustic character

**Generate a Pass 2 question for a DVE when:**
- Same conditions as Phase 3 step 3.4 apply
- Additionally: for a continuity element — ask for its state in frame A and frame B separately

**Question formation rules are identical to Phase 3 step 3.4:**
- One element per question
- Physical, verifiable language only
- Never embed the expected answer
- Never name case entities in Pass 2 unless Pass 1 independently established a relevant physical element

**Example derived Pass 2 questions from DTEs:**
- DTE (unclear utterance at 00:01:46): "Listen to the segment from 00:01:44 to 00:01:54. Transcribe every audible word. For words that cannot be determined, describe the vowel/consonant sounds present."
- DTE (acoustic event — door sound at 00:00:33): "Describe the sound at 00:00:33 more precisely. Is it a single impact, a creak, or a sequence of sounds? What is its approximate duration?"
- DTE (15-second silence at 00:07:10): "During the silence from 00:07:10 to 00:07:25, is there any ambient sound present? Describe the noise floor during this period."

---

## 4.5 — Deep-Drill: Conditional Trigger (Audio/Video)

Same three conditions as Phase 3 step 3.5 apply. Applied here to DTEs and DVEs.

### Condition A — Specificity
The Pass 2 response describes the element with enough precision to form a targeted follow-up.
- ✅ "The speaker says 'Calloway' — clearly audible, no ambiguity"
- ❌ "There is a word that might start with a 'K' sound"

### Condition B — Anomaly

**B1 — Internal inconsistency:**
- Speaker claims one thing verbally while a co-occurring visual element (keyframe) shows something different
- The transcript contains a direct self-contradiction within the same recording
- Audio level drops to zero mid-sentence without a pause in speech cadence (splice indicator)
- Noise floor changes abruptly without any described acoustic cause

**B2 — External inconsistency:**
- A spoken statement contradicts an `[E]` fact from the CKB or other evidence
- The external inconsistency must be with an **established** `[E]` fact only

**B3 — Physical implausibility:**
- A described acoustic event is physically implausible in context (e.g., outdoor bird sounds in a described indoor setting)
- Video continuity: an object is present in frame A and absent in frame B with no intervening action that would explain the change

**What is NOT anomaly in AV:**
- A speaker saying something surprising — surprise is not anomaly
- A speaker pausing — pauses are normal
- Background sounds in a recording — presence of background sounds is not anomaly

### Condition C — Materiality
The anomaly relates to a category of fact relevant to the case type as described.

### Deep-Drill Execution

When all three conditions are met:
- For audio: generate a targeted re-listen or re-transcription prompt for the specific segment, or a follow-up question to an LLM about the acoustic properties of that specific segment
- For video: generate a targeted visual question about the specific frame or the specific transition
- Maximum 3 rounds per element
- One question per anomaly — never bundle

**Example Deep-Drills:**

*B2 external inconsistency — audio:*
- Pass 2 established `[E]`: "Speaker says at 00:01:23: 'I haven't spoken to anyone about this'"
- CKB `[E]`: "Witness statement states suspect 'called Victoria at 8 PM to arrange meeting'"
- Condition A ✅ — specific statement; B2 ✅ — contradicts `[E]` fact; C ✅ — material
- Deep-Drill: "Listen to the segment from 00:01:20 to 00:01:30. Is the speaker's statement 'I haven't spoken to anyone about this' clearly audible and unambiguous? Are there any qualifiers or conditional phrases preceding or following it?"

*B1 internal inconsistency — video:*
- Pass 2 established `[E]` (frame at 00:02:14): "A large cardboard box is visible in the right corner"
- Pass 2 established `[E]` (frame at 00:02:52): "The right corner of the room is empty"
- No intervening frame shows the box being moved
- Condition A ✅; B1 ✅ — internal video contradiction; C ✅ — material (theft case)
- Deep-Drill: "Extract and compare frame at 00:02:14 and frame at 00:02:52. Describe every element visible in the right corner of the room in each frame. Is there any frame between these two timestamps that shows the transition?"

---

## 4.6 — Assign Epistemic States

Same as Phase 3 step 3.6. Applied to all AV findings.

**Special rule for voice-based observations:**
- Transcribed words are `[E]` if Whisper confidence ≥0.7 and no deep-drill contradicted them
- Transcribed words are `[P]` if confidence <0.7 or if the segment was marked `[UNCLEAR]`
- Inferences about speaker identity, emotion, or intent are always `[P]` at best — never `[E]`
- Acoustic event descriptions are `[E]` if the sound is unambiguously described; `[P]` if the source is uncertain

---

## 4.7 — Report Filter

Same logic as Phase 3 step 3.7.
- `[E]` and `[S]` with materiality → main report body with timestamps
- `[P]` → noted as "possible interpretation; not established" with what would establish/exclude it
- All external inconsistencies → forwarded to Phase 5 contradiction matrix

---

## 4.8 — AV Evidence Entry Format

```markdown
### 🎬 [Filename] ([modality])
**Path:** `[relative/path]`
**Duration:** HH:MM:SS | **Format:** [codec/container] | **Audio:** Yes/No
**Metadata facts:**
- Creation date field: [value]
- Modification date field: [value]
- Encoder/software tag: [value or "not present"]
- Field discrepancy notes: [exact factual description, no interpretation]

---

**PASS 1 — Neutral Transcript (full stored separately in transcripts/[filename].txt):**
[First 5 transcript lines as preview]
Discrete transcript elements (DTEs) identified: [N]

**PASS 1 — Visual (video only):**
Keyframes extracted: [N] | Discrete visual elements (DVEs) per frame: [avg]

---

**PASS 2 — Derived Questions:**
| DTE/DVE | Timestamp | Question asked | Response summary | State |
|---|---|---|---|---|

---

**DEEP DRILL LOG:**
| Element | Timestamp | Conditions (A/B/C) | Anomaly type | Round | Question | Response | State |
|---|---|---|---|---|---|---|---|

---

**Established Findings [E]:**
- [Timestamp] [Finding] — source: Pass [N]

**Supported Findings [S] — with logical chains:**
PREMISE 1 [E]: [fact] — [timestamp]
PREMISE 2 [E]: [fact] — [timestamp]
LOGICAL FORM: [...]
CONCLUSION [S]: [claim]

**Possible Interpretations [P]:**
| Interpretation | Would be established by | Would be excluded by |
|---|---|---|

**External Inconsistencies → Phase 5:**
| This [E] finding | Contradicts | Source |
|---|---|---|
```

---

## 4.9 — Produce Phase 4 Output

| Output File | Content |
|---|---|
| `av_analysis_report.json` | Full structured AV findings: all passes, DTEs, DVEs, deep-drill logs, epistemic states |
| `av_analysis_report.md` | Human-readable formatted report section |
| `transcripts/[filename].txt` | Full verbatim transcript per file |
| `keyframes/[filename]/` | Extracted keyframe images with timestamps |

**Pass to Phase 5:**
- All `[E]` and `[S]` findings with materiality, with timestamps
- All external inconsistencies
- All `[P]` findings clearly labelled
- Any names/entities independently established in transcripts re-injected into CKB as `[E]` facts with source citation and timestamp
