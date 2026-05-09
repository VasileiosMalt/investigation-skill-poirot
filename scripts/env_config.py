"""
env_config.py — Centralised environment / API key resolver for Poirot.

Priority order for every key:
  1. Already set in os.environ (e.g. shell export, CI variable)
  2. Loaded from a .env file (searched: cwd → script dir → skill root)
  3. Interactive prompt to the user (only when the key is actually required)

Usage:
    from env_config import get_config

    cfg = get_config()          # loads .env, no prompting yet
    key = cfg.require("OPENAI_API_KEY")   # prompts only if absent
    key = cfg.get("ANTHROPIC_API_KEY")    # returns None if absent, no prompt
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, Dict

# ── .env parser (no external dependency) ──────────────────────────────────────

def _parse_dotenv(path: Path) -> Dict[str, str]:
    """Minimal .env parser — handles KEY=VALUE, quoted values, and comments."""
    pairs: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes
        if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
            value = value[1:-1]
        pairs[key] = value
    return pairs


def _find_dotenv() -> Optional[Path]:
    """Search for .env in: cwd, script dir, two levels up (skill root)."""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).parent / ".env",
        Path(__file__).parent.parent / ".env",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


# ── Config object ──────────────────────────────────────────────────────────────

class PoirotConfig:
    """Holds resolved environment variables and provides get/require helpers."""

    # Known keys with human-readable descriptions (used in prompts)
    _DESCRIPTIONS: Dict[str, str] = {
        "OPENAI_API_KEY":      "OpenAI API key (for GPT-4o / GPT-4o-mini vision and text)",
        "ANTHROPIC_API_KEY":   "Anthropic API key (for Claude Opus/Sonnet/Haiku)",
        "OPENROUTER_API_KEY":  "OpenRouter API key (multi-provider gateway)",
        "GOOGLE_API_KEY":      "Google AI API key (for Gemini models)",
        "GROQ_API_KEY":        "Groq API key (fast inference for open models)",
        "TOGETHER_API_KEY":    "Together AI API key (hosted open models)",
        "MISTRAL_API_KEY":     "Mistral API key",
        # Model selection overrides
        "POIROT_TEXT_MODEL":   "LLM model for text/synthesis (e.g. gpt-4o, claude-sonnet-4-5)",
        "POIROT_VISION_MODEL": "VLLM model for image analysis (e.g. gpt-4o, claude-opus-4-5)",
        "POIROT_AUDIO_MODEL":  "ASR/Whisper model for audio transcription (e.g. whisper-1)",
        "POIROT_PROVIDER":     "Default provider: openai | anthropic | openrouter | google | local",
        "POIROT_LOCAL_URL":    "Base URL for local / vLLM server (e.g. http://localhost:11434/v1)",
        "POIROT_LOCAL_MODEL":  "Model name served by the local endpoint",
        "POIROT_OUTPUT_DIR":   "Directory for analysis outputs (default: <case_dir>/_poirot_output)",
        "POIROT_PROVIDER":     "Provider override: openai|anthropic|openrouter|google|groq|together|mistral|local|agent\n"
                               "                   Use 'agent' to let the calling AI agent handle all LLM calls natively.",
    }

    def __init__(self, env_path: Optional[Path] = None):
        self._store: Dict[str, str] = {}
        self.env_file: Optional[Path] = env_path or _find_dotenv()
        if self.env_file:
            loaded = _parse_dotenv(self.env_file)
            # Only inject keys not already in os.environ
            for k, v in loaded.items():
                if k not in os.environ:
                    os.environ[k] = v
                    self._store[k] = v
                else:
                    self._store[k] = os.environ[k]
            print(f"[Poirot] Loaded .env: {self.env_file}", file=sys.stderr)
        else:
            print("[Poirot] No .env file found — using environment variables / interactive prompts.", file=sys.stderr)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Return value from env or None — never prompts."""
        return os.environ.get(key, default)

    def require(self, key: str, prompt_override: Optional[str] = None) -> str:
        """Return value from env, or interactively prompt the user.

        The value entered interactively is stored back into os.environ for the
        lifetime of the process (not written to disk).
        """
        value = os.environ.get(key)
        if value:
            return value

        description = prompt_override or self._DESCRIPTIONS.get(key, key)
        print(f"\n[Poirot] Required configuration not found: {key}")
        print(f"  {description}")
        print(f"  (Leave blank to skip — some analysis steps may be unavailable)")

        if sys.stdin.isatty():
            try:
                entered = input(f"  Enter {key}: ").strip()
            except (EOFError, KeyboardInterrupt):
                entered = ""
        else:
            # Non-interactive context (piped input / CI)
            print(f"  [WARN] Non-interactive context — {key} left unset.", file=sys.stderr)
            entered = ""

        if entered:
            os.environ[key] = entered
        return entered

    def get_provider(self) -> str:
        """Resolve the active LLM provider with sane defaults.

        Special value "agent": use the calling agent's own LLM — no key or
        provider configuration required.  Poirot will emit prompts/responses
        as plain text for the agent to handle natively.
        """
        explicit = self.get("POIROT_PROVIDER")
        if explicit:
            return explicit.lower()
        # Auto-detect from whichever key is present
        if self.get("OPENAI_API_KEY"):
            return "openai"
        if self.get("ANTHROPIC_API_KEY"):
            return "anthropic"
        if self.get("OPENROUTER_API_KEY"):
            return "openrouter"
        if self.get("GOOGLE_API_KEY"):
            return "google"
        if self.get("POIROT_LOCAL_URL"):
            return "local"
        # Nothing configured → agent passthrough mode
        return "agent"

    def get_text_model(self, fallback: str = "gpt-4o-mini") -> str:
        return self.get("POIROT_TEXT_MODEL") or fallback

    def get_vision_model(self, fallback: str = "gpt-4o") -> str:
        return self.get("POIROT_VISION_MODEL") or fallback

    def get_audio_model(self, fallback: str = "whisper-1") -> str:
        return self.get("POIROT_AUDIO_MODEL") or fallback

    def get_api_key(self, provider: Optional[str] = None) -> Optional[str]:
        """Return the API key for the resolved (or given) provider."""
        p = provider or self.get_provider()
        mapping = {
            "openai":      "OPENAI_API_KEY",
            "anthropic":   "ANTHROPIC_API_KEY",
            "openrouter":  "OPENROUTER_API_KEY",
            "google":      "GOOGLE_API_KEY",
            "groq":        "GROQ_API_KEY",
            "together":    "TOGETHER_API_KEY",
            "mistral":     "MISTRAL_API_KEY",
        }
        env_key = mapping.get(p)
        if env_key:
            return self.get(env_key)
        return None

    def summary(self) -> str:
        """Return a human-readable config summary (keys masked)."""
        lines = []
        provider = self.get_provider()
        lines.append(f"  Provider  : {provider}")
        if provider == "agent":
            lines.append("  Mode      : AGENT PASSTHROUGH — Poirot will use the calling agent's LLM")
            return "\n".join(lines)
        lines.append(f"  Text model: {self.get_text_model()}")
        lines.append(f"  Vision    : {self.get_vision_model()}")
        lines.append(f"  Audio     : {self.get_audio_model()}")
        if provider == "local":
            lines.append(f"  Local URL : {self.get('POIROT_LOCAL_URL', 'http://localhost:11434/v1')}")
            lines.append(f"  Local mdl : {self.get('POIROT_LOCAL_MODEL', 'default')}")
        key = self.get_api_key()
        if key:
            masked = key[:6] + "..." + key[-4:] if len(key) > 10 else "***"
            lines.append(f"  API key   : {masked}")
        else:
            lines.append(f"  API key   : (none — local/default models assumed)")
        if self.env_file:
            lines.append(f"  .env file : {self.env_file}")
        return "\n".join(lines)


# ── Module-level singleton ─────────────────────────────────────────────────────

_config: Optional[PoirotConfig] = None


def get_config(env_path: Optional[Path] = None) -> PoirotConfig:
    """Return the process-wide PoirotConfig singleton."""
    global _config
    if _config is None:
        _config = PoirotConfig(env_path=env_path)
    return _config


def reset_config():
    """Reset the singleton (useful in tests)."""
    global _config
    _config = None
