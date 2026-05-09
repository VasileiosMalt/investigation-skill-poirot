"""
model_router.py — Live model discovery + optimal task routing for Poirot.

Given a provider and (optionally) an API key, this module:
  1. Fetches the list of available models from the provider's API.
  2. Classifies each model's capabilities (vision, audio, reasoning, context).
  3. Builds an optimal routing plan that assigns the best available model
     to each investigation task:
       - ckb_generation   (Phase 1 — text, long-context preferred)
       - classification   (Phase 2 — text, cheap/fast OK)
       - image_analysis   (Phase 3 — vision required)
       - audio_analysis   (Phase 4 — audio/ASR required)
       - video_analysis   (Phase 4 — vision + long-context preferred)
       - synthesis        (Phase 5 — text, strongest reasoner preferred)

When no provider/key is available ("agent" mode) the routing plan is empty
and each phase falls back to whatever the calling agent natively uses.

Usage:
    from model_router import build_routing_plan, RoutingPlan
    plan = build_routing_plan(provider="openai", api_key="sk-...", case_modalities={"image","audio"})
    print(plan.summary())
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# ── Task names ────────────────────────────────────────────────────────────────

TASKS = [
    "ckb_generation",
    "classification",
    "image_analysis",
    "audio_transcription",
    "video_analysis",
    "doe_parsing",        # Extract Directly Observed Elements from images
    "dte_parsing",        # Extract Directly Transcribed Elements from AV
    "deep_drill",         # Detailed follow-up VQA when anomaly detected
    "synthesis",          # Final cross-modal deductive report
]

# ── Model capability registry ─────────────────────────────────────────────────
# Static knowledge about well-known models.  The live model list supplements
# (and can override) these entries.

_KNOWN_CAPS: dict[str, dict] = {
    # ── OpenAI ────────────────────────────────────────────────────────────────
    "gpt-4o":              {"vision": True,  "audio": False, "context": 128_000, "tier": "premium",  "reasoning": True},
    "gpt-4o-mini":         {"vision": True,  "audio": False, "context": 128_000, "tier": "standard", "reasoning": False},
    "gpt-4-turbo":         {"vision": True,  "audio": False, "context": 128_000, "tier": "premium",  "reasoning": True},
    "gpt-4.1":             {"vision": True,  "audio": False, "context": 128_000, "tier": "premium",  "reasoning": True},
    "gpt-4.1-mini":        {"vision": True,  "audio": False, "context": 128_000, "tier": "standard", "reasoning": False},
    "o1":                  {"vision": False, "audio": False, "context": 200_000, "tier": "reasoning","reasoning": True},
    "o1-mini":             {"vision": False, "audio": False, "context": 128_000, "tier": "reasoning","reasoning": True},
    "o3-mini":             {"vision": False, "audio": False, "context": 200_000, "tier": "reasoning","reasoning": True},
    "o3":                  {"vision": True,  "audio": False, "context": 200_000, "tier": "reasoning","reasoning": True},
    "whisper-1":           {"vision": False, "audio": True,  "context": 0,       "tier": "standard", "reasoning": False},
    # ── Anthropic ─────────────────────────────────────────────────────────────
    "claude-opus-4-5":     {"vision": True,  "audio": False, "context": 200_000, "tier": "premium",  "reasoning": True},
    "claude-sonnet-4-5":   {"vision": True,  "audio": False, "context": 200_000, "tier": "standard", "reasoning": True},
    "claude-haiku-3-5":    {"vision": True,  "audio": False, "context": 200_000, "tier": "fast",     "reasoning": False},
    "claude-opus-4":       {"vision": True,  "audio": False, "context": 200_000, "tier": "premium",  "reasoning": True},
    "claude-sonnet-4":     {"vision": True,  "audio": False, "context": 200_000, "tier": "standard", "reasoning": True},
    # ── Google ────────────────────────────────────────────────────────────────
    "gemini-2.5-pro":      {"vision": True,  "audio": True,  "context": 1_000_000,"tier": "premium", "reasoning": True},
    "gemini-2.5-flash":    {"vision": True,  "audio": True,  "context": 1_000_000,"tier": "standard","reasoning": False},
    "gemini-2.0-flash":    {"vision": True,  "audio": True,  "context": 1_000_000,"tier": "fast",    "reasoning": False},
    # ── Groq ──────────────────────────────────────────────────────────────────
    "llama-3.3-70b-versatile": {"vision": False,"audio": False,"context": 128_000,"tier": "standard","reasoning": False},
    "llama-3.1-8b-instant":    {"vision": False,"audio": False,"context": 128_000,"tier": "fast",    "reasoning": False},
    "llava-v1.5-7b-4096-preview":{"vision": True,"audio":False,"context": 4_096,  "tier": "fast",   "reasoning": False},
    # ── Mistral ───────────────────────────────────────────────────────────────
    "mistral-large-latest":    {"vision": False,"audio": False,"context": 128_000,"tier": "premium", "reasoning": True},
    "mistral-small-latest":    {"vision": False,"audio": False,"context": 128_000,"tier": "standard","reasoning": False},
    "pixtral-large-latest":    {"vision": True, "audio": False,"context": 128_000,"tier": "premium", "reasoning": True},
    "pixtral-12b":             {"vision": True, "audio": False,"context": 128_000,"tier": "standard","reasoning": False},
}

# ── Routing plan dataclass ────────────────────────────────────────────────────

@dataclass
class RoutingPlan:
    provider: str
    api_key_available: bool
    models_fetched: list[str] = field(default_factory=list)
    assignments: dict[str, str] = field(default_factory=dict)  # task -> model_id
    rationale: dict[str, str] = field(default_factory=dict)    # task -> reason
    fallback_mode: bool = False   # True when no provider available

    def get(self, task: str, fallback: str = "") -> str:
        """Return the assigned model for a task, or fallback."""
        return self.assignments.get(task, fallback)

    def summary(self) -> str:
        lines = [f"  Provider : {self.provider}"]
        lines.append(f"  Key set  : {'yes' if self.api_key_available else 'no (agent/local mode)'}")
        lines.append(f"  Models   : {len(self.models_fetched)} fetched from API")
        if self.fallback_mode:
            lines.append("  Mode     : AGENT PASSTHROUGH — no routing applied")
            return "\n".join(lines)
        lines.append("  Routing assignments:")
        for task, model in self.assignments.items():
            r = self.rationale.get(task, "")
            lines.append(f"    {task:<22} → {model}  ({r})")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> "RoutingPlan":
        d = json.loads(text)
        obj = cls.__new__(cls)
        obj.__dict__.update(d)
        return obj

    @classmethod
    def agent_passthrough(cls) -> "RoutingPlan":
        return cls(
            provider="agent",
            api_key_available=False,
            fallback_mode=True,
        )


# ── Provider model fetchers ───────────────────────────────────────────────────

def _http_get_json(url: str, headers: dict) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  [router] HTTP error fetching {url}: {e}", file=sys.stderr)
        return None


def fetch_openai_models(api_key: str, base_url: str = "https://api.openai.com") -> list[str]:
    data = _http_get_json(
        f"{base_url}/v1/models",
        {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    if not data:
        return []
    return [m["id"] for m in data.get("data", [])]


def fetch_anthropic_models(api_key: str) -> list[str]:
    data = _http_get_json(
        "https://api.anthropic.com/v1/models",
        {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
    )
    if not data:
        return []
    return [m["id"] for m in data.get("data", [])]


def fetch_google_models(api_key: str) -> list[str]:
    data = _http_get_json(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
        {},
    )
    if not data:
        return []
    return [m["name"].replace("models/", "") for m in data.get("models", [])]


def fetch_openrouter_models(api_key: str) -> list[str]:
    data = _http_get_json(
        "https://openrouter.ai/api/v1/models",
        {"Authorization": f"Bearer {api_key}"},
    )
    if not data:
        return []
    return [m["id"] for m in data.get("data", [])]


def fetch_groq_models(api_key: str) -> list[str]:
    data = _http_get_json(
        "https://api.groq.com/openai/v1/models",
        {"Authorization": f"Bearer {api_key}"},
    )
    if not data:
        return []
    return [m["id"] for m in data.get("data", [])]


def fetch_together_models(api_key: str) -> list[str]:
    data = _http_get_json(
        "https://api.together.xyz/v1/models",
        {"Authorization": f"Bearer {api_key}"},
    )
    if not data:
        return []
    return [m["id"] for m in data.get("data", [])]


def fetch_mistral_models(api_key: str) -> list[str]:
    data = _http_get_json(
        "https://api.mistral.ai/v1/models",
        {"Authorization": f"Bearer {api_key}"},
    )
    if not data:
        return []
    return [m["id"] for m in data.get("data", [])]


def fetch_local_models(base_url: str) -> list[str]:
    """Fetch models from an OpenAI-compatible local server (Ollama, vLLM, LM Studio)."""
    data = _http_get_json(f"{base_url.rstrip('/')}/models", {})
    if not data:
        return []
    return [m["id"] for m in data.get("data", [])]


FETCHERS = {
    "openai":     lambda key, _cfg: fetch_openai_models(key),
    "anthropic":  lambda key, _cfg: fetch_anthropic_models(key),
    "google":     lambda key, _cfg: fetch_google_models(key),
    "openrouter": lambda key, _cfg: fetch_openrouter_models(key),
    "groq":       lambda key, _cfg: fetch_groq_models(key),
    "together":   lambda key, _cfg: fetch_together_models(key),
    "mistral":    lambda key, _cfg: fetch_mistral_models(key),
    "local":      lambda _key, cfg: fetch_local_models(
                      cfg.get("POIROT_LOCAL_URL", "http://localhost:11434/v1")
                      if cfg else "http://localhost:11434/v1"),
}


def fetch_models(provider: str, api_key: Optional[str], cfg=None) -> list[str]:
    """Dispatch to the correct fetcher and return model IDs."""
    fetcher = FETCHERS.get(provider)
    if not fetcher:
        return []
    print(f"  [router] Fetching available models from {provider}...", file=sys.stderr)
    models = fetcher(api_key or "", cfg)
    print(f"  [router] {len(models)} models available.", file=sys.stderr)
    return models


# ── Capability inference ──────────────────────────────────────────────────────

def _infer_caps(model_id: str) -> dict:
    """Infer capabilities for an unknown model from its name."""
    mid = model_id.lower()
    vision  = any(x in mid for x in ["vision","vl","llava","pixtral","4o","gpt-4","claude","gemini","phi-3","qwen-vl","moondream","bakllava"])
    audio   = any(x in mid for x in ["whisper","audio","speech","tts","gemini"])
    context = 128_000 if "128k" in mid else (200_000 if "200k" in mid else (1_000_000 if "1m" in mid else 32_000))
    tier = (
        "premium"  if any(x in mid for x in ["opus","ultra","large","70b","72b","405b","pro","gpt-4","o1","o3"]) else
        "standard" if any(x in mid for x in ["sonnet","medium","7b","8b","13b","flash","mini"]) else
        "fast"
    )
    reasoning = any(x in mid for x in ["o1","o3","opus","sonnet","large","gemini-2.5","claude-3.5","claude-3-7"])
    return {"vision": vision, "audio": audio, "context": context, "tier": tier, "reasoning": reasoning}


def get_caps(model_id: str) -> dict:
    """Return capability dict, from registry or inferred."""
    return _KNOWN_CAPS.get(model_id) or _infer_caps(model_id)


# ── Routing logic ─────────────────────────────────────────────────────────────

TIER_ORDER = {"premium": 0, "reasoning": 0, "standard": 1, "fast": 2}


def _rank(models: list[str], require_vision=False, require_audio=False,
          prefer_context=0, prefer_reasoning=False) -> list[str]:
    """Score and sort a list of model IDs by capability fit."""
    def score(m: str) -> tuple:
        c = get_caps(m)
        if require_vision and not c["vision"]:
            return (99, 99, 0)
        if require_audio and not c["audio"]:
            return (99, 99, 0)
        tier_score = TIER_ORDER.get(c["tier"], 3)
        # Prefer reasoning models for reasoning tasks
        reason_bonus = 0 if (prefer_reasoning and c["reasoning"]) else 1
        ctx_score = 0 if c["context"] >= prefer_context else 1
        return (tier_score, reason_bonus, -c["context"])
    return sorted(models, key=score)


def _pick(ranked: list[str]) -> Optional[str]:
    return ranked[0] if ranked else None


def build_routing_plan(
    provider: str,
    api_key: Optional[str],
    case_modalities: set[str],
    cfg=None,
) -> RoutingPlan:
    """
    Fetch live models and assign the optimal model to each investigation task.

    case_modalities: set of present modalities, e.g. {"text","image","audio","video"}
    """
    if provider == "agent":
        return RoutingPlan.agent_passthrough()

    models = fetch_models(provider, api_key, cfg)

    if not models:
        print("  [router] Could not fetch model list — using static registry.", file=sys.stderr)
        # Fall back to known models for this provider
        prefix_map = {
            "openai":     ("gpt-", "o1", "o3", "whisper"),
            "anthropic":  ("claude-",),
            "google":     ("gemini-",),
            "openrouter": (),           # no useful prefix filter
            "groq":       ("llama-","mixtral-","gemma-","llava"),
            "together":   (),
            "mistral":    ("mistral-","pixtral-","codestral"),
            "local":      (),
        }
        prefixes = prefix_map.get(provider, ())
        if prefixes:
            models = [m for m in _KNOWN_CAPS if any(m.startswith(p) for p in prefixes)]
        else:
            models = list(_KNOWN_CAPS.keys())

    has_images = "image" in case_modalities
    has_audio  = "audio" in case_modalities
    has_video  = "video" in case_modalities

    assignments: dict[str, str] = {}
    rationale:   dict[str, str] = {}

    def assign(task: str, ranked: list[str], reason: str):
        m = _pick(ranked)
        if m:
            assignments[task] = m
            rationale[task] = reason

    # ── Phase 1: CKB generation — text, long-context, reasoning ───────────────
    assign("ckb_generation",
           _rank(models, prefer_context=32_000, prefer_reasoning=True),
           "long-context + strong reasoning")

    # ── Phase 2: Classification — cheap/fast text ─────────────────────────────
    fast_text = _rank(models, prefer_reasoning=False)
    assign("classification",
           fast_text,
           "fast text classification, reasoning not required")

    # ── Phase 3: Image analysis — vision required ──────────────────────────────
    if has_images:
        assign("image_analysis",
               _rank(models, require_vision=True, prefer_reasoning=True),
               "vision + reasoning for VQA/DOE extraction")
        assign("doe_parsing",
               _rank(models, require_vision=True),
               "vision for directly-observed element extraction")
        assign("deep_drill",
               _rank(models, require_vision=True, prefer_reasoning=True),
               "premium vision model for anomaly deep-dives")

    # ── Phase 4: Audio — audio or best text fallback ──────────────────────────
    if has_audio:
        audio_models = _rank(models, require_audio=True)
        if audio_models:
            assign("audio_transcription", audio_models, "native audio/ASR support")
        else:
            # No native audio model — will fall back to local Whisper
            assignments["audio_transcription"] = "local_whisper"
            rationale["audio_transcription"] = "no cloud ASR model available — using local Whisper"

    # ── Phase 4: Video — vision + large context ───────────────────────────────
    if has_video:
        assign("video_analysis",
               _rank(models, require_vision=True, prefer_context=500_000, prefer_reasoning=True),
               "vision + large-context for video keyframe sequences")

    # ── Phase 4/5: DTE parsing ────────────────────────────────────────────────
    assign("dte_parsing",
           _rank(models, prefer_reasoning=False),
           "fast text parsing of transcripts")

    # ── Phase 5: Synthesis — strongest reasoning, long context ────────────────
    assign("synthesis",
           _rank(models, prefer_context=64_000, prefer_reasoning=True),
           "strongest reasoner for cross-modal deductive synthesis")

    return RoutingPlan(
        provider=provider,
        api_key_available=bool(api_key),
        models_fetched=models,
        assignments=assignments,
        rationale=rationale,
        fallback_mode=False,
    )


# ── Convenience: build from env_config ────────────────────────────────────────

def routing_plan_from_config(cfg, case_modalities: set[str]) -> RoutingPlan:
    """Build a RoutingPlan using the active PoirotConfig."""
    provider = cfg.get_provider()
    api_key  = cfg.get_api_key(provider)
    return build_routing_plan(
        provider=provider,
        api_key=api_key,
        case_modalities=case_modalities,
        cfg=cfg,
    )


# ── CLI (for debugging) ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Fetch models and print routing plan")
    p.add_argument("--provider", default=None)
    p.add_argument("--api-key", default=None)
    p.add_argument("--modalities", default="text,image,audio,video")
    args = p.parse_args()

    sys.path.insert(0, str(Path(__file__).parent))
    from env_config import get_config
    cfg = get_config()
    provider = args.provider or cfg.get_provider()
    key = args.api_key or cfg.get_api_key(provider)
    modalities = set(args.modalities.split(","))

    plan = build_routing_plan(provider, key, modalities, cfg)
    print("\n" + "="*60)
    print("Poirot Routing Plan")
    print("="*60)
    print(plan.summary())
    print("\nJSON:\n" + plan.to_json())
