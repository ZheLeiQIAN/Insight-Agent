"""PP-Human 行人分析 pipeline（V0.3 阶段 C1）

封装 PPEngine，加入:
- IoU 跟踪（轻量多目标跟踪）
- 行人属性分析（V0.3: 仅高度/位置；C2: 接入 PP-YOLOE 属性模型）
- 行人事件流（enter / leave / linger / cross）
- 行为识别（V0.4 阶段 C2: 摔倒/打电话/打架/抽烟）

V0.3 简化：只做基础 detection + tracking，不做属性识别
阶段 C2: 接入 PP-YOLOE 行人属性（性别/年龄/上衣/背包）+ 行为识别
"""
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import numpy as np

from pp_engine import PPEngine, Detection, get_engine
from .behavior import BehaviorAnalyzer, get_analyzer as get_behavior_analyzer

logger = logging.getLogger(__name__)


@dataclass
class Track:
    track_id: int
    bbox: tuple
    class_name: str
    score: float
    first_seen: float
    last_seen: float
    age_frames: int = 0
    missed_frames: int = 0
    history: deque = field(default_factory=lambda: deque(maxlen=30))  # 最近 30 帧中心点

    @property
    def center(self):
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)


class IoUTracker:
    """基于 IoU 的轻量多目标跟踪器（无外观特征）"""

    def __init__(self, iou_threshold: float = 0.3, max_missed: int = 15):
        self.iou_threshold = iou_threshold
        self.max_missed = max_missed
        self.next_id = 1
        self.tracks: Dict[int, Track] = {}

    def _iou(self, box_a, box_b):
        x1 = max(box_a[0], box_b[0])
        y1 = max(box_a[1], box_b[1])
        x2 = min(box_a[2], box_b[2])
        y2 = min(box_a[3], box_b[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
        area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
        union = area_a + area_b - inter
        return inter / (union + 1e-6)

    def update(self, detections: List[Detection]) -> List[Track]:
        """更新跟踪器"""
        now = time.time()
        used = set()

        # 1) 已有 track 匹配
        for tid, track in list(self.tracks.items()):
            best_iou, best_det = 0, -1
            for i, det in enumerate(detections):
                if i in used:
                    continue
                if det.class_name != "person":
                    continue
                iou = self._iou(track.bbox, det.bbox)
                if iou > best_iou:
                    best_iou, best_det = iou, i
            if best_iou >= self.iou_threshold and best_det >= 0:
                det = detections[best_det]
                track.bbox = det.bbox
                track.score = det.score
                track.last_seen = now
                track.age_frames += 1
                track.missed_frames = 0
                track.history.append(track.center)
                used.add(best_det)
            else:
                track.missed_frames += 1
                if track.missed_frames > self.max_missed:
                    del self.tracks[tid]

        # 2) 新检测创建新 track
        for i, det in enumerate(detections):
            if i in used or det.class_name != "person":
                continue
            tid = self.next_id
            self.next_id += 1
            self.tracks[tid] = Track(
                track_id=tid,
                bbox=det.bbox,
                class_name=det.class_name,
                score=det.score,
                first_seen=now,
                last_seen=now,
            )
            self.tracks[tid].history.append(self.tracks[tid].center)

        return list(self.tracks.values())

    def clear(self):
        self.tracks.clear()
        self.next_id = 1


class PPHumanPipeline:
    """PP-Human pipeline（V0.3: 行人检测 + IoU 跟踪；V0.4: + 行为识别）"""

    def __init__(
        self,
        engine: Optional[PPEngine] = None,
        conf_threshold: float = 0.5,
        person_only: bool = True,
        enable_behavior: bool = True,
    ):
        self.engine = engine or get_engine(conf=conf_threshold)
        self.person_only = person_only
        self.enable_behavior = enable_behavior
        self.tracker = IoUTracker(iou_threshold=0.3, max_missed=10)
        self.behavior_analyzer: Optional[BehaviorAnalyzer] = (
            get_behavior_analyzer() if enable_behavior else None
        )
        self._frame_count = 0
        self._last_count = 0
        # 给非 person detection（如 cell phone）分配临时 track_id
        # 用最近的 person track 的 id

    def process(self, frame: np.ndarray) -> List[Track]:
        """单帧处理：检测+跟踪，返回活跃 track 列表"""
        self._frame_count += 1
        detections = self.engine.infer(frame)
        if self.person_only:
            detections = [d for d in detections if d.is_person()]
        tracks = self.tracker.update(detections)
        return tracks

    def process_with_events(self, frame: np.ndarray) -> dict:
        """单帧处理 + 事件提取（含行为识别）"""
        self._frame_count += 1

        # 1) 一次性推理（所有类别，给行为识别用）
        all_detections = self.engine.infer(frame)

        # 2) 仅 person 跟踪
        person_detections = [d for d in all_detections if d.is_person()]
        tracks = self.tracker.update(person_detections)

        events = []

        # 3) 人数变化
        current_count = len(tracks)
        if current_count != self._last_count:
            events.append({
                "type": "count",
                "subtype": "person_increase" if current_count > self._last_count else "person_decrease",
                "persons": current_count,
                "change": current_count - self._last_count,
                "source": "backend",
            })
            self._last_count = current_count

        # 4) 滞留检测（连续 N 帧未移动）
        for t in tracks:
            if t.age_frames > 60 and len(t.history) >= 30:
                # 检查最近 30 帧是否位移 < 10 像素
                hist = list(t.history)
                xs = [p[0] for p in hist[-30:]]
                ys = [p[1] for p in hist[-30:]]
                if (max(xs) - min(xs) < 10) and (max(ys) - min(ys) < 10):
                    if t.age_frames % 60 == 0:  # 每 60 帧触发一次
                        events.append({
                            "type": "dwell",
                            "subtype": "static_person",
                            "track_id": t.track_id,
                            "duration_sec": round(t.age_frames / 30, 1),
                            "bbox": t.bbox,
                            "source": "backend",
                        })

        # 5) 行为识别（摔倒/打电话/打架/抽烟）
        if self.behavior_analyzer is not None:
            # 给所有 detection 关联 track_id（给 person 用 tracker 的 id，
            # 给 cell phone 等非 person 用最近 person track 的 id）
            detections_with_tid = self._assign_track_ids(all_detections, tracks)
            behavior_events = self.behavior_analyzer.analyze(
                detections=detections_with_tid,
                frame_idx=self._frame_count,
                frame_shape=frame.shape[:2],
            )
            for be in behavior_events:
                events.append(be.to_dict())

        return {
            "tracks": [
                {
                    "track_id": t.track_id,
                    "bbox": t.bbox,
                    "score": t.score,
                    "age_frames": t.age_frames,
                    "class_name": t.class_name,
                }
                for t in tracks
            ],
            "events": events,
            "behavior_stats": self.behavior_analyzer.stats if self.behavior_analyzer else {},
        }

    def _assign_track_ids(
        self,
        detections: List[Detection],
        tracks: List[Track],
    ) -> List[Detection]:
        """给所有 detection 分配 track_id
        - person detection: 用 tracker 的 id（通过 IoU 匹配）
        - 非 person (cell phone 等): 用最近的 person track id
        """
        if not tracks:
            return detections

        # 预计算 track 的中心点和 bbox
        track_centers = []
        for t in tracks:
            x1, y1, x2, y2 = t.bbox
            track_centers.append({
                "track_id": t.track_id,
                "center": ((x1 + x2) / 2, (y1 + y2) / 2),
                "bbox": t.bbox,
            })

        result = []
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

            # 找最近 track（按中心点距离）
            best_tid = None
            best_dist = float("inf")
            for tc in track_centers:
                tcx, tcy = tc["center"]
                dist = ((cx - tcx) ** 2 + (cy - tcy) ** 2) ** 0.5
                # 必须落在 track bbox 内或附近
                tx1, ty1, tx2, ty2 = tc["bbox"]
                margin = max(tx2 - tx1, ty2 - ty1) * 0.5
                if abs(cx - tcx) < margin * 2 and abs(cy - tcy) < margin * 2:
                    if dist < best_dist:
                        best_dist = dist
                        best_tid = tc["track_id"]

            new_det = Detection(
                track_id=best_tid if best_tid is not None else det.track_id,
                bbox=det.bbox,
                score=det.score,
                class_id=det.class_id,
                class_name=det.class_name,
                source=det.source,
            )
            result.append(new_det)
        return result

    @property
    def stats(self) -> dict:
        return {
            "frame_count": self._frame_count,
            "current_tracks": len(self.tracker.tracks),
            "engine": self.engine.stats(),
        }
