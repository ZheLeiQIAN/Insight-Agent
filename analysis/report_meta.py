"""报告数据元信息 — 给"2. 数据说明"段提供结构化数据

不依赖 LLM，纯粹从数据本身算：字段类型、缺失率、分位数、唯一值数等。
"""

import csv
import json
import re
import statistics
from pathlib import Path
from typing import Dict, List, Any, Optional


# ---- 字段类型检测（从 quantitative.py 同步，保持口径一致） ----

def _is_numeric(values: list) -> bool:
    count = 0
    for v in values[:50]:
        try:
            float(str(v).replace(",", "").replace("%", ""))
            count += 1
        except (ValueError, TypeError):
            pass
    return count >= max(1, len(values[:50]) * 0.5)


def _is_date(values: list) -> bool:
    date_patterns = [
        r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",
        r"\d{1,2}[-/]\d{1,2}[-/]\d{4}",
        r"\d{4}年\d{1,2}月\d{1,2}日",
        r"\d{4}\d{2}\d{2}",
    ]
    count = 0
    for v in values[:50]:
        s = str(v)
        if any(re.search(p, s) for p in date_patterns):
            count += 1
    return count >= max(1, len(values[:50]) * 0.3)


def _is_text(values: list) -> bool:
    count = 0
    for v in values[:50]:
        s = str(v) if v is not None else ""
        if re.search(r'[\u4e00-\u9fff]', s) or len(s) > 15:
            count += 1
    return count >= max(1, len(values[:50]) * 0.3)


# ---- 元信息主函数 ----

def build_data_meta(data: list, data_file: Optional[Path] = None) -> Dict[str, Any]:
    """从原始数据生成报告用的元信息。

    Returns
    -------
    dict
        {
            "file_name": str,
            "record_count": int,
            "field_count": int,
            "fields": [
                {
                    "name": str,
                    "type": "numeric" | "text" | "date" | "other",
                    "missing_rate": float (0-1),
                    "non_null": int,
                    "unique_count": int,
                    "sample": str,
                    # 数值字段额外：
                    "min", "max", "mean", "median", "p25", "p75",
                    # 文本字段额外：
                    "top_values": [(value, count), ...],
                }
            ],
            "quality_issues": [str, ...]
        }
    """
    if not data:
        return {
            "file_name": data_file.name if data_file else "未知",
            "record_count": 0,
            "field_count": 0,
            "fields": [],
            "quality_issues": ["数据为空，无可分析样本"],
        }

    columns = list(data[0].keys())
    n = len(data)

    fields_info = []
    for col in columns:
        values = [row.get(col) for row in data]
        non_null = [v for v in values if v is not None and str(v).strip() != ""]
        missing_rate = round(1.0 - len(non_null) / n, 4) if n > 0 else 0.0
        sample = str(non_null[0])[:60] if non_null else ""

        # 字段类型
        if _is_numeric(non_null):
            ftype = "numeric"
        elif _is_date(non_null):
            ftype = "date"
        elif _is_text(non_null):
            ftype = "text"
        else:
            ftype = "other"

        info = {
            "name": col,
            "type": ftype,
            "missing_rate": missing_rate,
            "non_null": len(non_null),
            "unique_count": len(set(str(v) for v in non_null)),
            "sample": sample,
        }

        # 数值字段统计
        if ftype == "numeric":
            nums = []
            for v in non_null:
                try:
                    nums.append(float(str(v).replace(",", "").replace("%", "")))
                except (ValueError, TypeError):
                    pass
            if nums:
                info["min"] = min(nums)
                info["max"] = max(nums)
                info["mean"] = round(statistics.mean(nums), 2)
                info["median"] = round(statistics.median(nums), 2)
                if len(nums) >= 4:
                    sorted_nums = sorted(nums)
                    info["p25"] = round(sorted_nums[len(sorted_nums) // 4], 2)
                    info["p75"] = round(sorted_nums[len(sorted_nums) * 3 // 4], 2)
                else:
                    info["p25"] = info["min"]
                    info["p75"] = info["max"]

        # 文本字段高频值
        if ftype == "text":
            counter: Dict[str, int] = {}
            for v in non_null:
                key = str(v)[:80]
                counter[key] = counter.get(key, 0) + 1
            top = sorted(counter.items(), key=lambda x: -x[1])[:5]
            info["top_values"] = top

        fields_info.append(info)

    # 数据质量提示（规则版，不依赖 LLM）
    quality_issues = []
    for f in fields_info:
        if f["missing_rate"] >= 0.5:
            quality_issues.append(
                f"字段「{f['name']}」缺失率 {int(f['missing_rate']*100)}%，"
                f"可能影响该字段相关分析的可靠性"
            )
        elif f["missing_rate"] >= 0.2:
            quality_issues.append(
                f"字段「{f['name']}」缺失率 {int(f['missing_rate']*100)}%，建议补抓或谨慎解读"
            )
    if n < 30:
        quality_issues.append(f"样本数仅 {n} 条，定量结论的统计意义有限")
    if not quality_issues:
        quality_issues.append(f"数据质量良好：{n} 条记录无显著缺失")

    return {
        "file_name": data_file.name if data_file else "未知",
        "record_count": n,
        "field_count": len(columns),
        "fields": fields_info,
        "quality_issues": quality_issues,
    }


def get_data_preview(data: list, n: int = 10) -> List[Dict[str, str]]:
    """拿前 n 行做附录预览；长字段截断到 50 字"""
    preview = []
    for row in data[:n]:
        item = {}
        for k, v in row.items():
            sv = "" if v is None else str(v)
            item[k] = sv[:50] + ("..." if len(sv) > 50 else "")
        preview.append(item)
    return preview
