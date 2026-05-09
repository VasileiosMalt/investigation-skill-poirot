# Phase 5 â€” Synthesis & Final Report

> *"Everything must be taken into account. If the fact does not conform to the theory â€” let us not discard the fact, let us discard the theory."*

**Reasoning Protocol:** This phase operates under the full constraints of `00-reasoning-protocol.md`. Every claim in the final report must carry an explicit epistemic state `[E/S/P/X]`. Every `[S]` claim must have its full logical chain written out. No inductive leaps. No narrative gravity. The case description is not the answer â€” the evidence is.

## Purpose

Combine ALL `[E]` and `[S]` findings from Phases 1â€“4 into a single, coherent, deductively rigorous investigation report. This phase does not add new analysis â€” it synthesises what has already been established, traces logical chains across modalities, builds the contradiction matrix, and delivers bounded conclusions with explicit epistemic states.

---

## Synthesis Pipeline

```
case_knowledge_base.md      (Phase 1 â€” [E] facts from text)
image_analysis_report.json  (Phase 3 â€” [E/S/P] findings per image)
av_analysis_report.json     (Phase 4 â€” [E/S/P] findings per AV file)
         â”‚
         â–¼
  [5.1] Collect all [E] facts across all modalities
         â”‚
         â–¼
  [5.2] Build contradiction matrix from [E] vs [E] conflicts
         â”‚
         â–¼
  [5.3] Build cross-modal corroboration map
         â”‚
         â–¼
  [5.4] Reconstruct unified timeline from [E] facts only
         â”‚
         â–¼
  [5.5] Build logical chains â†’ derive [S] conclusions
         â”‚
         â–¼
  [5.6] Collect all [P] findings â†’ state what would establish/exclude each
         â”‚
         â–¼
  [5.7] Identify investigative gaps (absence of expected evidence)
         â”‚
         â–¼
  [5.8] Assemble final report
```

---

## 5.1 â€” Collect All [E] Facts

Gather every finding marked `[E]` from all phases. This is the only raw material for synthesis. Nothing else.

**Sources:**
- Phase 1: facts directly stated in documents, structured data, emails
- Phase 3: observations established by the VQA adaptive loop (Pass 1/2/Deep-Drill)
- Phase 4: transcribed words (confidence â‰¥0.7), acoustic events, metadata fields

**For each `[E]` fact, record:**
```
[E-N] Fact text
Source: [filename, page/timestamp if applicable]
Modality: text | image | audio | video
```

**Do NOT include:**
- `[P]` findings at this stage (they are handled separately in step 5.6)
- The case description itself â€” it is a `[P]` claim pending corroboration unless specific elements have been independently established as `[E]` by evidence

---

## 5.2 â€” Contradiction Matrix

Systematically compare every `[E]` fact against every other `[E]` fact for direct logical contradiction.

A contradiction exists when: if `[E-A]` is true, `[E-B]` cannot also be true by the laws of logic or physics.

**Contradiction matrix format:**

| ID | [E] Fact A | Source A | [E] Fact B | Source B | Contradiction type | Cannot both be true because |
|---|---|---|---|---|---|---|
| C1 | "SPEAKER_A states at 00:01:23: 'I have not left the building'" | recording_01.mp3 | "CCTV frame at 22:14 shows a figure exiting via the north door" | cctv_north.mp4 | Direct temporal/spatial | A person cannot simultaneously be inside and exiting a building |
| C2 | "EXIF DateTimeOriginal field: 09:17:03" | scene_01.jpg | "Shadow angle in image consistent with afternoon light (270â€“290Â°)" | Phase 3 deep-drill | Temporal inconsistency | EXIF states morning; shadow geometry requires afternoon sun angle |

**Contradiction classification:**
- **Logical** â€” one fact directly negates the other
- **Temporal** â€” facts assign different times to the same event
- **Spatial** â€” facts assign different locations to the same entity at the same time
- **Numerical** â€” facts give different quantities for the same count
- **Physical** â€” one fact is physically impossible given the other

**Handling contradictions:** Both `[E]` facts remain `[E]`. The contradiction itself becomes a new `[E]` finding: *"[E-A] and [E-B] are logically contradictory."* The resolution is NOT performed here â€” it is noted in the investigation gaps as requiring additional evidence to determine which `[E]` fact is in error.

