# Supported Evidence Formats

## Text & Documents

| Format | Extension(s) | Native Support | Pre-processing Needed |
|---|---|---|---|
| Plain text | `.txt`, `.log`, `.csv`, `.tsv` | ✅ Direct read | None |
| Markdown | `.md`, `.markdown` | ✅ Direct read | None |
| JSON / YAML / XML | `.json`, `.yaml`, `.yml`, `.xml` | ✅ Parse + summarise | None |
| HTML | `.html`, `.htm` | ✅ Strip tags, extract text | Strip markup |
| PDF (text layer) | `.pdf` | ✅ Extract text via `pdfplumber` / `pymupdf` | Check if text layer exists |
| PDF (scanned/image) | `.pdf` | ⚠️ Treat as images | Render pages as PNG → Phase 3 |
| Word document | `.docx`, `.doc` | ✅ via `python-docx` | `.doc` requires `antiword` or LibreOffice |
| OpenDocument | `.odt`, `.ods` | ✅ via `odfpy` | None |
| Email | `.eml`, `.msg` | ✅ via `email` stdlib / `extract-msg` | `.msg` requires `extract-msg` |
| Rich text | `.rtf` | ⚠️ Strip RTF markup | Use `striprtf` |
| Spreadsheet | `.xlsx`, `.xls`, `.ods` | ✅ via `openpyxl` / `xlrd` | Convert sheets to DataFrames |

---

## Images

| Format | Extension(s) | Native Support | Pre-processing Needed |
|---|---|---|---|
| JPEG | `.jpg`, `.jpeg` | ✅ Direct | None |
| PNG | `.png` | ✅ Direct | None |
| WebP | `.webp` | ✅ Direct | None |
| GIF | `.gif` | ⚠️ Animated | Extract representative frames |
| TIFF | `.tiff`, `.tif` | ⚠️ Convert | `Pillow` → PNG |
| BMP | `.bmp` | ⚠️ Convert | `Pillow` → PNG |
| HEIC / HEIF | `.heic`, `.heif` | ⚠️ Convert | `pillow-heif` or `heif-convert` → JPEG |
| RAW (Canon) | `.cr2`, `.cr3` | ⚠️ Convert | `rawpy` + `imageio` → JPEG |
| RAW (Nikon) | `.nef`, `.nrw` | ⚠️ Convert | `rawpy` + `imageio` → JPEG |
| RAW (Sony) | `.arw` | ⚠️ Convert | `rawpy` + `imageio` → JPEG |
| RAW (Adobe) | `.dng` | ⚠️ Convert | `rawpy` + `imageio` → JPEG |
| SVG | `.svg` | ⚠️ Convert | `cairosvg` → PNG |
| AVIF | `.avif` | ⚠️ Convert | `Pillow` (>=9.1) → PNG |

**Model input limits:**
- OpenAI GPT-4o: max 20MB per image, up to 10 images per call
- Anthropic Claude: max 5MB per image (base64), up to 20 per call
- Google Gemini: max 7MB per image, up to 16 per call
- Local (LLaVA / InternVL): depends on VRAM; typically 1024–2048px recommended

**Resize policy:** If image exceeds model limit, resize to longest side = 2048px, preserve aspect ratio, use Lanczos resampling. Always keep original file untouched.

---

## Audio

| Format | Extension(s) | Native Support | Pre-processing Needed |
|---|---|---|---|
| WAV | `.wav` | ✅ Direct (Whisper) | None |
| MP3 | `.mp3` | ✅ Direct (Whisper) | None |
| FLAC | `.flac` | ✅ Direct (Whisper) | None |
| AAC | `.aac`, `.m4a` | ✅ Direct (Whisper) | None |
| OGG Vorbis | `.ogg` | ✅ Direct (Whisper) | None |
| Opus | `.opus` | ✅ Direct (Whisper) | None |
| WMA | `.wma` | ⚠️ Convert | `ffmpeg` → WAV |
| AIFF | `.aiff`, `.aif` | ⚠️ Convert | `ffmpeg` → WAV |
| AMR | `.amr` | ⚠️ Convert | `ffmpeg` → WAV |

**Sample rate:** Whisper prefers 16kHz mono. Convert via:
```bash
ffmpeg -i input.mp3 -ar 16000 -ac 1 output.wav
```

**Max duration:** Whisper API has a 25MB limit per file. For longer files, chunk into overlapping segments:
- Chunk size: 10 minutes
- Overlap: 30 seconds (to preserve context across chunks)
- Merge transcripts by deduplicating overlap

---

## Video

| Format | Extension(s) | Native Support | Pre-processing Needed |
|---|---|---|---|
| MP4 (H.264) | `.mp4` | ✅ Direct (`ffmpeg`) | None |
| MP4 (H.265/HEVC) | `.mp4` | ✅ Direct (`ffmpeg`) | None |
| MOV | `.mov` | ✅ Direct (`ffmpeg`) | None |
| MKV | `.mkv` | ✅ Direct (`ffmpeg`) | None |
| AVI | `.avi` | ✅ Direct (`ffmpeg`) | None |
| WMV | `.wmv` | ⚠️ May need codec | `ffmpeg` with wmv decoder |
| FLV | `.flv` | ✅ Direct (`ffmpeg`) | None |
| WebM | `.webm` | ✅ Direct (`ffmpeg`) | None |
| MPEG | `.mpeg`, `.mpg` | ✅ Direct (`ffmpeg`) | None |
| TS (Transport Stream) | `.ts`, `.m2ts` | ✅ Direct (`ffmpeg`) | None |

**Keyframe extraction command:**
```bash
# Scene change based
ffmpeg -i input.mp4 -vf "select='gt(scene,0.3)'" -vsync vfr frame_%04d.jpg

# Time-based (every 30 seconds)
ffmpeg -i input.mp4 -vf fps=1/30 frame_%04d.jpg

# Specific timestamp
ffmpeg -i input.mp4 -ss 00:01:23 -frames:v 1 frame_00123.jpg
```

---

## Archives & Containers

| Format | Extension(s) | Action |
|---|---|---|
| ZIP | `.zip` | Extract and process contents |
| RAR | `.rar` | Extract via `patoolib` or `unrar` |
| 7-Zip | `.7z` | Extract via `py7zr` |
| TAR | `.tar`, `.tar.gz`, `.tgz` | Extract via `tarfile` stdlib |
| Encrypted archive | Any | Log as inaccessible; note in report |

---

## Unsupported / Unknown Formats

- Log file path, extension, and size
- Attempt MIME type detection via `python-magic`
- If binary: note as "binary file — possible database, executable, or proprietary format"
- Flag for manual review in the report
- Do NOT skip silently — unsupported files may be significant
