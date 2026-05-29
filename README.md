# Insight Agent

> 🤖 一句话描述需求，自动采集全网数据，AI 智能分析生成报告
>
> Crawl · Clean · Analyze · Report · Chat — Powered by DeepSeek

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)]()

**支持平台**：知乎 · B站 · 小红书 · 抖音 · 知网 · 天猫 · 京东 · 豆瓣

---

## 一、项目概述

Insight Agent 是一个**完全独立可分发的 AI 数据分析智能体**，集成多平台数据采集、数据清洗、智能分析、可视化报告生成和持续对话能力。面向学术研究者、数据分析师和商业决策者，将"爬虫→清洗→分析→报告→问答"全流程闭环为一个命令行工具。

**核心理念**：不是"先跑代码再问 AI"，而是 **AI 主持分析全程**——AI 直接查看数据、动态决定分析方法、写 Python 执行、呈现结论、接受追问。

---

## 二、技术架构

```
                         ┌─────────────────────────┐
                         │     Insight CLI 入口         │
                         └───────────┬─────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
     ┌────────────────┐    ┌────────────────┐    ┌────────────────┐
     │   ui/          │    │   crawlers/    │    │   analysis/    │
     │   欢迎页+菜单   │    │   8平台爬虫    │    │   10个分析工具  │
     └────────────────┘    └────────────────┘    └────────────────┘
              │               │       │                   │
              │               ▼       ▼                   ▼
              │      ┌──────────────────────┐    ┌────────────────┐
              │      │   common/            │    │   pipeline.py  │
              │      │   浏览器反检测       │    │   自动化流水线  │
              │      │   登录会话管理       │    └────────────────┘
              │      └──────────────────────┘            │
              │                                          ▼
     ┌────────────────┐    ┌────────────────┐    ┌────────────────┐
     │   chat/        │◄───│   config.py    │───▶│   report/      │
     │   AI分析师     │    │   状态+Key     │    │   HTML+PDF报告 │
     └────────────────┘    └────────────────┘    └────────────────┘
```

### 技术栈

| 层级 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| LLM | DeepSeek (OpenAI 兼容 API) |
| CLI | Rich |
| 爬虫 | Playwright / Selenium / requests |
| 分析 | jieba · SnowNLP · pandas · matplotlib |
| 报告 | Chart.js + HTML |
| 导出 | weasyprint → PDF |
| Web | Flask |

### 项目规模

| 指标 | 数值 |
|------|------|
| 代码行数 | ~22,000 行 |
| 文件数量 | 108 个 |
| 爬虫平台 | 8 个（知乎/B站/小红书/抖音/知网/天猫/京东/豆瓣） |
| 分析工具 | 10 个（4定量 + 3定性 + 3高级） |

---

## 三、功能清单

### 3.1 数据采集

- **8 大平台爬虫**：知乎回答、B站视频、小红书笔记、抖音评论、知网论文、天猫/京东商品评论、豆瓣图书/电影
- **自然语言启动**：说"爬抖音上关于AI的视频评论"，AI 自动选平台+配参数
- **实时进度**：采集过程实时输出采集条数，Rich 动画进度条
- **登录会话管理**：首次手动登录 → 缓存浏览器 Profile → 后续自动无头运行
- **反检测机制**：统一的 Playwright 反检测配置（隐藏 webdriver、伪造指纹等）

### 3.2 数据清洗

- **自动清洗流水线**：HTML 标签去除、实体解码、零宽字符清理
- **中文数字解析**：自动识别 "1.2万" → 12000、"3.5w" → 35000、"2亿" → 200000000
- **日期标准化**：自动转换 "3天前" → YYYY-MM-DD 等相对时间
- **智能去重**：精确/模糊去重，保留最新数据

### 3.3 数据分析

- **智能字段检测**：自动识别文本/数值/日期列，无需手动配置
- **定量分析**：描述性统计、情感分析(SnowNLP)、词频+TF-IDF(jieba)、时间序列
- **定性分析**：LLM 主题提取、内容分类、观点挖掘
- **高级分析**：评论聚类(关键词Jaccard)、用户活跃度排行、互动网络分析
- **并行执行**：6线程并发分析模型，速度提升 3-4 倍
- **结果缓存**：MD5 缓存键 + 24小时 TTL，相同数据不重复分析
- **AI 动态分析**：AI 主动写 Python 代码执行，不限于预置模型

### 3.4 报告与导出

- **HTML 可视化报告**：Chart.js 图表 + 专业排版 + 响应式设计
- **PDF 导出**：一键生成 PDF（weasyprint → playwright → 降级方案）
- **批量对比**：选多个数据文件，排队分析，产出对比报告

