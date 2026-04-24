import io
import base64
import numpy as np
from PIL import Image

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False


def _jet_colormap(gray: np.ndarray) -> np.ndarray:
    normalized = gray.astype(np.float32) / 255.0
    r = np.clip(1.5 - np.abs(4.0 * normalized - 3.0), 0, 1)
    g = np.clip(1.5 - np.abs(4.0 * normalized - 2.0), 0, 1)
    b = np.clip(1.5 - np.abs(4.0 * normalized - 1.0), 0, 1)
    rgb = np.stack([r, g, b], axis=-1)
    return (rgb * 255).astype(np.uint8)


def analyze_noise(raw_bytes: bytes, suffix: str) -> dict:
    result = {
        "image_base64": "",
        "std_dev": 0.0,
        "noise_mean": 0.0,
        "noise_entropy": 0.0,
        "suspicious": False,
    }

    img = Image.open(io.BytesIO(raw_bytes)).convert("L")

    if img.width * img.height > 4096 * 4096:
        img.thumbnail((2048, 2048), Image.LANCZOS)

    gray = np.array(img, dtype=np.float32)

    if _CV2_AVAILABLE:
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    else:
        from PIL import ImageFilter
        blurred_pil = Image.fromarray(gray.astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=2))
        blurred = np.array(blurred_pil, dtype=np.float32)

    residual = gray - blurred
    abs_res = np.abs(residual)
    std_dev = float(np.std(residual))
    noise_mean = float(np.mean(abs_res))

    hist, _ = np.histogram(abs_res.astype(np.uint8), bins=256, range=(0, 255), density=True)
    hist = hist + 1e-12
    noise_entropy = float(-np.sum(hist * np.log2(hist)))

    result["std_dev"] = round(std_dev, 4)
    result["noise_mean"] = round(noise_mean, 4)
    result["noise_entropy"] = round(noise_entropy, 4)

    if std_dev < 2.0:
        result["suspicious"] = True

    abs_residual = abs_res
    norm_residual = np.clip(abs_residual / (abs_residual.max() + 1e-6) * 255, 0, 255).astype(np.uint8)

    noise_rgb = _jet_colormap(norm_residual)
    noise_img = Image.fromarray(noise_rgb, mode="RGB")

    out_io = io.BytesIO()
    noise_img.save(out_io, format="PNG")
    result["image_base64"] = base64.b64encode(out_io.getvalue()).decode()

    return result
