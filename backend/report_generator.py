import json
from datetime import datetime

RISK_COLOR = {
    "low": "#10b981",
    "medium": "#f59e0b",
    "high": "#ef4444",
    "critical": "#dc2626",
}

RISK_LABEL = {
    "low": "低风险（0-30）",
    "medium": "中等风险（31-60）",
    "high": "高风险（61-85）",
    "critical": "强证据 AI 生成（86-100）",
}


def _exif_table(exif: dict) -> str:
    if not exif.get("available"):
        return "<p class='na'>EXIF 元数据不可用或完全缺失</p>"
    rows = ""
    for k, v in list(exif.get("data", {}).items())[:40]:
        rows += f"<tr><td>{k}</td><td>{v}</td></tr>"
    return f"<table><thead><tr><th>字段</th><th>值</th></tr></thead><tbody>{rows}</tbody></table>"


def _evidence_list(evidence: list) -> str:
    items = "".join(f"<li>{e}</li>" for e in evidence)
    return f"<ul class='evidence'>{items}</ul>"


def generate_html_report(
    analysis_id: str,
    filename: str,
    score: int,
    risk_level: str,
    evidence: list,
    mode: str,
    exif_result: dict,
    c2pa_result: dict,
    ela_result: dict,
    noise_result: dict,
    fft_result: dict | None = None,
    vlm_result: dict | None = None,
) -> str:
    fft_result = fft_result or {}
    vlm_result = vlm_result or {}
    color = RISK_COLOR.get(risk_level, "#6b7280")
    risk_label = RISK_LABEL.get(risk_level, risk_level)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mode_label = "截图/元数据缺失模式" if mode == "screenshot" else "原图模式"

    ela_img_tag = ""
    if ela_result.get("image_base64"):
        ela_img_tag = f'<img src="data:image/png;base64,{ela_result["image_base64"]}" alt="ELA Analysis" />'

    noise_img_tag = ""
    if noise_result.get("image_base64"):
        noise_img_tag = f'<img src="data:image/png;base64,{noise_result["image_base64"]}" alt="Noise Analysis" />'

    fft_img_tag = ""
    if fft_result.get("image_base64"):
        fft_img_tag = f'<img src="data:image/png;base64,{fft_result["image_base64"]}" alt="FFT Spectrum" />'

    c2pa_detail = ""
    if c2pa_result.get("found"):
        sigs = ", ".join(c2pa_result.get("raw_signatures", [])[:5]) or "（通过 c2patool 解析）"
        c2pa_detail = f"<p>检测特征签名：{sigs}</p>"
        if c2pa_result.get("generator"):
            c2pa_detail += f"<p>疑似生成工具：<strong>{c2pa_result['generator']}</strong></p>"
        if c2pa_result.get("manifest"):
            c2pa_detail += f"<pre>{json.dumps(c2pa_result['manifest'], indent=2, ensure_ascii=False)[:3000]}</pre>"
    else:
        c2pa_detail = "<p class='na'>未检测到 C2PA / Content Credentials</p>"

    vlm_section = ""
    if vlm_result.get("available"):
        artifacts = "、".join(vlm_result.get("visual_artifacts", [])[:5]) or "无"
        text_anom = vlm_result.get("text_anomaly_detail") or "无异常"
        vlm_section = f"""
<h2>VLM 视觉模型分析</h2>
<div class="card">
  <p>AI 生成可能性：<strong style="color:{color}">{vlm_result.get('ai_likelihood', 0):.0%}</strong>
    &nbsp;（置信度：{vlm_result.get('confidence', '—')}）</p>
  <p>视觉伪影：{artifacts}</p>
  <p>文字 / OCR 异常：{text_anom}</p>
  <p style="color:#94a3b8;font-size:0.85rem;margin-top:8px;">{vlm_result.get('reasoning', '')[:400]}</p>
</div>"""
    elif vlm_result.get("error"):
        vlm_section = f"""
<h2>VLM 视觉模型分析</h2>
<div class="card"><p class="na">{vlm_result['error'][:200]}</p></div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>OriginLens 检测报告 #{analysis_id}</title>
<style>
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0a14; color: #e2e8f0; margin: 0; padding: 32px; }}
  h1 {{ color: #00d4ff; margin-bottom: 4px; }}
  h2 {{ color: #7c3aed; border-bottom: 1px solid #1e1b4b; padding-bottom: 8px; margin-top: 32px; }}
  .meta {{ color: #64748b; font-size: 0.875rem; margin-bottom: 24px; }}
  .badge {{ display: inline-block; background: #1e1b4b; border-radius: 4px; padding: 2px 8px;
    font-size: 0.75rem; color: #a5b4fc; margin-left: 8px; }}
  .score-box {{ display: inline-block; background: #0f1020; border: 2px solid {color}; border-radius: 12px;
    padding: 24px 48px; text-align: center; margin-bottom: 24px; }}
  .score-num {{ font-size: 4rem; font-weight: 800; color: {color}; line-height: 1; }}
  .score-label {{ color: {color}; font-size: 0.9rem; margin-top: 4px; }}
  .evidence {{ padding-left: 20px; line-height: 1.8; }}
  .evidence li {{ margin-bottom: 6px; }}
  .card {{ background: #0f1020; border: 1px solid #1a1b2e; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th {{ background: #1e1b4b; color: #a5b4fc; text-align: left; padding: 8px 12px; }}
  td {{ padding: 6px 12px; border-bottom: 1px solid #1a1b2e; word-break: break-all; }}
  tr:hover td {{ background: #12132a; }}
  img {{ max-width: 100%; border-radius: 8px; border: 1px solid #1a1b2e; }}
  pre {{ background: #0a0a14; border: 1px solid #1a1b2e; border-radius: 6px; padding: 16px;
    font-size: 0.78rem; overflow-x: auto; white-space: pre-wrap; color: #94a3b8; }}
  .na {{ color: #64748b; font-style: italic; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  .grid3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }}
  .forensic-label {{ color: #94a3b8; font-size: 0.8rem; margin-top: 8px; }}
  footer {{ margin-top: 48px; color: #334155; font-size: 0.75rem; text-align: center; }}
</style>
</head>
<body>
<h1>🔍 OriginLens — AI 图像来源与取证报告</h1>
<div class="meta">
  报告 ID：{analysis_id} &nbsp;|&nbsp; 文件名：{filename} &nbsp;|&nbsp; 生成时间：{timestamp}
  <span class="badge">{mode_label}</span>
</div>

<h2>综合风险评分</h2>
<div class="score-box">
  <div class="score-num">{score}</div>
  <div class="score-label">{risk_label}</div>
</div>

<h2>检测依据</h2>
<div class="card">
{_evidence_list(evidence)}
<p style="color:#64748b;font-size:0.8rem;margin-top:12px;">
  ⚠️ 免责声明：本报告为辅助分析工具，不构成唯一证据。检测不到痕迹不代表图片真实。
</p>
</div>

<h2>C2PA / Content Credentials</h2>
<div class="card">
  <p>检测结果：<strong style="color:{'#10b981' if c2pa_result.get('found') else '#64748b'}">
    {'已发现 C2PA 凭证' if c2pa_result.get('found') else '未检测到 C2PA 凭证'}
  </strong></p>
  <p>AI 生成判定：<strong style="color:{'#ef4444' if c2pa_result.get('ai_generated') else '#64748b'}">
    {'是' if c2pa_result.get('ai_generated') else '否/不确定'}
  </strong></p>
  {c2pa_detail}
</div>

<h2>EXIF 元数据</h2>
<div class="card">
  <p>软件字段：<strong>{exif_result.get('software') or '—'}</strong></p>
  <p>设备：{exif_result.get('make') or '—'} {exif_result.get('model') or ''}</p>
  <p>拍摄时间：{exif_result.get('datetime') or '—'}</p>
  <p>分辨率：{exif_result.get('width')}×{exif_result.get('height')}
    {'&nbsp;<span style="color:#f59e0b">⚠ 常见 AI 尺寸</span>' if exif_result.get('resolution_suspicious') else ''}
    {'&nbsp;<span style="color:#a78bfa">⚠ 疑似截图</span>' if exif_result.get('screenshot_suspected') else ''}
  </p>
  <p>AI 相关关键词：{', '.join(exif_result.get('ai_hints', [])) or '无'}</p>
  {_exif_table(exif_result)}
</div>

<h2>图像取证可视化</h2>
<div class="grid3">
  <div class="card">
    <strong>ELA 误差级别分析</strong>
    <p class="forensic-label">
      最大差异：{ela_result.get('max_diff', 0):.1f} &nbsp;|&nbsp; 平均差异：{ela_result.get('mean_diff', 0):.4f}<br>
      异常判定：{'⚠ 异常' if ela_result.get('suspicious') else '正常'}
    </p>
    {ela_img_tag}
  </div>
  <div class="card">
    <strong>噪声残差分析</strong>
    <p class="forensic-label">
      噪声标准差：{noise_result.get('std_dev', 0):.2f} &nbsp;|&nbsp;
      熵值：{noise_result.get('noise_entropy', 0):.2f}<br>
      异常判定：{'⚠ 异常' if noise_result.get('suspicious') else '正常'}
    </p>
    {noise_img_tag}
  </div>
  <div class="card">
    <strong>FFT 频谱分析</strong>
    <p class="forensic-label">
      高频占比：{fft_result.get('high_freq_ratio', 0):.3f} &nbsp;|&nbsp;
      均值：{fft_result.get('fft_mean', 0):.2f}<br>
      异常判定：{'⚠ 异常' if fft_result.get('suspicious') else '正常'}
    </p>
    {fft_img_tag}
  </div>
</div>

{vlm_section}

<footer>
  OriginLens v2.0 — AI 图像来源与取证分析系统 | 仅供研究与教育用途
</footer>
</body>
</html>"""
