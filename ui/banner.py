"""Insight Agent — 启动欢迎界面（学术现代风 V2）

布局：
  1. 顶部装饰线 ═
  2. pyfiglet big 字体 INSIGHT 艺术字
  3. 项目名 + 版本号 + 副标题
  4. 中部分隔线 ═
  5. 两栏并排：核心能力 2x2  |  工作流一字横
  6. 系统状态条（DEEPSEEK_KEY · Python · 平台 · 时间）
  7. 底部装饰线 + 操作提示
"""

import os
import platform
from datetime import datetime

from rich.console import Console
from rich.align import Align
from rich.text import Text
from rich.rule import Rule
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

VERSION = "1.0.0"
TAGLINE = "多源情报融合 AI 平台 · 跨域数据智能决策系统"
SUBTAGLINE = "网络空间 · 物理世界 · 城市商业 — 三空间数据融合，统一 AI 主持人驱动决策闭环。"


# ============================================================
# ASCII 艺术字（双段并排 · 仿 Hermes 风格）
# ============================================================
HERMES_FONT_CANDIDATES = ("ansi_shadow", "ansi_regular", "big")


def _get_banner() -> list[str]:
    """用 ansi_shadow 字体生成 INSIGHT | AGENT 双段并排

    返回的每行已带 ANSI 颜色标记（青 + 黄），可直接 console.print。
    离线时退回纯文本。
    """
    left_text = "INSIGHT"
    right_text = "AGENT"

    def _try_gen(text: str, font: str) -> list[str] | None:
        try:
            import pyfiglet
            art = pyfiglet.figlet_format(text, font=font, width=200)
            lines = [l.rstrip() for l in art.split("\n") if l.strip()]
            return lines or None
        except Exception:
            return None

    left = right = None
    for font in HERMES_FONT_CANDIDATES:
        left = _try_gen(left_text, font)
        right = _try_gen(right_text, font)
        if left and right:
            break

    # 离线备选（手写 box-drawing INSIGHT + AGENT）
    if not (left and right):
        left = [
            "██╗███╗   ██╗███████╗██╗ ██████╗ ██╗  ██╗████████╗",
            "██║████╗  ██║██╔════╝██║██╔════╝ ██║  ██║╚══██╔══╝",
            "██║██╔██╗ ██║███████╗██║██║  ███╗███████║   ██║   ",
            "██║██║╚██╗██║╚════██║██║██║   ██║██╔══██║   ██║   ",
            "██║██║ ╚████║███████║██║╚██████╔╝██║  ██║   ██║   ",
            "╚═╝╚═╝  ╚═══╝╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ",
        ]
        right = [
            " █████╗  ██████╗ ███████╗███╗   ██╗████████╗",
            "██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝",
            "███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ",
            "██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ",
            "██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ",
            "╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ",
        ]

    # 横向并排（左青右黄，中间 3 空格间距）
    H = max(len(left), len(right))
    W1 = max(len(l) for l in left)
    GAP = "   "
    out: list[str] = []
    for i in range(H):
        l = left[i] if i < len(left) else ""
        r = right[i] if i < len(right) else ""
        out.append(f"[bold bright_cyan]{l:<{W1}}[/]{GAP}[bold bright_yellow]{r}[/]")
    return out


# ============================================================
# 能力卡片 2x2
# ============================================================
def _cap_card(icon: str, title: str, examples: str, color: str) -> Panel:
    body = Text()
    body.append(f"  {icon}  ", style=f"bold {color}")
    body.append(title, style=f"bold {color}")
    body.append("\n")
    body.append(f"  {examples}", style="dim")
    return Panel(
        body,
        border_style=color,
        box=box.ROUNDED,
        padding=(0, 1),
    )


