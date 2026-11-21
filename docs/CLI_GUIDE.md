# Insight Agent CLI 使用指南

> Insight Agent 的命令行（CLI）是一个基于菜单的交互式工具：启动后选择工作模式，按提示完成参数、确认、执行，必要时进入 AI 分析师持续对话。
>
> 本指南与你今天在终端里看到的界面一一对应。

---

## 🚀 快速开始

### 启动方式（任选其一）

| 入口 | 命令 | 适用人群 |
|------|------|----------|
| **macOS 一键** | 双击 `Insight Agent.app` | 普通用户（无需命令行） |
| **Python 入口** | `python3 main.py` | 开发者、调试 |
| **全局命令** | `bash setup.sh` 之后 `insight` | 想在任何目录启动 |

```bash
# 方式 A：直接跑（最常用）
cd insight-agent
python3 main.py

# 方式 B：先安装全局命令（写入 ~/.local/bin/insight）
bash setup.sh
insight        # 之后在任何目录都可以直接启动
```

`setup.sh` 实际会做四件事：

1. `pip install -r requirements.txt`
2. `python3 -m playwright install chromium`
3. 在 `~/.local/bin` 写入一个 `insight` 启动脚本（等价于 `python3 main.py`），同时还会写入 `insight-web`（直接打开 Web UI）
4. 跑一次冒烟检查，确认所有模块能 import

> 历史上存在过 `tools/cli_enhancer.py`（另一套带 `insight crawl` / `Insight ›` 提示符的命令式 CLI），已于本次清理中删除。
> 现在的 CLI **只有 `python main.py` 这一条入口**；`insight` 只是一个指向 `main.py` 的 shell 别名。

### 验证系统是否装好

```bash
python3 validate_system.py
# ✅ 配置 / 模块 / 工具 / 分析 / Web 五项检查
```

---

## 📋 主菜单（7 种工作模式）

启动后第一眼看到的是一个 **三列数字菜单**。输入编号（1-7）或 `q` 退出。

```
╔═══════════════════════════════════════════════════════════╗
║  1. 🕷 抓取新数据    │ 4. 📋 分析模板      │ 7. 🔑 登录管理  ║
║  2. 📂 分析已有数据   │ 5. 📅 定时任务                      ║
║  3. 💬 自然语言       │ 6. 🌐 Web UI                       ║
╚═══════════════════════════════════════════════════════════╝

选择 [1]:
```

| # | 模式 key | 名称 | 作用 | 典型后续 |
|---|----------|------|------|----------|
| 1 | `crawl`    | 🕷 抓取新数据    | 选平台 → 填参数 → 跑爬虫 → 自动进入分析 | 数据预览 → AI 分析师 |
| 2 | `existing` | 📂 分析已有数据  | 从本地 CSV/XLSX/JSON 选一个（或批量选多个） | 数据预览 → AI 分析师 |
| 3 | `nl_crawl` | 💬 自然语言      | 用一句话描述需求，AI 选平台+配参数 | 同 1 |
| 4 | `template` | 📋 分析模板      | 选预设套餐（一键跑多模型） | 自动生成报告 |
| 5 | `schedule` | 📅 定时任务      | 添加/查看/删除/立即执行定时爬取 | 持久化到 `output/scheduler.json` |
| 6 | `web`      | 🌐 Web UI        | 启动 Flask 工作台，自动打开浏览器 | 浏览器内操作 |
| 7 | `login`    | 🔑 登录管理      | 预登录知乎/小红书/抖音/天猫/京东 | 浏览器手动登录一次 |

输入编号后，**每一步都是引导式的**——不会出现让你猜的 `--flag`。

### 会话恢复

如果之前 AI 分析师对话中保存过会话，启动时会出现：

```
╭──────────────────────────────────────╮
│ 📋 发现已保存的分析会话                │
╰──────────────────────────────────────╯

  #  时间                数据文件           对话
  1  2026-06-01 14:30   zhihu_ai.csv      12轮
  2  2026-05-29 09:12   tmall_reviews.csv 4轮
  n  —                  开始新分析         —

选择 [n]:
```

输入 `1`/`2` 直接回到上次的话题；输入 `n`（或回车）走主菜单。

---

## 🎯 典型工作流

### 模式 1：抓取新数据（`crawl`）

