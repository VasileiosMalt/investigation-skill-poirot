# Contributing to Poirot

Thank you for your interest in contributing. Poirot is a precise tool — contributions should uphold the same standards it applies to evidence.

---

## What we welcome

- **New provider support** — additional model fetchers in `model_router.py`
- **New file format support** — text extraction for formats not yet handled in `ingest_case.py`
- **Improved capability inference** — better model classification heuristics in `model_router.py`
- **Additional reasoning checks** — improvements to the epistemic protocol in `steps/00-reasoning-protocol.md`
- **Bug fixes** — especially around edge cases in file parsing, API error handling, or routing logic
- **Documentation** — clearer phase instructions, examples, or reference material

---

## What we do not want

- Changes that weaken the orthological reasoning constraints (no speculative leaps, no bias injection)
- Hard-coded model names in phase scripts (routing must stay dynamic)
- API keys or case data committed to the repository
- Dependencies that are not optional (Poirot must always degrade gracefully)

---

## How to contribute

1. **Fork** the repository and create a branch from `main`.
2. **Make your changes** — keep them focused and atomic.
3. **Test your changes** with a real or mock case directory:
   ```bash
   python scripts/poirot_run.py --case /path/to/test/case --no-router
   ```
4. **Verify scripts compile** before opening a PR:
   ```bash
   python -m py_compile scripts/poirot_run.py
   python -m py_compile scripts/model_router.py
   # etc.
   ```
5. **Open a pull request** with a clear description of what changed and why.

---

## Code style

- Python 3.10+ compatible
- All external imports wrapped in `try/except ImportError` with graceful fallback
- No hard-coded API keys, model names, or file paths
- Type hints where they add clarity; not required throughout
- Comments only where the logic is non-obvious

---

## Reporting issues

Open a GitHub issue with:
- What you ran (command line, provider, modalities)
- What you expected
- What actually happened (output, error message)
- Python version and OS

Do **not** include case data, personal information, or API keys in issue reports.
