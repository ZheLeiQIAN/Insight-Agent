# Agent 内核

> 本目录是 Insight-Agent 项目的 **Agent 内核** —— 源自上游
> [hermes-agent](https://github.com/NousResearch/hermes-agent) 项目的快照。
>
> ✅ 直接入库（81MB / 500+ 文件），开箱即用，clone 仓库后无需任何 setup 步骤。
> ⚠️ **不要直接修改本目录代码**——这是上游 hermes-agent 的快照，所有定制在
> 外层（`chat/`, `analysis/`, `report/`, `crawlers/`, `web/`, `ui/`）做。

## 来源

- **上游项目**：[hermes-agent](https://github.com/NousResearch/hermes-agent)
  （NousResearch 出品的 Agent 内核；支持 file/terminal/web 工具集、流式输出、
  提示缓存、子任务委派、技能系统等）
- **本仓库位置**：`agent_kernel/`（81MB / 500+ 文件 / 7,000+ 行业务代码）
- **集成日期**：2026-06-02
- **集成方式**：直接物理复制到项目文件夹（区别于软链接方案：开箱即用、clone 后即用）

## 在我们项目中的角色

`agent_kernel` 是 Insight-Agent 的 **第 1 层（依赖层）**：

```
┌─────────────────────────────────────────────────────┐
│  第 3 层：应用入口                                    │
│  main.py · cli/ · ui/ · web/ · "Insight Agent.app"    │
├─────────────────────────────────────────────────────┤
│  第 2 层：业务模块（我们自己写的）                      │
│  chat/ · analysis/ · report/ · crawlers/ · webui/    │
│  依赖：agent_kernel（用 AIAgent）                     │
├─────────────────────────────────────────────────────┤
│  第 1 层：Agent 内核（第三方，几乎不改）                │
│  agent_kernel/ ←── 源自 hermes-agent 上游              │
└─────────────────────────────────────────────────────┘
```

`chat/agent.py` 里的 `InsightAnalyst` 类通过 `AIAgent` 接入：

```python
from run_agent import AIAgent   # agent_kernel/run_agent.py

self.agent = AIAgent(
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
    model=LLM_MODEL,
    provider="deepseek",
    enabled_toolsets=["file", "terminal", "web"],
    max_iterations=30,
    ...
)
```

`AIAgent.run_conversation(...)` 调用 LLM，AI 决定是否调工具，工具执行结果回传 LLM，循环直到 `text_response` 或 `max_iterations`。

## 8 个加载的工具

| 工具 | 工具集 | 能力 |
|---|---|---|
| `read_file` | file | 读文件（含分页、行范围、glob） |
| `write_file` | file | 写文件（自动建目录、lint、原子写） |
| `patch` | file | 局部修改（增删改行块） |
| `search_files` | file | 文件/目录搜索 |
| `terminal` | terminal | 同步执行 shell 命令 |
| `process` | terminal | 后台进程（fire-and-forget） |
| `web_search` | web | 联网搜索（DDG / Exa / Tavily 多 provider） |
| `web_extract` | web | 抓取 URL 全文（CSS 选择器过滤） |

我们项目只启用了这 8 个。其他 toolset（`browser-cdp`, `computer_use`,
`discord`, `homeassistant`, `kanban`, `mcp` 等）因为不需要或缺 API key 未启用。

## 集成 + 验证记录

- ✅ `from run_agent import AIAgent` 可用
- ✅ AIAgent 加载 8 个工具（`file` / `terminal` / `web`）
- ✅ AI 端到端能真调工具（write_file smoke test：AI 主动写文件到磁盘）
- ✅ 流式输出 + token 缓存（96% 命中）+ tool call 可视化（`📞 Tool 1: write_file(...)`）
- ✅ TUI 系统层有兜底：用户在 AI 对话中输入"导出报告"等关键词时，系统自动生成报告

## 同步上游（如何升级 hermes-agent 版本）

如需更新到 hermes-agent 上游最新版（修 bug / 加新工具 / 升级 model 适配）：

```bash
# 1. 备份当前快照（万一新版本有 break）
cp -R agent_kernel agent_kernel.bak

# 2. 同步上游
cd /Users/qianzhelei/Downloads/Insight\ Agent\ BP初稿
rm -rf Insight-Agent-main/agent_kernel
cp -R hermes-agent-main Insight-Agent-main/agent_kernel

# 3. 跑测试看会不会 break
cd Insight-Agent-main
python3 -m unittest tests.test_report_generator

# 4. 烟测：AI 调工具
python3 -c "
import sys; sys.path.insert(0, '.')
from chat.agent import InsightAnalyst
from pathlib import Path
import tempfile
with tempfile.TemporaryDirectory() as t:
    p = Path(t)/'x.csv'; p.write_text('a,b\n1,2\n', encoding='utf-8')
    a = InsightAnalyst([{'a':1,'b':2}], p)
    print(type(a.agent).__name__, '实例化成功')
"
```

## 修改约定

**⚠️ 不要直接改 `agent_kernel/` 下的代码**——下次同步上游会被覆盖。

需要定制时：
1. **优先在外层加抽象**：在 `chat/agent.py` / `main.py` 里包装 AIAgent
2. **实在要改内核**：在 `agent_kernel/` 改完后，**立刻**在 `chat/` 加补丁函数，
   避免下次同步丢失改动
3. **用 git**：如果项目有 git 仓库，建议在 `agent_kernel/` 之外加自定义层

## 日志位置

- `output/app.log` — Insight-Agent 自己的日志（含 chat.agent 的 WARNING / INFO）
- `~/.hermes/logs/agent.log` — hermes-agent 的工具调用日志（如需调试 AI 工具循环可看这里）

## 上游资源

- **GitHub**：<https://github.com/NousResearch/hermes-agent>
- **文档**：<https://hermes-agent.dev/>
- **AGENTS.md**（本目录自带）：hermes-agent 上游项目的开发指南（1600+ 行）
  - 包含 AIAgent 类签名、工具开发规范、插件系统、皮肤主题、技能系统、调度器、
    Kanban 多 agent 等所有内部细节
  - 想知道 hermes-agent 是怎么实现的，**直接读它**——比看代码更快