```
1 → 选平台（zhihu / bilibili / xiaohongshu / douyin / cnki / tmall / jd / douban）
   → 填参数（关键词、URL 等，由 Rich Prompt 一步步问）
   → 自动检查登录态（仅需登录的平台，见模式 7）
   → 确认运行 → 实时进度条
   → 自动定位最新输出文件
   → 数据预览（字段类型自动检测 + 前 10 行表格）
   → 进入 AI 分析师对话
   → 退出对话后自动生成专业报告（Markdown + HTML），见"报告输出"小节
```

> **报告输出**：分析完成后，CLI 会在 `output/reports/` 下自动生成两份报告：
> - `analysis_<时间戳>.md` — 可贴 IM、可直接 markdown 渲染
> - `analysis_<时间戳>.html` — 含图表 + 打印样式，`Ctrl+P` 直接出 PDF
>
> 报告结构为七段式：执行摘要 → 数据说明 → 工具说明 → 分析结果 → 关键发现 → 启示与预测 → 附录数据预览。配 LLM API 时自动启用"执行摘要/关键发现/启示预测"三段增强；无 LLM 时走降级模板，依然能出完整报告。

### 模式 2：分析已有数据（`existing`）

```
2 → 在 output/data 下选一个 CSV/XLSX/JSON
   → 数据预览 → 确认
   → 进入 AI 分析师对话
```

**批量对比**：在文件选择后，CLI 会问 `批量对比多个数据文件？`，选 `y` 后会进入多选，逐个跑分析并产出对比报告（`run_batch_analysis`）。

### 模式 3：自然语言（`nl_crawl`）

```
3 → 用中文描述需求，例如：
     "爬知乎上关于 LLM Agent 的 100 条回答"
   → AI 自动选平台（zhihu）+ 配参数
   → 显示理由，确认执行
   → 同模式 1 后半段
```

需要 `DEEPSEEK_API_KEY`（或自定义 OpenAI 兼容 API）。未配置会在提示后直接退出。

### 模式 4：分析模板（`template`）

5 个内置模板（定义在 `skills.py`）：

| 模板 | 包含的模型 | 适用场景 |
|------|-----------|----------|
| 🏷️ 品牌舆情审计 | basic_stats + sentiment + word_freq + theme_extraction + insight_mining | 品牌口碑 |
| ⚡ 快速扫描 | basic_stats + sentiment + word_freq | 3 分钟出结果 |
| 🔬 深度挖掘 | 全 7 个模型 | 详尽报告 |
| 🥊 竞品对比 | basic_stats + sentiment + word_freq | 两份数据对比 |
| 📈 趋势追踪 | basic_stats + time_series + sentiment | 时序变化 |

```
4 → 选模板 → 选数据文件 → 后台跑 6 线程并发 → 生成报告
   → 问 `进入AI对话？` 可继续追问
```

### 模式 5：定时任务（`schedule`）

```
5 → 操作 [add/remove/run/q]:
   add   → 选爬虫 → 填参数 → 间隔（小时）→ 写入 scheduler.json
   remove → 输入任务 ID 删除
   run   → 立即执行所有任务一次
```

### 模式 6：Web UI（`web`）

```
6 → 选择模式 [1=前台 / 2=后台]，默认 2
   → 启动 Flask (127.0.0.1:9527)
   → 等待 /api/healthz 通过（15s 超时）
   → 浏览器自动打开 http://127.0.0.1:9527
   → 后台模式：终端立刻可继续用
```

### 模式 7：登录管理（`login`）

```
7 → 显示 5 个平台当前登录状态
   → 选平台 → 弹浏览器让你手动登录一次
   → 登录态写入 .session_state.json，24h 内复用
```

哪些平台需要登录见 `config.REQUIRES_LOGIN`：`douyin, zhihu, xiaohongshu, tmall, jd`。

---

## 💬 AI 分析师对话

进入模式 1/2/3 完成后，CLI 都会跳到这个对话循环（`chat_loop_analyst`）：

```
  💬 你 › 帮我做情感分析
                                          ┌──────────────────────┐
                                          │ 🤖 AI 分析师          │
                                          │ 数据情感倾向 78% 正面…│
                                          └──────────────────────┘

  💬 你 › 词<TAB>       ← Tab 自动补全
  💬 你 › 词频统计
```

### 快捷指令（Tab 补全可用）

| 指令 | 含义 |
|------|------|
| `情感分析` | 跑情感模型 |
| `词频统计` | 跑 jieba 词频 |
| `趋势分析` | 跑时间序列 |
| `总结`     | LLM 出总结 |
| `建议`     | LLM 出建议 |
| `help`     | 列出当前数据可执行的所有分析 |
| `exit`     | 退出对话（自动保存会话到 `output/sessions/`） |

