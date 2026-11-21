"""定量分析模型 — 智能字段检测版"""

import json
import csv
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import Counter
from datetime import datetime


# ===================== 智能字段检测 =====================

def _is_numeric(values: list) -> bool:
    """判断字段是否为数值型"""
    count = 0
    for v in values[:20]:  # 抽样检查
        try:
            float(str(v).replace(",", "").replace("%", ""))
            count += 1
        except (ValueError, TypeError):
            pass
    return count >= max(1, len(values[:20]) * 0.5)


def _is_date(values: list) -> bool:
    """判断字段是否为日期型"""
    date_patterns = [
        r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",  # 2025-01-15
        r"\d{1,2}[-/]\d{1,2}[-/]\d{4}",  # 01-15-2025
        r"\d{4}年\d{1,2}月\d{1,2}日",    # 2025年1月15日
        r"\d{4}\d{2}\d{2}",               # 20250115
    ]
    count = 0
    for v in values[:20]:
        s = str(v)
        if any(re.search(p, s) for p in date_patterns):
            count += 1
    return count >= max(1, len(values[:20]) * 0.3)


def _is_text(values: list) -> bool:
    """判断字段是否为文本型（含中文或较长）"""
    count = 0
    for v in values[:20]:
        s = str(v)
        # 含中文 或 长度>15
        if re.search(r'[\u4e00-\u9fff]', s) or len(s) > 15:
            count += 1
    return count >= max(1, len(values[:20]) * 0.3)


def auto_detect_fields(data: List[Dict]) -> dict:
    """自动检测每个字段的类型"""
    if not data:
        return {}
    fields = {}
    for field in data[0].keys():
        values = [row.get(field) for row in data if row.get(field) not in (None, "")]
        if not values:
            continue
        if _is_numeric(values):
            fields[field] = "numeric"
        elif _is_date(values):
            fields[field] = "date"
        elif _is_text(values):
            fields[field] = "text"
        else:
            fields[field] = "other"
    return fields


def get_text_field(data: List[Dict]) -> Optional[str]:
    """获取最优文本字段（用于情感/词频/主题分析）"""
    field_types = auto_detect_fields(data)
    text_fields = [f for f, t in field_types.items() if t == "text"]
    if not text_fields:
        return None
    # 取平均内容最长的那个
    best = max(text_fields, key=lambda f: sum(
        len(str(row.get(f, ""))) for row in data
    ) / max(len(data), 1))
    return best


def get_numeric_fields(data: List[Dict]) -> list:
    """获取所有数值字段"""
    field_types = auto_detect_fields(data)
    return [f for f, t in field_types.items() if t == "numeric"]


def get_date_field(data: List[Dict]) -> Optional[str]:
    """获取日期字段"""
    field_types = auto_detect_fields(data)
    date_fields = [f for f, t in field_types.items() if t == "date"]
    return date_fields[0] if date_fields else None


# ===================== 分析函数 =====================

