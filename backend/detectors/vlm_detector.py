import io
import json
import base64
from PIL import Image
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

VLM_SYSTEM_PROMPT = """你是一个 AI 生成图像取证专家。你的任务是从视觉和语义角度分析图片是否可能由 AI 生成。

请从以下维度逐一检查，并如实报告你的发现：

1. **手部/肢体**：手指数量、关节弯曲是否自然
2. **面部细节**：牙齿、耳朵、眼镜、发际线是否异常
3. **文字/Logo/OCR**：图中文字是否可读、是否有乱码或伪字符
4. **光照与阴影**：光照方向是否一致、阴影是否合理
5. **透视与几何**：物体透视关系是否正确、直线是否弯曲
6. **纹理与重复**：是否存在不自然的重复纹理或过度平滑
7. **背景逻辑**：背景物体是否存在不合逻辑的拼接

请严格以 JSON 格式输出，不要输出其他内容：

```json
{
  "ai_likelihood": 0.0到1.0之间的浮点数,
  "confidence": "low" 或 "medium" 或 "high",
  "text_anomaly": true/false,
  "text_anomaly_detail": "描述文字异常情况，无异常则为空字符串",
  "visual_artifacts": ["异常点1", "异常点2"],
  "reasoning": "综合判断理由（一段话）"
}
```"""


def _resize_for_api(raw_bytes: bytes, max_side: int = 1024) -> str:
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def _build_context_text(
    exif_result: dict,
    c2pa_result: dict,
    ela_result: dict,
    noise_result: dict,
    fft_result: dict,
) -> str:
    lines = ["\n以下是其他检测模块已得到的数据，请结合这些数据综合分析：\n"]

    # C2PA
    if c2pa_result.get("ai_generated"):
        gen = c2pa_result.get("generator") or "AI 工具"
        lines.append(f"- C2PA 来源凭证：确认 AI 生成（生成工具：{gen}）")
    elif c2pa_result.get("found"):
        lines.append("- C2PA 来源凭证：发现凭证但无法确认 AI 来源")
    else:
        lines.append("- C2PA 来源凭证：未检测到")

    # EXIF
    if exif_result.get("ai_hints"):
        lines.append(f"- EXIF 软件字段：{', '.join(exif_result['ai_hints'][:3])}（AI 工具关键词）")
    if exif_result.get("screenshot_suspected"):
        lines.append(f"- EXIF 截图判断：疑似截图（{exif_result.get('width')}×{exif_result.get('height')}）")
    if exif_result.get("make") or exif_result.get("model"):
        lines.append(f"- EXIF 相机设备：{exif_result.get('make','')} {exif_result.get('model','')}")
    else:
        lines.append("- EXIF 相机设备：无")

    # ELA
    ela_flag = "⚠ 异常" if ela_result.get("suspicious") else "正常"
    lines.append(
        f"- ELA 误差分析：max_diff={ela_result.get('max_diff',0):.1f}，"
        f"mean_diff={ela_result.get('mean_diff',0):.4f}，判定={ela_flag}"
    )

    # Noise
    noise_flag = "⚠ 异常" if noise_result.get("suspicious") else "正常"
    lines.append(
        f"- 噪声残差：std={noise_result.get('std_dev',0):.2f}，"
        f"entropy={noise_result.get('noise_entropy',0):.2f}，判定={noise_flag}"
    )

    # FFT
    fft_flag = "⚠ 异常" if fft_result.get("suspicious") else "正常"
    lines.append(
        f"- FFT 频谱：high_freq_ratio={fft_result.get('high_freq_ratio',0):.3f}，判定={fft_flag}"
    )

    return "\n".join(lines)


def analyze_vlm(
    raw_bytes: bytes,
    suffix: str,
    exif_result: dict | None = None,
    c2pa_result: dict | None = None,
    ela_result: dict | None = None,
    noise_result: dict | None = None,
    fft_result: dict | None = None,
) -> dict:
    result = {
        "available": False,
        "ai_likelihood": 0.0,
        "confidence": "none",
        "text_anomaly": False,
        "text_anomaly_detail": "",
        "visual_artifacts": [],
        "reasoning": "",
        "error": "",
    }

    if not OPENAI_API_KEY:
        result["error"] = "未配置 OPENAI_API_KEY，VLM 分析已跳过"
        return result

    try:
        from openai import OpenAI
    except ImportError:
        result["error"] = "未安装 openai 包，请运行 pip install openai"
        return result

    try:
        img_b64 = _resize_for_api(raw_bytes)

        client_kwargs: dict = {"api_key": OPENAI_API_KEY}
        if OPENAI_BASE_URL:
            base_url = OPENAI_BASE_URL.rstrip("/")
            if not base_url.endswith("/v1"):
                base_url += "/v1"
            client_kwargs["base_url"] = base_url

        client = OpenAI(**client_kwargs)

        context_text = _build_context_text(
            exif_result or {},
            c2pa_result or {},
            ela_result or {},
            noise_result or {},
            fft_result or {},
        )
        user_text = (
            "请结合图片内容和以下检测数据，分析这张图片是否可能由 AI 生成，严格以 JSON 格式输出。"
            + context_text
        )

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": VLM_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_b64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            max_tokens=1024,
            temperature=0.2,
        )

        raw_text = _extract_content(response)
        parsed = _parse_vlm_response(raw_text)

        result["available"] = True
        result["ai_likelihood"] = parsed.get("ai_likelihood", 0.0)
        result["confidence"] = parsed.get("confidence", "low")
        result["text_anomaly"] = parsed.get("text_anomaly", False)
        result["text_anomaly_detail"] = parsed.get("text_anomaly_detail", "")
        result["visual_artifacts"] = parsed.get("visual_artifacts", [])
        result["reasoning"] = parsed.get("reasoning", raw_text[:500])

    except Exception as e:
        result["error"] = f"VLM 调用失败：{str(e)[:300]}"

    return result


def _extract_content(response) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        try:
            return response["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return json.dumps(response)[:500]
    try:
        return response.choices[0].message.content or ""
    except AttributeError:
        pass
    try:
        return str(response)
    except Exception:
        return ""


def _parse_vlm_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    import re
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass

    return {"reasoning": text[:500]}
