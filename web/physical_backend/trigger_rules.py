"""意图预判规则（V0.4 阶段 C2: 12 规则）

V0.1: 5 规则 (gesture + queue + anomaly)
V0.4: 12 规则
  - 4 行为异常 (fall_down, fight, phone_call, smoking)
  - 5 ROI/队列 (entrance, checkout, shelf, queue_overflow, crowd_gathering)
  - 3 留存/商品 (dwell, high_value_customer, attention_zone)

阶段 D 完整实现:
- 维护滚动窗口（每事件/每用户/每区域）
- 匹配规则模式 → 输出 AgentAdvice
- 支持热加载商家自定义规则
"""
from typing import Dict, List, Optional
from event_schema import AgentAdvice, PhysicalEvent


# 规则模板
RULES: Dict[tuple, dict] = {
    # ========== 1) 手势/表情意图（来自浏览器） ==========
    ("gesture", "thumbs_up"): {
        "intent": "customer_satisfied",
        "priority": "low",
        "query_template": "用户对{category}表示满意，找类似好评案例与可推荐产品",
    },
    ("gesture", "thumbs_down"): {
        "intent": "customer_dissatisfied",
        "priority": "medium",
        "query_template": "用户对{category}表示不满，分析常见原因和补救策略",
    },
    ("face", "smile"): {
        "intent": "customer_happy",
        "priority": "low",
        "query_template": "用户表情愉悦，可推荐关联商品",
    },
    ("face", "frown"): {
        "intent": "customer_unhappy",
        "priority": "medium",
        "query_template": "用户表情不悦，分析可能原因并提示店员关注",
    },

    # ========== 2) 行为异常（来自后端 behavior analyzer） ==========
    ("anomaly", "fall_down"): {
        "intent": "emergency_fall",
        "priority": "high",
        "query_template": "检测到摔倒事件，立即通知现场人员并启动应急流程；分析 {zone} 区域的安全隐患",
        "actions": ["alert_staff", "call_manager", "call_emergency"],
    },
    ("anomaly", "fight"): {
        "intent": "security_incident",
        "priority": "high",
        "query_template": "检测到打架事件，立即通知安保；分析该区域历史纠纷记录",
        "actions": ["alert_security", "call_police", "review_cameras"],
    },
    ("anomaly", "phone_call"): {
        "intent": "distracted_customer",
        "priority": "low",
        "query_template": "用户在 {zone} 区域打电话，可能有销售机会",
        "actions": ["notify_sales"],
    },
    ("anomaly", "smoking"): {
        "intent": "policy_violation",
        "priority": "medium",
        "query_template": "检测到 {zone} 区域有人吸烟，违反禁烟规定",
        "actions": ["alert_staff", "play_announcement"],
    },

    # ========== 3) 排队/拥堵（V0.4 新增） ==========
    ("queue", "queue_overflow"): {
        "intent": "service_bottleneck",
        "priority": "medium",
        "query_template": "{zone} 区域排队 {length} 人持续 {duration_sec} 秒，分析原因并给出加开窗口建议",
        "actions": ["open_extra_window", "alert_manager"],
    },
    ("queue", "length>5_for>3min"): {
        "intent": "service_bottleneck",
        "priority": "medium",
        "query_template": "排队超过 5 人持续 3 分钟，分析常见原因与改善建议",
    },

    # ========== 4) 滞留/留存（V0.4 新增） ==========
    ("dwell", "static_person"): {
        "intent": "high_engagement",
        "priority": "low",
        "query_template": "用户在 {zone} 区域停留 {duration_sec} 秒，可能对商品感兴趣",
    },
    ("dwell", "long_dwell>60s"): {
        "intent": "high_value_customer",
        "priority": "medium",
        "query_template": "用户在 {zone} 停留超过 60 秒，可能是高价值客户，安排店员主动服务",
        "actions": ["notify_sales", "suggest_promotion"],
    },

    # ========== 5) 客流/区域（V0.4 新增） ==========
    ("roi_enter", "entrance"): {
        "intent": "customer_arrival",
        "priority": "low",
        "query_template": "新客户进入 {zone}，统计客流量",
    },
    ("count", "person_increase"): {
        "intent": "crowd_growing",
        "priority": "low",
        "query_template": "区域人数增加到 {persons}，监控客流密度",
    },
}


def match_rule(event: PhysicalEvent) -> Optional[dict]:
    """根据事件匹配预定义规则；返回规则模板或 None"""
    key = (event.type, event.subtype)
    if key in RULES:
        return RULES[key]
    return None


def list_rules() -> List[dict]:
    """列出所有规则（API 用）"""
    return [
        {
            "type": t,
            "subtype": s,
            "intent": r.get("intent", ""),
            "priority": r.get("priority", "low"),
            "query_template": r.get("query_template", ""),
            "actions": r.get("actions", []),
        }
        for (t, s), r in RULES.items()
    ]


def build_advice_from_rule(event: PhysicalEvent, rule: dict) -> AgentAdvice:
    """根据规则生成 AgentAdvice 草稿（不含 LLM 增强）"""
    return AgentAdvice(
        priority=rule.get("priority", "low"),
        intent=rule.get("intent", ""),
        text=rule.get("query_template", "").format(**event.context),
        actions=rule.get("actions", []),
        reasoning=f"事件 {event.type}:{event.subtype} 命中规则",
    )
