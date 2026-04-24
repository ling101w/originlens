import io
import base64
import numpy as np
from PIL import Image


def analyze_fft(raw_bytes: bytes, suffix: str) -> dict:
    result = {
        "image_base64": "",
        "fft_mean": 0.0,
        "fft_std": 0.0,
        "high_freq_ratio": 0.0,
        "suspicious": False,
    }

    img = Image.open(io.BytesIO(raw_bytes)).convert("L")

    if img.width * img.height > 4096 * 4096:
        img.thumbnail((2048, 2048), Image.LANCZOS)

    gray = np.array(img, dtype=np.float32)

    f = np.fft.fft2(gray)
    fshift = np.fft.fftshift(f)
    magnitude = np.log(np.abs(fshift) + 1)

    h, w = magnitude.shape
    center = magnitude[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]
    center_energy = float(center.sum())
    outer_energy = float(magnitude.sum()) - center_energy
    high_freq_ratio = outer_energy / (center_energy + 1e-6)

    result["fft_mean"] = round(float(magnitude.mean()), 4)
    result["fft_std"] = round(float(magnitude.std()), 4)
    result["high_freq_ratio"] = round(high_freq_ratio, 4)

    if high_freq_ratio < 1.2:
        result["suspicious"] = True

    norm = (magnitude - magnitude.min()) / (magnitude.max() - magnitude.min() + 1e-6) * 255
    norm = norm.astype(np.uint8)

    colored = _inferno_colormap(norm)
    fft_img = Image.fromarray(colored, mode="RGB")

    out_io = io.BytesIO()
    fft_img.save(out_io, format="PNG")
    result["image_base64"] = base64.b64encode(out_io.getvalue()).decode()

    return result


def _inferno_colormap(gray: np.ndarray) -> np.ndarray:
    t = gray.astype(np.float32) / 255.0
    r = np.clip(np.sqrt(t) * 255, 0, 255)
    g = np.clip(t * t * t * 255, 0, 255)
    b = np.clip(np.sin(t * np.pi) * 255, 0, 255)
    return np.stack([r, g, b], axis=-1).astype(np.uint8)
