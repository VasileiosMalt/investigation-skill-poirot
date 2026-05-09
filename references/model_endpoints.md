# Model Endpoints Reference

## Selection Strategy

Choose models based on:
1. **Task type** — vision, audio, text reasoning, or multimodal
2. **Evidence sensitivity** — high-sensitivity cases should prefer local models
3. **Cost vs quality** — higher relevance evidence warrants better models
4. **Rate limits** — batch large evidence sets accordingly

---

## Vision / Image Analysis Models (VQA / VLLM)

### OpenAI (api.openai.com)

| Model | Context | Vision | Best For | Cost (approx) |
|---|---|---|---|---|
| `gpt-4o` | 128k | ✅ Multi-image | Scene analysis, OCR, reasoning | ~$5/1M tokens |
| `gpt-4o-mini` | 128k | ✅ | Fast analysis, lower cost | ~$0.15/1M tokens |
| `gpt-4-turbo` | 128k | ✅ | Detail-heavy forensic analysis | ~$10/1M tokens |
| `o1` | 200k | ❌ | Text reasoning only | ~$15/1M tokens |

**Setup:**
```python
import openai
client = openai.OpenAI(api_key="OPENAI_API_KEY")
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}},
            {"type": "text", "text": "Your question here"}
        ]
    }]
)
```

---

### Anthropic (api.anthropic.com)

| Model | Context | Vision | Best For | Cost (approx) |
|---|---|---|---|---|
| `claude-opus-4-5` | 200k | ✅ Multi-image | Complex reasoning, long docs | ~$15/1M tokens |
| `claude-sonnet-4-5` | 200k | ✅ | Balanced quality/speed | ~$3/1M tokens |
| `claude-haiku-3-5` | 200k | ✅ | Fast, cheap screening | ~$0.25/1M tokens |

**Setup:**
```python
import anthropic
client = anthropic.Anthropic(api_key="ANTHROPIC_API_KEY")
response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=2048,
    messages=[{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_image}},
            {"type": "text", "text": "Your question here"}
        ]
    }]
)
```

---

### Google (generativelanguage.googleapis.com)

| Model | Context | Vision | Best For | Cost (approx) |
|---|---|---|---|---|
| `gemini-2.5-pro` | 1M | ✅ Multi-image + video | Long video analysis, large batches | ~$3.50/1M tokens |
| `gemini-2.5-flash` | 1M | ✅ | Speed + cost balance | ~$0.15/1M tokens |
| `gemini-2.0-flash` | 1M | ✅ + Audio | Native audio + vision | ~$0.10/1M tokens |

**Special capability:** Gemini 2.5 Pro can process **entire video files natively** (up to 1 hour) — no keyframe extraction needed for shorter videos.

**Setup:**
```python
import google.generativeai as genai
genai.configure(api_key="GOOGLE_API_KEY")
model = genai.GenerativeModel("gemini-2.5-pro")
response = model.generate_content([image_part, "Your question here"])
```

---

### OpenRouter (openrouter.ai)

OpenRouter provides unified access to many models via a single API. Useful for model routing and fallback.

**Base URL:** `https://openrouter.ai/api/v1`
**Auth:** Bearer token in `Authorization` header

**Top vision models via OpenRouter:**

| Model ID | Provider | Vision | Notes |
|---|---|---|---|
| `openai/gpt-4o` | OpenAI | ✅ | Same as direct |
| `anthropic/claude-opus-4-5` | Anthropic | ✅ | Same as direct |
| `google/gemini-2.5-pro` | Google | ✅ + video | Native video |
| `meta-llama/llama-4-maverick` | Meta | ✅ | Open-weight, strong vision |
| `mistralai/pixtral-large-2411` | Mistral | ✅ | 128k context, strong OCR |
| `qwen/qwen2.5-vl-72b-instruct` | Alibaba | ✅ | Excellent detail analysis |
| `x-ai/grok-2-vision-1212` | xAI | ✅ | Strong for complex scenes |

**Setup (OpenAI-compatible):**
```python
import openai
client = openai.OpenAI(
    api_key="OPENROUTER_API_KEY",
    base_url="https://openrouter.ai/api/v1"
)
# Use any model ID from the table above
```

---

## Audio / Speech Models

### OpenAI Whisper (Local)

Best for sensitive audio. Runs fully offline.

```python
import whisper
model = whisper.load_model("large-v3")  # Options: tiny, base, small, medium, large-v3
result = model.transcribe("audio.wav", word_timestamps=True, language="en")
```

