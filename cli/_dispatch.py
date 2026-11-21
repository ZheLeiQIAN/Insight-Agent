"""CLI 调度辅助 — 把 main.py 和 cli/commands.py 都依赖的工具函数集中到这里

目的：消除 main.py ↔ cli/commands.py 之间的循环引用。
之前 _run_single_quant / _run_single_qual 写在 main.py 里，cli/commands.py 又从 main 反向 import，
任何提前 import 都会炸。现在统一放这里，两边都单向 import。
"""
import logging
import webbrowser
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()
logger = logging.getLogger(__name__)


def run_single_quant(data, model: str, data_file: Path) -> dict:
    """单个定量分析任务（线程安全）"""
    try:
        from analysis.quantitative import basic_stats, sentiment_analysis, word_frequency, time_series
        models_map = {
            "basic_stats": basic_stats,
            "sentiment": sentiment_analysis,
            "word_freq": word_frequency,
            "time_series": time_series,
        }
        fn = models_map.get(model)
        if fn:
            return {model: fn(data, data_file)}
        return {model: {"model": model, "error": f"未知模型: {model}"}}
    except Exception as e:
        logger.error("定量分析失败 [%s]: %s", model, e)
        return {model: {"model": model, "error": f"分析失败: {e}"}}


def run_single_qual(data, model: str, data_file: Path) -> dict:
    """单个定性分析任务（线程安全）"""
    try:
        from analysis.qualitative import theme_extraction, content_category, insight_mining
        models_map = {
            "theme_extraction": theme_extraction,
            "content_category": content_category,
            "insight_mining": insight_mining,
        }
        fn = models_map.get(model)
        if fn:
            return {model: fn(data)}
        return {model: {"model": model, "error": f"未知模型: {model}"}}
    except Exception as e:
        logger.error("定性分析失败 [%s]: %s", model, e)
        return {model: {"model": model, "error": f"分析失败: {e}"}}


def show_summary(report_path: Path, data_file: Path) -> None:
    """分析完成后打印总结面板（不再 console.clear() 以保留上下文）"""
    console.print()
    console.print(Panel.fit(
        "\n".join([
            "[bold green]✅ 分析完成！[/]",
            "",
            f"📊 报告文件: [bold cyan]{report_path}[/]",
            f"📁 数据文件: [bold cyan]{data_file}[/]",
        ]),
        border_style="green",
        title="[bold]任务总结[/]",
    ))
    console.print()
    from rich.prompt import Confirm
    if Confirm.ask("  在浏览器中打开报告？", default=True):
        webbrowser.open(f"file://{report_path}")
