# Phase 3 — Image Analysis (Adaptive VQA Loop)

> *"I have a very great regard for the texture of things."*

**Reasoning Protocol:** This entire phase operates under `00-reasoning-protocol.md`. The agent does not know what it is looking for when it opens an image. It observes first. It asks questions second. It asks deeper questions only when what it sees specifically warrants them.

This phase is **skipped entirely** if the case contains zero image files.

---

## Pipeline Overview

```
evidence_manifest.json (phase3 items, sorted by relevance desc)
         │
         ▼
  [3.1] Pre-process: convert format, extract EXIF metadata
         │
         ▼
  [3.2] PASS 1 — Neutral observation (no case context injected)
         │         Single open-ended prompt. Model is a blind observer.
         ▼
  [3.3] Parse Pass 1 → identify discrete observable elements (DOEs)
         │
         ▼
  [3.4] PASS 2 — Derived questions (one per DOE that warrants precision)
         │         Questions generated from what was observed, not from templates.
         ▼
  [3.5] Evaluate each Pass 2 response against Deep-Drill conditions:
         │     A: Specificity  B: Anomaly  C: Materiality
         │
         ├── All 3 met → DEEP DRILL (targeted, iterative follow-ups, max 3 rounds)
         └── Any fails  → log element as note, do not drill
         │
         ▼
  [3.6] Assign epistemic state [E/S/P/X] to each finding
         │
         ▼
  [3.7] Filter for report: [E]+[S] with materiality → report body
                            [P] → "requires corroboration" section
         │
         ▼
  image_analysis_report.json / .md
```

---

## 3.1 — Pre-processing & EXIF Extraction

Before any model call:

1. Verify file is readable — log as `unreadable` and skip if corrupt
2. Convert to model-compatible format if needed (see `references/supported_formats.md`)
3. Resize to max 2048px longest side if needed — preserve original, work on copy
4. Extract EXIF metadata — these are raw `[E]` facts if the field is populated

**EXIF fields to record:**

| Field | What it records (not what it proves) |
|---|---|
| `DateTimeOriginal` | Value of device clock when shutter fired |
| `DateTime` (ModifyDate) | Value of software modification timestamp |
| `GPS` | Device-reported coordinates at capture |
| `Make` / `Model` | Device type string |
| `Software` | Post-processing software field value |
| `ImageWidth` / `ImageHeight` | Stored native resolution |
| `Orientation` | Stored rotation flag |

**EXIF is recorded as raw metadata — not as conclusions.**
- ✅ `[E]` "EXIF DateTimeOriginal field: 2024-03-14 22:17:03"
- ❌ "The photo was taken at 10:17 PM" — presupposes device clock accuracy

**Objective field-level discrepancy flags (always `[E]` — never labelled "tampering"):**
- ModifyDate later than DateTimeOriginal by more than 1 minute → record the factual delta, nothing more
- Software field contains a known image editor → record the exact string value

---

## 3.2 — Pass 1: Neutral Observation

Use the `pass1_prompt` from the evidence manifest. If none was set, use:

```
Describe this image completely and objectively. Include:
- The type of setting or scene visible
- Every distinct object or element you can see, and its position relative to others
- The lighting conditions: apparent source direction, shadow angles and lengths, quality
- Any text, symbols, numbers, or markings visible anywhere in the image
- The physical state of every object: condition, damage, displacement, cleanliness
- Any people or animals present: describe only physical appearance, position, and posture
- Anything that appears physically inconsistent, unusual in placement, or out of proportion

Do not interpret. Do not infer. Do not speculate. Describe only what is directly visible.
```

**System prompt for ALL VQA model calls in this phase:**
```
You are a precise visual observer assisting a factual analysis. Describe only what you see
with maximum accuracy and zero speculation. If you cannot determine a detail, state what
you can observe and note the limit explicitly. Never name people. Never infer intent or
emotion. Never assert cause or meaning. Report observable physical facts only.
```

Store the full Pass 1 response verbatim. It is a primary evidence record.

---

## 3.3 — Parse Pass 1: Discrete Observable Elements (DOEs)

After Pass 1 returns, parse the response into a structured list of discrete observable elements. A DOE is any self-contained described item that could independently be the subject of a precise follow-up question.

**DOE identification rules:**
- Every distinct named object → one DOE
- Every spatial relationship with physical specificity → one DOE
- Every piece of text mentioned (even partial) → one DOE
- Every person or figure → one DOE
- Every lighting or shadow characteristic → one DOE
- Every physical state (damage, stain, displacement, orientation anomaly) → one DOE

**Example:** Pass 1 returns: *"A desk near the right wall with an open drawer. Papers scattered on the floor. A lamp with its shade at an angle. A glass containing a clear liquid. A book lying face-down on the floor near the bottom-left corner."*

Parsed DOEs:
1. Desk — position: near right wall
2. Desk drawer — state: open
3. Papers — position: floor; state: scattered
4. Lamp shade — state: angled (not vertical)
5. Glass — position: desk; contents: clear liquid; fill level: unspecified
6. Book — position: floor bottom-left; orientation: face-down (spine-up)

---

## 3.4 — Pass 2: Derived Questions

For each DOE, determine whether a more specific question yields precision beyond Pass 1.

**Generate a Pass 2 question when:**
- The DOE was described vaguely and more precision has potential investigative value
- Text was noted but not fully transcribed
- A physical state was approximated and can be described more precisely
- A quantity, colour, or dimension was left unspecified

**Do NOT generate a Pass 2 question when:**
- Pass 1 already described the DOE with full precision
- The DOE is unambiguously background (painted ceiling, unremarkable floor)
- Asking more would require injecting case-context assumptions

