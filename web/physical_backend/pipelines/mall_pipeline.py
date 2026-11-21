"""MallPipeline 商场定制 pipeline（V0.3 阶段 C1: 基础客流）

V0.3 实现:
- 区域 ROI 计数（划定"入口/收银台/货架"等区域，统计人数）
- 累计跟踪轨迹（热区图基础数据）

V0.4 实现（C2 阶段）:
- 排队检测（多人聚集 + 在 ROI 内）
- 滞留分析（每个 ROI 累积停留时长排序）
"""
import logging
import time
from collections import defaultdict
from typing import List, Dict, Optional
import numpy as np
from .pphuman_pipeline import PPHumanPipeline, Track

logger = logging.getLogger(__name__)


class ROI:
    """感兴趣区域（矩形）"""

    def __init__(self, name: str, x1: int, y1: int, x2: int, y2: int):
        self.name = name
        self.bbox = (x1, y1, x2, y2)
        self.enter_count = 0
        self.exit_count = 0
        self.current_count = 0
        self.last_inside: Dict[int, bool] = {}  # track_id -> 是否在区域内
        # V0.4: 滞留分析
        self._dwell_start: Dict[int, float] = {}  # track_id -> 进入时间戳
        self.dwell_seconds_per_track: Dict[int, float] = {}  # track_id -> 累计停留秒
        self.dwell_total_seconds: float = 0.0
        self.dwell_max_track_id: Optional[int] = None
        self.dwell_max_seconds: float = 0.0
        # V0.4: 排队检测
        self.queue_first_detected: Optional[float] = None  # 排队起始时间
        self.queue_max_length: int = 0
        self.queue_alerted: bool = False  # 是否已告警

    def contains(self, point) -> bool:
        x, y = point
        return self.bbox[0] <= x <= self.bbox[2] and self.bbox[1] <= y <= self.bbox[3]

    def update(self, tracks: List[Track]) -> int:
        """更新区域统计；返回当前在区域内的 track 数"""
        now = time.time()
        inside_now = {t.track_id: self.contains(t.center) for t in tracks}
        enters = 0
        for tid, inside in inside_now.items():
            prev = self.last_inside.get(tid, False)
            if inside and not prev:
                enters += 1
                self.enter_count += 1
                self._dwell_start[tid] = now
            elif not inside and prev:
                # 离开时累加停留时长
                start = self._dwell_start.pop(tid, None)
                if start is not None:
                    duration = now - start
                    self.dwell_seconds_per_track[tid] = self.dwell_seconds_per_track.get(tid, 0) + duration
                    self.dwell_total_seconds += duration
                    if self.dwell_seconds_per_track[tid] > self.dwell_max_seconds:
                        self.dwell_max_seconds = self.dwell_seconds_per_track[tid]
                        self.dwell_max_track_id = tid
        # 更新仍在 ROI 内的 track 累积停留
        for tid, inside in inside_now.items():
            if inside and tid in self._dwell_start:
                duration = now - self._dwell_start[tid]
                # 实时累加到总时长
                # 注意: 这里累加为"瞬时值"，离开时再正式入账
        self.current_count = sum(inside_now.values())
        self.last_inside = inside_now
        return enters


