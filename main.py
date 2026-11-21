#!/usr/bin/env python3
"""
Insight Agent — 智能数据分析爬虫智能体
===========================================
CLI 交互式工具，集成爬虫采集 → 数据分析 → 报告生成 → AI问答

用法:
  python3 main.py           # 交互模式
  insight                    # 全局命令（需安装到 PATH）
"""

import sys
import json
import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent))

from logging_config import setup_logging
setup_logging()

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich.prompt import Prompt

from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.completion import WordCompleter

from config import (
    PROJECT_ROOT, REPORT_DIR, DATA_DIR, ANALYSIS_MODELS,
    THEME, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
    CRAWLER_SCRIPTS,
)
from ui import (
    show_welcome,
    select_mode, select_existing_file, select_multiple_files,
    select_crawler, get_crawler_args, select_analysis_models, confirm_step,
    save_crawler_state, save_mode_state,
)
from crawlers.runner import run_crawler, get_latest_output_files
from analysis import run_quantitative, run_qualitative
from report import generate_report
from chat import AnalystSession
from chat.agent import SESSION_DIR

logger = logging.getLogger(__name__)
console = Console()

PROMPT_STYLE = Style.from_dict({
    "prompt": "bold cyan",
    "separator": "dim",
})


# ================================================================
# 数据加载与预览
# ================================================================

def load_data(file_path: Path) -> list:
    """从文件加载数据"""
    ext = file_path.suffix.lower()

    try:
        if ext == ".csv":
            with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
                return list(csv.DictReader(f))
        elif ext == ".xlsx":
            try:
                import openpyxl
                wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
                if not rows:
                    return []
                headers = [str(h) if h else f"col_{i}" for i, h in enumerate(rows[0])]
                data = []
                for row in rows[1:]:
                    data.append({headers[i]: str(v) if v is not None else "" for i, v in enumerate(row)})
                wb.close()
                return data
            except ImportError:
                logger.error("缺少 openpyxl 依赖，请运行: pip install openpyxl")
                console.print("[red]缺少 openpyxl 依赖，请运行: pip install openpyxl[/]")
                return []
            except Exception as e:
                logger.error(f"读取Excel失败: {e}")
                console.print(f"[red]读取Excel失败: {e}[/]")
                return []
        elif ext == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, list):
                    return content
                elif isinstance(content, dict):
                    for v in content.values():
                        if isinstance(v, list) and v:
                            return v
                    return [content]
    except FileNotFoundError:
        logger.error(f"文件不存在: {file_path}")
        console.print(f"[red]文件不存在: {file_path}[/]")
        return []
    except PermissionError:
        logger.error(f"没有文件读取权限: {file_path}")
        console.print(f"[red]没有文件读取权限: {file_path}[/]")
        return []
    except Exception as e:
        logger.error(f"加载数据失败: {e}")
        console.print(f"[red]加载数据失败: {e}[/]")
        return []

    return []


def preview_data(data: list, data_file: Path) -> bool:
    """预览数据：展示前10行 + 字段类型检测，确认是否继续"""
    from rich.table import Table
    from analysis.quantitative import auto_detect_fields

    console.print()
    console.print(Panel.fit(
        f"[bold cyan]数据预览: {data_file.name}[/]",
        border_style="cyan"
    ))

    file_size = data_file.stat().st_size
    size_str = f"{file_size/1024:.1f}KB" if file_size < 1024*1024 else f"{file_size/1024/1024:.1f}MB"
    console.print(f"  [dim]记录数:[/] [bold]{len(data)}[/]  |  "
                f"[dim]字段数:[/] [bold]{len(data[0]) if data else 0}[/]  |  "
                f"[dim]文件大小:[/] [bold]{size_str}[/]")
    console.print()

    field_types = auto_detect_fields(data)
    type_icons = {"text": "📝", "numeric": "🔢", "date": "📅", "other": "📦"}
    type_colors = {"text": "cyan", "numeric": "green", "date": "yellow", "other": "dim"}

    console.print("  [bold]字段类型检测:[/]")
    type_strs = []
    for f, t in field_types.items():
        icon = type_icons.get(t, "•")
        color = type_colors.get(t, "white")
        type_strs.append(f"[{color}]{icon} {f} ({t})[/]")
    console.print("    " + "  |  ".join(type_strs))
    console.print()

    if data:
        console.print("  [bold]数据预览 (前10行):[/]")
        table = Table(show_header=True, header_style="bold white", border_style="dim",
                     show_lines=False, padding=(0, 1))

        columns = list(data[0].keys())[:8]
        for col in columns:
            table.add_column(col[:12], style="dim", max_width=15, no_wrap=True)

        for i, row in enumerate(data[:10]):
            values = [str(row.get(c, ""))[:15] for c in columns]
            table.add_row(*values)

        console.print(table)

    console.print()
    return confirm_step("确认使用此数据进行分析？")