**Question formation rules (from `00-reasoning-protocol.md`):**
1. One element per question — never bundle
2. Physical, verifiable language only
3. Never embed the expected answer
4. Never name case entities unless Pass 1 independently described a physical element matching a known description
5. The question must be answerable with "no such element is present" — this is a valid answer

**Example derived Pass 2 questions:**
- DOE 2: "Describe the interior of the open drawer. Is it empty, or does it contain items? If items are present, describe each one's appearance and position."
- DOE 3: "Can any text on the scattered papers be read from this image? If yes, transcribe it exactly, including partial words."
- DOE 4: "Describe the angle of the lamp shade relative to the lamp base. Is it displaced uniformly in one direction, or does it appear twisted or deformed?"
- DOE 5: "Describe the liquid in the glass: its colour, opacity, approximate fill level relative to the rim, and whether any particles or solid matter are visible."
- DOE 6: "What text, if any, is visible on the spine or cover of the book lying face-down?"

No Pass 2 question needed for DOE 1 — position is already precisely stated.

---

## 3.5 — Deep-Drill: Conditional Trigger

After Pass 2 responses return, evaluate each against all three conditions.

### Condition A — Specificity
The Pass 2 response describes the element with enough precision to form a targeted follow-up. Vague responses do not qualify.
- ✅ "The text reads: 'RE: Account 4471 — transfer authorised 14/03'"
- ❌ "There appears to be some text but it is not clearly legible"

### Condition B — Anomaly
The element is objectively anomalous by at least one of:

**B1 — Internal inconsistency:** Something within this image contradicts something else within this image.
- Example: shadow geometry contradicts the apparent light source position

**B2 — External inconsistency:** The observed element contradicts an `[E]` fact already established from another evidence source.
- The contradiction must be with an **established** `[E]` fact — not with a hypothesis or the case description

**B3 — Physical implausibility:** The described state is physically implausible within the described context.
- Example: a brimming undisturbed glass in a scene with overturned furniture

**What is NOT anomaly:**
- Something being "noteworthy" or "interesting"
- Something fitting a hypothesis
- Something merely unexpected — unexpectedness alone is not inconsistency

### Condition C — Materiality
The anomaly involves a category of fact relevant to the case type as described. Derive from the case description, not from hypotheses.

### Deep-Drill Execution

When all three conditions are met, generate targeted deep-drill questions:
- One question per anomaly — never bundle
- Target the specific element and the specific inconsistency only
- If testing a B2 inconsistency: reference the physical description of the established `[E]` fact as the comparison anchor — not its interpretation
- Maximum 3 rounds per element
- Stop when: no new information, anomaly is not extended, or 3 rounds completed

All deep-drill rounds are logged in `deep_drill_log`.

---

## 3.6 — Assign Epistemic States

| State | When it applies |
|---|---|
| `[E]` ESTABLISHED | Directly and clearly described by the model; directly extracted text; EXIF field value |
| `[S]` SUPPORTED | Two or more `[E]` findings logically require the claim; logical chain must be written out |
| `[P]` POSSIBLE | Consistent with observations but other interpretations also fit |
| `[X]` EXCLUDED | Directly contradicted by an `[E]` finding |

Every claim gets a state. No exceptions.

---

## 3.7 — Report Filter

**Main report body:** `[E]` findings with case materiality + `[S]` findings with full logical chain + all confirmed external inconsistencies.

**"Possible Interpretations" section:** `[P]` findings — recorded as "consistent with observations; not established." Each `[P]` states what would establish it and what would exclude it.

**Excluded from report:** Background `[E]` findings with no materiality. `[X]` claims forwarded to contradiction matrix in Phase 5.

---

## 3.8 — Image Evidence Entry Format

```markdown
### 📸 [Filename]
**Path:** `[relative/path/to/file]`
**Link:** [View Image](file:///absolute/path/to/image)

**EXIF Metadata (raw fields):**
- DateTimeOriginal: [value or "field not present"]
- ModifyDate: [value or "field not present"]
- GPS: [value or "field not present"]
- Device: [Make + Model or "field not present"]
- Software: [value or "field not present"]
- Field discrepancy notes: [exact factual description of any field-level discrepancies, no interpretation]

**PASS 1 — Neutral Observation (verbatim summary):**
[First 3–5 sentences or full response if short]
Discrete observable elements identified: [N]

**PASS 2 — Derived Questions:**
| DOE | Question asked | Response summary | Epistemic state |
|---|---|---|---|

**DEEP DRILL LOG:**
| Element | Conditions (A/B/C) | Anomaly type (B1/B2/B3) | Round | Question | Response | State |
|---|---|---|---|---|---|---|

**Established Findings [E]:**
- [Finding] — source: Pass [N], question: "[question]"

**Supported Findings [S]:**
PREMISE 1 [E]: [fact] — source
PREMISE 2 [E]: [fact] — source
LOGICAL FORM: [why P1 and P2 entail/are inconsistent with C]
CONCLUSION [S]: [claim]

**Possible Interpretations [P]:**
| Interpretation | Would be established by | Would be excluded by |
|---|---|---|

**External Inconsistencies → Phase 5 contradiction matrix:**
| This [E] finding | Contradicts | Source |
|---|---|---|
```

---

## 3.9 — Produce Phase 3 Output

| Output File | Content |
|---|---|
| `image_analysis_report.json` | Full structured findings per image: all passes, DOEs, deep-drill logs, epistemic states |
| `image_analysis_report.md` | Human-readable report section |

**Pass to Phase 5:**
- All `[E]` and `[S]` findings with materiality
- All external inconsistencies
- All `[P]` findings clearly labelled as unestablished
- Text extracted from images re-injected into CKB as `[E]` facts with source citation
