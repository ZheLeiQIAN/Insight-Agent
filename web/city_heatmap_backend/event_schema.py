"""城市热区图 — 事件数据模型"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import datetime
import uuid
import json


@dataclass
class HeatmapPoint:
    """热力图数据点"""
    lng: float
    lat: float
    count: float  # 热度值


@dataclass
class HotspotInfo:
    """热区信息"""
    lng: float
    lat: float
    radius: float
    value: float
    name: str = ""
    category: str = ""


@dataclass
class CrowdEvent:
    """人群行为事件"""
    event_id: str = ""
    timestamp: str = ""
    event_type: str = ""       # density_surge, anomaly_gather 等
    location: str = ""
    description: str = ""
    severity: str = "low"     # high / medium / low
    data: Dict = field(default_factory=dict)
    icon: str = "📌"
    label: str = ""

    def __post_init__(self):
        if not self.event_id:
            self.event_id = str(uuid.uuid4())[:8]
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class AgentAdvice:
    """Agent 智能建议"""
    advice_id: str = ""
    timestamp: str = ""
    priority: str = "medium"
    title: str = ""
    description: str = ""
    suggested_actions: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.advice_id:
            self.advice_id = str(uuid.uuid4())[:8]
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class AnalysisSnapshot:
    """分析快照"""
    timestamp: str = ""
    total_people: int = 0
    density: float = 0
    hotspot_count: int = 0
    anomaly_count: int = 0
    events: List[CrowdEvent] = field(default_factory=list)
    hotspots: List[HotspotInfo] = field(default_factory=list)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


def to_json(obj):
    """将 dataclass 转为 JSON 兼容字典"""
    if hasattr(obj, '__dataclass_fields__'):
        result = {}
        for k in obj.__dataclass_fields__:
            v = getattr(obj, k)
            if isinstance(v, list):
                result[k] = [to_json(item) for item in v]
            elif hasattr(v, '__dataclass_fields__'):
                result[k] = to_json(v)
            else:
                result[k] = v
        return result
    return obj
