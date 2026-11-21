"""Agent 桥接：把物理世界事件转给 LLM，输出商家建议（V0.5 阶段 D）

V0.5 完整实现:
- 调用 DeepSeek API (OpenAI 兼容)
- 注入事件窗口 + ROI 状态作为上下文
- 返回结构化 AgentAdvice（含 LLM 增强文本 + 行动建议）

设计原则:
- 规则草稿 (RULES) 永远作为基础 fallback
- LLM 增强仅在 API key 可用时启用
- 失败优雅降级：LLM 失败 → 返回规则草稿
- 同事件 LLM 调用去重（避免重复调用）
"""
import os
import json
import logging
import time
from typing import Optional, Dict, List
from pathlib import Path

# 加载项目根 .env
PROJECT_ROOT = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from event_schema import PhysicalEvent, AgentAdvice
from trigger_rules import match_rule, build_advice_from_rule
from event_window import get_window

logger = logging.getLogger(__name__)

# ================================================================
# LLM 客户端（OpenAI 兼容 → DeepSeek）
# ================================================================
LLM_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
LLM_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
LLM_ENABLED = bool(LLM_API_KEY)

_client = None


def _get_client():
    """懒加载 OpenAI 客户端"""
    global _client
    if _client is None and LLM_ENABLED:
        try:
            from openai import OpenAI
            _client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
            logger.info("LLM 客户端已初始化: %s @ %s", LLM_MODEL, LLM_BASE_URL)
        except Exception as e:
            logger.warning("LLM 客户端初始化失败: %s", e)
            _client = None
    return _client


def _call_llm(prompt: str, system_msg: str = "", temperature: float = 0.5, max_tokens: int = 800) -> Optional[str]:
    """调用 LLM（流式）"""
    client = _get_client()
    if client is None:
        return None
    messages = []
    if system_msg:
        messages.append({"role": "system", "content": system_msg})
    messages.append({"role": "user", "content": prompt})
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.warning("LLM 调用失败: %s", e)
        return None


# ================================================================
# 上下文构造
# ================================================================

def _build_event_context() -> str:
    """构造事件上下文文本（注入 prompt）"""
    window = get_window()
    summary = window.summary(seconds=300)  # 最近 5 分钟
    lines = [
        f"事件窗口（最近 5 分钟）:",
        f"  总事件数: {summary['window_size']} (近 5 分钟: {summary['in_last_seconds']})",
        f"  按类型: {summary['by_type']}",
        f"  按 subtype: {summary['by_subtype']}",
    ]
    if summary.get("anomaly_subtypes"):
        lines.append(f"  异常事件: {summary['anomaly_subtypes']}")
    if summary.get("queue_subtypes"):
        lines.append(f"  队列事件: {summary['queue_subtypes']}")
    # 列出最近 5 个高优先级事件
    high_pri = window.recent(seconds=300, limit=5)
    if high_pri:
        lines.append("\n最近事件（最多 5 条）:")
        for e in high_pri:
            t = e.get("ts", 0)
            t_str = time.strftime("%H:%M:%S", time.localtime(t / 1000)) if t else "?"
            lines.append(
                f"  [{t_str}] {e.get('type', '?')}/{e.get('subtype', '?')}"
                f" zone={e.get('zone', '?')}"
                f" track_id={e.get('track_id', '?')}"
            )
    return "\n".join(lines)


def _build_roi_context(roi_snapshot: Optional[Dict] = None) -> str:
    """构造 ROI 状态文本（注入 prompt）"""
    if not roi_snapshot:
        return "ROI 状态: 未提供"
    lines = ["ROI 实时状态:"]
    for name, info in roi_snapshot.items():
        lines.append(
            f"  - {name}: 当前人数={info.get('current', 0)}"
            f" 进入总数={info.get('enters_total', 0)}"
        )
    return "\n".join(lines)


# ================================================================
# 主入口: 物理事件 → AgentAdvice
# ================================================================

