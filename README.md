<div align="center">

```
██╗███╗   ██╗███████╗██╗ ██████╗ ██╗  ██╗████████╗     █████╗  ██████╗ ███████╗███╗   ██╗████████╗
██║████╗  ██║██╔════╝██║██╔════╝ ██║  ██║╚══██╔══╝    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
██║██╔██╗ ██║███████╗██║██║  ███╗███████║   ██║       ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║
██║██║╚██╗██║╚════██║██║██║   ██║██╔══██║   ██║       ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║
██║██║ ╚████║███████║██║╚██████╔╝██║  ██║   ██║       ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║
╚═╝╚═╝  ╚═══╝╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝       ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝
```

# Insight Agent

### 多源情报融合 AI 平台 · 跨域数据智能决策系统

> **网络空间 · 物理世界 · 城市商业** — 三空间数据融合，统一 AI 主持人驱动决策闭环。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)
[![Code Lines](https://img.shields.io/badge/Code-~3.0K%20lines-orange.svg)](#)
[![Platforms](https://img.shields.io/badge/Crawlers-8%20platforms-brightgreen.svg)](#)
[![Cold Start](https://img.shields.io/badge/Cold%20Start-130ms-ff69b4.svg)](#)

[文档](docs/) · [快速开始](#-快速开始) · [商业化路径](#-商业化路径) · [路线图](#-路线图)

</div>

---

## 🎯 平台定位

> **多源情报融合 AI 平台** — 通过 8 平台爬虫（网络空间）、多模态视觉感知（物理世界）、地理空间分析（城市商业）三空间数据汇集，统一 AI 主持人驱动「**采集 → 融合 → 分析 → 决策 → 报告**」全链路。

传统数据栈是「**单源采集 → 单领域分析 → 单点报告**」。  
Insight Agent 是「**多源融合 → 跨域分析 → 智能决策**」 — 数据分析师升级为「指挥官」，一句话驱动整个数据基础设施。

---

## 🌐 核心竞争力：三空间情报融合

### ① 网络空间情报 · Cyber Intelligence
**8 平台爬虫 + 自然语言启动**

- **统一反检测**：Playwright 全平台覆盖，浏览器指纹伪装、登录会话缓存
- **智能字段识别**：自动检测文本/数值/日期列，零配置即导即用
- **AI 主持分析**：动态决定方法、并行执行 7 个分析模型
- **多形态输出**：HTML / PDF / PPT 三态报告

> 适用场景：舆情监测、竞品分析、消费者洞察、学术研究

📦 入口：[`main.py`](main.py) · [`crawlers/`](crawlers) · [`analysis/`](analysis) · [`web/server.py`](web/server.py)

### ② 物理世界感知 · Physical World Perception
**MediaPipe + YOLO 多模态视觉引擎**

- **人体感知**：MediaPipe Pose / Hands / Face Mesh 实时识别姿态与表情
- **物体检测**：YOLOv4-tiny 轻量模型，CPU 实时推理
- **行为分析**：行为流水线、触发规则引擎、自动告警
- **多场景适配**：商超客流、行为分析、产品检测、客流热力

> 适用场景：智慧零售、安防监控、人机交互、数字孪生

📦 入口：[`web/physical_world/`](web/physical_world) · [`web/physical_backend/`](web/physical_backend)

### ③ 城市商业洞察 · Urban Commercial Insight
**高德地图 + Canvas 粒子流 + AI 智能体**

- **实时粒子流**：贝塞尔曲线 + 菜系色 + 爆点动画，呈现城市餐饮人群流向
- **多维热区分析**：热门区域 TOP 5、菜系分布、客流增长率、实时人流
- **AI 智能体**：城市餐饮智能体对话式问询，自动生成选址建议
- **可交互仪表盘**：Vite + 高德 JS API v2.0，WebSocket 实时数据流

> 适用场景：商业选址、招商分析、城市运营、连锁拓店

📦 入口：[`web/city_heatmap/`](web/city_heatmap) · [`web/city_heatmap_backend/`](web/city_heatmap_backend)

### 三空间融合示意
```
  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
  │   网络空间    │    │   物理世界    │    │   城市商业    │
  │  8 平台爬虫   │    │ MediaPipe+YOLO│    │  高德 + 粒子  │
  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ▼
                  ┌──────────────────────┐
                  │   AI 主持人决策层     │
                  │   跨域数据融合 · 推理  │
                  └──────────────────────┘
```

---

## ❗ 痛点：数据分析的 6 道坎

| 现状 | 痛点 | 我们怎么解 |
|---|---|---|
| 🔍 **采集** | 8 个平台，8 套登录/反爬/字段体系 | 统一 Playwright 反检测，**自然语言启动** |
| 🧹 **清洗** | HTML 标签、零宽字符、中文数字、相对时间 | 智能流水线：**"1.2万"→12000、"3天前"→YYYY-MM-DD** |
| 📊 **分析** | 写 Python、调库、调参、画图 | **AI 主持人**：动态决定方法、写代码、给结论 |
| 🤖 **追问** | 老板换个角度问，又要从头跑 | **多轮对话 + 会话持久化**，断点续跑 |
| 📄 **报告** | Word 排版、PPT 模板、PDF 导出 | **一键 HTML / PDF / PPT** 三态输出 |
| 💸 **成本** | SaaS 月费 $50-500，数据上云 | **本地运行、MIT 开源、零云依赖** |

---

## 💡 我们的解法：AI 主持分析，而不是 AI 辅助分析

```
传统 AI 工具   =  你跑代码 → AI 答疑
Insight Agent  =  AI 主持人 → 动态选工具 → 写代码 → 输出结论 → 接受追问
```

**对话示例**：

```
你：「这些评论的情感倾向如何？」
AI：直接写代码跑 SnowNLP → 输出分布图 + 正负面例句 → 追问「负面主要集中在什么问题？」

你：「再对比一下天猫和京东对同一款产品的评价」
AI：重新加载两个数据集 → 并行分析 → 输出对比结论
```

---

## ✨ 核心亮点

### ① 8 平台爬虫 + 自然语言启动
| 平台 | 数据类型 |
|---|---|
| 知乎 / 豆瓣 | 问答、评分 |
| B 站 | 视频弹幕 / 评论 |
| 小红书 | 笔记 |
| 抖音 | 短视频评论 |
| 知网 | 学术论文 |
| 天猫 / 京东 | 商品评论 |

> 不需要手动选平台、配参数。说「爬抖音上关于 AI 的视频评论」，AI 自动选择爬虫、设置关键词、启动采集。

### ② 智能字段检测，零配置
不同平台爬下来的数据列名千奇百怪 —— `content` / `评论内容` / `text` 三种命名都有。  
平台的 `auto_detect_fields()` 自动推断每列类型（文本 / 数值 / 日期），**对任意平台的数据「即导即用」**。

### ③ 自研 Agent 内核（520 文件）
不是调 API 的薄壳。项目内嵌完整 AIAgent 引擎：
- **懒加载**：冷启动 **130ms**
- **工具编排**：可视化 Agent 决策链
- **流式输出**：逐 token 打字机效果
- **会话持久化**：分析到一半退出，下次打开继续

### ④ 双界面 + 一键分发
- **终端版** (`insight`)：ANSI Shadow 艺术字欢迎页，六宫格菜单，Rich 动画
- **Web 版** (`insight-web`)：Apple 白色极简设计，毛玻璃侧栏，Flask + Chart.js
- **城市热区图 Demo** (`web/city_heatmap`)：高德地图 + Canvas 粒子流，Vite + Vue 风格 Web 仪表盘

### ⑤ 端到端 Pipeline
`采集 → 清洗 → 分析 → 报告 → PDF` 一键自动化：
```python
pipe.add_crawl().add_clean().add_analyze().add_report().add_export_pdf()
```

### ⑥ 极小体积，U 盘即用
整个项目 **37MB**，MIT 开源协议，**一根 U 盘就能带走**。

---

## 🏗 技术架构

```
                    ┌──────────────────────┐
                    │   insight CLI 入口       │
                    │   "多源情报融合 · 决策"  │
                    └──────────┬───────────┘
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                     ▼
   ┌──────────────┐   ┌──────────────┐    ┌──────────────┐
   │ 8 平台爬虫    │   │ 7 分析模型   │    │ Web UI       │
   │ Playwright   │   │ 4 定量+3 定性 │    │ Flask + Vite │
   └──────────────┘   └──────────────┘    └──────────────┘
          │                    │                     │
          └────────────────────┼─────────────────────┘
                               ▼
                    ┌──────────────────────┐
                    │   AIAgent 引擎        │
                    │   520 文件 · 自研内核  │
                    │   懒加载 · 流式 · 记忆 │
                    └──────────────────────┘
```

| 指标 | 数据 |
|---|---|
| 自写代码 | ~3,000 行 Python |
| Agent 内核 | 520 文件，37MB |
| LLM | DeepSeek（可替换 OpenAI 兼容 API） |
| 爬虫平台 | **8** 个 |
| 分析模型 | **7** 个（4 定量 + 3 定性） |
| Web 端示例 | 城市餐饮热区图（高德 + Canvas 粒子） |
| 冷启动 | **~130ms** |

---

## 🚀 快速开始

### 1️⃣ 零门槛：双击启动
- **macOS** · 双击 [`Insight Agent.app`](Insight%20Agent.app) 或 [`启动 Insight Agent.command`](启动%20Insight%20Agent.command)
- **Windows** · 双击 [`启动 Insight Agent.bat`](启动%20Insight%20Agent.bat)

图形化启动器会自动检查依赖、创建配置文件、引导配置 DeepSeek API Key、打开 Web 工作台。  
📖 详细：[`普通用户使用指南`](docs/普通用户使用指南.md)

### 2️⃣ 开发者：命令行
```bash
# 克隆
git clone https://github.com/ZheLeiQIAN/Insight-Agent.git
cd Insight-Agent

# 虚拟环境
python3 -m venv venv && source venv/bin/activate

# 装依赖
pip install -r requirements.txt
playwright install chromium

# 配置 API Key
cp .env.example .env
# 编辑 .env 写入 DEEPSEEK_API_KEY=sk-xxx
```

### 3️⃣ 启动
```bash
# 全局命令
./setup.sh && insight

# 或直接跑
python3 main.py

# 启动城市热区图 demo
cd web/city_heatmap && npm run dev
```

### 4️⃣ 典型工作流
```
insight 启动 → 看到 ASCII 艺术字欢迎页
   ↓
选择模式：
   [1] 抓取新数据    → 手动选平台
   [2] 分析已有数据   → 从本地文件开始
   [3] 描述需求       → 自然语言启动爬虫
   ↓
数据预览 → AI 打招呼并列出分析能力
   ↓
持续对话：指挥 AI 做分析
   ↓
可选：生成报告 / 导出 PDF
```

### 5️⃣ 无 API Key 也能用
即使没有 DeepSeek Key，以下功能仍可用：
- ✅ 8 个平台的数据采集
- ✅ 数据清洗和预处理
- ✅ 定量分析（统计 / 情感 / 词频 / 时间序列）
- ❌ 定性分析（需 LLM）
- ❌ AI 对话（需 LLM）

---

## 🧩 子项目导览

| 路径 | 说明 | 栈 |
|---|---|---|
| [`main.py`](main.py) | CLI 主入口（ANSI Shadow 欢迎页） | Python · Rich · pyfiglet |
| [`chat/`](chat) | AI 对话 + Agent 调度 | DeepSeek · Function Calling |
| [`crawlers/`](crawlers) | 8 平台爬虫（统一反检测） | Playwright |
| [`analysis/`](analysis) | 7 个分析模型 | SnowNLP · jieba · LLM |
| [`web/`](web) | Web UI 工作台 | Flask · Vite |
| [`web/city_heatmap/`](web/city_heatmap) | 城市餐饮热区图 Demo | AMap · Canvas 粒子流 |
| [`agent_kernel/`](agent_kernel) | 自研 AIAgent 内核（懒加载） | Hermes-style |
| [`docs/`](docs) | BP / 用户指南 / CLI 指南 | Markdown |

---

## 💼 商业化路径

### 路径 A：SaaS 云端版
| 套餐 | 价格 | 能力 |
|---|---|---|
| **Free** | ¥0 | 3 次 / 月 · 1 平台 · HTML 报告 |
| **Pro** | ¥199 / 月 | 无限分析 · 8 平台 · PDF / PPT |
| **Team** | ¥699 / 月 | 5 人协作 · API 接口 · 数据看板 |

- ✅ 零部署、手机可用
- ⚠️ 需 IP 池 + 验证码服务应对反爬

### 路径 B：企业本地部署
> **¥30,000 - 80,000 / 年** · 源码交付 + 定制爬虫 + 内网部署 + 培训

- ✅ 高客单价、客户粘性强
- ⚠️ 销售周期长、需技术支持团队

### 路径 C：开源 + 增值服务（推荐）
```
MIT 开源版            → GitHub 获取用户 + 社区共建
  ├─ 定制爬虫开发       ¥5,000 - 20,000 / 个
  ├─ 企业内训           ¥10,000 - 30,000 / 场
  ├─ 私有化部署服务      ¥50,000 起
  └─ 行业解决方案模板     ¥100,000+ / 行业
```

- ✅ 用户拉新成本低、品牌口碑好
- ✅ 增值服务可标准化交付

---

## 🛣 路线图

| 阶段 | 目标 | 状态 |
|---|---|---|
| **V1.0** · 已完成 | 8 平台爬虫 + 7 分析模型 + 双界面 + Agent 内核 | ✅ |
| **V1.1** · 进行中 | 城市热区图 Demo（V4.5）· 实时粒子流 · 智能体对话 | 🚧 |
| **V2.0** · Q4 2026 | SaaS 云端版 · 多租户 · 计费系统 | 📋 |
| **V2.5** · Q1 2027 | 行业垂直模板（餐饮 / 电商 / 舆情） | 📋 |
| **V3.0** · Q2 2027 | 多模态（图 / 视频 / 语音分析） | 📋 |

---

## 📊 关键指标

| 维度 | 当前 |
|---|---|
| 自写代码 | **~3,000 行** Python |
| Agent 内核 | **520 文件** · 37MB |
| 爬虫平台 | **8** |
| 分析模型 | **7**（4 定量 + 3 定性） |
| 冷启动 | **130ms** |
| 报告输出 | **HTML / PDF / PPT** 三态 |
| 部署形态 | 终端 + Web + 单页 Demo |
| 许可证 | **MIT** |

---

## 🤝 团队与贡献

- **作者**：[ZheLeiQIAN](https://github.com/ZheLeiQIAN) · [qianzhelei@gmail.com](mailto:qianzhelei@gmail.com)
- **贡献**：欢迎 PR、Issue、Feature Request
- **社区**：GitHub Discussions · 微信群（见 [`docs/普通用户使用指南`](docs/普通用户使用指南.md)）

---

## 📄 许可证

```
MIT License

Copyright (c) 2026 ZheLeiQIAN

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software...
```

详见 [`LICENSE`](LICENSE)。

---

## 🙏 致谢

- 灵感来源：[Hermes Agent](https://github.com/agent) · [LangChain](https://github.com/langchain-ai/langchain) · [Playwright](https://github.com/microsoft/playwright)
- LLM 服务：[DeepSeek](https://platform.deepseek.com/)
- 地图数据：[高德开放平台](https://lbs.amap.com/)

---

<div align="center">

**⭐ 如果这个项目对你有帮助，欢迎 Star · Fork · PR ⭐**

[🐛 报告 Bug](https://github.com/ZheLeiQIAN/Insight-Agent/issues) · [✨ 提 Feature](https://github.com/ZheLeiQIAN/Insight-Agent/issues/new) · [💬 Discussions](https://github.com/ZheLeiQIAN/Insight-Agent/discussions)

<sub>Built with ❤️ by ZheLeiQIAN · 2026</sub>

</div>