---

## 5.3 â€” Cross-Modal Corroboration Map

For each `[E]` fact, identify other `[E]` facts from *different* modalities that independently support the same claim.

**Corroboration format:**

```
CLAIM: [statement being corroborated]
CORROBORATING FACTS:
  - [E-N] from [modality]: [fact]
  - [E-M] from [modality]: [fact]
CORROBORATION TYPE: [full | partial | circumstantial]
EPISTEMIC UPGRADE: [does this corroboration elevate a [P] to [S]? If yes, write the logical chain]
```

**Corroboration types:**
- **Full** â€” two or more facts independently establish exactly the same claim
- **Partial** â€” facts are consistent with the claim but establish different aspects of it
- **Circumstantial** â€” facts are all consistent with the claim but none establishes it directly

A **full corroboration from 2+ independent modalities** can elevate a `[P]` claim to `[S]` *only if a logical chain can be written connecting the corroborating `[E]` facts to the claim.*

---

## 5.4 â€” Unified Timeline

Build a timeline using **only `[E]` facts with temporal information**. No inferences, no estimates, no case description claims.

```markdown
| Timestamp | Event (exact [E] fact) | Source | Modality | Precision |
|---|---|---|---|---|
| 2024-03-14 21:00 | Document states: "Last confirmed communication logged 21:00" | comms_log.csv | text | exact |
| 2024-03-14 22:14 | CCTV frame shows figure at north door | cctv_north.mp4 @ 00:22:14 | video | exact |
| 2024-03-14 ~22:17 | EXIF DateTimeOriginal of scene_01.jpg | scene_01.jpg | image | device clock (unverified) |
```

**Precision labels:**
- `exact` â€” the timestamp is directly recorded in evidence with no inferential step
- `device clock (unverified)` â€” from device metadata; clock accuracy not independently verified
- `estimated` â€” derived from physical evidence (sun angle, biological indicators, etc.) â€” state the method and margin

**Timeline gaps:** Any period with no `[E]` temporal coverage is explicitly marked as a gap. Gaps are not filled with inferences.

---

## 5.5 â€” Logical Chain Construction: Deriving [S] Conclusions

This is the core analytical step. The only mechanism for producing a `[S]` conclusion is a complete, written logical chain from `[E]` premises.

### Logical Chain Format

```
CHAIN-[N]: [Title describing the conclusion]

PREMISE 1 [E-ref]: [Exact fact] â€” Source: [file, timestamp]
PREMISE 2 [E-ref]: [Exact fact] â€” Source: [file, timestamp]
[Additional premises if needed]

LOGICAL FORM:
  [State explicitly: "P1 and P2 together entail C because..."]
  [OR: "P1 and P2 are inconsistent with X because..."]
  [The logical form must be a complete sentence that a reader could verify without knowing the conclusion]

CONCLUSION [S]: [Precise claim â€” no more than what the premises entail]

WHAT THIS CONCLUSION DOES NOT ESTABLISH:
  [State what is commonly assumed to follow but actually does not follow from these premises alone]

WHAT WOULD EXTEND THIS TO A STRONGER CONCLUSION:
  [State what additional [E] fact would be needed]
```

### Rules for Logical Chain Construction

1. **Premises must all be `[E]`** â€” a chain built on any `[P]` premise produces a `[P]` conclusion, not `[S]`

2. **The logical form must be explicit** â€” "these two facts are related" is not a logical form. State the specific entailment relationship.

3. **The conclusion must be bounded** â€” state only what the premises actually entail, not what they suggest or what seems likely. If the premises entail a narrow conclusion, the conclusion is narrow.

4. **Name what does NOT follow** â€” this prevents the "slipping" of bounded conclusions into broader inferences in the report.

5. **No intent inferences from physical facts** â€” physical facts establish *what happened*, not *why* or *by whom intentionally*. Intent remains `[P]` unless there is direct testimony that is itself `[E]`.

### Example

