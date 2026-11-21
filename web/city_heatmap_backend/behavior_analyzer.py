"""城市热区图 — 人群行为分析引擎

分析维度：
1. 密度分析 — 区域人群密度评估
2. 流向分析 — 人群流动方向与速度
3. 热区检测 — 热点区域识别与演化追踪
4. 异常检测 — 异常聚集、踩踏风险预警
5. 趋势预测 — 基于历史数据的短期趋势
"""

import math
import uuid
from typing import List, Dict, Optional
from datetime import datetime

from event_schema import (
    CrowdEvent, HotspotInfo, AnalysisSnapshot, HeatmapPoint,
)


class BehaviorAnalyzer:
    """人群行为分析器"""

    def __init__(self):
        self._event_history: List[CrowdEvent] = []
        self._prev_total: int = 0
        self._prev_density: float = 0
        self._prev_hotspots: List[HotspotInfo] = []

    def analyze(
        self,
        total_people: int,
        hotspots: List[Dict],
        density: Optional[float] = None,
    ) -> AnalysisSnapshot:
        """执行全维度分析"""
        if density is None:
            density = total_people / 2.5  # 默认密度计算

        events = []

        # 1. 密度分析
        events.extend(self._analyze_density(density))

        # 2. 流向分析
        events.extend(self._analyze_flow(total_people))

        # 3. 热区检测
        events.extend(self._analyze_hotspots(hotspots))

        # 4. 异常检测
        events.extend(self._analyze_anomalies(density, len(hotspots)))

        # 更新历史
        self._prev_total = total_people
        self._prev_density = density
        self._prev_hotspots = [
            HotspotInfo(
                lng=h.get('lng', 0),
                lat=h.get('lat', 0),
                radius=h.get('radius', 300),
                value=h.get('value', 0),
                name=h.get('name', ''),
            )
            for h in hotspots
        ]

        # 转换为 HotspotInfo
        hotspot_infos = [
            HotspotInfo(
                lng=h.get('lng', 0),
                lat=h.get('lat', 0),
                radius=h.get('radius', 300),
                value=h.get('value', 0),
                name=h.get('name', ''),
            )
            for h in hotspots
        ]

        self._event_history = (events + self._event_history)[:100]  # 保留最近100条

        return AnalysisSnapshot(
            timestamp=datetime.now().isoformat(),
            total_people=total_people,
            density=density,
            hotspot_count=len(hotspots),
            anomaly_count=sum(1 for e in events if e.severity == 'high'),
            events=events,
            hotspots=hotspot_infos,
        )

    def _analyze_density(self, density: float) -> List[CrowdEvent]:
        """密度分析"""
        events = []
        if density > 400:
            events.append(CrowdEvent(
                event_type='anomaly_stampede',
                location='高密度区域',
                description=f'踩踏风险预警：密度 {density:.0f} 人/km²',
                severity='high',
                icon='🚨',
                label='踩踏风险',
                data={'density': density},
            ))
        elif density > 300:
            events.append(CrowdEvent(
                event_type='density_surge',
                location='核心区域',
                description=f'密度激增：{density:.0f} 人/km²，建议疏导',
                severity='high',
                icon='🔴',
                label='密度激增',
                data={'density': density},
            ))
        elif density > 200:
            events.append(CrowdEvent(
                event_type='density_warning',
                location='商业中心',
                description=f'密度偏高：{density:.0f} 人/km²',
                severity='medium',
                icon='🟡',
                label='密度预警',
                data={'density': density},
            ))
        return events

    def _analyze_flow(self, total: int) -> List[CrowdEvent]:
        """流向分析"""
        events = []
        if self._prev_total > 0:
            change_rate = (total - self._prev_total) / self._prev_total
            if change_rate > 0.3:
                events.append(CrowdEvent(
                    event_type='flow_converge',
                    location='监测区域',
                    description=f'人流快速增长 +{change_rate * 100:.0f}%',
                    severity='medium',
                    icon='➡️',
                    label='人流汇聚',
                    data={'change_rate': change_rate},
                ))
            elif change_rate < -0.25:
                events.append(CrowdEvent(
                    event_type='flow_disperse',
                    location='监测区域',
                    description=f'人流快速减少 {change_rate * 100:.0f}%',
                    severity='low',
                    icon='⬅️',
                    label='人流扩散',
                    data={'change_rate': change_rate},
                ))
        return events

    def _analyze_hotspots(self, hotspots: List[Dict]) -> List[CrowdEvent]:
        """热区检测"""
        events = []
        if len(hotspots) > len(self._prev_hotspots):
            events.append(CrowdEvent(
                event_type='hotspot_emerge',
                location='新增区域',
                description=f'新增热区，当前共 {len(hotspots)} 个',
                severity='medium',
                icon='🔥',
                label='热区形成',
                data={'count': len(hotspots)},
            ))
        elif len(hotspots) < len(self._prev_hotspots) and len(hotspots) > 0:
            events.append(CrowdEvent(
                event_type='hotspot_fade',
                location='部分区域',
                description=f'热区消退，当前共 {len(hotspots)} 个',
                severity='low',
                icon='❄️',
                label='热区消退',
                data={'count': len(hotspots)},
            ))
        return events

    def _analyze_anomalies(self, density: float, hotspot_count: int) -> List[CrowdEvent]:
        """异常检测"""
        events = []
        if density > 300 and hotspot_count < 2:
            events.append(CrowdEvent(
                event_type='anomaly_gather',
                location='热点区域',
                description='人群异常聚集在单一热点，建议分散引导',
                severity='high',
                icon='⚠️',
                label='异常聚集',
                data={'density': density, 'hotspots': hotspot_count},
            ))
        return events

    def get_history(self, limit: int = 50) -> List[CrowdEvent]:
        """获取事件历史"""
        return self._event_history[:limit]


def compute_heatmap_data(hotspots: List[Dict]) -> List[Dict]:
    """将热区数据转为热力图数据格式"""
    result = []
    for h in hotspots:
        # 在每个热区中心生成密集的采样点
        lng, lat = h.get('lng', 0), h.get('lat', 0)
        radius = h.get('radius', 300)
        value = h.get('value', 50)
        points_count = max(5, int(value / 2))

        for _ in range(points_count):
            angle = (hash(str(_)) % 360) * math.pi / 180
            r = (hash(str(_ + 1)) % 100) / 100 * radius * 0.6
            result.append({
                'lng': lng + (r * math.cos(angle)) / 111000,
                'lat': lat + (r * math.sin(angle)) / 111000,
                'count': value * (0.5 + (hash(str(_ + 2)) % 100) / 200),
            })
    return result