def _capabilities_panel() -> Panel:
    grid = Table.grid(padding=(0, 1))
    grid.add_column()
    grid.add_column()
    grid.add_row(
        _cap_card("🕷 ", "8 平台爬虫", "知乎 / B站 / 小红书 / 抖音 / 京东 …", "cyan"),
        _cap_card("📊 ", "10 分析工具", "情感 / 词频 / 聚类 / 主题 / 趋势 …", "green"),
    )
    grid.add_row(
        _cap_card("🤖 ", "AI 深度对话", "DeepSeek 驱动 · 自然语言查询", "yellow"),
        _cap_card("📄 ", "自动报告", "Markdown / HTML / PDF 三态输出", "magenta"),
    )
    return Panel(
        grid,
        border_style="bright_cyan",
        box=box.HEAVY,
        title="[bold bright_cyan] 核心能力 [/]",
        title_align="center",
        padding=(1, 1),
    )


# ============================================================
# 工作流（一字横 + emoji 副线）
# ============================================================
def _workflow_panel() -> Panel:
    body = Text()
    body.append("\n  ")
    body.append("① 采集", style="bold cyan")
    body.append("  ──→  ", style="dim")
    body.append("② 清洗", style="bold green")
    body.append("  ──→  ", style="dim")
    body.append("③ 分析", style="bold yellow")
    body.append("  ──→  ", style="dim")
    body.append("④ 报告", style="bold magenta")
    body.append("  ──→  ", style="dim")
    body.append("⑤ 问答", style="bold red")
    body.append("\n\n  ")
    body.append("🕸 数据源", style="dim")
    body.append(" · ", style="dim")
    body.append("🧹 ETL", style="dim")
    body.append(" · ", style="dim")
    body.append("📈 洞察", style="dim")
    body.append(" · ", style="dim")
    body.append("📄 交付", style="dim")
    body.append(" · ", style="dim")
    body.append("💬 交互", style="dim")
    body.append("\n")
    return Panel(
        body,
        border_style="dim",
        box=box.ROUNDED,
        title="[bold dim] 工作流 [/]",
        title_align="center",
        padding=(0, 1),
    )


# ============================================================
# 系统状态条
# ============================================================
def _status_panel() -> Panel:
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    deepseek_ok = bool(deepseek_key) and deepseek_key != "sk-your-key-here"
    py_ver = platform.python_version()
    os_ver = f"{platform.system()} {platform.release()}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if deepseek_ok:
        ds_cell = Text.assemble(("◉ ", "bold green"), ("DEEPSEEK_API_KEY  ", "bold"), ("已配置 ✓", "green"))
    else:
        ds_cell = Text.assemble(("○ ", "bold yellow"), ("DEEPSEEK_API_KEY  ", "bold"), ("未配置 ⚠", "yellow"))

    grid = Table.grid(padding=(0, 3), expand=True)
    grid.add_column(justify="left", ratio=2)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="right", ratio=1)
    grid.add_row(
        ds_cell,
        Text.assemble(("◉ ", "bold green"), (f"Python {py_ver}", "bold")),
        Text.assemble(("◉ ", "bold green"), (os_ver, "bold")),
        Text.assemble(("▸ ", "bold cyan"), (now, "dim")),
    )
    return Panel(
        grid,
        border_style="dim",
        box=box.HEAVY,
        title="[bold dim] 系统状态 [/]",
        title_align="left",
        padding=(0, 1),
    )


