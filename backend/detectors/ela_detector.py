import io
import base64
import numpy as np
from PIL import Image


def analyze_ela(raw_bytes: bytes, suffix: str) -> dict:
    result = {
        "image_base64": "",
        "max_diff": 0.0,
        "mean_diff": 0.0,
        "suspicious": False,
    }

    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")

    if img.width * img.height > 4096 * 4096:
        img.thumbnail((2048, 2048), Image.LANCZOS)

    recompressed_io = io.BytesIO()
    img.save(recompressed_io, format="JPEG", quality=90)
    recompressed_io.seek(0)
    recompressed = Image.open(recompressed_io).convert("RGB")

    orig_arr = np.array(img, dtype=np.float32)
    recomp_arr = np.array(recompressed, dtype=np.float32)

    diff = np.abs(orig_arr - recomp_arr)
    scale_factor = 15.0
    ela_arr = np.clip(diff * scale_factor, 0, 255).astype(np.uint8)

    max_diff = float(diff.max())
    mean_diff = float(diff.mean())

    result["max_diff"] = round(max_diff, 3)
    result["mean_diff"] = round(mean_diff, 4)

    if mean_diff < 0.8 and max_diff < 10:
        result["suspicious"] = True

    ela_img = Image.fromarray(ela_arr, mode="RGB")
    out_io = io.BytesIO()
    ela_img.save(out_io, format="PNG")
    result["image_base64"] = base64.b64encode(out_io.getvalue()).decode()

    return result