### 3.5 自动化流水线

- **一键 Pipeline**：采集 → 清洗 → 分析 → 报告 → PDF 全自动
- **链式调用**：`pipe.add_crawl().add_clean().add_analyze().add_report().add_export_pdf()`
- **Web API 驱动**：通过 `/api/dashboard/pipeline` 一键启动

### 3.6 AI 交互

- **AI 打招呼**：数据预览后 AI 立即分析数据，列出全部分析能力+适用性矩阵
- **流式输出**：AI 回复逐字显示，打字机效果
- **工具可视化**：Agent 调用工具全过程实时可见
- **多轮对话**：持续追问、切换方向、深度挖掘

### 3.7 Web UI 看板

- **数据预览**：在线浏览上传文件的前 N 行
- **快速统计**：一键查看字段检测、基础统计
- **工具选择分析**：从 10 个分析工具中选择执行
- **在线流水线**：通过 Web 界面启动完整 Pipeline

### 3.8 工程特性

- **配置记忆**：记住上次爬虫选择、分析偏好，下次默认
- **会话持久化**：分析到一半退出，下次 `insight` 能恢复继续
- **自适应布局**：终端宽度检测，卡片自动适配
- **登录管理**：统一的 5 平台登录状态管理，24 小时自动过期
- **日志系统**：统一日志配置，文件+控制台双输出

---

## 四、快速开始

### 普通用户：双击启动

如果你不熟悉命令行，优先使用一键启动入口：

- macOS：双击 `Insight Agent.app`，或备用双击 `启动 Insight Agent.command`
- Windows：双击 `启动 Insight Agent.bat`

图形化启动器会自动检查依赖、创建配置文件、让你选择是否配置 DeepSeek API Key，并打开本地 Web 工作台。

更详细说明见：`普通用户使用指南.md`

### 环境要求

- Python 3.10+
- macOS / Linux / Windows (WSL)
- DeepSeek API Key（用于 AI 分析功能）

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/insight-agent.git
cd insight-agent

# 2. 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装浏览器（用于爬虫）
playwright install chromium

# 5. 配置 API Key
cp .env.example .env
# 编辑 .env 文件，填入你的 DeepSeek API Key
```

### 配置 API Key

**必需配置**（用于 AI 对话和定性分析）：

1. 访问 [DeepSeek 开放平台](https://platform.deepseek.com/) 注册账号
2. 创建 API Key
3. 编辑 `.env` 文件：

```bash
DEEPSEEK_API_KEY=sk-your-api-key-here
```

**可选配置**（使用其他 OpenAI 兼容 API）：

```bash
DEEPSEEK_BASE_URL=https://api.deepseek.com  # 或其他兼容 API 地址
DEEPSEEK_MODEL=deepseek-chat                 # 或其他模型名称
```

### 启动

```bash
# 方式一：全局命令（需要先运行 setup.sh）
./setup.sh
insight

# 方式二：直接运行
python3 main.py
```

### 典型工作流

```
1. insight 启动 → 看到欢迎页
2. 选择模式：
   - [1] 抓取新数据    → 手动选平台
   - [2] 分析已有数据   → 从本地文件开始
   - [3] 描述需求       → 自然语言启动爬虫
3. 数据预览 → AI 打招呼并列出分析能力
4. 持续对话：指挥 AI 做分析
5. 可选：生成报告 / 导出 PDF
```

### 无 API Key 也能用

即使没有配置 API Key，以下功能仍然可用：
- ✅ 8 个平台的数据采集
- ✅ 数据清洗和预处理
- ✅ 定量分析（统计、情感、词频、时间序列）
- ❌ 定性分析（需要 LLM）
- ❌ AI 对话（需要 LLM）

---

## 五、商业化路径

### 5.1 产品定位

| 维度 | 描述 |
|------|------|
| 目标用户 | 高校研究者、市场分析师、新媒体运营、舆情监测团队 |
| 核心价值 | 一句话启动数据采集+分析，降低数据分析门槛 10 倍 |
| 竞品差异 | 非 SaaS/云端，本地运行；非单一功能，全流程闭环 |

### 5.2 商业模式

#### 路径 A：SaaS 云端版

```
┌─────────────────────────────────────────────┐
│              Insight Agent Cloud                │
├─────────────────────────────────────────────┤
│  Free Tier      │  Pro ($29/月)  │  Team ($99/月) │
│  ─────────────  │  ────────────  │  ────────────── │
│  3次分析/月     │  无限分析      │  5人协作        │
│  1个爬虫平台    │  8平台全开     │  API接口        │
│  HTML报告       │  PDF/PPT导出   │  定制报告模板   │
│                 │  批量对比      │  数据看板       │
└─────────────────────────────────────────────┘
```

**优势**：零部署、手机可用、数据云端存储
**挑战**：爬虫需处理反爬（需IP池+验证码服务）

#### 路径 B：企业本地部署

```
一次性授权费：￥30,000-80,000/年
内容：源码交付 + 定制爬虫 + 内网部署 + 培训
目标：舆情监测公司、品牌方市场部、高校实验室
```

**优势**：高客单价、客户粘性强
**挑战**：销售周期长、需技术支持团队

#### 路径 C：开源 + 增值服务（推荐）

```
开源版（MIT）          → GitHub 获取用户
  ↓
