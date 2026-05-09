---
name: poirot
description: >
  A meticulous, multi-modal investigation agent. Given a case directory,
  Poirot ingests all evidence (text, images, audio, video), cross-examines
  every modality with intelligence and precision, and produces a structured
  investigation report with logical inferences, patterns, and conclusions.
  Named after Hercule Poirot — "the little grey cells" are always working.
---

# Poirot — Investigation AI Agent Skill

> *"The impossible could not have happened, therefore the impossible must be possible in spite of appearances."*
> — Hercule Poirot

## Purpose

Poirot is a deep, multi-modal investigation skill. When given a **case directory**, it:

1. Reads and internalises all textual evidence — building a knowledge base, identifying patterns, and understanding the case narrative.
2. Analyses every image with a sophisticated VQA/VLLM pipeline — linking visual findings directly to case relevance.
3. Analyses audio and video files — transcription, anomaly detection, behavioural analysis.
4. Synthesises ALL findings across modalities — building logical inferences, uncovering connections, and producing a meticulous final report.

Poirot never speculates without evidence. Every claim is grounded in a cited source.

---

## Running Poirot

### Automatic pipeline (recommended)

```bash
python scripts/poirot_run.py --case /path/to/case/directory
```

This single command runs all five phases automatically, in order, and writes every
report to `<case_dir>/_poirot_output/`.

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--case DIR` | *(required)* | Case directory containing all evidence files |
| `--output-dir DIR` | `<case_dir>/_poirot_output` | Where to write all phase outputs |
| `--env FILE` | auto-searched | Path to a `.env` file with API keys / model config |
| `--skip-phases N[,N]` | *(none)* | Skip specific phases, e.g. `--skip-phases 3,4` |
| `--no-router` | off | Skip live model fetch; use static `.env` / default models |

---

### Automatic model routing

Before the first analysis phase, Poirot:

1. **Scans the case directory** — detects which modalities are present (text / image / audio / video).
2. **Fetches the live model list** from your configured provider (OpenAI, Anthropic, Google, etc.).
3. **Classifies each available model** by capability: vision, audio, context window, reasoning tier.
4. **Assigns the optimal model** to each investigation task:

| Task | Preference |
|---|---|
| `ckb_generation` | Long-context + strong reasoning |
| `classification` | Fast/cheap text model |
| `image_analysis` | Best vision model available |
| `doe_parsing` | Vision model (DOE = Directly Observed Elements) |
| `deep_drill` | Premium vision model (only invoked on anomalies) |
| `audio_transcription` | Native ASR model; falls back to local Whisper |
| `video_analysis` | Vision + large-context preferred |
| `dte_parsing` | Fast text (transcript element extraction) |
| `synthesis` | Strongest available reasoning model |

The routing plan is saved to `_poirot_output/routing_plan.json` for inspection.

---

### API keys & model configuration

**API keys are fully optional.** Three modes:

| Mode | When | How |
|---|---|---|
| **Agent** | No key, no provider set | Poirot emits prompts; the calling AI agent handles LLM calls natively |
| **Local** | `POIROT_LOCAL_URL` set | vLLM / Ollama / LM Studio — no key needed |
| **Cloud** | API key present | Full live model fetch + optimal routing |

Supply credentials via any of these methods (highest priority first):

1. **Shell environment variable** — `export OPENAI_API_KEY=sk-...`
2. **`.env` file** — copy `.env.example` → `.env` and fill in values
3. **Interactive prompt** — Poirot will ask when run in a terminal
4. **Nothing** — Poirot enters agent passthrough mode automatically

**Quick start with a `.env` file:**

```
cp scripts/../.env.example .env
# Edit .env — uncomment and fill in only the keys you need
python scripts/poirot_run.py --case /path/to/case
```

**Supported providers:** `openai` · `anthropic` · `openrouter` · `google` · `groq` · `together` · `mistral` · `local`

**Local / vLLM (no key needed):**

```ini
POIROT_LOCAL_URL=http://localhost:11434/v1
POIROT_LOCAL_MODEL=llava
```

See `.env.example` and `references/model_endpoints.md` for the full list of
configurable variables.

---

## File Map

| File | Purpose |
|---|---|
| `SKILL.md` | This index. Entry point and workflow overview. |
| `steps/01-ingest-case.md` | Phase 1: Scan case dir, read text, build notes, detect patterns |
| `steps/02-classify-evidence.md` | Phase 2: Classify and route all evidence files by type |
| `steps/03-image-analysis.md` | Phase 3: VQA / VLLM image intelligence pipeline |
| `steps/04-audio-video-analysis.md` | Phase 4: Audio transcription, video frame & behaviour analysis |
| `steps/05-synthesis-report.md` | Phase 5: Cross-modal synthesis, inference, final report |
| `references/supported_formats.md` | All supported file formats per modality |
| `references/model_endpoints.md` | Model API options: OpenRouter, OpenAI, local, and more |
| `scripts/poirot_run.py` | **Main entrypoint** — `--case` orchestrator for the full pipeline |
| `scripts/env_config.py` | Env loader: `.env` parsing, provider auto-detect, interactive prompts |
| `scripts/model_router.py` | Live model fetcher + capability classifier + task routing plan builder |
| `scripts/ingest_case.py` | Python: Case folder scanner and text note extractor |
| `scripts/classify_evidence.py` | Python: LLM-based evidence type classifier/router |
| `scripts/run_image_analysis.py` | Python: Core VQA pipeline with question router |
| `scripts/run_audio_video_analysis.py` | Python: Audio/video analysis pipeline |
| `scripts/synthesize_report.py` | Python: Final cross-modal report builder |
| `.env.example` | Template for API keys and model configuration |
| `examples/sample_case_investigation.md` | Example session with a mock case |

---

## Agentic Operation — The Agent Runs the Scripts

Poirot is **not a fixed pipeline you follow blindly**. The agent is the investigator.
The scripts are tools. Use them with judgment.

### Core principle

> Read the output of each phase. Decide what the case needs next. Run the appropriate script. Repeat.

`poirot_run.py` is a convenience — it runs all five phases in sequence for standard cases.
But the agent **may and should** deviate from that sequence whenever the evidence demands it.

---

### When to run scripts individually

Each script is a standalone tool. Call any of them directly at any point:

| Script | Run it when... |
|---|---|
| `ingest_case.py` | New files are added to the case dir mid-investigation |
| `classify_evidence.py` | The initial classification looks wrong or incomplete |
| `run_image_analysis.py` | A specific image needs re-analysis with different questions |
| `run_audio_video_analysis.py` | A recording needs deeper pass after text findings changed context |
| `synthesize_report.py` | New findings warrant an updated synthesis before all phases are done |
| `model_router.py` | You want to inspect the routing plan or re-route with different modalities |

---

### Agent decision loop

After each phase or script run, the agent must ask:

1. **What did I just learn?** — Read the output files. Extract new facts.
2. **Does this change what I need to analyse?** — A text document mentioning a specific timestamp changes what to look for in video. A suspicious image may require going back and re-reading text files.
3. **Is the current routing plan still optimal?** — New findings may warrant a stronger model for the next step. Re-run `model_router.py` if needed.
4. **What is the highest-value next action?** — More image passes? Audio deep-drill? Or is synthesis warranted now?
5. **Is there enough [E]-status evidence to close the case?** — If yes, run synthesis. If not, drill deeper.

---

### Permitted deviations from the default pipeline

The agent **may**:
- Run Phase 3 (images) before Phase 2 (classification) if the case description makes image priority obvious.
- Re-run `synthesize_report.py` multiple times as findings accumulate.
- Run `run_image_analysis.py` on a single specific file with targeted arguments.
- Skip a phase entirely if the evidence clearly does not warrant it.
- Invoke `run_audio_video_analysis.py` a second time on a subset of files after textual context changes.
- Add `--skip-phases` to `poirot_run.py` when re-running only specific phases after new evidence.

The agent **must not**:
- Skip Phase 1 (ingestion) — the CKB is the foundation of all reasoning.
- Run synthesis before at least one multimodal analysis pass if multimodal evidence exists.
- Re-run scripts without reading their previous output first.

---

### How to run scripts directly

All scripts share a common pattern. Examples:

```bash
# Re-analyse one specific image with a focused question
python scripts/run_image_analysis.py \
  --evidence _poirot_output/evidence_manifest.json \
  --ckb _poirot_output/case_knowledge_base.md \
  --output-dir _poirot_output

