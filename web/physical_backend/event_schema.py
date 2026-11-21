"""统一事件 JSON Schema

浏览器与后端、后端与 LLM 之间流转的事件结构
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import Enum
import time


class EventType(str, Enum):
    GESTURE = "gesture"
    FACE = "face"
    COUNT = "count"
    HEATMAP = "heatmap"
    ANOMALY = "anomaly"
    QUEUE = "queue"
    DWELL = "dwell"
    INTEREST = "interest"


class Source(str, Enum):
    BROWSER = "browser"
    BACKEND = "backend"


@dataclass
class PhysicalEvent:
    ts: int = field(default_factory=lambda: int(time.time() * 1000))
    type: str = ""
    subtype: str = ""
    confidence: float = 0.0
    bbox: Optional[List[float]] = None  # [x, y, w, h]
    track_id: Optional[str] = None
    source: str = Source.BROWSER.value
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# 阶段 D Agent 建议返回结构
@dataclass
class AgentAdvice:
    ts: int = field(default_factory=lambda: int(time.time() * 1000))
    priority: str = "low"  # low / medium / high
    intent: str = ""
    text: str = ""
    actions: List[str] = field(default_factory=list)
    reasoning: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