增值服务：
  ├── 定制爬虫开发      ￥5,000-20,000/个
  ├── 私有化部署        ￥20,000起
  ├── 培训工作坊        ￥3,000/人·天
  └── 年度技术支持      ￥10,000/年
```

**优势**：低成本获客、快速验证市场
**案例**：RStudio、Jupyter 均走此路径

#### 路径 D：垂直行业套件

| 行业 | 定制内容 | 年费 |
|------|----------|------|
| 🏫 高校科研版 | 论文爬虫+文献综述+引用分析 | ￥5,000 |
| 📊 品牌监测版 | 竞品分析模板+舆情预警 | ￥8,000 |
| 🛒 电商分析版 | 评论分析+竞品价格监控 | ￥6,000 |
| 📰 媒体监测版 | 新闻聚合+话题追踪 | ￥10,000 |

### 5.3 市场数据

| 指标 | 数据 |
|------|------|
| 中国数据分析市场规模 | ~￥500亿 (2025) |
| 舆情监测市场增速 | 年增 18% |
| 高校社科研究者数量 | ~50万人 |
| 新媒体运营从业者 | ~300万人 |
| 目标客户获取成本 (CAC) | ￥200-500 (线上) |

### 5.4 推荐路线图

```
Phase 1 (0-3月)：验证 PMF
  ├── 开源到 GitHub，获取 100+ Star
  ├── 录制 3 个演示视频
  ├── 联系 10 个种子用户免费试用
  └── 收集反馈迭代

Phase 2 (3-6月)：商业化
  ├── 上线 Pro 版（SaaS 或本地）
  ├── 发布第一个行业套件（高校科研版）
  ├── 建立文档站 + 社区
  └── 目标：50 付费用户

Phase 3 (6-12月)：规模化
  ├── 全行业套件上线
  ├── 企业版销售团队
  ├── API 对外开放
  └── 目标：MRR ￥10万+
```

### 5.5 竞争分析

| 产品 | 定位 | Insight Agent 优势 |
|------|------|----------------|
| 八爪鱼/后羿 | 可视化爬虫 | AI 分析闭环，不止采集 |
| ChatGPT Code Interpreter | AI 分析 | 本地运行+多平台爬虫 |
| 舆情通/清博 | 商业舆情 | 开源可定制，价格优势 |
| Python 脚本 | 手动分析 | 自然语言交互，降低门槛 |

---

## 六、项目结构

```
insight-agent/
├── main.py                        主流程编排
├── config.py                      配置+状态持久化
├── pipeline.py                    采集→清洗→分析→报告 自动化流水线
├── scheduler.py                   定时任务调度
├── skills.py                      分析模板管理
├── logging_config.py              日志配置
├── requirements.txt               全量依赖
├── setup.sh                       一键安装脚本
├── .env.example                   环境变量模板
│
├── ui/                            CLI界面
│   ├── banner.py                  欢迎页
│   └── menu.py                    交互式菜单+配置记忆
│
├── cli/                           CLI 命令
│   └── commands.py                交互式命令实现
│
├── crawlers/                      8平台爬虫
│   ├── runner.py                  运行器+实时输出
│   ├── common/                    公共模块
│   │   ├── browser.py             反检测浏览器配置
│   │   └── login_helper.py        统一登录会话管理
│   ├── cnki/                      知网
│   ├── zhihu/                     知乎
│   ├── bilibili/                  B站
│   ├── douyin/                    抖音
│   ├── xiaohongshu/               小红书
│   ├── tmall/                     天猫
│   ├── jd/                        京东
│   └── douban/                    豆瓣
│
├── analysis/                      分析引擎 (10个工具)
│   ├── quantitative.py            智能检测+4定量模型
│   ├── qualitative.py             3定性模型（LLM）
│   ├── advanced.py                高级分析（聚类/用户/网络）
│   ├── data_cleaner.py            数据清洗流水线
│   ├── smart_analyzer.py          AI智能分析器
│   ├── tools_registry.py          工具注册表
│   └── cache.py                   分析结果缓存
│
├── chat/                          AI交互
│   └── agent.py                   AI分析师+会话管理
│
├── report/                        报告
│   └── generator.py               HTML/Chart.js+PDF导出
│
├── web/                           Web UI
│   ├── server.py                  Flask 后端
│   └── static/                    静态资源
│
├── tools/                         辅助工具
│   ├── webui_manager.py           Web UI 管理器
│   ├── cli_enhancer.py            CLI 增强器
│   └── web.sh                     一键启动脚本
│
├── tests/                         测试套件
│   ├── test_data_cleaner.py       数据清洗测试
│   ├── test_tools_registry.py     工具注册表测试
│   └── ...                        其他测试
│
├── docs/                          文档
│   ├── CLI_GUIDE.md               CLI 使用指南
│   ├── WEB_UI_GUIDE.md            Web UI 指南
│   └── ANALYSIS_TOOLS_GUIDE.md    分析工具指南
│
├── examples/                      使用示例
│   ├── full_workflow_demo.py      完整工作流演示
│   └── analysis_tools_demo.py     分析工具演示
│
└── output/                        输出目录 (git 忽略)
    ├── data/                      爬虫数据
    └── reports/                   HTML报告
