import io
import json
import shutil
import subprocess
import tempfile
import os

C2PA_BINARY_SIGNATURES = [
    b"c2pa",
    b"contentCredential",
    b"contentcredential",
    b"stds.iso.org/18013",
    b"c2pa.assertions",
    b"c2pa.claim",
    b"adobe:docid:photoshop:",
    b"urn:c2pa",
    b"cai:assertion",
]

AI_GENERATOR_KEYWORDS = {
    "openai": "OpenAI (DALL-E / ChatGPT)",
    "dall-e": "OpenAI DALL-E",
    "dall·e": "OpenAI DALL-E",
    "adobe firefly": "Adobe Firefly",
    "firefly": "Adobe Firefly",
    "midjourney": "Midjourney",
    "stable diffusion": "Stable Diffusion",
    "google": "Google (Gemini / Imagen)",
    "imagen": "Google Imagen",
    "microsoft": "Microsoft / Azure AI",
    "bing": "Bing Image Creator",
    "canva": "Canva AI",
}


def _try_c2patool(raw_bytes: bytes, suffix: str) -> dict | None:
    c2patool_bin = shutil.which("c2patool")
    if not c2patool_bin:
        return None

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(raw_bytes)
        tmp_path = tmp.name

    try:
        proc = subprocess.run(
            [c2patool_bin, tmp_path],
            capture_output=True,
            timeout=15,
            text=True,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout)
    except Exception:
        pass
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
    return None


def _scan_binary(raw_bytes: bytes) -> dict:
    lower_bytes = raw_bytes[:200_000]
    found_sigs = []
    for sig in C2PA_BINARY_SIGNATURES:
        if sig in lower_bytes:
            found_sigs.append(sig.decode("utf-8", errors="replace"))

    return {
        "method": "binary_scan",
        "signatures_found": found_sigs,
        "found": len(found_sigs) > 0,
    }


def _detect_generator_from_manifest(manifest: dict) -> str | None:
    manifest_str = json.dumps(manifest).lower()
    for kw, name in AI_GENERATOR_KEYWORDS.items():
        if kw.lower() in manifest_str:
            return name
    return None


def _detect_generator_from_binary(raw_bytes: bytes) -> str | None:
    chunk = raw_bytes[:200_000].lower()
    for kw, name in AI_GENERATOR_KEYWORDS.items():
        if kw.encode() in chunk:
            return name
    return None


def analyze_c2pa(raw_bytes: bytes, suffix: str) -> dict:
    result = {
        "found": False,
        "ai_generated": False,
        "generator": None,
        "manifest": None,
        "method": "none",
        "evidence": [],
        "raw_signatures": [],
    }

    manifest = _try_c2patool(raw_bytes, suffix)
    if manifest:
        result["found"] = True
        result["manifest"] = manifest
        result["method"] = "c2patool"
        result["evidence"].append("检测到 C2PA Content Credentials（通过 c2patool 解析）")

        manifest_str = json.dumps(manifest).lower()
        ai_claim_keywords = [
            "ai_generative_training", "c2pa.ai.generative",
            "dall", "openai", "midjourney", "stable-diffusion",
            "firefly", "adobe firefly", "ai generated",
        ]
        for kw in ai_claim_keywords:
            if kw in manifest_str:
                result["ai_generated"] = True
                break

        gen = _detect_generator_from_manifest(manifest)
        if gen:
            result["generator"] = gen
            result["evidence"].append(f"AI 生成工具：{gen}")

        return result

    scan = _scan_binary(raw_bytes, )
    if scan["found"]:
        result["found"] = True
        result["method"] = "binary_scan"
        result["raw_signatures"] = scan["signatures_found"]
        result["evidence"].append(
            f"在文件二进制中检测到 C2PA/Content Credentials 特征签名：{', '.join(scan['signatures_found'][:5])}"
        )

        gen = _detect_generator_from_binary(raw_bytes)
        if gen:
            result["generator"] = gen
            result["ai_generated"] = True
            result["evidence"].append(f"AI 生成工具疑似：{gen}")

    return result