# ================================================================
# 分析调度
# ================================================================
# 单个分析任务函数已挪到 cli/_dispatch.py，打破 main ↔ cli.commands 循环引用。
# 这里只保留向后兼容的薄壳。
from cli._dispatch import run_single_quant as _run_single_quant
from cli._dispatch import run_single_qual as _run_single_qual


# ================================================================
# AI 分析对话
# ================================================================

def run_ai_analysis_flow(data: list, data_file: Path):
    """AI 驱动分析流程：数据预览后 AI 直接主持分析 + 持续对话

    退出 AI 对话（exit / Ctrl+C）后自动生成五段式报告（Markdown + HTML）。
    """
    console.print()
    console.print(Panel.fit(
        "[bold cyan]🤖 AI 分析师已就绪[/]\n"
        f"数据: [dim]{data_file.name}[/] — {len(data)} 条记录, {len(data[0]) if data else 0} 个字段\n\n"
        f"[dim]字段预览: {', '.join(list(data[0].keys())[:8]) if data else '无'}[/]\n"
        "[dim]正在连接 DeepSeek 并生成分析开场白...[/]",
        border_style="cyan"
    ))

    session = AnalystSession(data, data_file)

    console.print()
    # 先打印表头，然后直接流式输出，不用 spinner 遮挡
    console.print("[bold cyan]━━━ 🤖 AI 分析中 ━━━[/]")
    console.print()
    greeting = session.analyst.greet_and_analyze()

    result = chat_loop_analyst(session)

    # 如果是退出（不是 MENU），自动生成完整报告
    if result != "MENU":
        _generate_report_after_ai_chat(session, data_file)