```

---

## 七、技术亮点

1. **智能字段检测**：自动推断文本/数值/日期列，零配置
2. **并行分析**：ThreadPool 6线程加速 3-4 倍
3. **流式输出**：AI 回复逐 token 显示，实时可见
4. **会话恢复**：退出自动保存，下次 `insight` 继续
5. **自然语言爬虫**：描述需求 → AI 选择平台+参数
6. **统一登录管理**：5 平台共享登录框架，Profile 目录缓存，24h 自动过期
7. **反检测浏览器**：Playwright 反指纹配置，隐藏 webdriver 特征
8. **分析结果缓存**：MD5 缓存键，相同数据不重复分析
9. **自动化流水线**：采集→清洗→分析→报告→PDF 一行代码搞定
10. **工具注册表模式**：10 个分析工具统一注册、按数据特征自动推荐
11. **数据清洗引擎**：中文数字解析、相对时间转换、HTML 清理、智能去重

---

## 八、贡献与许可

- **许可证**：MIT
- **Python 版本**：>= 3.10
- **创建时间**：2026年5月

### 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m 'Add some feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 提交 Pull Request

### 问题反馈

遇到问题？请提交 [Issue](https://github.com/your-username/insight-agent/issues)，包含：
- 操作系统和 Python 版本
- 完整的错误信息
- 复现步骤

---

## 九、常见问题

### Q1: 没有 DeepSeek API Key 能用吗？

**可以！** 以下功能无需 API Key：
- ✅ 8 个平台的数据采集
- ✅ 数据清洗和预处理
- ✅ 定量分析（统计、情感、词频、时间序列）

需要 API Key 的功能：
- ❌ 定性分析（主题提取、内容分类、观点挖掘）
- ❌ AI 对话分析

### Q2: 如何获取 DeepSeek API Key？

1. 访问 [DeepSeek 开放平台](https://platform.deepseek.com/)
2. 注册账号并完成实名认证
3. 创建 API Key
4. 复制 Key 到 `.env` 文件

### Q3: 可以用其他 LLM 吗？

**可以！** 任何 OpenAI 兼容的 API 都可以使用：

```bash
# 通义千问
DEEPSEEK_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DEEPSEEK_MODEL=qwen-turbo

# 智谱 AI
DEEPSEEK_BASE_URL=https://open.bigmodel.cn/api/paas/v4
DEEPSEEK_MODEL=glm-4

# 本地 Ollama
DEEPSEEK_BASE_URL=http://localhost:11434/v1
DEEPSEEK_MODEL=llama3
```

### Q4: 爬虫需要登录吗？

部分平台需要登录才能获取完整数据：
- **需要登录**：知乎、小红书、抖音、天猫、京东
- **无需登录**：B站、知网、豆瓣

首次使用时，系统会自动打开浏览器让你手动登录，之后会缓存登录状态（24小时有效）。

### Q5: 安装依赖失败怎么办？

```bash
# 1. 升级 pip
pip install --upgrade pip

# 2. 使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 单独安装失败的包
pip install playwright
playwright install chromium
```

### Q6: 如何更新到最新版本？

```bash
git pull origin main
pip install -r requirements.txt --upgrade
```
