import io
from PIL import Image, ExifTags

AI_SOFTWARE_KEYWORDS = [
    "midjourney", "dall-e", "dall·e", "stable diffusion", "stablediffusion",
    "firefly", "adobe firefly", "imagen", "gemini", "chatgpt", "openai",
    "novelai", "playground ai", "leonardo", "ideogram", "comfyui",
    "automatic1111", "invoke ai", "dream studio", "dreamstudio",
    "nightcafe", "bluewillow", "bing image creator", "canva ai",
    "synthid", "gpt-image", "civitai",
]

SCREENSHOT_RESOLUTIONS = {
    (1920, 1080), (2560, 1440), (3840, 2160), (1280, 720),
    (1280, 800), (1366, 768), (1440, 900), (1600, 900),
    (2560, 1600), (2880, 1800), (3024, 1964), (3456, 2234),
    (2048, 1536), (2732, 2048), (1668, 2388), (1170, 2532),
    (1080, 1920), (1080, 2340), (1080, 2400), (1242, 2688),
    # 横屏变体
    (1080, 1920), (2160, 3840), (2160, 2560),
}

AI_RESOLUTIONS = {
    (512, 512), (768, 768), (1024, 1024),
    (1152, 896), (1216, 832), (1344, 768), (1536, 640),
    (640, 1536), (768, 1344), (832, 1216), (896, 1152),
    (1792, 1024), (1024, 1792),
    (2048, 2048), (1280, 720), (1280, 960),
}

TAG_ID_TO_NAME = {v: k for k, v in ExifTags.TAGS.items()}


def _decode_value(v):
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8", errors="replace").strip("\x00").strip()
        except Exception:
            return repr(v)
    if isinstance(v, tuple):
        return list(v) if len(v) > 1 else (v[0] if v else None)
    return v


def analyze_exif(raw_bytes: bytes, suffix: str) -> dict:
    result = {
        "available": False,
        "data": {},
        "software": None,
        "make": None,
        "model": None,
        "datetime": None,
        "width": None,
        "height": None,
        "ai_hints": [],
        "resolution_suspicious": False,
        "screenshot_suspected": False,
        "xmp_data": None,
    }

    img = Image.open(io.BytesIO(raw_bytes))
    result["width"] = img.width
    result["height"] = img.height

    if (img.width, img.height) in AI_RESOLUTIONS:
        result["resolution_suspicious"] = True

    exif_raw = img.getexif()
    if exif_raw:
        result["available"] = True
        decoded = {}
        for tag_id, value in exif_raw.items():
            tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
            decoded[tag_name] = _decode_value(value)
        result["data"] = decoded

        result["software"] = decoded.get("Software")
        result["make"] = decoded.get("Make")
        result["model"] = decoded.get("Model")
        result["datetime"] = decoded.get("DateTime") or decoded.get("DateTimeOriginal")

    xmp_bytes = img.info.get("xmp") or img.info.get("XML:com.adobe.xmp")
    if xmp_bytes:
        if isinstance(xmp_bytes, bytes):
            xmp_str = xmp_bytes.decode("utf-8", errors="replace")
        else:
            xmp_str = str(xmp_bytes)
        result["xmp_data"] = xmp_str[:4000]
        if not result.get("software"):
            import re
            m = re.search(r"<xmp:CreatorTool>(.*?)</xmp:CreatorTool>", xmp_str)
            if m:
                result["software"] = m.group(1)

    all_text = " ".join(filter(None, [
        result.get("software") or "",
        result.get("make") or "",
        result.get("model") or "",
        result.get("xmp_data") or "",
        str(result.get("data", {})),
    ])).lower()

    for kw in AI_SOFTWARE_KEYWORDS:
        if kw in all_text:
            result["ai_hints"].append(kw.title())

    result["ai_hints"] = list(dict.fromkeys(result["ai_hints"]))

    w, h = result["width"], result["height"]
    no_camera = not result.get("make") and not result.get("model")
    is_screen_res = (w, h) in SCREENSHOT_RESOLUTIONS or (h, w) in SCREENSHOT_RESOLUTIONS
    no_software_camera = not result.get("software") or not any(
        cam in (result.get("software") or "").lower()
        for cam in ["canon", "nikon", "sony", "fuji", "olympus", "panasonic", "leica", "hasselblad"]
    )
    if no_camera and is_screen_res and not result["ai_hints"]:
        result["screenshot_suspected"] = True

    return result
