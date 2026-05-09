#!/usr/bin/env python3
import argparse, json, subprocess, sys, os
from pathlib import Path
from datetime import datetime

SCRIPTS_DIR = Path(__file__).parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

def _python(): return sys.executable

def _run(args, step):
    print("\n" + "="*70)
    print("[Poirot]    " + step)
    print("="*70)
    result = subprocess.run(args, env=os.environ.copy())
    if result.returncode != 0:
        print("[Poirot] FAIL  " + step, file=sys.stderr)
    else:
        print("[Poirot] OK    " + step)
    return result.returncode

def _detect_case_modalities(case_dir):
    IMAGE_EXT = {".jpg",".jpeg",".png",".gif",".bmp",".tiff",".tif",".webp",".heic",".heif"}
    AUDIO_EXT = {".mp3",".wav",".m4a",".aac",".flac",".ogg",".wma",".opus"}
    VIDEO_EXT = {".mp4",".mov",".avi",".mkv",".wmv",".flv",".webm",".m4v",".mpeg",".mpg"}
    TEXT_EXT  = {".txt",".md",".pdf",".docx",".doc",".rtf",".odt",".msg",".eml",".xlsx",".csv"}
    modalities = set()
    for f in case_dir.rglob("*"):
        if not f.is_file(): continue
        ext = f.suffix.lower()
        if ext in IMAGE_EXT: modalities.add("image")
        elif ext in AUDIO_EXT: modalities.add("audio")
        elif ext in VIDEO_EXT: modalities.add("video")
        elif ext in TEXT_EXT: modalities.add("text")
    return modalities

def bootstrap(env_file, case_dir, no_router):
    from env_config import get_config
    cfg = get_config(env_path=env_file)
    print("\n[Poirot] Configuration:")
    print(cfg.summary())
    provider = cfg.get_provider()
    if provider == "agent":
        print("\n[Poirot] AGENT MODE - no API key configured.")
        print("  Poirot will emit prompts for the calling agent to execute.")
        print("  Set POIROT_PROVIDER in .env to use a cloud or local provider.\n")
        from model_router import RoutingPlan
        return cfg, RoutingPlan.agent_passthrough()
    key_map = {"openai":"OPENAI_API_KEY","anthropic":"ANTHROPIC_API_KEY",
               "openrouter":"OPENROUTER_API_KEY","google":"GOOGLE_API_KEY",
               "groq":"GROQ_API_KEY","together":"TOGETHER_API_KEY","mistral":"MISTRAL_API_KEY"}
    env_key = key_map.get(provider)
    if env_key and not cfg.get(env_key):
        cfg.require(env_key)
    if no_router:
        from model_router import RoutingPlan
        tasks = ["ckb_generation","classification","image_analysis","doe_parsing",
                 "deep_drill","audio_transcription","video_analysis","dte_parsing","synthesis"]
        assignments = {
            "ckb_generation":cfg.get_text_model(),"classification":cfg.get_text_model(),
            "image_analysis":cfg.get_vision_model(),"doe_parsing":cfg.get_vision_model(),
            "deep_drill":cfg.get_vision_model(),"audio_transcription":cfg.get_audio_model(),
            "video_analysis":cfg.get_vision_model(),"dte_parsing":cfg.get_text_model(),
            "synthesis":cfg.get_text_model()}
        plan = RoutingPlan(provider=provider,api_key_available=bool(cfg.get_api_key(provider)),
            fallback_mode=False,assignments=assignments,
            rationale={t:"static from .env / defaults" for t in tasks})
        return cfg, plan
    from model_router import routing_plan_from_config
    modalities = _detect_case_modalities(case_dir)
    print("\n[Poirot] Detected modalities: " + (", ".join(sorted(modalities)) or "none"))
    print("[Poirot] Building optimal model routing plan...")
    plan = routing_plan_from_config(cfg, modalities)
    print("\n[Poirot] Routing Plan:")
    print(plan.summary())
    return cfg, plan

ROUTING_ENV_KEY = "POIROT_ROUTING_PLAN"

def _inject_plan(plan):
    os.environ[ROUTING_ENV_KEY] = plan.to_json()

def phase1_ingest(case_dir, output_dir):
    return _run([_python(), str(SCRIPTS_DIR/"ingest_case.py"),
                 "--case-dir", str(case_dir), "--output-dir", str(output_dir)],
                "Phase 1 - Case Ingestion and Text Extraction")

def phase2_classify(output_dir, cfg, plan):
    manifest = output_dir/"case_manifest.json"
    ckb = output_dir/"case_knowledge_base.md"
    out_ev = output_dir/"evidence_manifest.json"
    cmd = [_python(), str(SCRIPTS_DIR/"classify_evidence.py"),
           "--manifest", str(manifest),
           "--ckb", str(ckb) if ckb.exists() else str(manifest),
           "--output", str(out_ev)]
    model = plan.get("classification")
    key = cfg.get_api_key(plan.provider)
    if plan.fallback_mode or plan.provider == "agent":
        cmd += ["--no-llm"]
    else:
        if key: cmd += ["--api-key", key]
        if model: cmd += ["--model", model]
    return _run(cmd, "Phase 2 - Evidence Classification")