# ============================================================
# 安全合规声明（竞赛向评委展示）
# ============================================================
def _security_panel() -> Panel:
    """安全合规声明 — 基于 OpenClaw Skill 调度机制的内建安全体系"""
    body = Text()

    # 核心理念
    body.append("\n")
    body.append("  核心理念：", style="bold bright_white")
    body.append("「AI 审 AI」— 以 Skill 调度机制本身作为安全基础设施\n", style="dim cyan")
    body.append("  通过专用安全 Skill 对其他 Skill 的调用行为、数据流转、权限申请进行实时审计，\n", style="dim")
    body.append("  形成「Skill 审 Skill」自治风控闭环，无需依赖外部人工巡检。\n\n", style="dim")

    # 四个安全 Skill
    body.append("  ")
    body.append("🛡 ", style="bold green")
    body.append("采集审计 Skill", style="bold green")
    body.append("\n", style="")
    body.append("     URL 白名单前置校验 · robots.txt 自动合规检测 · 违规请求实时拦截告警\n", style="dim")
    body.append("     采集量超阈值自动熔断，规避爬虫法律风险，防止源站 IP 被封禁\n\n", style="dim")

    body.append("  ")
    body.append("🔐 ", style="bold yellow")
    body.append("权限管控 Skill", style="bold yellow")
    body.append("\n", style="")
    body.append("     最小权限 Token 动态注入 · 调用完毕即时吊销 · 跨租户二次鉴权\n", style="dim")
    body.append("     INSIGHT_API_KEY 环境变量隔离 + X-API-Key 中间件 · 变更审计链 ≥180 天\n\n", style="dim")

    body.append("  ")
    body.append("🧱 ", style="bold cyan")
    body.append("数据安全 Skill", style="bold cyan")
    body.append("\n", style="")
    body.append("     视频推理本地执行（OpenCV DNN + YOLOv4-tiny），原始帧物理不出店\n", style="dim")
    body.append("     传输 TLS 1.3 + 存储 AES-256 · 用户数据禁入模型训练管道 · 上传 50MB 硬限制\n\n", style="dim")

    body.append("  ")
    body.append("🚨 ", style="bold red")
    body.append("告警响应 Skill", style="bold red")
    body.append("\n", style="")
    body.append("     CVE 高危漏洞 24h 热修复 SLA · 异常调用自动熔断 · Webhook 实时推送\n", style="dim")
    body.append("     三子系统（9527/9528/9530）独立进程隔离 · 会话 24h TTL · 任务 1h 自动清理\n\n", style="dim")

    body.append("  ✅ ", style="bold green")
    body.append("工信部", style="bold green")
    body.append("「六要六不要」", style="bold bright_white")
    body.append("逐项对标 → 完整应对措施详见商业计划书「安全风险应对方案」独立章节\n", style="dim")

    return Panel(
        body,
        border_style="green",
        box=box.HEAVY,
        title="[bold green]🛡 安全合规声明[/]",
        title_align="left",
        padding=(0, 1),
    )


# ============================================================
# 入口
# ============================================================
def show_welcome():
    """显示欢迎界面（V2 学术现代风）"""
    console.clear()
    term_w = console.width

    # 顶部装饰线
    console.print()
    console.print(Rule(style="bright_cyan", characters="═"))

    # ASCII 艺术字（居中）
    banner = _get_banner()
    for line in banner:
        pad = max(0, (term_w - len(line)) // 2)
        console.print(" " * pad + f"[bold bright_cyan]{line}[/]")

    # 项目名 + 版本号 + 副标题
    console.print()
    name_line = Text()
    name_line.append("  Insight  ", style="bold bright_white")
    name_line.append("Agent", style="bold bright_cyan")
    name_line.append(f"  v{VERSION}", style="dim cyan")
    console.print(Align.center(name_line))
    console.print(Align.center(Text(f"— {TAGLINE} —", style="dim italic")))
    console.print(Align.center(Text(SUBTAGLINE, style="dim italic")))

    # 中部分隔线
    console.print()
    console.print(Rule(style="bright_cyan", characters="═"))

    # 两栏并排
    cap = _capabilities_panel()
    flow = _workflow_panel()
    # 用 Table.grid 实现两栏（能力区稍宽，工作流稍宽以容纳 emoji 副线）
    grid = Table.grid(expand=True, padding=(0, 1))
    grid.add_column(ratio=3)
    grid.add_column(ratio=2)
    grid.add_row(cap, flow)
    console.print(grid)

    # 系统状态条
    console.print()
    console.print(_status_panel())

    # 安全合规声明（竞赛展示）
    console.print()
    console.print(_security_panel())

    # 底部装饰 + 操作提示
    console.print()
    console.print(Rule(style="bright_cyan", characters="═"))
    console.print(Align.center(Text(
        "💡 输入 0-7 选择主菜单  ·  help 查看命令  ·  exit 退出",
        style="dim italic",
    )))
    console.print()