def _do_generate_report(session: 'AnalystSession', data_file: Path, *, in_chat: bool = False):
    """核心报告生成：跑分析工具 + 写 .md + qa.json + 询问 HTML

    Parameters
    ----------
    in_chat : True 表示在 AI 对话中被触发（用户说"导出报告"等）；
              False 表示在 AI 对话退出后被调用。两者 UI 提示风格略有不同。
    """
    from report.generator import generate_report, generate_html_from_markdown
    # 实际只用到 4 个分析函数：basic_stats / sentiment / word_freq / insight_mining
    # 它们分散在 quantitative 和 qualitative 两个模块里
    from analysis.quantitative import basic_stats, sentiment_analysis, word_frequency
    try:
        from analysis.qualitative import insight_mining
    except ImportError:
        # 老版本可能没有 qualitative 模块，回退拿一个空的
        logger.warning("analysis.qualitative 不可用，insight_mining 跳过")
        insight_mining = None

    # 1) 跑分析工具
    data = session.analyst.data
    results: dict = {}
    try:
        results["basic_stats"] = basic_stats(data, data_file)
        from analysis.quantitative import auto_detect_fields
        ftypes = auto_detect_fields(data)
        if any(t == "text" for t in ftypes.values()):
            try:
                # 注意：sentiment_analysis / word_frequency 的第二参数是 text_field（字段名），
                # 不传让它自动检测文本字段，不要传 data_file
                results["sentiment"] = sentiment_analysis(data)
            except Exception as e:
                logger.debug("情感分析跳过: %s", e)
        try:
            results["word_freq"] = word_frequency(data)
        except Exception as e:
            logger.debug("词频跳过: %s", e)
        if insight_mining is not None:
            try:
                results["insight_mining"] = insight_mining(data)
            except Exception as e:
                logger.debug("洞察跳过: %s", e)
    except Exception as e:
        logger.warning("分析工具运行失败: %s", e)

    crawler_info = {
        "platform": "AI 分析师驱动",
        "name": data_file.stem,
        "crawl_method": "AI 对话式分析",
    }

    # 2) 写 .md 到数据文件同目录
    if in_chat:
        console.print("  [cyan]📝 正在为你生成 Markdown 报告...[/]")
    else:
        console.print("\n  [cyan]📝 正在生成 Markdown 报告...[/]")
    report = generate_report(
        crawler_info=crawler_info,
        analysis_results=results,
        data_file=data_file,
        output_dir=data_file.parent,
        conversation=session.history,
        formats=("md", "qa_json"),
    )
    md_path = report["md"]

    if in_chat:
        # 对话中触发：简洁一行的反馈
        console.print(f"  [green]✅ Markdown 报告已生成：[/][bold]{md_path}[/]")
    else:
        console.print(Panel.fit(
            "\n".join([
                "[bold green]✅ Markdown 报告已生成！[/]",
                "",
                f"📝 {md_path}",
                f"📦 原始数据（AI 问答用）: [dim]{report.get('qa_json', '')}[/]",
            ]),
            border_style="green",
            title="[bold]📊 Markdown 报告（七段式：执行摘要 / 数据说明 / 工具说明 / 分析结果 / 关键发现 / 启示预测）[/]",
        ))

    # 3) 询问是否要 HTML
    from rich.prompt import Confirm
    if not Confirm.ask("  生成 HTML 可视化报告？", default=True):
        console.print(f"  [dim]已跳过 HTML 生成；Markdown 在 {md_path}。[/]")
        return report

    # 4) 让 LLM 读 .md → 写更丰富的 .html
    console.print("  [cyan]🔮 正在让 LLM 读懂 Markdown 并生成精美 HTML...[/]")
    html_path = generate_html_from_markdown(md_path)
    if html_path is None:
        console.print("  [red]✗ HTML 生成失败[/]")
        return report

    console.print(f"  [green]✅ HTML 报告: [bold]{html_path}[/][/]")
    report["html"] = html_path

    if Confirm.ask("  在浏览器中打开 HTML 报告？", default=True):
        import webbrowser
        webbrowser.open(f"file://{html_path}")

    if Confirm.ask("  导出 PDF？", default=False):
        from report.generator import export_pdf
        pdf_path = export_pdf(html_path)
        if pdf_path:
            console.print(f"  [green]✓[/] PDF: [bold]{pdf_path}[/]")

    return report


def _generate_report_after_ai_chat(session: 'AnalystSession', data_file: Path):
    """AI 对话退出后 → 调用 _do_generate_report"""
    _do_generate_report(session, data_file, in_chat=False)


# 导出报告的关键词 —— 在 AI 对话中识别后立即触发报告生成
_EXPORT_TRIGGERS = (
    "导出报告", "生成报告", "出报告", "导出 markdown", "生成 markdown",
    "导出md", "生成md", "出md", "导出全部结果", "保存报告", "保存为报告",
    "我要报告", "给我报告", "下载报告", "写报告", "写一份报告",
    "report", "markdown 报告", "md 报告",
)


def _is_export_report_request(text: str) -> bool:
    """判断用户消息是否是"导出报告"类指令"""
    t = text.strip().lower()
    if not t:
        return False
    for kw in _EXPORT_TRIGGERS:
        if kw in t:
            return True
    return False