def phase3_images(output_dir, cfg, plan):
    evidence = output_dir/"evidence_manifest.json"
    ckb = output_dir/"case_knowledge_base.md"
    if not evidence.exists():
        print("[Poirot] SKIP Phase 3 - evidence_manifest.json not found.", file=sys.stderr)
        return 0
    model = plan.get("image_analysis") or cfg.get_vision_model()
    key = cfg.get_api_key(plan.provider)
    prov_arg = plan.provider if not plan.fallback_mode else "openai"
    cmd = [_python(), str(SCRIPTS_DIR/"run_image_analysis.py"),
           "--evidence", str(evidence),
           "--ckb", str(ckb) if ckb.exists() else str(evidence),
           "--output-dir", str(output_dir),
           "--model", model, "--provider", prov_arg]
    if key: cmd += ["--api-key", key]
    text_model = plan.get("doe_parsing") or plan.get("classification") or cfg.get_text_model()
    if text_model and text_model != model: cmd += ["--text-model", text_model]
    return _run(cmd, "Phase 3 - Image / VQA Analysis")

def phase4_av(output_dir, cfg, plan):
    evidence = output_dir/"evidence_manifest.json"
    ckb = output_dir/"case_knowledge_base.md"
    if not evidence.exists():
        print("[Poirot] SKIP Phase 4 - evidence_manifest.json not found.", file=sys.stderr)
        return 0
    llm_model = plan.get("dte_parsing") or cfg.get_text_model()
    whisper_model = plan.get("audio_transcription") or cfg.get_audio_model()
    key = cfg.get_api_key(plan.provider)
    cmd = [_python(), str(SCRIPTS_DIR/"run_audio_video_analysis.py"),
           "--evidence", str(evidence),
           "--ckb", str(ckb) if ckb.exists() else str(evidence),
           "--output-dir", str(output_dir),
           "--llm-model", llm_model, "--whisper-model", whisper_model]
    if key: cmd += ["--api-key", key]
    return _run(cmd, "Phase 4 - Audio / Video Analysis")

def phase5_synthesis(output_dir, cfg, plan):
    ckb = output_dir/"case_knowledge_base.md"
    img_report = output_dir/"image_analysis_report.json"
    av_report = output_dir/"av_analysis_report.json"
    model = plan.get("synthesis") or cfg.get_text_model()
    key = cfg.get_api_key(plan.provider)
    prov_arg = plan.provider if not plan.fallback_mode else "openai"
    cmd = [_python(), str(SCRIPTS_DIR/"synthesize_report.py"),
           "--ckb", str(ckb) if ckb.exists() else "",
           "--image-report", str(img_report),
           "--av-report", str(av_report),
           "--output-dir", str(output_dir),
           "--model", model, "--provider", prov_arg]
    if key: cmd += ["--api-key", key]
    return _run(cmd, "Phase 5 - Cross-Modal Synthesis and Report")

def main():
    parser = argparse.ArgumentParser(prog="poirot_run",
        description="Poirot - Automated multi-phase case investigation pipeline")
    parser.add_argument("--case", required=True, metavar="DIR")
    parser.add_argument("--output-dir", metavar="DIR", default=None)
    parser.add_argument("--env", metavar="FILE", default=None)
    parser.add_argument("--skip-phases", metavar="N[,N...]", default="")
    parser.add_argument("--no-router", action="store_true",
                        help="Skip live model fetching; use static .env / default models.")
    args = parser.parse_args()

    case_dir = Path(args.case).resolve()
    if not case_dir.exists() or not case_dir.is_dir():
        print("[Poirot] ERROR: Case directory not found: " + str(case_dir), file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir).resolve() if args.output_dir else case_dir/"_poirot_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    env_file = Path(args.env).resolve() if args.env else None
    skip = {int(x.strip()) for x in args.skip_phases.split(",") if x.strip().isdigit()}

    cfg, plan = bootstrap(env_file, case_dir, no_router=args.no_router)
    _inject_plan(plan)

    plan_path = output_dir/"routing_plan.json"
    plan_path.write_text(plan.to_json(), encoding="utf-8")

    started = datetime.utcnow().isoformat() + "Z"
    print("\n" + "#"*70)
    print("  Poirot Investigation Pipeline")
    print("  Case   : " + str(case_dir))
    print("  Output : " + str(output_dir))
    print("  Started: " + started)
    print("  Router : " + ("agent passthrough" if plan.fallback_mode else plan.provider))
    print("#"*70 + "\n")

    errors = []
    if 1 not in skip:
        if phase1_ingest(case_dir, output_dir) != 0: errors.append("Phase 1 (ingestion) failed")
    if 2 not in skip:
        if phase2_classify(output_dir, cfg, plan) != 0: errors.append("Phase 2 (classification) failed")
    if 3 not in skip:
        if phase3_images(output_dir, cfg, plan) != 0: errors.append("Phase 3 (image analysis) failed - continuing")
    if 4 not in skip:
        if phase4_av(output_dir, cfg, plan) != 0: errors.append("Phase 4 (AV analysis) failed - continuing")
    if 5 not in skip:
        if phase5_synthesis(output_dir, cfg, plan) != 0: errors.append("Phase 5 (synthesis) failed")

    finished = datetime.utcnow().isoformat() + "Z"
    print("\n" + "#"*70)
    print("  Poirot Pipeline Complete")
    print("  Finished : " + finished)
    print("  Output   : " + str(output_dir))
    if errors:
        print("  Warnings : " + str(len(errors)) + " phase(s) reported errors:")
        for e in errors: print("    " + e)
    else:
        print("  Status   : All phases completed successfully.")
    report = output_dir/"poirot_report.md"
    if report.exists(): print("\n  Final report  " + str(report))
    print("  Routing plan  " + str(plan_path))
    print("#"*70 + "\n")
    if errors and any("failed" in e and "continuing" not in e for e in errors):
        sys.exit(1)

if __name__ == "__main__":
    main()