**Models:**
| Model | VRAM | Speed | Accuracy |
|---|---|---|---|
| `tiny` | 1GB | Very fast | Low |
| `base` | 1GB | Fast | Moderate |
| `medium` | 5GB | Moderate | Good |
| `large-v3` | 10GB | Slow | Best |

### OpenAI Whisper API

```python
with open("audio.wav", "rb") as f:
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=f,
        response_format="verbose_json",
        timestamp_granularities=["word"]
    )
```

### AssemblyAI (assemblyai.com)

Excellent for diarisation + emotion analysis:
```python
import assemblyai as aai
aai.settings.api_key = "ASSEMBLYAI_API_KEY"
config = aai.TranscriptionConfig(
    speaker_labels=True,
    sentiment_analysis=True,
    entity_detection=True,
    auto_highlights=True
)
transcriber = aai.Transcriber()
transcript = transcriber.transcribe("audio.wav", config=config)
```

### Deepgram (api.deepgram.com)

Fast, accurate, good diarisation:
```python
from deepgram import DeepgramClient
dg = DeepgramClient("DEEPGRAM_API_KEY")
response = dg.listen.rest.v("1").transcribe_file(
    {"url": audio_url},
    {"model": "nova-2", "diarize": True, "smart_format": True}
)
```

---

## Text / Reasoning LLMs (for CKB building, inference generation)

### Recommended for Investigation Synthesis

| Model | Provider / Route | Best For |
|---|---|---|
| `claude-opus-4-5` | Anthropic / OpenRouter | Deep reasoning, long-form synthesis |
| `gpt-4o` | OpenAI / OpenRouter | Balanced analysis |
| `gemini-2.5-pro` | Google / OpenRouter | Extremely long context (full case files) |
| `deepseek/deepseek-r1` | OpenRouter | Logical inference, pattern detection |
| `google/gemini-2.5-flash-thinking` | OpenRouter | Fast reasoning, good for classification |

---

## Local Models (Offline / Privacy-sensitive Cases)

For cases where evidence must not leave the local machine:

### Vision (Local)
| Model | Tool | VRAM | Notes |
|---|---|---|---|
| `LLaVA-1.6-34B` | `ollama run llava:34b` | 24GB | Strong general VQA |
| `InternVL2-26B` | HuggingFace + vLLM | 20GB | Excellent OCR + detail |
| `Qwen2.5-VL-7B` | HuggingFace + vLLM | 8GB | Good balance |
| `MiniCPM-V 2.6` | HuggingFace | 8GB | Efficient, good quality |
| `moondream2` | HuggingFace | 4GB | Lightweight, fast |

### Audio (Local)
| Model | Notes |
|---|---|
| `whisper large-v3` | Best offline transcription |
| `whisper-large-v3-turbo` | Faster, slightly less accurate |
| `pyannote/speaker-diarization-3.1` | Local diarisation (requires HF token) |

### Text (Local)
| Model | Tool | VRAM |
|---|---|---|
| `llama3.3-70b` | `ollama run llama3.3:70b` | 48GB |
| `qwen2.5-72b` | `ollama run qwen2.5:72b` | 48GB |
| `mistral-small-3.1` | `ollama run mistral-small3.1` | 16GB |

---

## Model Selection Decision Tree

```
Is the evidence highly sensitive (legal, personal)?
  YES → Use local models
  NO ↓

Is video analysis needed (full video, not just frames)?
  YES → Use Gemini 2.5 Pro (native video)
  NO ↓

Is cost the primary constraint?
  YES → Use GPT-4o-mini or Claude Haiku for screening; escalate only high-relevance items
  NO ↓

Is maximum reasoning quality needed (synthesis, inference)?
  YES → Use Claude Opus or GPT-4o
  NO → Use Claude Sonnet or GPT-4o-mini
```

---

## Rate Limits & Batch Strategy

| Provider | Images/min | Tokens/min | Batch Strategy |
|---|---|---|---|
| OpenAI | 500 | 800k | Parallel workers x5 |
| Anthropic | 300 | 400k | Parallel workers x3 |
| Google | 1000 | 4M | Parallel workers x10 |
| OpenRouter | Varies | Varies | Check per-model limits |

**Always implement exponential backoff on 429 errors.**

```python
import time, random
def call_with_retry(fn, max_retries=5):
    for attempt in range(max_retries):
        try:
            return fn()
        except RateLimitError:
            wait = (2 ** attempt) + random.random()
            time.sleep(wait)
    raise Exception("Max retries exceeded")
```