def chat_loop_analyst(session: AnalystSession):
    """AI 分析对话循环"""
    completer = WordCompleter(["情感分析", "词频统计", "趋势分析", "总结", "建议",
                                "导出报告", "生成报告", "exit", "help", "返回主菜单"])
    console.print(Panel.fit(
        "[bold]现在可以指挥 AI 做分析了[/]\n"
        "[dim]输入分析需求，AI 自动写代码执行 | exit 退出 | help 帮助 | menu 返回主菜单[/]\n\n"
        "[bold yellow]💡 提示：[/]\n"
        "  · 输入 [bold]exit[/] 退出对话后，会[bold]自动生成 .md 报告[/]\n"
        "  · 在对话中说 [bold]\"导出报告\"[/] / [bold]\"生成 markdown\"[/] —— "
        "[green]系统会为你生成报告[/]，[bold]不退出对话[/]\n"
        "  · 输入 [bold]menu[/] 或 [bold]返回主菜单[/] 回到主菜单，也会自动生成报告",
        border_style="dim"
    ))

    prompt_session = PromptSession(
        history=InMemoryHistory(),
        style=PROMPT_STYLE,
        completer=completer,
    )

    data_file = session.data_file

    while True:
        try:
            user_input = prompt_session.prompt(
                [("class:prompt", "  💬 你"), ("class:separator", " › ")],
            ).strip()
            if not user_input:
                continue

            # === 返回主菜单 ===
            if user_input.lower() in ("menu", "返回主菜单"):
                console.print("  [dim]返回主菜单...[/]")
                _generate_report_after_ai_chat(session, data_file)
                return "MENU"

            # === 导出报告 ===
            if _is_export_report_request(user_input):
                with console.status(
                    "[bold cyan]📊 正在为你生成报告...[/]",
                    spinner="dots",
                    spinner_style="cyan",
                ):
                    _do_generate_report(session, data_file, in_chat=True)
                console.print("  [dim]（已生成报告；继续对话或输入 exit 退出）[/]\n")
                continue

            # 不藏 spinner，直接流式输出
            console.print()
            console.print("[bold cyan]━━━ 🤖 AI 分析中 ━━━[/]")
            console.print()
            result = session.process_message(user_input)

            if result == "__EXIT__":
                break

            # 如果 LLM 已经在 chat() 里流式输出过，这里不再重复包裹
            # 只追加换行分隔
            console.print()
            console.print("[dim]──[/]")
            console.print()

        except KeyboardInterrupt:
            console.print("\n  [dim]已中断当前思考，继续对话或输入 exit 退出[/]\n")
            continue
        except EOFError:
            break


# ================================================================
# 批量分析 + 导出
# ================================================================

