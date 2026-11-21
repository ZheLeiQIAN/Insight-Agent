#!/usr/bin/env python3
"""舆情全景套餐：情感分析 + 主题提取 + 观点挖掘 + 词频统计"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analysis.tools_registry import execute_tool
import pandas as pd
from pathlib import Path

DATA_FILE = Path("/Users/qianzhelei/Downloads/Insight Agent BP初稿/Insight-Agent-main/output/data/douyin_20260602_163108/douyin_20260602_163252.xlsx")
OUTPUT_DIR = Path("/Users/qianzhelei/Downloads/Insight Agent BP初稿/Insight-Agent-main/output/data/douyin_20260602_163108")

print("=" * 70)
print("🔥 舆情全景套餐 - 执行中...")
print("=" * 70)

# 加载数据
df = pd.read_excel(DATA_FILE)
data = df.to_dict(orient="records")
print(f"✅ 加载数据: {len(data)} 条记录, {len(df.columns)} 个字段\n")

# ========== 1. 情感分析 ==========
print("━" * 60)
print("📊 工具 1/4: sentiment_analysis（情感分析）")
print("━" * 60)
try:
    sentiment_result = execute_tool("sentiment_analysis", data, DATA_FILE)
    print(json.dumps(sentiment_result, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"❌ 情感分析出错: {e}")
print()

# ========== 2. 词频统计 ==========
print("━" * 60)
print("📊 工具 2/4: word_frequency（词频统计）")
print("━" * 60)
try:
    wf_result = execute_tool("word_frequency", data, DATA_FILE)
    # 只显示前30个关键词
    wf_display = wf_result.copy()
    if "keywords" in wf_display and len(wf_display["keywords"]) > 30:
        wf_display["keywords"] = wf_display["keywords"][:30]
        wf_display["_note"] = f"(仅显示前30个，共{len(wf_result['keywords'])}个)"
    print(json.dumps(wf_display, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"❌ 词频统计出错: {e}")
print()

# ========== 3. 主题提取 ==========
print("━" * 60)
print("📊 工具 3/4: theme_extraction（主题提取）")
print("━" * 60)
try:
    theme_result = execute_tool("theme_extraction", data, DATA_FILE)
    print(json.dumps(theme_result, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"❌ 主题提取出错: {e}")
print()

# ========== 4. 观点挖掘 ==========
print("━" * 60)
print("📊 工具 4/4: insight_mining（观点挖掘）")
print("━" * 60)
try:
    insight_result = execute_tool("insight_mining", data, DATA_FILE)
    print(json.dumps(insight_result, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"❌ 观点挖掘出错: {e}")
print()

print("=" * 70)
print("✅ 舆情全景套餐执行完毕！")
print("=" * 70)
