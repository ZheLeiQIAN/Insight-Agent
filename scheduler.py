#!/usr/bin/env python3
"""Insight Agent 定时调度器 — 后台自动爬取+分析"""

import sys
import json
import time
import threading
import logging
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import OUTPUT_DIR, CRAWLER_SCRIPTS, LLM_API_KEY

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SCHEDULE_FILE = OUTPUT_DIR / ".schedule.json"


class Scheduler:
    """轻量级定时任务调度"""

    def __init__(self):
        self.jobs = self._load()

    def _load(self) -> list:
        if SCHEDULE_FILE.exists():
            try:
                return json.loads(SCHEDULE_FILE.read_text())
            except json.JSONDecodeError as e:
                logger.error(f"调度文件格式错误: {e}")
                return []
            except Exception as e:
                logger.error(f"加载调度文件失败: {e}")
                return []
        return []

    def _save(self):
        SCHEDULE_FILE.write_text(json.dumps(self.jobs, ensure_ascii=False, indent=2))

    def add(self, crawler: str, params: dict, interval_hours: int = 24, models: list = None):
        """添加定时任务"""
        job = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "crawler": crawler,
            "params": params,
            "interval_hours": interval_hours,
            "models": models or ["all"],
            "last_run": None,
            "next_run": datetime.now().isoformat(),
            "enabled": True,
        }
        self.jobs.append(job)
        self._save()
        return job["id"]

    def list_jobs(self) -> list:
        """列出所有任务"""
        now = datetime.now()
        result = []
        for j in self.jobs:
            status = "⏳" if j["enabled"] else "⏸"
            next_run = j.get("next_run", "?")[:16]
            last = j.get("last_run", "从未")[:16] if j.get("last_run") else "从未"
            result.append({
                "id": j["id"],
                "status": status,
                "platform": CRAWLER_SCRIPTS.get(j["crawler"], {}).get("platform", j["crawler"]),
                "params": str(j["params"])[:40],
                "interval": f"{j['interval_hours']}h",
                "last": last,
                "next": next_run,
            })
        return result

    def remove(self, job_id: str) -> bool:
        """删除任务，返回是否真的删除了（False 表示 ID 不存在）"""
        before = len(self.jobs)
        self.jobs = [j for j in self.jobs if j["id"] != job_id]
        if len(self.jobs) == before:
            return False
        self._save()
        return True

    def run_now(self) -> list:
        """立即执行所有到期任务"""
        results = []
        now = datetime.now()
        for job in self.jobs:
            if not job["enabled"]:
                continue
            next_run = datetime.fromisoformat(job["next_run"]) if job.get("next_run") else now
            if now < next_run:
                continue

            try:
                from main import load_data
                from crawlers.runner import run_crawler, get_latest_output_files
                from analysis.quantitative import basic_stats, sentiment_analysis, word_frequency
                from report.generator import generate_report

                output_dir = run_crawler(job["crawler"], job["params"])
                files = get_latest_output_files(output_dir)
                if files:
                    data = load_data(files[0])
                    if data:
                        results_data = {}
                        for m in ["basic_stats", "sentiment", "word_freq"]:
                            try:
                                fn = {"basic_stats": basic_stats, "sentiment": sentiment_analysis, "word_freq": word_frequency}[m]
                                results_data[m] = fn(data, files[0])
                            except Exception as e:
                                logger.warning(f"分析模型 {m} 失败: {e}")
                                continue

                        crawler_info = {"platform": CRAWLER_SCRIPTS[job["crawler"]]["platform"], "name": files[0].name}
                        report = generate_report(crawler_info, results_data, files[0], output_dir)
                        results.append({"job": job["id"], "status": "✅", "report": str(report['html'])})
                    else:
                        results.append({"job": job["id"], "status": "⚠️ 无数据"})
                else:
                    results.append({"job": job["id"], "status": "⚠️ 无输出"})

                job["last_run"] = now.isoformat()
                job["next_run"] = (now + timedelta(hours=job["interval_hours"])).isoformat()

            except Exception as e:
                results.append({"job": job["id"], "status": f"❌ {e}"})
                job["last_run"] = now.isoformat()

        self._save()
        return results


def start_scheduler(interval_seconds: int = 600):
    """后台启动调度器（每10分钟检查一次）"""
    scheduler = Scheduler()
    print(f"📅 调度器已启动（每{interval_seconds}秒检查）")
    print(f"   当前任务: {len(scheduler.jobs)} 个")

    def loop():
        while True:
            time.sleep(interval_seconds)
            results = scheduler.run_now()
            if results:
                for r in results:
                    print(f"  [{datetime.now():%H:%M}] {r['status']} {r['job']}")

    thread = threading.Thread(target=loop, daemon=True, name="scheduler")
    thread.start()
    return scheduler
