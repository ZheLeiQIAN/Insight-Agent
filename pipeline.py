"""
爬虫调度流水线

将「采集 → 清洗 → 分析 → 报告」串成自动化流水线

用法：
    from pipeline import Pipeline

    # 单平台流水线
    pipe = Pipeline()
    pipe.add_crawl("douyin", {"url": "https://...", "max": 200})
    pipe.add_clean()
    pipe.add_analyze(["sentiment", "word_freq", "user_activity"])
    pipe.add_report(template="full")
    pipe.add_export_pdf()
    result = pipe.run()

    # 多平台并行
    pipe = Pipeline()
    pipe.add_crawl("douyin", {"url": "..."})
    pipe.add_crawl("zhihu", {"url": "..."})
    pipe.add_clean()
    pipe.add_analyze(["sentiment"])
    pipe.run()
"""

import sys
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)


@dataclass
class PipelineStep:
    """流水线步骤"""
    name: str
    func: str  # 函数名
    args: dict = field(default_factory=dict)
    status: str = "pending"  # pending / running / done / failed
    result: Any = None
    error: str = ""
    duration: float = 0


class Pipeline:
    """采集-清洗-分析-报告 自动化流水线"""

    def __init__(self):
        self.steps: List[PipelineStep] = []
        self.data_file: Optional[Path] = None
        self.data: Optional[List[Dict]] = None
        self.report_path: Optional[Path] = None

    def add_crawl(self, crawler_key: str, args: dict = None):
        """添加采集步骤"""
        self.steps.append(PipelineStep(
            name=f"采集: {crawler_key}",
            func="crawl",
            args={"crawler_key": crawler_key, **(args or {})},
        ))
        return self

    def add_clean(self, **kwargs):
        """添加清洗步骤"""
        self.steps.append(PipelineStep(
            name="数据清洗",
            func="clean",
            args=kwargs,
        ))
        return self

    def add_analyze(self, models: List[str], template: str = None):
        """添加分析步骤"""
        if template:
            from skills import get_template
            tmpl = get_template(template)
            if tmpl:
                models = tmpl.get("models", models)
        self.steps.append(PipelineStep(
            name=f"分析: {', '.join(models)}",
            func="analyze",
            args={"models": models},
        ))
        return self

    def add_report(self, template: str = "full"):
        """添加报告生成步骤"""
        self.steps.append(PipelineStep(
            name=f"生成报告 ({template})",
            func="report",
            args={"template": template},
        ))
        return self

    def add_export_pdf(self):
        """添加 PDF 导出步骤"""
        self.steps.append(PipelineStep(
            name="导出 PDF",
            func="export_pdf",
        ))
        return self

    def run(self) -> Dict[str, Any]:
        """执行整个流水线"""
        from rich.console import Console
        from rich.panel import Panel
        from rich.progress import Progress, SpinnerColumn, TextColumn

        console = Console()
        total_steps = len(self.steps)

        console.print()
        console.print(Panel.fit(
            f"[bold cyan]🔄 流水线执行[/]\n"
            f"共 {total_steps} 个步骤: {' → '.join(s.name for s in self.steps)}",
            border_style="cyan"
        ))

        start_time = time.time()

        for i, step in enumerate(self.steps, 1):
            console.print(f"\n  [bold cyan][{i}/{total_steps}][/] {step.name}")
            step.status = "running"
            step_start = time.time()

            try:
                if step.func == "crawl":
                    self._run_crawl(step)
                elif step.func == "clean":
                    self._run_clean(step)
                elif step.func == "analyze":
                    self._run_analyze(step)
                elif step.func == "report":
                    self._run_report(step)
                elif step.func == "export_pdf":
                    self._run_export_pdf(step)

                step.status = "done"
                step.duration = time.time() - step_start
                console.print(f"  [green]✅ 完成[/] ({step.duration:.1f}s)")

            except Exception as e:
                step.status = "failed"
                step.error = str(e)
                step.duration = time.time() - step_start
                console.print(f"  [red]❌ 失败: {e}[/]")
                logger.error(f"流水线步骤失败 [{step.name}]: {e}")

                # 如果采集失败，后续步骤无意义
                if step.func == "crawl":
                    console.print("  [yellow]⚠ 采集失败，跳过后续步骤[/]")
                    break

        total_duration = time.time() - start_time

        # 汇总
        done = sum(1 for s in self.steps if s.status == "done")
        failed = sum(1 for s in self.steps if s.status == "failed")

        console.print(f"\n{'─' * 50}")
        console.print(f"  [bold]流水线完成[/]: {done} 成功, {failed} 失败, 总耗时 {total_duration:.1f}s")

        if self.report_path:
            console.print(f"  [bold]报告路径:[/] {self.report_path}")

        return {
            "steps": [
                {"name": s.name, "status": s.status, "duration": s.duration, "error": s.error}
                for s in self.steps
            ],
            "total_duration": total_duration,
            "data_file": str(self.data_file) if self.data_file else None,
            "report_path": str(self.report_path) if self.report_path else None,
        }

    def _run_crawl(self, step: PipelineStep):
        """执行采集"""
        from crawlers.runner import run_crawler, get_latest_output_files

        crawler_key = step.args.pop("crawler_key")
        output_dir = run_crawler(crawler_key, step.args)
        files = get_latest_output_files(output_dir)

        if files:
            self.data_file = files[0]
            step.result = {"file": str(files[0]), "count": len(files)}
        else:
            raise RuntimeError("采集完成但无输出文件")

    def _run_clean(self, step: PipelineStep):
        """执行清洗"""
        if not self.data_file:
            raise RuntimeError("没有数据文件（采集步骤可能未执行）")

        from main import load_data
        from analysis.data_cleaner import clean_and_report

        self.data = load_data(self.data_file)
        if not self.data:
            raise RuntimeError("数据加载失败")

        self.data = clean_and_report(self.data, **step.args)

    def _run_analyze(self, step: PipelineStep):
        """执行分析"""
        if not self.data:
            # 尝试从文件加载
            if self.data_file:
                from main import load_data
                self.data = load_data(self.data_file)
            if not self.data:
                raise RuntimeError("没有数据可分析")

        models = step.args["models"]
        from analysis.tools_registry import execute_tool

        results = {}
        for model in models:
            try:
                results[model] = execute_tool(model, self.data, self.data_file)
            except Exception as e:
                results[model] = {"error": str(e)}

        step.result = results

        # 同步到 report 步骤
        self._analysis_results = results

    def _run_report(self, step: PipelineStep):
        """生成报告"""
        if not hasattr(self, '_analysis_results'):
            raise RuntimeError("没有分析结果（分析步骤可能未执行）")

        from report.generator import generate_report

        crawler_info = {"platform": "流水线", "name": self.data_file.name if self.data_file else "unknown"}
        self.report = generate_report(
            crawler_info, self._analysis_results,
            self.data_file, self.data_file.parent if self.data_file else Path("."),
        )
        self.report_path = self.report['html']
        return self.report_path

    def _run_export_pdf(self, step: PipelineStep):
        """导出 PDF"""
        if not self.report_path:
            raise RuntimeError("没有 HTML 报告（报告步骤可能未执行）")

        from report.generator import export_pdf
        pdf_path = export_pdf(self.report_path)
        if pdf_path:
            step.result = str(pdf_path)
        else:
            raise RuntimeError("PDF 导出失败，请安装 weasyprint: pip install weasyprint")


def quick_pipeline(crawler_key: str, url: str, max_items: int = 200,
                   models: List[str] = None) -> Dict:
    """
    一键流水线：采集 → 清洗 → 分析 → 报告

    用法：
        from pipeline import quick_pipeline
        result = quick_pipeline("douyin", "https://...", max_items=100)
    """
    if models is None:
        models = ["basic_stats", "sentiment", "word_freq"]

    pipe = Pipeline()
    pipe.add_crawl(crawler_key, {"url": url, "max": max_items})
    pipe.add_clean()
    pipe.add_analyze(models)
    pipe.add_report()
    return pipe.run()
