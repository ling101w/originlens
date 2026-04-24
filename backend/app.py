import uuid
import traceback
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from detectors.exif_detector import analyze_exif
from detectors.c2pa_detector import analyze_c2pa
from detectors.ela_detector import analyze_ela
from detectors.noise_detector import analyze_noise
from detectors.fft_detector import analyze_fft
from detectors.vlm_detector import analyze_vlm
from scorer import compute_score
from report_generator import generate_html_report

app = FastAPI(title="OriginLens API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
MAX_FILE_SIZE = 30 * 1024 * 1024  # 30 MB


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "OriginLens", "version": "2.0.0"}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    suffix = Path(file.filename or "image.jpg").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 30 MB)")

    analysis_id = str(uuid.uuid4())[:8]

    try:
        exif_result = analyze_exif(raw_bytes, suffix)
    except Exception:
        exif_result = {"available": False, "data": {}, "ai_hints": [], "error": traceback.format_exc()}

    try:
        c2pa_result = analyze_c2pa(raw_bytes, suffix)
    except Exception:
        c2pa_result = {"found": False, "ai_generated": False, "evidence": [], "error": traceback.format_exc()}

    try:
        ela_result = analyze_ela(raw_bytes, suffix)
    except Exception:
        ela_result = {"image_base64": "", "max_diff": 0, "mean_diff": 0, "suspicious": False, "error": traceback.format_exc()}

    try:
        noise_result = analyze_noise(raw_bytes, suffix)
    except Exception:
        noise_result = {"image_base64": "", "std_dev": 0, "suspicious": False, "error": traceback.format_exc()}

    try:
        fft_result = analyze_fft(raw_bytes, suffix)
    except Exception:
        fft_result = {"image_base64": "", "high_freq_ratio": 0, "suspicious": False, "error": traceback.format_exc()}

    try:
        vlm_result = analyze_vlm(
            raw_bytes, suffix,
            exif_result=exif_result,
            c2pa_result=c2pa_result,
            ela_result=ela_result,
            noise_result=noise_result,
            fft_result=fft_result,
        )
    except Exception:
        vlm_result = {"available": False, "error": traceback.format_exc()}

    score, risk_level, evidence, mode = compute_score(
        exif_result, c2pa_result, ela_result, noise_result, fft_result, vlm_result
    )

    report_html = generate_html_report(
        analysis_id=analysis_id,
        filename=file.filename or "unknown",
        score=score,
        risk_level=risk_level,
        evidence=evidence,
        mode=mode,
        exif_result=exif_result,
        c2pa_result=c2pa_result,
        ela_result=ela_result,
        noise_result=noise_result,
        fft_result=fft_result,
        vlm_result=vlm_result,
    )

    return JSONResponse({
        "id": analysis_id,
        "filename": file.filename,
        "score": score,
        "risk_level": risk_level,
        "mode": mode,
        "evidence": evidence,
        "exif": exif_result,
        "c2pa": c2pa_result,
        "ela": ela_result,
        "noise": noise_result,
        "fft": fft_result,
        "vlm": vlm_result,
        "report_html": report_html,
    })
