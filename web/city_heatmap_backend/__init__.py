"""城市热区图 — 后端数据结构"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import json


@dataclass
class HotspotData:
    """热区数据"""
    lng: float
    lat: float
    radius: float
    value: float          # 热度值 0-100
    name: str = ""
    category: str = ""    # 商圈/景区/交通枢纽/居住区


@dataclass
class CrowdEvent:
    """人群事件"""
    event_id: str
    timestamp: str
    event_type: str       # density_surge / flow_converge / anomaly_gather 等
    location: str
    description: str
    severity: str         # high / medium / low
    data: Dict = field(default_factory=dict)


@dataclass
class AgentAdvice:
    """Agent 建议"""
    advice_id: str
    timestamp: str
    priority: str         # high / medium / low
    title: str
    description: str
    suggested_actions: List[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """分析结果"""
    timestamp: str
    total_people: int
    density: float        # 人/km²
    hotspot_count: int
    anomaly_count: int
    events: List[CrowdEvent] = field(default_factory=list)
    hotspots: List[HotspotData] = field(default_factory=list)