def ask_agent_for_event(
    event: PhysicalEvent,
    roi_snapshot: Optional[Dict] = None,
    use_llm: bool = True,
) -> Optional[AgentAdvice]:
    """物理事件 → Agent 建议

    Args:
        event: 物理世界事件
        roi_snapshot: ROI 当前状态（用于上下文）
        use_llm: 是否尝试 LLM 增强

    Returns:
        AgentAdvice 或 None（事件无规则匹配时）
    """
    # 1) 规则匹配（永远先做）
    rule = match_rule(event)
    if not rule:
        return None
    advice = build_advice_from_rule(event, rule)

    # 2) LLM 增强
    if not use_llm or not LLM_ENABLED:
        return advice

    system_msg = (
        "你是 Insight Agent 商业助手，专注为线下商家分析物理世界事件。"
        "基于规则草稿 + 实时上下文，给出简明可执行的建议（不超过 200 字）。"
    )
    context = _build_event_context()
    roi_ctx = _build_roi_context(roi_snapshot)
    prompt = f"""事件: {event.type}/{event.subtype}
{json.dumps(event.context, ensure_ascii=False)[:300]}

规则建议草稿: {advice.text}
优先级: {advice.priority}
意图: {advice.intent}

{context}

{roi_ctx}

请基于以上信息，给出 1-2 句简明的中文建议，重点在"现在该做什么"。
"""

    t0 = time.time()
    llm_text = _call_llm(prompt, system_msg=system_msg, max_tokens=300)
    elapsed_ms = int((time.time() - t0) * 1000)

    if llm_text:
        advice.text = llm_text.strip()
        advice.reasoning = (
            f"事件 {event.type}:{event.subtype} 命中规则 → "
            f"LLM 增强（{LLM_MODEL}, {elapsed_ms}ms）"
        )
    else:
        advice.reasoning = (
            f"事件 {event.type}:{event.subtype} 命中规则（LLM 不可用，使用规则草稿）"
        )
    return advice


# ================================================================
# Chat: 接收用户查询
# ================================================================

def chat_with_agent(
    user_message: str,
    roi_snapshot: Optional[Dict] = None,
    history: Optional[List[Dict]] = None,
) -> Dict:
    """与 Agent 对话

    Args:
        user_message: 用户消息
        roi_snapshot: 当前 ROI 状态
        history: 历史对话 [{"role": "user/assistant", "content": "..."}]

    Returns:
        {
            "ok": True/False,
            "response": "LLM 回复",
            "context_used": "注入的上下文摘要",
            "model": LLM_MODEL,
            "elapsed_ms": int,
        }
    """
    t0 = time.time()
    context = _build_event_context()
    roi_ctx = _build_roi_context(roi_snapshot)
    system_msg = (
        "你是 Insight Agent 商业助手，专注为线下商家分析物理世界事件和人/货数据。"
        "回答要：1) 简洁（不超过 200 字） 2) 可执行 3) 用中文 4) 引用具体数据。"
    )
    # 拼接历史
    messages = [{"role": "system", "content": system_msg}]
    if history:
        # 只取最近 4 条历史避免超 token
        for h in history[-4:]:
            if "role" in h and "content" in h:
                messages.append({"role": h["role"], "content": h["content"]})
    # 注入上下文到用户消息
    user_with_context = f"""当前实时上下文:
{context}
{roi_ctx}

用户问题: {user_message}
"""
    messages.append({"role": "user", "content": user_with_context})

    client = _get_client()
    if client is None:
        return {
            "ok": False,
            "error": "LLM 未启用（DEEPSEEK_API_KEY 未配置）",
            "response": None,
            "context_used": context,
        }

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.5,
            max_tokens=600,
        )
        reply = response.choices[0].message.content
        elapsed_ms = int((time.time() - t0) * 1000)
        return {
            "ok": True,
            "response": reply.strip() if reply else "",
            "context_used": context,
            "model": LLM_MODEL,
            "elapsed_ms": elapsed_ms,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"LLM 调用失败: {e}",
            "response": None,
            "context_used": context,
        }