```
CHAIN-1: Relationship between EXIF date field and shadow geometry

PREMISE 1 [E-12]: "scene_01.jpg EXIF DateTimeOriginal field value: 2024-03-14 09:17:03" â€” Source: scene_01.jpg EXIF
PREMISE 2 [E-31]: "Phase 3 deep-drill response: shadow in image falls at approximately 260-270Â° from objects, consistent with a sun azimuth of 260-270Â°" â€” Source: scene_01.jpg Phase 3 deep-drill round 1
PREMISE 3 [E-32]: "At latitude 51.5Â°N on March 14, sun azimuth of 260-270Â° occurs between approximately 14:30 and 16:00 local time" â€” Source: astronomical calculation (verifiable)

LOGICAL FORM:
  P1 states the device clock recorded 09:17. P2 and P3 together establish that the light in the image is geometrically consistent with mid-afternoon (14:30â€“16:00), not with 09:17. P1 and {P2+P3} are therefore temporally inconsistent with each other.

CONCLUSION [S]: The EXIF timestamp field (09:17) is inconsistent with the shadow geometry evidence (14:30â€“16:00) for this location and date.

WHAT THIS DOES NOT ESTABLISH:
  - Which value is correct (the device clock may have been wrong, or the shadow analysis may have error margin)
  - That the image was deliberately misdated
  - The actual time the image was captured

WHAT WOULD EXTEND THIS:
  - Independent corroboration of either the clock time or the shadow-derived time from another source
```

---

## 5.6 â€” Possible Interpretations [P]

Collect all `[P]` findings from Phases 1â€“4 and all cases where `[S]` chains do not fully resolve a question.

**Format for each `[P]` claim:**

```
[P-N]: [Statement of the possible interpretation]
Consistent with: [E-ref list]
Not contradicted by: [list what evidence it does not conflict with]
Would be established by: [what [E] fact would elevate this to [S]]
Would be excluded by: [what [E] fact would mark this [X]]
Current status: open | partially supported | weakly supported
```

**Critical rule:** `[P]` claims are listed as open questions, not as probable truths. The report does not rank them by likelihood unless a logical chain supports that ranking.

---

## 5.7 â€” Investigative Gaps

State explicitly what is unknown and what evidence would be most valuable. Do not present gaps as evidence of anything â€” they are absences in the record, nothing more.

**Gap format:**
```
GAP-[N]: [Description of what is missing]
Why it matters: [What question it would answer â€” state as a question, not an assumed answer]
How to address: [Specific evidence type or action that would fill the gap]
```

---

## 5.8 â€” Final Report Assembly

The Poirot Investigation Report assembles all of the above into a single document. Every claim in this document must trace back to a logged `[E]` fact or a written `[S]` logical chain.

```markdown
# Poirot Investigation Report
**Case:** [directory name]
**Analysed:** [date]
**Evidence processed:** [N text | N images | N audio | N video]

---

## Case Description (as provided)
[Verbatim or close paraphrase of the case description from Phase 1. This is a [P] claim â€” it is the starting frame, not established truth.]

---

## Established Facts [E]
[Grouped by modality. Each fact with its source citation. No interpretation.]

---

## Contradiction Matrix
[From step 5.2 â€” all [E] vs [E] conflicts, stated as contradictions, not resolved]

---

## Cross-Modal Corroborations
[From step 5.3 â€” facts independently supported by 2+ modalities]

---

## Unified Timeline
[From step 5.4 â€” [E] facts with temporal data only, with precision labels and gaps marked]

---

## Logical Chains and Supported Conclusions [S]
[From step 5.5 â€” each chain written out in full. No conclusions stated without their chain.]

---

## Possible Interpretations [P]
[From step 5.6 â€” open questions, not ranked unless a chain supports ranking]

---

## Investigative Gaps
[From step 5.7 â€” what is unknown, stated as questions]

---

## Conclusion
[The final bounded assessment. States:
  - What is established [E]
  - What is supported [S] and by which chains
  - What remains possible [P] and what would resolve it
  - What is excluded [X]
  - What the next investigative steps should be, in priority order

The conclusion does not exceed what the evidence supports.
It does not fill gaps with narrative.
It does not resolve contradictions by choosing a side without additional evidence.
It is complete when it has stated the maximum that the evidence permits â€” and nothing more.]
```

---

## Produce Phase 5 Output

| Output File | Content |
|---|---|
| `poirot_report.md` | Final investigation report (human-readable) |
| `poirot_report.json` | Machine-readable structured report |
| `logical_chains.md` | All [S] logical chains in full â€” the working notebook |
| `contradiction_matrix.md` | Full [E] vs [E] contradiction table |