> 补全的关键词是固定的 7 个；其他自由提问（如"和上个月比呢"）直接输入即可，不走补全。

对话支持 `Ctrl+C` 优雅退出，会自动写入 `output/sessions/<id>.json`，下次启动会出现在"会话恢复"列表里。

---

## 🔧 高级用法

### 自动化脚本里调用

CLI 是交互式的，不能直接用管道喂命令。如果要在脚本里跑完整流程，调用内部的 Python API：

```python
import sys
from pathlib import Path
sys.path.insert(0, "/path/to/insight-agent")

from main import load_data, run_analysis_flow
from cli._dispatch import run_single_quant
from report import generate_report

data = load_data(Path("output/data/zhihu_ai.csv"))
results = run_single_quant(data, "sentiment", Path("output/data/zhihu_ai.csv"))
generate_report(
    {"platform": "本地文件", "name": "zhihu_ai.csv"},
    results,
    Path("output/data/zhihu_ai.csv"),
    Path("output/reports"),
)
```

### Pipeline 一键跑

```python
from pipeline import Pipeline
Pipeline().add_crawl("zhihu", {"keyword": "AI", "max": 100}) \
          .add_clean() \
          .add_analyze() \
          .add_report() \
          .add_export_pdf() \
          .run()
```

### 定时任务持久化

`scheduler` 写 `output/scheduler.json`，重启后任务保留。看任务列表直接走模式 5。

---

## 📊 工具系统

CLI 里跑的每个分析，背后都是 `analysis.tools_registry` 里的一个工具。Python 端可以直接调用：

```python
from analysis.tools_registry import execute_tool
from pathlib import Path

data = [
    {"content": "这个产品非常好", "score": "85"},
    {"content": "体验很差", "score": "45"},
]

result = execute_tool("sentiment_analysis", data, Path("data.csv"))
print(result)
```

注册表里共 10 个工具，分四类：

| 类别 | 工具 | 需要字段 |
|------|------|----------|
| 定量 | `basic_stats` | 任意 |
| 文本 | `sentiment_analysis` | text |
| 文本 | `word_frequency` | text |
| 时间 | `time_series` | date |
| 定性 | `theme_extraction` | text |
| 定性 | `content_category` | text |
| 定性 | `insight_mining` | text |
| 高级 | `comment_cluster` | text |
| 高级 | `user_activity` | author |
| 高级 | `interaction_network` | (author, reply) |

完整字段说明见 [ANALYSIS_TOOLS_GUIDE.md](ANALYSIS_TOOLS_GUIDE.md)。

---

## 🐛 故障排除

### 问题 1：启动报 `ModuleNotFoundError`

```bash
pip install -r requirements.txt
# 或
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 问题 2：爬虫说"未登录"

走主菜单 → 模式 7（登录管理）→ 选对应平台 → 浏览器弹出后手动登录一次。之后 24 小时内无需重复。

### 问题 3：Web UI 打不开 / 启动后浏览器空白

```bash
curl http://127.0.0.1:9527/api/healthz
# {"status":"ok","time":"..."}
```

- 不返回 → Flask 没起来，看终端报错（通常是 `Address already in use`）
- 返回 ok → 是浏览器缓存，强制刷新（`Cmd+Shift+R`）

### 问题 4：自然语言模式提示"未配置 API Key"

`mode 3`（自然语言）和 AI 分析师对话都依赖 LLM。在项目根目录的 `.env` 里加：

```bash
DEEPSEEK_API_KEY=sk-your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

或者换成任何 OpenAI 兼容的 API（通义千问 / 智谱 / Ollama 等）。

### 问题 5：分析报告里"定性"模型空着

定性分析（主题、分类、观点挖掘）调用 LLM，没配 API Key 会自动跳过。可以去 `.env` 配 `DEEPSEEK_API_KEY` 后重跑。

---

## 📚 相关文档

- [README.md](../README.md) — 项目总览
- [WEB_UI_GUIDE.md](WEB_UI_GUIDE.md) — Web UI 看板
- [ANALYSIS_TOOLS_GUIDE.md](ANALYSIS_TOOLS_GUIDE.md) — 10 个分析工具字段说明
- [CHANGELOG.md](../CHANGELOG.md) — 版本变更历史

---

## 🎉 总结

CLI 提供 7 种工作模式 + AI 分析师持续对话，主菜单三列布局，全程 Rich 引导式输入，零命令行参数记忆成本。

**立即开始**：

```bash
# 已经装好依赖的话
python3 main.py

# 第一次跑、想装全局命令
bash setup.sh
insight
```