def basic_stats(data: List[Dict], file_path: Path) -> Dict[str, Any]:
    """基础统计分析"""
    results = {
        "model": "基础统计分析",
        "timestamp": datetime.now().isoformat(),
        "record_count": len(data),
        "fields": {},
    }

    if not data:
        results["error"] = "无数据"
        return results
    field_types = auto_detect_fields(data)
    # 附带原始数据，供报告生成器构建 data_meta（不显示给最终用户）
    results["_raw_data"] = data
    results["_data_fields"] = list(data[0].keys())

    for field in data[0].keys():
        values = [row.get(field) for row in data if row.get(field) not in (None, "")]
        if not values:
            continue

        ftype = field_types.get(field, "other")
        field_info = {
            "count": len(values),
            "non_null": len(values),
            "type": ftype,
        }

        if ftype == "numeric":
            nums = []
            for v in values:
                try:
                    nums.append(float(str(v).replace(",", "").replace("%", "")))
                except (ValueError, TypeError):
                    pass
            if nums:
                field_info.update({
                    "min": round(min(nums), 2),
                    "max": round(max(nums), 2),
                    "mean": round(sum(nums) / len(nums), 2),
                    "median": round(sorted(nums)[len(nums) // 2], 2),
                    "sum": round(sum(nums), 2),
                })
        elif ftype == "text":
            value_counts = Counter(str(v)[:100] for v in values if v)
            field_info["unique_count"] = len(value_counts)
            field_info["top_values"] = value_counts.most_common(10)

        results["fields"][field] = field_info

    return results


def sentiment_analysis(data: List[Dict], text_field: str = None) -> Dict[str, Any]:
    """情感分析"""
    results = {
        "model": "情感分析",
        "timestamp": datetime.now().isoformat(),
        "total": 0,
        "positive": 0, "negative": 0, "neutral": 0,
        "scores": [],
    }

    if not text_field:
        text_field = get_text_field(data)

    if not text_field:
        results["error"] = "未检测到文本字段，无法进行情感分析"
        return results

    texts = [str(row.get(text_field, "")) for row in data if row.get(text_field)]
    results["total"] = len(texts)
    results["text_field"] = text_field

    if not texts:
        results["error"] = "文本字段为空"
        return results

    try:
        from snownlp import SnowNLP
    except ImportError:
        results["error"] = "请安装 snownlp: pip install snownlp"
        return results

    for text in texts:
        try:
            s = SnowNLP(text)
            score = s.sentiments
            results["scores"].append({"text": text[:200], "score": round(score, 3)})
            if score > 0.6:
                results["positive"] += 1
            elif score < 0.4:
                results["negative"] += 1
            else:
                results["neutral"] += 1
        except Exception:
            results["neutral"] += 1

    total = results["total"] or 1
    results["positive_pct"] = round(results["positive"] / total * 100, 1)
    results["negative_pct"] = round(results["negative"] / total * 100, 1)
    results["neutral_pct"] = round(results["neutral"] / total * 100, 1)
    results["avg_score"] = round(
        sum(s["score"] for s in results["scores"]) / max(len(results["scores"]), 1), 3
    )

    return results


def word_frequency(data: List[Dict], text_field: str = None) -> Dict[str, Any]:
    """词频与关键词分析"""
    results = {
        "model": "词频与关键词分析",
        "timestamp": datetime.now().isoformat(),
        "keywords": [],
    }

    if not text_field:
        text_field = get_text_field(data)

    if not text_field:
        results["error"] = "未检测到文本字段"
        return results

    results["text_field"] = text_field

    all_text = " ".join(
        str(row.get(text_field, "")) for row in data if row.get(text_field)
    )

    if not all_text.strip():
        results["error"] = "文本字段内容为空"
        return results

    try:
        import jieba
        import jieba.analyse
    except ImportError:
        results["error"] = "请安装 jieba: pip install jieba"
        return results

    # TF-IDF 关键词
    keywords = jieba.analyse.extract_tags(all_text, topK=30, withWeight=True)
    results["keywords"] = [{"word": w, "weight": round(s, 3)} for w, s in keywords]

    # 词频统计
    words = jieba.lcut(all_text)
    filtered = [w for w in words if len(w) >= 2 and not w.isdigit()]
    word_counts = Counter(filtered)
    results["top_words"] = word_counts.most_common(50)

    return results


def time_series(data: List[Dict], date_field: str = None) -> Dict[str, Any]:
    """时间序列分析"""
    results = {
        "model": "时间序列分析",
        "timestamp": datetime.now().isoformat(),
        "time_data": [],
    }

    if not date_field:
        date_field = get_date_field(data)

    if not date_field:
        results["error"] = "未检测到日期字段"
        return results

    results["date_field"] = date_field

    from collections import defaultdict
    time_buckets = defaultdict(int)

    for row in data:
        val = row.get(date_field)
        if not val:
            continue
        date_str = str(val)[:10]
        time_buckets[date_str] += 1

    results["time_data"] = sorted(
        [{"date": d, "count": c} for d, c in time_buckets.items()],
        key=lambda x: x["date"]
    )

    return results


def run_quantitative(data: List[Dict], models: List[str], data_file: Path) -> Dict[str, Any]:
    """运行选定的定量分析模型"""
    all_results = {}

    for model in models:
        try:
            if model == "basic_stats":
                all_results["basic_stats"] = basic_stats(data, data_file)
            elif model == "sentiment":
                all_results["sentiment"] = sentiment_analysis(data)
            elif model == "word_freq":
                all_results["word_freq"] = word_frequency(data)
            elif model == "time_series":
                all_results["time_series"] = time_series(data)
        except Exception as e:
            all_results[model] = {"model": model, "error": str(e)}

    return all_results
