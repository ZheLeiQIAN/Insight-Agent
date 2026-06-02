#!/usr/bin/env python3
"""Insight Agent 配置文件"""

import os
import logging
from pathlib import Path

# 加载 .env 文件（如果存在）
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv 未安装时跳过，依赖系统环境变量

# === 项目路径 ===
PROJECT_ROOT = Path(__file__).parent.resolve()
CRAWLERS_DIR = PROJECT_ROOT / "crawlers"
OUTPUT_DIR = PROJECT_ROOT / "output"
REPORT_DIR = OUTPUT_DIR / "reports"
DATA_DIR = OUTPUT_DIR / "data"

for d in [OUTPUT_DIR, REPORT_DIR, DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# === LLM 配置 (使用 DeepSeek API) ===
LLM_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
LLM_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
LLM_MAX_TOKENS = 4096
LLM_TEMPERATURE = 0.7

if not LLM_API_KEY:
    logging.getLogger(__name__).warning(
        "未设置 DEEPSEEK_API_KEY 环境变量，AI 对话和定性分析功能不可用。"
        "请在 .env 文件中配置，或运行: export DEEPSEEK_API_KEY=sk-xxx"
    )

# === 爬虫脚本映射 ===
CRAWLER_SCRIPTS = {
    "zhihu": {
        "name": "知乎回答爬虫",
        "script": "zhihu_scraper.py",
        "description": "爬取知乎问题下的回答内容",
        "platform": "知乎",
        "output_type": "xlsx",
    },
    "bilibili": {
        "name": "B站视频数据爬虫",
        "script": "bilibili_crawler_v3.py",
        "description": "采集B站视频播放量、弹幕、评论等数据",
        "platform": "哔哩哔哩",
        "output_type": "xlsx",
    },
    "xiaohongshu": {
        "name": "小红书笔记爬虫",
        "script": "xiaohongshu_scraper.py",
        "description": "爬取小红书笔记内容和评论区",
        "platform": "小红书",
        "output_type": "xlsx",
    },
    "douyin": {
        "name": "抖音视频爬虫",
        "script": "douyin_scraper.py",
        "description": "抓取抖音视频信息和评论数据",
        "platform": "抖音",
        "output_type": "xlsx",
    },
    "cnki": {
        "name": "知网学术文献爬虫",
        "script": "main.py",
        "description": "搜索知网学术论文，支持多条件筛选",
        "platform": "中国知网",
        "output_type": "csv",
    },
    "tmall": {
        "name": "天猫评论爬虫",
        "script": "run.py",
        "description": "爬取天猫商品评论，支持整店采集",
        "platform": "天猫",
        "output_type": "xlsx",
    },
    "jd": {
        "name": "京东评论爬虫",
        "script": "run.py",
        "description": "爬取京东商品评论，支持单品/整店/批量",
        "platform": "京东",
        "output_type": "xlsx",
    },
    "douban": {
        "name": "豆瓣信息爬虫",
        "script": "douban_crawler.py",
        "description": "爬取豆瓣图书/电影信息与评分",
        "platform": "豆瓣",
        "output_type": "csv",
    },
    "generic_web": {
        "name": "Scrapling 通用网页采集",
        "script": "run.py",
        "description": "使用 Scrapling 采集任意网页的标题、段落和链接",
        "platform": "通用网页",
        "output_type": "csv",
    },
}

# === 分析模型注册（由 tools_registry 统一管理，此处仅为兼容旧代码的视图） ===
# 旧代码使用的 key → tools_registry 中的 tool name
_QUANT_KEY_MAP = {
    "basic_stats": "basic_stats",
    "sentiment": "sentiment_analysis",
    "word_freq": "word_frequency",
    "time_series": "time_series",
}
_QUAL_KEY_MAP = {
    "theme_extraction": "theme_extraction",
    "content_category": "content_category",
    "insight_mining": "insight_mining",
}


def _build_analysis_models() -> dict:
    """从 tools_registry 动态构建，保持单一数据源"""
    try:
        from analysis.tools_registry import ToolsRegistry

        all_tools = {t.name: t for t in ToolsRegistry.get_all_tools()}

        quant = {}
        for key, tool_name in _QUANT_KEY_MAP.items():
            tool = all_tools.get(tool_name)
            if tool:
                quant[key] = {
                    "name": tool.name,
                    "description": tool.description,
                    "category": tool.category.value,
                }

        qual = {}
        for key, tool_name in _QUAL_KEY_MAP.items():
            tool = all_tools.get(tool_name)
            if tool:
                qual[key] = {
                    "name": tool.name,
                    "description": tool.description,
                    "category": tool.category.value,
                }

        return {"quantitative": quant, "qualitative": qual}
    except ImportError:
        return {"quantitative": {}, "qualitative": {}}

ANALYSIS_MODELS = _build_analysis_models()

# === 颜色主题 ===
THEME = {
    "primary": "bold cyan",
    "secondary": "bold green",
    "accent": "bold magenta",
    "warning": "bold yellow",
    "error": "bold red",
    "info": "dim cyan",
}

# === 配置记忆：记住上次选择 ===
STATE_FILE = OUTPUT_DIR / ".insight_state.json"

import json as _json

def load_state() -> dict:
    """加载上次的配置"""
    if STATE_FILE.exists():
        try:
            return _json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_state(state: dict):
    """保存配置"""
    try:
        STATE_FILE.write_text(_json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