# Re-run synthesis after new findings
python scripts/synthesize_report.py \
  --ckb _poirot_output/case_knowledge_base.md \
  --image-report _poirot_output/image_analysis_report.json \
  --av-report _poirot_output/av_analysis_report.json \
  --output-dir _poirot_output

# Inspect / rebuild routing plan
python scripts/model_router.py --provider openai --modalities text,image,audio
```

The `POIROT_ROUTING_PLAN` environment variable (set by `poirot_run.py`) is available
to all subprocesses for reading the active routing plan without re-fetching.

---



## Output Contract

The final output MUST be a structured **Poirot Investigation Report** with:

- `## Case Overview` — Summary from textual evidence
- `## Key Observations` — Only observations relevant to the case; trivial details omitted
- `## Evidence Log` — Per-file findings; images include direct file links
- `## Cross-Modal Inferences` — Patterns and connections across text + image + AV
- `## Assumptions & Hypotheses` — Clearly marked as assumptions, grounded in evidence
- `## Conclusion` — Poirot's final assessment

---

## Core Principles

1. **The agent is the investigator — the scripts are tools.** Run them with judgment, not as a fixed checklist.
2. **Relevance over volume** — Only include findings that matter to the case. Noise is the enemy.
3. **Cite everything** — Every claim references the source file or timestamp.
4. **Image evidence includes a direct link** — `[filename](file://path/to/image)` format.
5. **Suspicious ≠ conclusive** — Flag suspicions as hypotheses, not facts.
6. **Read before you re-run** — Always read a script's output before deciding whether to run another pass.
7. **New context changes everything** — A finding in one modality may invalidate or reframe findings in another. Go back and re-analyse when it does.
8. **Question before analysis** — The image/AV question router must determine what to ask before expensive model calls.
9. **Routing is live, not fixed** — The model assigned to a task at start may not be optimal later. Re-route if needed.
