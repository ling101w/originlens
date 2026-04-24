def compute_score(
    exif_result: dict,
    c2pa_result: dict,
    ela_result: dict,
    noise_result: dict,
    fft_result: dict | None = None,
    vlm_result: dict | None = None,
) -> tuple[int, str, list[str], str]:
    """Returns (score, risk_level, evidence, mode)."""

    fft_result = fft_result or {}
    vlm_result = vlm_result or {}

    is_screenshot = bool(exif_result.get("screenshot_suspected"))
    provenance_missing = (
        not c2pa_result.get("found")
        and not exif_result.get("ai_hints")
        and not exif_result.get("available")
    )
    mode = "screenshot" if (is_screenshot or provenance_missing) and not c2pa_result.get("found") else "original"

    provenance_pts = 0.0
    forensic_pts = 0.0
    vlm_pts = 0.0
    evidence: list[str] = []

    # ── Provenance layer ────────────────────────────
    if c2pa_result.get("ai_generated"):
        provenance_pts += 90
        gen = c2pa_result.get("generator") or "AI 工具"
        evidence.append(f"强证据：检测到 C2PA Content Credentials，显示由 {gen} 生成")
    elif c2pa_result.get("found"):
        provenance_pts += 40
        evidence.append("中等证据：检测到 C2PA/Content Credentials 特征，但无法确认 AI 来源")

    if exif_result.get("ai_hints"):
        hints = "、".join(exif_result["ai_hints"][:3])
        provenance_pts += 70
        evidence.append(f"强证据：元数据软件字段包含 AI 工具信息 —— {hints}")

    if not exif_result.get("available"):
        provenance_pts += 15
        evidence.append("弱证据：EXIF 元数据完全缺失，来源不可验证")

    if exif_result.get("resolution_suspicious"):
        provenance_pts += 12
        w = exif_result.get("width", "?")
        h = exif_result.get("height", "?")
        evidence.append(f"弱证据：分辨率 {w}×{h} 为常见 AI 生成图片尺寸")

    provenance_pts = min(provenance_pts, 100)

    # ── Screenshot hint ─────────────────────────────
    if is_screenshot:
        w = exif_result.get("width", "?")
        h = exif_result.get("height", "?")
        evidence.append(
            f"提示：疑似截图（分辨率 {w}×{h} 为常见屏幕尺寸，且无相机设备信息）"
            " —— C2PA 来源凭证可能已在截图时丢失"
        )

    # ── Forensic layer ──────────────────────────────
    if ela_result.get("suspicious"):
        forensic_pts += 30
        evidence.append(
            f"中等证据：ELA 误差水平异常低（max={ela_result.get('max_diff', 0):.1f}，"
            f"mean={ela_result.get('mean_diff', 0):.3f}），可能为无损生成图"
        )

    if noise_result.get("suspicious"):
        forensic_pts += 25
        evidence.append(
            f"中等证据：噪声分布异常均匀（std={noise_result.get('std_dev', 0):.2f}，"
            f"entropy={noise_result.get('noise_entropy', 0):.2f}），"
            "真实相机图像通常噪声更高"
        )

    if fft_result.get("suspicious"):
        forensic_pts += 25
        evidence.append(
            f"中等证据：频域高频能量占比偏低（ratio={fft_result.get('high_freq_ratio', 0):.3f}），"
            "AI 生成图像在高频区域通常能量不足"
        )

    forensic_pts = min(forensic_pts, 100)

    # ── VLM layer ───────────────────────────────────
    if vlm_result.get("available"):
        ai_like = vlm_result.get("ai_likelihood", 0.0)
        vlm_pts = ai_like * 100

        conf = vlm_result.get("confidence", "low")
        artifacts = vlm_result.get("visual_artifacts", [])
        if artifacts:
            evidence.append(
                f"弱证据（VLM {conf}）：视觉模型检测到疑似伪影 —— "
                + "、".join(artifacts[:4])
            )

        if vlm_result.get("text_anomaly"):
            detail = vlm_result.get("text_anomaly_detail", "")
            forensic_pts = min(forensic_pts + 20, 100)
            evidence.append(f"中等证据：图中文字 / OCR 异常 —— {detail[:100]}")

        reasoning = vlm_result.get("reasoning", "")
        if reasoning and not artifacts:
            evidence.append(f"弱证据（VLM {conf}）：{reasoning[:120]}")
    elif vlm_result.get("error"):
        evidence.append(f"提示：VLM 分析未执行 —— {vlm_result['error'][:80]}")

    vlm_pts = min(vlm_pts, 100)

    # ── Weighted fusion ─────────────────────────────
    if mode == "original":
        score = int(
            0.55 * provenance_pts
            + 0.25 * forensic_pts
            + 0.15 * vlm_pts
            + 0.05 * (forensic_pts * 0.5)
        )
    else:
        score = int(
            0.10 * provenance_pts
            + 0.45 * forensic_pts
            + 0.30 * vlm_pts
            + 0.15 * (forensic_pts * 0.5)
        )

    # ── Hard floor for strong provenance evidence ────
    if c2pa_result.get("ai_generated"):
        score = max(score, 82)
    elif exif_result.get("ai_hints"):
        score = max(score, 70)
    elif c2pa_result.get("found"):
        score = max(score, 50)

    score = max(0, min(score, 100))

    if not evidence:
        evidence.append("未检测到明显 AI 生成痕迹，但缺乏痕迹不等于真实来源")

    if score <= 30:
        risk_level = "low"
    elif score <= 60:
        risk_level = "medium"
    elif score <= 85:
        risk_level = "high"
    else:
        risk_level = "critical"

    mode_label = "截图/元数据缺失模式" if mode == "screenshot" else "原图模式"
    evidence.insert(0, f"评分模式：{mode_label}（{mode}）")

    return score, risk_level, evidence, mode