def run_analysis_flow(data: list, data_file: Path, output_dir: Path = None):
    """分析流程：选模型 → 并行分析 → 报告 → AI问答"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    selected_models = select_analysis_models()
    if not selected_models:
        console.print("\n[yellow]未选择分析模型[/]")
        return

    console.print()
    console.print(Panel.fit(
        "[bold magenta]运行分析 & 生成报告[/]",
        border_style="magenta"
    ))

    quant_models = [m for m in selected_models if m in ANALYSIS_MODELS.get("quantitative", {})]
    qual_models = [m for m in selected_models if m in ANALYSIS_MODELS.get("qualitative", {})]

    results = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {}
        for model in quant_models:
            futures[pool.submit(_run_single_quant, data, model, data_file)] = model
        if qual_models and LLM_API_KEY:
            for model in qual_models:
                futures[pool.submit(_run_single_qual, data, model, data_file)] = model

        total = len(futures)
        done_count = 0
        for future in as_completed(futures):
            done_count += 1
            model = futures[future]
            try:
                result = future.result()
                results.update(result)
                status = "✓" if "error" not in list(result.values())[0] else "⚠"
                model_name = list(result.values())[0].get("model", model)
                console.print(f"  [{done_count}/{total}] {status} {model_name}")
            except Exception as e:
                console.print(f"  [{done_count}/{total}] ✗ {model}: {e}")

    if not results:
        console.print("\n[red]✗ 所有分析模型均失败[/]")
        return

    crawler_info = {"platform": "本地文件", "name": data_file.name}
    if output_dir is None:
        output_dir = data_file.parent

    console.print("\n  [cyan]📝 正在生成 Markdown 报告...[/]")
    report = generate_report(
        crawler_info, results, data_file, data_file.parent,
        formats=("md", "qa_json"),
    )
    md_path = report["md"]
    console.print(f"  [green]✓[/] Markdown: [bold]{md_path}[/]")

    report_data = {
        "crawler": crawler_info,
        "analysis": results,
        "data_file": str(data_file),
        "generated_at": datetime.now().isoformat(),
    }

    # 询问是否要 HTML
    if confirm_step("生成 HTML 可视化报告？"):
        from report.generator import generate_html_from_markdown
        console.print("  [cyan]🔮 正在让 LLM 读懂 Markdown 并生成精美 HTML...[/]")
        html_path = generate_html_from_markdown(md_path)
        if html_path:
            console.print(f"  [green]✓[/] HTML: [bold]{html_path}[/]")
            if confirm_step("导出 PDF？"):
                _export_pdf(html_path)
            if confirm_step("在浏览器中打开？"):
                import webbrowser
                webbrowser.open(f"file://{html_path}")
            # 让后续 AI 问答用上 HTML
            report_for_chat = html_path
        else:
            report_for_chat = md_path
    else:
        report_for_chat = md_path

    if confirm_step("进入AI问答模式？"):
        chat_loop_analyst_with_report(report_for_chat, report_data)

    from cli._dispatch import show_summary
    show_summary(report_for_chat, data_file)
    return report_data


def _export_pdf(html_path: Path):
    """将 HTML 报告导出为 PDF"""
    from report.generator import export_pdf
    pdf_path = export_pdf(html_path)
    if pdf_path:
        console.print(f"  [green]✓[/] PDF 已生成: [bold]{pdf_path}[/]")
    else:
        console.print("  [yellow]⚠ PDF 导出失败，请安装 weasyprint: pip install weasyprint[/]")


# ================================================================
# 主流程
# ================================================================

def main():
    show_welcome()

    while True:
        # 检测已保存的会话
        sessions = AnalystSession.list_sessions()
        if sessions:
            console.print()
            console.print(Panel.fit(
                "[bold yellow]📋 发现已保存的分析会话[/]",
                border_style="yellow"
            ))
            from rich.table import Table
            t = Table(show_header=True, header_style="bold")
            t.add_column("#", width=4)
            t.add_column("时间", width=18)
            t.add_column("数据文件", width=30)
            t.add_column("对话", width=8)
            for i, s in enumerate(sessions, 1):
                fname = Path(s["file"]).name if s["file"] else "?"
                t.add_row(str(i), s["saved"], fname, f"{s['messages']}轮")
            t.add_row("n", "—", "开始新分析", "—")
            console.print(t)
            console.print()

            choice = Prompt.ask("[bold]选择会话[/]", default="n")
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(sessions):
                    _resume_session(sessions[idx]["id"])
                    continue

        mode = select_mode()
        if not mode:
            console.print("\n[yellow]已取消[/]")
            continue

        save_mode_state(mode)

        # cli/commands 只依赖 cli._dispatch（通过 cli.commands 间接 import），
        # 不再反向 import main，所以这里可以安全顶层导入。
        from cli.commands import (
            natural_language_crawl, run_skill_template, manage_schedule,
            start_web_ui, login_setup, check_and_login_if_needed,
            run_batch_analysis, start_physical_world_ui,
            start_city_heatmap_ui,
        )

        if mode == "nl_crawl":
            natural_language_crawl(load_data, run_ai_analysis_flow)
            continue

        if mode == "template":
            run_skill_template(load_data, preview_data, run_ai_analysis_flow)
            continue

        if mode == "schedule":
            manage_schedule()
            continue

        if mode == "web":
            start_web_ui()
            continue

        if mode == "login":
            login_setup()
            continue

        if mode == "physical":
            start_physical_world_ui()
            continue

        if mode == "cityheat":
            start_city_heatmap_ui()
            continue

        if mode == "existing":
            if confirm_step("批量对比多个数据文件？"):
                files = select_multiple_files()
                if files:
                    run_batch_analysis(files, load_data)
                continue

            data_file = select_existing_file()
            if not data_file:
                console.print("\n[yellow]已取消[/]")
                continue

            console.print(f"\n  [dim]正在加载数据...[/]")
            data = load_data(data_file)
            if not data:
                console.print("[red]✗ 数据为空或无法读取[/]")
                continue

            if not preview_data(data, data_file):
                console.print("\n[yellow]已取消[/]")
                continue

            run_ai_analysis_flow(data, data_file)
            console.print()
            console.print("[dim]已保存报告，返回主菜单...[/]")
            continue

        else:
            crawler_selection = select_crawler()
            if not crawler_selection:
                console.print("\n[yellow]已取消[/]")
                continue

            crawler_key, crawler_info = crawler_selection
            save_crawler_state(crawler_key)

            args = get_crawler_args(crawler_info)

            check_and_login_if_needed(crawler_key)

            if not confirm_step("确认运行爬虫？"):
                console.print("\n[yellow]已取消[/]")
                continue

            output_dir = run_crawler(crawler_key, args)
            files = get_latest_output_files(output_dir)

            if not files:
                console.print("\n[red]✗ 未找到输出文件[/]")
                continue

            data_file = files[0]
            if len(files) > 1:
                console.print("\n  [bold]找到多个输出文件:[/]")
                for i, f in enumerate(files, 1):
                    console.print(f"    {i}. {f.name}")
                try:
                    choice = Prompt.ask("  [bold]选择[/]", default="1")
                    idx = int(choice) - 1
                    if 0 <= idx < len(files):
                        data_file = files[idx]
                except (ValueError, IndexError):
                    pass

            console.print(f"\n  [green]✓[/] 数据文件: [bold]{data_file.name}[/]")

            console.print("\n  [dim]正在加载数据...[/]")
            data = load_data(data_file)
            if not data:
                console.print("[red]✗ 数据为空或无法读取[/]")
                continue

            if not preview_data(data, data_file):
                console.print("\n[yellow]已取消[/]")
                continue

            run_ai_analysis_flow(data, data_file)
            continue


def _resume_session(session_id: str):
    """恢复已保存的会话"""
    result = AnalystSession.load_session(session_id)
    if not result:
        console.print("[red]会话数据文件已不存在[/]")
        return
    data, data_file = result

    data = load_data(data_file)
    if not data:
        console.print("[red]无法加载数据文件[/]")
        return

    console.print(f"\n  [green]✓[/] 恢复会话: {data_file.name}")
    run_ai_analysis_flow(data, data_file)


def chat_loop_analyst_with_report(report_path: Path, report_data: dict):
    """基于报告的 AI 问答（用 AnalystSession 而不是旧版）"""
    session = AnalystSession(
        [{"k": str(v)[:200] for k, v in item.items()} for item in [report_data]],
        report_path,
    )
    chat_loop_analyst(session)


if __name__ == "__main__":
    try:
        from config import OUTPUT_DIR, DATA_DIR, REPORT_DIR
        for dir_path in [OUTPUT_DIR, DATA_DIR, REPORT_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    try:
        from validator import ConfigValidator
        if not ConfigValidator.print_status():
            console.print("\n[yellow]提示: 部分配置缺失，某些功能可能不可用[/]")

        # 启动前一次性 ping Web 工作台状态，给个提示
        try:
            from cli._helpers import ping_api
            web_status = "[green]online[/]" if ping_api("http://127.0.0.1:9527") else "[dim]offline（菜单 6 可启动）[/]"
            console.print(f"  [dim]💡 Web UI 状态: {web_status}[/]")
        except Exception:
            pass

        main()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]👋 已退出 Insight Agent[/]")
        sys.exit(0)
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
        console.print(f"\n[red]发生错误: {e}[/]")
        sys.exit(1)
