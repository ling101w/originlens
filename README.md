# OriginLens — AI 图像来源与取证分析系统

> AI-Generated Image Provenance & Forensics Analyzer  
> 版本：v2.0 · 仅供研究与教育用途

## 核心亮点

- **截图鲁棒性**：截图/压缩/转发后仍能通过视觉取证和 VLM 给出风险判断
- **双模评分**：自动识别原图 vs 截图场景，切换不同权重融合策略
- **多模态融合**：C2PA 凭证 + EXIF + ELA + 噪声 + FFT 频域 + VLM 视觉模型 六层检测
- **可解释报告**：每条证据标注强/中/弱等级，支持下载完整 HTML 报告

## 检测架构

```text
上传图片
  ↓
来源凭证层 ─── C2PA / EXIF / XMP / 软件字段
  ↓
截图判断层 ─── 分辨率匹配 + 无相机设备 → 自动切换评分模式
  ↓
图像取证层 ─── ELA 误差 / FFT 频谱 / 噪声残差+熵值
  ↓
VLM 语义层 ─── OpenAI 多模态模型（视觉伪影 + OCR 文字异常）
  ↓
加权融合 ──── 原图模式(.45/.30/.15/.10) vs 截图模式(.10/.45/.30/.15)
  ↓
综合报告 ──── 分数 + 证据 + 可视化 + HTML 报告
```

## 功能列表

| 检测层 | 内容 |
|---|---|
| C2PA / Content Credentials | c2patool CLI + 二进制特征扫描双降级 |
| EXIF / XMP 元数据 | AI 软件关键词、分辨率异常、截图特征检测 |
| ELA 误差级别分析 | 压缩误差可视化，AI 图通常接近零 |
| 噪声残差分析 | 标准差 + 熵值，传感器噪声分布检测 |
| FFT 频谱分析 | 频域高频能量占比，AI 图通常高频不足 |
| VLM 视觉模型 | OpenAI API 多模态分析：伪影 + OCR 文字异常 |
| 双模评分 | 自动识别原图/截图，动态调整权重 |
| HTML 检测报告 | 包含全部分析结果的可下载报告 |

## 快速启动

### 后端（FastAPI）

```bash
cd backend
pip install -r requirements.txt
```

配置 `.env`（可选，不配则跳过 VLM 分析）：

```env
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://your-api-endpoint/v1
OPENAI_MODEL=gpt-4o
```

启动：

```bash
uvicorn app:app --reload --port 8000
```

可选工具（安装后自动调用）：
- `c2patool` — https://github.com/contentauth/c2patool/releases

### 前端（Next.js）

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

## 评分说明

### 双模评分策略

**原图模式**（检测到 C2PA 或 EXIF 时优先来源凭证）：

| 层 | 权重 |
|---|---|
| 来源凭证（C2PA/EXIF） | 45% |
| 图像取证（ELA/噪声/FFT） | 30% |
| VLM 视觉模型 | 15% |
| 取证补充 | 10% |

**截图/元数据缺失模式**（来源凭证丢失时优先视觉特征）：

| 层 | 权重 |
|---|---|
| 图像取证（ELA/噪声/FFT） | 45% |
| VLM 视觉模型 | 30% |
| 取证补充 | 15% |
| 来源凭证 | 10% |

| 分值 | 风险等级 |
|---|---|
| 0–30 | 低风险 |
| 31–60 | 中等风险 |
| 61–85 | 高风险 |
| 86–100 | 强证据 AI 生成 |

## 免责声明

- 检测结果不构成唯一证据。
- 未检测到痕迹 ≠ 图片真实来源。
- 截图/社交平台压缩会导致 C2PA 元数据丢失（系统会自动切换截图模式）。
- VLM 分析依赖外部模型 API，结果作为弱证据参考。

## 目录结构

```
originlens/
├── backend/
│   ├── app.py                # FastAPI 主应用
│   ├── config.py             # OpenAI API 配置
│   ├── .env                  # 环境变量（API Key）
│   ├── detectors/
│   │   ├── exif_detector.py  # EXIF/XMP + 截图特征检测
│   │   ├── c2pa_detector.py  # C2PA 凭证检测（双降级）
│   │   ├── ela_detector.py   # ELA 误差级别分析
│   │   ├── noise_detector.py # 噪声残差 + 熵值分析
│   │   ├── fft_detector.py   # FFT 频谱分析
│   │   └── vlm_detector.py   # VLM 视觉模型（OpenAI API）
│   ├── scorer.py             # 双模加权评分
│   ├── report_generator.py   # HTML 报告生成
│   └── requirements.txt
├── frontend/
│   ├── app/                  # Next.js App Router
│   ├── components/           # React 组件（含 VLMPanel）
│   └── lib/types.ts          # TypeScript 类型定义
└── README.md
```
