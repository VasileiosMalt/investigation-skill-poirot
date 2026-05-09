# Phase 1 — Ingest Case & Build Knowledge Base

> *"First, one must know the facts. Then one can use the little grey cells."*

## Purpose

Scan the entire case directory. Read all textual data. Extract structured notes. Identify patterns, anomalies, and connections. Build a **Case Knowledge Base (CKB)** that all subsequent phases will reference.

This phase is **always mandatory** — even if the case is purely visual, the CKB provides the interpretive frame for all evidence analysis.

---

## Step-by-Step Instructions

### 1.1 — Scan the Case Directory

Use `scripts/ingest_case.py` or manually enumerate the case folder.

**Collect:**
- Full recursive file listing with paths, sizes, and extensions
- Folder structure (may reveal intentional organisation — e.g., `suspects/`, `timeline/`, `financials/`)
- File count per modality: text, image, audio, video, structured data (CSV/JSON/XML), PDFs, archives

**Output:** `case_manifest.json` — a structured inventory of all files.

```json
{
  "case_root": "/path/to/case/",
  "scanned_at": "2024-01-15T10:30:00Z",
  "files": [
    { "path": "notes/witness_statement.txt", "type": "text", "size_bytes": 4210 },
    { "path": "photos/scene_01.jpg", "type": "image", "size_bytes": 2048000 },
    ...
  ],
  "modality_counts": { "text": 8, "image": 12, "audio": 2, "video": 1, "data": 3 }
}
```

---

### 1.2 — Read All Textual Evidence

Process every text-bearing file in priority order:

**Priority 1 — Case description / brief**
- Files named: `case.txt`, `description.md`, `brief.txt`, `README`, `summary.*`, `overview.*`
- Read first. This is the **anchor** — it defines what is relevant.

**Priority 2 — Witness statements, reports, testimonies**
- Any `.txt`, `.md`, `.pdf`, `.docx` files
- Extract: who, what, when, where, why (5W framework)

**Priority 3 — Structured data**
- `.csv`, `.json`, `.xml`, `.xlsx` — financial records, logs, timelines, databases
- Parse and summarise key fields. Flag anomalies (gaps, spikes, inconsistencies).

**Priority 4 — Metadata**
- File creation/modification dates, EXIF data (deferred to Phase 3 for images)
- Communication logs, email headers, system logs

**For each file read:**
- Extract key entities: **people**, **places**, **dates/times**, **objects**, **organisations**
- Note any **contradictions** across documents
- Note any **missing expected information** (e.g., a report with pages missing, a timeline with unexplained gaps)

---

### 1.3 — Build the Case Knowledge Base (CKB)

The CKB is a structured mental model of the case. Produce it as `case_knowledge_base.md`.

#### Structure:

```markdown
## Case Summary
[2-4 sentence summary of the case as understood from the description/brief]

## Known Entities
### People
| Name | Role | Key Facts | First Mentioned In |
|---|---|---|---|

### Places
| Name | Relevance | Mentioned In |
|---|---|---|

### Timeline
| Date/Time | Event | Source | Confidence |
|---|---|---|---|

### Key Objects / Items
| Item | Relevance | Mentioned In |
|---|---|---|

## Contradictions & Inconsistencies
[List ONLY if found — each with sources that contradict each other]

## Information Gaps
[Missing data that SHOULD be present given the case context]

## Pattern Observations
[ONLY include patterns that are genuinely notable — do not pad]
```

**Pattern detection rules:**
- A pattern requires ≥2 corroborating data points
- Patterns must connect to the case description — irrelevant coincidences are excluded
- Annotate each pattern with its evidence sources

---

### 1.4 — Produce Phase 1 Output

| Output File | Content |
|---|---|
| `case_manifest.json` | Full file inventory |
| `case_knowledge_base.md` | CKB: entities, timeline, contradictions, patterns |
| `phase1_notes.md` | Analyst notes — raw observations before filtering |

**Pass to Phase 2:** `case_manifest.json` (for evidence routing) + `case_knowledge_base.md` (as context for all subsequent phases).

---

## Handling Special Text Cases

| Scenario | Action |
|---|---|
| PDF with scanned pages (no text layer) | Flag as image evidence; defer to Phase 3 |
| Encrypted / password-protected file | Log as `inaccessible`; note in report |
| Foreign language text | Translate using LLM before processing |
| Corrupted file | Log as `unreadable`; note in report |
| Very large file (>10MB text) | Chunk and summarise per section |

---

## What NOT to Do

- Do NOT read image EXIF here (Phase 3)
- Do NOT analyse audio/video content here (Phase 4)
- Do NOT draw final conclusions here — this is evidence gathering only
- Do NOT include trivial observations in the CKB — quality over quantity