class MallPipeline:
    """商场定制 pipeline（V0.3: 区域计数 + 轨迹聚合）"""

    # 排队检测参数
    QUEUE_THRESHOLD = 3  # 触发排队告警的最小人数
    QUEUE_ALERT_DURATION_SEC = 5.0  # 持续 N 秒才告警
    QUEUE_COOLDOWN_SEC = 30.0  # 同 ROI 告警冷却

    def __init__(self, human_pipeline: Optional[PPHumanPipeline] = None):
        self.human_pipeline = human_pipeline or PPHumanPipeline()
        self.rois: Dict[str, ROI] = {}
        # 热区图（归一化 80x60 网格）
        self.heatmap_grid_w, self.heatmap_grid_h = 80, 60
        self.heatmap = np.zeros((self.heatmap_grid_h, self.heatmap_grid_w), dtype=np.float32)
        self._heatmap_subscribers = 0

    def add_roi(self, name: str, x1: int, y1: int, x2: int, y2: int):
        """添加 ROI 区域"""
        self.rois[name] = ROI(name, x1, y1, x2, y2)
        logger.info("添加 ROI: %s %s", name, (x1, y1, x2, y2))

    def process(self, frame: np.ndarray) -> dict:
        """单帧处理"""
        result = self.human_pipeline.process_with_events(frame)
        tracks = result["tracks"]
        events = result["events"]

        h, w = frame.shape[:2]

        # 1) ROI 计数
        roi_summary = {}
        for name, roi in self.rois.items():
            enters = roi.update([type('T', (), {'track_id': t['track_id'], 'center': (
                (t['bbox'][0] + t['bbox'][2]) / 2, (t['bbox'][1] + t['bbox'][3]) / 2
            )})() for t in tracks])
            roi_summary[name] = {
                "current": roi.current_count,
                "enters_total": roi.enter_count,
                "exits_total": roi.exit_count,
            }
            if enters > 0:
                events.append({
                    "type": "roi_enter",
                    "subtype": f"进入{name}",
                    "zone": name,
                    "persons": enters,
                    "source": "backend",
                })

        # 1.5) 排队检测（V0.4）
        queue_alerts = self._detect_queues(roi_summary)
        for alert in queue_alerts:
            events.append(alert)

        # 2) 热区图累加
        for t in tracks:
            cx = (t["bbox"][0] + t["bbox"][2]) / 2
            cy = (t["bbox"][1] + t["bbox"][3]) / 2
            gx = int(cx / w * self.heatmap_grid_w)
            gy = int(cy / h * self.heatmap_grid_h)
            if 0 <= gx < self.heatmap_grid_w and 0 <= gy < self.heatmap_grid_h:
                self.heatmap[gy, gx] += 1
        # 衰减（保持热区图持续更新）
        self.heatmap *= 0.995
        np.clip(self.heatmap, 0, 100, out=self.heatmap)

        return {
            "tracks": tracks,
            "events": events,
            "rois": roi_summary,
            "queues": self._queue_summary(roi_summary),
            "dwell": self._dwell_summary(),
            "heatmap": {
                "w": self.heatmap_grid_w,
                "h": self.heatmap_grid_h,
                "data": self.heatmap.tolist(),
                "max": float(self.heatmap.max()),
            },
            "stats": {
                "frame_count": self.human_pipeline._frame_count,
                "engine": self.human_pipeline.engine.stats(),
            },
        }

    def _detect_queues(self, roi_summary: Dict[str, dict]) -> List[dict]:
        """检测排队（V0.4）：ROI 内人数持续 >= 阈值 + 持续 N 秒"""
        alerts = []
        now = time.time()
        for name, roi in self.rois.items():
            count = roi.current_count
            if count >= self.QUEUE_THRESHOLD:
                if roi.queue_first_detected is None:
                    roi.queue_first_detected = now
                # 更新最大长度
                if count > roi.queue_max_length:
                    roi.queue_max_length = count
                # 持续时长
                duration = now - roi.queue_first_detected
                # 是否触发告警
                if (
                    duration >= self.QUEUE_ALERT_DURATION_SEC
                    and not roi.queue_alerted
                ):
                    roi.queue_alerted = True
                    alerts.append({
                        "type": "queue",
                        "subtype": "queue_overflow",
                        "zone": name,
                        "length": count,
                        "max_length": roi.queue_max_length,
                        "duration_sec": round(duration, 1),
                        "threshold": self.QUEUE_THRESHOLD,
                        "source": "backend",
                    })
            else:
                # 人数下降，重置
                roi.queue_first_detected = None
                if roi.queue_alerted and count == 0:
                    # 队列清空，重置告警标记
                    roi.queue_alerted = False
        return alerts

    def _queue_summary(self, roi_summary: Dict[str, dict]) -> dict:
        """汇总所有 ROI 的队列状态"""
        out = {}
        for name, roi in self.rois.items():
            out[name] = {
                "current_length": roi.current_count,
                "max_length": roi.queue_max_length,
                "queueing": roi.current_count >= self.QUEUE_THRESHOLD,
                "alerted": roi.queue_alerted,
                "alert_threshold": self.QUEUE_THRESHOLD,
            }
        return out

    def _dwell_summary(self) -> dict:
        """汇总所有 ROI 的滞留情况"""
        out = {}
        for name, roi in self.rois.items():
            # 仍在 ROI 内的 track 实时累加
            now = time.time()
            current_dwell_total = roi.dwell_total_seconds
            active_dwell = []
            for tid, start in roi._dwell_start.items():
                duration = now - start
                active_dwell.append({
                    "track_id": tid,
                    "duration_sec": round(duration, 1),
                })
                current_dwell_total += duration
            out[name] = {
                "total_dwell_sec": round(current_dwell_total, 1),
                "max_track_id": roi.dwell_max_track_id,
                "max_dwell_sec": round(roi.dwell_max_seconds, 1),
                "unique_visitors": len(roi.dwell_seconds_per_track),
                "active_in_roi": len(roi._dwell_start),
                "active_dwell": active_dwell[:10],  # 最多返回 10 个
            }
        return out
