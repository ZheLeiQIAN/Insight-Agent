"""LLM 报告增强 — 让 LLM 生成"执行摘要 / 关键发现 / 启示与预测"三段

降级策略：
- LLM 不可用 / 报错 → 用规则模板
- 每段独立 try/except，单段失败不影响其他段
- 整个模块 import-safe：LLM 不可用时不抛异常
"""

import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


# ---- Prompt 模板 ----

_PROMPT_SUMMARY = """你是一位资深数据分析师，请基于以下信息撰写一段 200-400 字的【执行摘要】。

要求：
1. 第一段：数据规模与质量概述（来源、样本数、字段、主要数据问题）
2. 第二段：2-3 条核心发现（突出利弊双向，不要流水账）
3. 第三段：1-2 条建议（可执行的、非空话）

直接输出 Markdown 文本，**不要**任何标题、代码块、列表项符号。
保持专业、克制，避免过度修饰。输入数据使用中文。
"""

_PROMPT_FINDINGS = """你是一位资深数据分析师，请基于以下分析结果，输出【关键发现】列表。

要求：
- 输出 3-5 条，每条 1 句话 + 1 行具体数据支撑
- 每条前标注情绪色块：
  🟢 表示优势 / 利好
  🟡 表示中性 / 待观察
  🔴 表示风险 / 需改进
- 按重要性从高到低排序
- 直接输出 Markdown 列表，每条独占一行

示例格式：
- 🟢 **品牌口碑偏正面**: 正面情感占 58%（n=1,234），高于行业基准 50%
"""

_PROMPT_IMPLICATIONS = """你是一位资深数据分析师，请基于以下关键发现，输出【启示与预测】。

要求：
- 输出 3 条【建议】（具体可执行的行动项）+ 2 条【预测】（趋势性判断）
- 预测必须带【高/中/低】置信度标签
- 每条 1-2 句话，简明扼要
- 格式严格按以下模板（**建议** 和 **预测** 标签必须有）：

**建议** [行动 1]
**建议** [行动 2]
**建议** [行动 3]
**预测** [趋势 1，置信度：高]
**预测** [趋势 2，置信度：中]
"""


# ---- LLM 调用 ----

def _call_llm(prompt: str, context: Dict[str, Any]) -> Optional[str]:
    """调 LLM。返回 None 表示 LLM 不可用。"""
    try:
        from openai import OpenAI
        from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE
    except Exception as e:
        logger.debug("LLM 配置不可用: %s", e)
        return None

    if not LLM_API_KEY:
        logger.debug("LLM_API_KEY 为空，跳过 LLM 调用")
        return None

    # 截断 context 防止 prompt 过大
    context_json = json.dumps(context, ensure_ascii=False, default=str)
    if len(context_json) > 12000:
        context_json = context_json[:12000] + "\n... (内容过长已截断)"

    user_msg = f"以下是分析上下文（JSON 格式）：\n\n```json\n{context_json}\n```\n\n{prompt}"

    try:
        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是一位专业的资深数据分析师。"},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=LLM_MAX_TOKENS,
            temperature=LLM_TEMPERATURE,
        )
        content = resp.choices[0].message.content
        return content.strip() if content else None
    except Exception as e:
        logger.warning("LLM 调用失败: %s", e)
        return None


# ---- 三个 LLM 增强段 ----

def synthesize_summary(context: Dict[str, Any]) -> str:
    """执行摘要：LLM 生成；失败用模板降级。"""
    result = _call_llm(_PROMPT_SUMMARY, context)
    if result:
        return result
    return _fallback_summary(context)


def synthesize_findings(context: Dict[str, Any]) -> List[str]:
    """关键发现：LLM 生成 list of bullet points；失败用模板降级。"""
    result = _call_llm(_PROMPT_FINDINGS, context)
    if result:
        findings = [
            line.strip(" -•\t").strip()
            for line in result.split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]
        if findings:
            return findings
    return _fallback_findings(context)


def synthesize_implications(context: Dict[str, Any]) -> Dict[str, List[str]]:
    """启示与预测：返回 {"建议": [...], "预测": [...]}；失败用模板降级。"""
    result = _call_llm(_PROMPT_IMPLICATIONS, context)
    if result:
        parsed = _parse_implications(result)
        if parsed["建议"] or parsed["预测"]:
            return parsed
    return _fallback_implications(context)