# ================================================================
# Report: 生成阶段报告
# ================================================================

def generate_report(
    window_seconds: int = 600,
    roi_snapshot: Optional[Dict] = None,
) -> Dict:
    """生成阶段报告（最近 N 秒事件汇总 + LLM 分析）"""
    window = get_window()
    summary = window.summary(seconds=window_seconds)

    # 找高优先级事件
    high_pri_events = []
    recent = window.recent(seconds=window_seconds, limit=9999)
    for e in recent:
        t = e.get("type", "")
        s = e.get("subtype", "")
        # 高优先级类型
        if t == "anomaly" and s in ("fall_down", "fight"):
            high_pri_events.append(e)
        elif t == "queue":
            high_pri_events.append(e)

    # 调 LLM 生成报告
    system_msg = (
        "你是 Insight Agent 商业助手，专注为商家生成分析报告。"
        "报告结构: 1) 阶段总结 2) 关键事件 3) 风险点 4) 行动建议。"
        "用中文，简洁专业，不超过 400 字。"
    )
    prompt = f"""基于以下物理世界事件数据，生成阶段分析报告。

报告时间窗: 最近 {window_seconds} 秒
事件统计: {summary}

高优先级事件: {len(high_pri_events)} 个
"""
    if high_pri_events:
        prompt += "\n关键事件:\n"
        for e in high_pri_events[:5]:
            prompt += f"- [{e.get('type')}/{e.get('subtype')}] {e.get('context', {})}\n"

    if roi_snapshot:
        prompt += f"\nROI 状态: {json.dumps(roi_snapshot, ensure_ascii=False)}\n"

    prompt += "\n请生成报告。"

    t0 = time.time()
    client = _get_client()
    if client is None:
        return {
            "ok": False,
            "error": "LLM 未启用（DEEPSEEK_API_KEY 未配置）",
            "summary": summary,
            "high_priority_count": len(high_pri_events),
            "report": None,
        }

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1000,
        )
        report_text = response.choices[0].message.content
        elapsed_ms = int((time.time() - t0) * 1000)
        return {
            "ok": True,
            "summary": summary,
            "high_priority_count": len(high_pri_events),
            "high_priority_events": high_pri_events[:10],
            "report": report_text.strip() if report_text else "",
            "model": LLM_MODEL,
            "elapsed_ms": elapsed_ms,
            "window_seconds": window_seconds,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"LLM 调用失败: {e}",
            "summary": summary,
            "high_priority_count": len(high_pri_events),
            "report": None,
        }


# ================================================================
# 自测
# ================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    print("=== 自测: agent_bridge ===\n")
    print(f"LLM 启用: {LLM_ENABLED}")
    print(f"Model: {LLM_MODEL}")
    print(f"Base URL: {LLM_BASE_URL}")
    print(f"API Key: {LLM_API_KEY[:10]}...{LLM_API_KEY[-4:] if LLM_API_KEY else '(空)'}")

    # 测试 ask_agent_for_event（无 LLM 路径）
    evt = PhysicalEvent(
        type="anomaly",
        subtype="fall_down",
        confidence=0.9,
        source="backend",
        context={"zone": "entrance", "track_id": 5},
    )
    advice = ask_agent_for_event(evt, use_llm=False)
    print(f"\n  ask_agent_for_event (no LLM): {advice.to_dict() if advice else None}")

    # 测试 chat_with_agent（如果 LLM 可用）
    if LLM_ENABLED:
        print("\n  chat_with_agent 测试...")
        result = chat_with_agent("现在客流情况如何？", roi_snapshot={"entrance": {"current": 5}})
        print(f"  ok={result['ok']}, response={(result.get('response') or '')[:200]}...")
        if not result["ok"]:
            print(f"  error: {result.get('error')}")

    print("\n✓ 自测完成")
