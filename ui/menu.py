"""Insight Agent - 交互式菜单"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text
from pathlib import Path
from typing import Optional, List, Tuple

from config import CRAWLER_SCRIPTS, ANALYSIS_MODELS, DATA_DIR, load_state, save_state

console = Console()


def get_term_cols() -> int:
    """获取终端可用列数"""
    return min(console.width, 100)


def select_mode() -> Optional[str]:
    """选择工作模式 — 三列布局"""
    modes = [
        ("1", "crawl",    "抓取新数据",    "选平台·采集·分析"),
        ("2", "existing", "分析已有数据",  "本地文件直接分析"),
        ("3", "nl_crawl", "自然语言",      "描述需求AI选爬虫"),
        ("4", "template", "分析模板",      "预设套餐一键执行"),
        ("5", "schedule", "定时任务",      "定时自动采集分析"),
        ("6", "web",      "Web UI",        "浏览器打开看板"),
        ("7", "login",    "登录管理",      "预登录各平台"),
        ("8", "physical", "物理世界",      "摄像头·人流·行为"),
        ("9", "cityheat", "城市热区图",    "地图·粒子流·行为分析"),
    ]
    icons = ["🕷", "📂", "💬", "📋", "📅", "🌐", "🔑", "👁", "🔥"]

    # 三列布局: [1-3] [4-6] [7-9]（3×3 网格）
    left = [(modes[i], icons[i]) for i in range(3)]
    mid = [(modes[i], icons[i]) for i in range(3, 6)]
    right = [(modes[i], icons[i]) for i in range(6, 9)]

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(width=30)
    table.add_column(width=30)
    table.add_column(width=25)

    for i in range(3):
        l_mode, l_icon = left[i]
        m_mode, m_icon = mid[i]
        l_cell = Text.from_markup(f"[bold dim]{l_mode[0]}[/]. {l_icon} [cyan]{l_mode[2]}[/]\n   [dim]{l_mode[3]}[/]")
        m_cell = Text.from_markup(f"[bold dim]{m_mode[0]}[/]. {m_icon} [cyan]{m_mode[2]}[/]\n   [dim]{m_mode[3]}[/]")
        r_cell = Text("")
        if i < len(right):
            r_mode, r_icon = right[i]
            r_cell = Text.from_markup(f"[bold dim]{r_mode[0]}[/]. {r_icon} [cyan]{r_mode[2]}[/]\n   [dim]{r_mode[3]}[/]")
        table.add_row(l_cell, m_cell, r_cell)

    console.print()
    console.print(table)
    console.print()

    try:
        choice = Prompt.ask(
            "[bold]选择[/]",
            choices=[str(i) for i in range(1, len(modes) + 1)] + ["q"],
            default="1",
        )
        if choice == "q":
            return None
        return modes[int(choice) - 1][1]
    except (ValueError, IndexError):
        return None


def select_existing_file() -> Optional[Path]:
    """选择已有的数据文件"""
    console.print()
    console.print(Panel.fit(
        "[bold cyan]选择数据文件[/]",
        border_style="cyan"
    ))

    # 扫描数据目录
    files = []
    for ext in ["*.xlsx", "*.csv", "*.json"]:
        files.extend(DATA_DIR.rglob(ext))
    files = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)

    if not files:
        console.print("  [yellow]未找到任何数据文件[/]")
        console.print(f"  [dim]请先将文件放入: {DATA_DIR}[/]")
        return None

    console.print(f"  [dim]找到 {len(files)} 个数据文件[/]")
    console.print("  [dim]输入关键词过滤文件名，留空显示全部[/]")

    keyword = Prompt.ask("  [bold]过滤[/]", default="").strip().lower()
    if keyword:
        files = [f for f in files if keyword in f.name.lower()]
        if not files:
            console.print(f"  [yellow]没有文件名包含「{keyword}」的文件[/]")
            return None
        console.print(f"  [dim]过滤后 {len(files)} 个:[/]\n")
    else:
        console.print()

    table = Table(show_header=True, header_style="bold white", border_style="dim")
    table.add_column("#", style="dim", width=4)
    table.add_column("文件名", style="cyan", width=35)
    table.add_column("大小", style="green", width=10)
    table.add_column("修改时间", style="dim", width=20)

    for i, f in enumerate(files[:20], 1):  # 最多显示20个
        size = f.stat().st_size
        size_str = f"{size/1024:.1f}KB" if size < 1024*1024 else f"{size/1024/1024:.1f}MB"
        mtime = Path(f).stat().st_mtime
        from datetime import datetime
        time_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        table.add_row(str(i), f.name, size_str, time_str)

    console.print(table)
    console.print()

    try:
        choice = Prompt.ask(
            "[bold]请选择文件[/] [dim](编号, q=返回)[/]",
            default="1"
        )
        if choice.lower() == "q":
            return None
        idx = int(choice) - 1
        if 0 <= idx < len(files):
            f = files[idx]
            console.print(f"\n  [green]✓[/] 已选择: [bold]{f.name}[/]")
            return f
    except (ValueError, IndexError):
        console.print("[red]无效选择[/]")

    return None


def select_crawler() -> Optional[Tuple[str, dict]]:
    """选择爬虫脚本"""
    console.print()
    console.print(Panel.fit(
        "[bold cyan]Step 1: 选择数据采集平台[/]\n"
        "请选择要使用的爬虫脚本",
        border_style="cyan"
    ))

    table = Table(show_header=True, header_style="bold white", border_style="dim")
    table.add_column("#", style="dim", width=4)
    table.add_column("平台", style="cyan", width=16)
    table.add_column("爬虫名称", style="green", width=20)
    table.add_column("说明", style="white", width=40)

    items = list(CRAWLER_SCRIPTS.items())
    for i, (key, info) in enumerate(items, 1):
        table.add_row(str(i), info["platform"], info["name"], info["description"])

    console.print(table)
    console.print()

    # 读取上次选择作为默认值
    state = load_state()
    last_crawler = state.get("last_crawler", "1")
    guess = last_crawler if last_crawler.isdigit() and 1 <= int(last_crawler) <= len(items) else "1"

    try:
        choice = Prompt.ask(
            "[bold]请选择[/] [dim](1-8, q=退出)[/]",
            default=str(guess),
        )
        if choice.lower() == "q":
            return None
        idx = int(choice) - 1
        if 0 <= idx < len(items):
            key, info = items[idx]
            console.print(f"\n  [green]✓[/] 已选择: [bold]{info['name']}[/] ({info['platform']})")
            return key, info
    except (ValueError, IndexError):
        console.print("[red]无效选择[/]")

    return None


def get_crawler_args(crawler_info: dict) -> dict:
    """获取爬虫运行参数"""
    platform = crawler_info["platform"]
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]配置爬虫参数: {crawler_info['name']}[/]",
        border_style="cyan"
    ))

    args = {}

    if platform in ["知乎", "小红书", "抖音"]:
        url = Prompt.ask("  目标URL [dim](留空使用默认)[/]", default="")
        if url:
            args["url"] = url

    elif platform == "哔哩哔哩":
        bv = Prompt.ask("  视频BV号 [dim](多个用空格分隔)[/]", default="")
        if bv:
            args["bv_list"] = bv.split()
        else:
            args["bv_list"] = []

    elif platform == "中国知网":
        keyword = Prompt.ask("  搜索关键词", default="人工智能")
        args["keyword"] = keyword
        pages = Prompt.ask("  搜索页数", default="5")
        args["pages"] = int(pages)
        lit_type = Prompt.ask(
            "  文献类型 [dim](journal/thesis/conference/newspaper/all)[/]",
            default="all"
        )
        if lit_type != "all":
            args["type"] = lit_type

    elif platform in ["天猫", "京东"]:
        url = Prompt.ask("  商品链接或ID", default="")
        args["url"] = url

    elif platform == "豆瓣":
        mode = Prompt.ask(
            "  爬取模式 [dim](book/movie/search)[/]",
            choices=["book", "movie", "search"],
            default="book"
        )
        args["mode"] = mode
        if mode == "search":
            keyword = Prompt.ask("  搜索关键词")
            args["keyword"] = keyword

    return args


def select_analysis_models() -> List[str]:
    """选择分析模型"""
    console.print()
    console.print(Panel.fit(
        "[bold magenta]Step 3: 选择分析模型[/]\n"
        "可多选，用逗号分隔编号 (如: 1,2,4)",
        border_style="magenta"
    ))

    # 定量分析
    console.print("\n[bold cyan]═══ 定量分析模型 ═══[/]")
    quant_table = Table(show_header=True, header_style="bold white", border_style="dim")
    quant_table.add_column("#", style="dim", width=4)
    quant_table.add_column("模型", style="cyan", width=20)
    quant_table.add_column("说明", style="white", width=50)

    quant_items = list(ANALYSIS_MODELS["quantitative"].items())
    for i, (key, info) in enumerate(quant_items, 1):
        quant_table.add_row(f"Q{i}", info["name"], info["description"])

    console.print(quant_table)

    # 定性分析
    console.print("\n[bold magenta]═══ 定性分析模型 ═══[/]")
    qual_table = Table(show_header=True, header_style="bold white", border_style="dim")
    qual_table.add_column("#", style="dim", width=4)
    qual_table.add_column("模型", style="magenta", width=20)
    qual_table.add_column("说明", style="white", width=50)

    qual_items = list(ANALYSIS_MODELS["qualitative"].items())
    for i, (key, info) in enumerate(qual_items, len(quant_items) + 1):
        qual_table.add_row(f"L{i}", info["name"], info["description"])

    console.print(qual_table)
    console.print()

    try:
        choice = Prompt.ask(
            "[bold]请选择模型[/] [dim](如: Q1,Q3,L6 或 all)[/]",
            default="all"
        )
        if choice.lower() == "all":
            selected = list(ANALYSIS_MODELS["quantitative"].keys()) + \
                       list(ANALYSIS_MODELS["qualitative"].keys())
            console.print(f"\n  [green]✓[/] 已选择全部 {len(selected)} 个模型")
            return selected

        # 解析选择
        selected = []
        all_quant = list(ANALYSIS_MODELS["quantitative"].keys())
        all_qual = list(ANALYSIS_MODELS["qualitative"].keys())

        parts = [p.strip().upper() for p in choice.split(",")]
        for part in parts:
            if part.startswith("Q"):
                idx = int(part[1:]) - 1
                if 0 <= idx < len(all_quant):
                    selected.append(all_quant[idx])
            elif part.startswith("L"):
                # L 编号从 len(quant)+1 开始，需映射回 0
                idx = int(part[1:]) - len(all_quant) - 1
                if 0 <= idx < len(all_qual):
                    selected.append(all_qual[idx])

        if selected:
            console.print(f"\n  [green]✓[/] 已选择 {len(selected)} 个模型: {', '.join(selected)}")
        return selected
    except (ValueError, IndexError):
        console.print("[red]无效选择，使用全部模型[/]")
        return list(ANALYSIS_MODELS["quantitative"].keys()) + \
               list(ANALYSIS_MODELS["qualitative"].keys())


def select_multiple_files() -> List[Path]:
    """批量选择多个数据文件用于对比分析"""
    console.print()
    console.print(Panel.fit(
        "[bold cyan]批量对比 — 选择多个数据文件[/]\n"
        "用逗号分隔编号，如: 1,3,5",
        border_style="cyan"
    ))

    files = []
    for ext in ["*.xlsx", "*.csv", "*.json"]:
        files.extend(DATA_DIR.rglob(ext))
    files = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)

    if len(files) < 2:
        console.print("  [yellow]至少需要2个数据文件才能对比[/]")
        return []

    console.print(f"  [dim]找到 {len(files)} 个数据文件:[/]\n")
    from rich.table import Table
    table = Table(show_header=True, header_style="bold white", border_style="dim")
    table.add_column("#", style="dim", width=4)
    table.add_column("文件名", style="cyan", width=35)
    table.add_column("记录数", style="green", width=8)

    file_sizes = {}
    for i, f in enumerate(files[:20], 1):
        count = "?"
        try:
            import openpyxl, csv
            ext = f.suffix.lower()
            if ext == ".xlsx":
                wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
                count = wb.active.max_row - 1
                wb.close()
            elif ext == ".csv":
                with open(f, encoding="utf-8-sig", errors="replace") as fh:
                    count = sum(1 for _ in fh) - 1
            else:
                count = "?"
            file_sizes[str(i)] = count
        except ImportError:
            count = "依赖缺失"
        except Exception as e:
            count = "读取失败"
        table.add_row(str(i), f.name, str(count))

    console.print(table)
    console.print()

    try:
        choice = Prompt.ask("[bold]选择文件[/] [dim](编号逗号分隔, q=返回)[/]", default="1,2")
        if choice.lower() == "q":
            return []
        indices = [int(x.strip()) - 1 for x in choice.split(",") if x.strip().isdigit()]
        selected = [files[i] for i in indices if 0 <= i < len(files)]
        if selected:
            names = ", ".join(f.name for f in selected)
            console.print(f"\n  [green]✓[/] 已选择 {len(selected)} 个文件: {names}")
        return selected
    except (ValueError, IndexError):
        console.print("[red]无效选择[/]")
        return []


def save_crawler_state(crawler_key: str):
    """记住爬虫选择"""
    items = list(CRAWLER_SCRIPTS.keys())
    idx = items.index(crawler_key) + 1 if crawler_key in items else 1
    save_state({"last_crawler": str(idx), "last_mode": "crawl"})


def save_mode_state(mode: str):
    """记住模式选择"""
    s = load_state()
    s["last_mode"] = mode
    save_state(s)


def confirm_step(message: str) -> bool:
    """确认步骤"""
    return Confirm.ask(f"\n  {message}", default=True)