def _parse_implications(text: str) -> Dict[str, List[str]]:
    parsed: Dict[str, List[str]] = {"建议": [], "预测": []}
    for line in text.split("\n"):
        line = line.strip()
        for key in ("建议", "预测"):
            if line.startswith(f"**{key}**"):
                content = line[len(f"**{key}**"):].strip()
                if content:
                    parsed[key].append(content)
    return parsed


# ---- 降级模板 ----

def _fallback_summary(context: Dict[str, Any]) -> str:
    meta = context.get("data_meta", {})
    results = context.get("analysis_results", {})
    record_count = meta.get("record_count", 0)
    file_name = meta.get("file_name", "未知")

    parts = [
        f"本次分析对象为 **{file_name}**，共 {record_count} 条记录、{meta.get('field_count', 0)} 个字段。"
    ]

    # 从 sentiment 拿亮点
    sentiment = results.get("sentiment", {})
    if "positive_pct" in sentiment:
        parts.append(
            f"情感分析显示正面情感占 {sentiment['positive_pct']}%，"
            f"负面情感占 {sentiment.get('negative_pct', 0)}%，"
            f"整体舆论倾向：{'偏正面' if sentiment['positive_pct'] > 50 else '需关注'}。"
        )

    # 从 insight_mining 拿发现
    insights = results.get("insight_mining", {}).get("insights", [])
    if insights:
        parts.append(
            f"从评论中挖掘出 {len(insights)} 条有价值的洞察，"
            f"其中最显著的是「{insights[0].get('content', '')[:50]}...」。"
        )

    parts.append("详细分析结果见下文各分析模型输出；数据质量提示与建议见数据说明与启示与预测章节。")
    return "\n\n".join(parts)


def _fallback_findings(context: Dict[str, Any]) -> List[str]:
    findings = []
    results = context.get("analysis_results", {})

    sentiment = results.get("sentiment", {})
    if "positive_pct" in sentiment:
        pct = sentiment["positive_pct"]
        tag = "🟢" if pct > 60 else "🟡" if pct > 40 else "🔴"
        findings.append(
            f"{tag} **情感倾向分析**: 正面 {pct}% / 中性 {sentiment.get('neutral_pct', 0)}% / 负面 {sentiment.get('negative_pct', 0)}%"
        )

    bs = results.get("basic_stats", {})
    if "record_count" in bs:
        findings.append(
            f"🟡 **数据规模**: 共 {bs['record_count']} 条记录，覆盖 {len(bs.get('fields', {}))} 个字段"
        )

    word_freq = results.get("word_freq", {})
    if word_freq.get("top_words"):
        top3 = word_freq["top_words"][:3]
        words = "、".join(w for w, _ in top3)
        findings.append(f"🟢 **高频词汇**: Top 3 为「{words}」")

    insights = results.get("insight_mining", {}).get("insights", [])
    for ins in insights[:2]:
        findings.append(
            f"{'🟢' if ins.get('type') == '建议' else '🟡' if ins.get('type') == '态度' else '🔴'} "
            f"**{ins.get('type', '发现')}**: {ins.get('content', '')[:60]}"
        )

    if not findings:
        findings.append("🟡 关键发现将由 LLM 进一步生成（当前 LLM 不可用，建议配置 DEEPSEEK_API_KEY）")
    return findings[:5]


def _fallback_implications(context: Dict[str, Any]) -> Dict[str, List[str]]:
    results = context.get("analysis_results", {})

    suggestions = []
    if "sentiment" in results:
        suggestions.append("基于情感分析结果，针对负面/中性评论分类制定差异化运营策略")
    if "word_freq" in results:
        suggestions.append("结合高频词汇，针对性优化产品/内容关键词布局")
    if "insight_mining" in results:
        suggestions.append("将洞察中的具体建议拆解为可执行的 1 周 / 1 月行动项")
    if not suggestions:
        suggestions.append("LLM 不可用时建议手动解读工具结果，配置 DEEPSEEK_API_KEY 后可自动生成启示")

    predictions = [
        "【置信度：中】本报告结论基于当前样本，后续需持续追踪以验证趋势",
        "【置信度：低】建议增加新分析维度以增强结论的稳健性",
    ]

    return {"建议": suggestions[:3], "预测": predictions[:2]}
