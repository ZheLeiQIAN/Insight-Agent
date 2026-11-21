"""行为识别模块（V0.4 阶段 C2：纯启发式方案）

设计原则:
- 不引入额外模型权重（节省 100MB+）
- 复用 YOLOv4-tiny 已有 detection 结果
- 基于几何关系 + 启发式规则

支持行为:
- fall_down 摔倒    : person bbox 高度/宽度比 < 0.7（横躺特征）
- phone_call 打电话 : cell phone 中心点与 person 中心点距离 < person 宽度
- fight 打架        : >= 2 person 且中心距离 < 50 像素（可能互相推搡）
- smoking 抽烟      : COCO 80 类不含 cigarette，预留接口返回 None

防抖:
- 每个 track_id 每个 subtype 5 秒内最多触发 1 次
- 摔倒/打架连续多帧确认（FRAME_CONFIRM=3）后触发

输出格式（与 trigger_rules.py 兼容）:
{
    "type": "anomaly",
    "subtype": "fall_down",
    "track_id": 5,
    "confidence": 0.85,
    "bbox": [x, y, w, h],
    "context": {"aspect_ratio": 0.42, "frame_idx": 123},
    "source": "backend",
}
"""
import logging
import time
from collections import defaultdict, deque
from typing import List, Dict, Optional
from dataclasses import dataclass

from pp_engine import Detection

logger = logging.getLogger(__name__)


def _center(bbox: tuple) -> tuple:
    """bbox (x1, y1, x2, y2) → 中心 (cx, cy)"""
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)


# COCO 类别 ID（COCO 80）
# 来源: coco.names 顺序
COCO_CLASSES = [
    "person", "bicycle", "car", "motorbike", "aeroplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign", "parking meter",
    "bench", "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear",
    "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase",
    "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat",
    "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle",
    "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut",
    "cake", "chair", "sofa", "pottedplant", "bed", "diningtable", "toilet",
    "tvmonitor", "laptop", "mouse", "remote", "keyboard", "cell phone",
    "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock",
    "vase", "scissors", "teddy bear", "hair drier", "toothbrush",
]
COCO_CELL_PHONE_ID = COCO_CLASSES.index("cell phone")  # 67


@dataclass
class BehaviorEvent:
    """行为事件（dataclass 形式，方便 pipeline 转换）"""
    subtype: str
    track_id: Optional[int]
    confidence: float
    bbox: tuple
    context: dict

    def to_dict(self) -> dict:
        x1, y1, x2, y2 = self.bbox
        return {
            "type": "anomaly",
            "subtype": self.subtype,
            "track_id": self.track_id,
            "confidence": self.confidence,
            "bbox": [x1, y1, x2 - x1, y2 - y1],
            "context": self.context,
            "source": "backend",
        }


class BehaviorAnalyzer:
    """启发式行为分析器

    用法:
        analyzer = BehaviorAnalyzer()
        events = analyzer.analyze(detections, frame_idx=0, frame_shape=(720, 1280))
    """

    # 摔倒: 高度/宽度比阈值（< 0.7 表示横躺）
    FALLDOWN_ASPECT_RATIO = 0.7
    FALLDOWN_MIN_SCORE = 0.5

    # 打电话: 手机中心点离 person 中心点的距离（按 person 宽度比例）
    PHONECALL_DIST_RATIO = 0.6  # 距离 < person 宽度 * 0.6
    PHONECALL_MIN_SCORE = 0.4

    # 打架: person 之间中心距离（按帧宽高最大值比例）
    FIGHT_DIST_RATIO = 0.10  # 距离 < max(h, w) * 0.10
    FIGHT_MIN_PERSONS = 2
    FIGHT_MIN_SCORE = 0.4

    # 抽烟: COCO 无 cigarette 类，保留接口
    SMOKING_ENABLED = False

    # 防抖
    COOLDOWN_SEC = 5.0
    FRAME_CONFIRM = 3  # 连续 N 帧确认才触发

    def __init__(self):
        # 上次触发时间: (track_id, subtype) -> ts
        self._last_trigger: Dict[tuple, float] = {}
        # 帧连续确认: (track_id, subtype) -> deque of (ts, evidence)
        self._confirm_buffer: Dict[tuple, deque] = defaultdict(lambda: deque(maxlen=self.FRAME_CONFIRM + 2))
        # 统计
        self._stats = {
            "analyze_calls": 0,
            "fall_down_count": 0,
            "phone_call_count": 0,
            "fight_count": 0,
            "smoking_count": 0,
        }

    def analyze(
        self,
        detections: List[Detection],
        frame_idx: int = 0,
        frame_shape: Optional[tuple] = None,
    ) -> List[BehaviorEvent]:
        """单帧行为分析 → 返回事件列表

        Args:
            detections: YOLO 检测结果列表
            frame_idx: 当前帧索引（写入 context 便于回溯）
            frame_shape: (h, w) 用于打架距离归一化
        """
        self._stats["analyze_calls"] += 1
        now = time.time()
        events: List[BehaviorEvent] = []

        persons = [d for d in detections if d.is_person()]
        cell_phones = [d for d in detections if d.class_id == COCO_CELL_PHONE_ID and d.score >= self.PHONECALL_MIN_SCORE]

        # 1) 摔倒检测
        for p in persons:
            evt = self._check_fall_down(p, frame_idx, now)
            if evt:
                events.append(evt)
                self._stats["fall_down_count"] += 1

        # 2) 打电话检测
        for p in persons:
            evt = self._check_phone_call(p, cell_phones, frame_idx, now)
            if evt:
                events.append(evt)
                self._stats["phone_call_count"] += 1

        # 3) 打架检测（多 person 互相接近）
        if len(persons) >= self.FIGHT_MIN_PERSONS and frame_shape is not None:
            fight_events = self._check_fight(persons, frame_idx, frame_shape, now)
            events.extend(fight_events)
            self._stats["fight_count"] += len(fight_events)

        # 4) 抽烟检测（占位）
        if self.SMOKING_ENABLED:
            # 未来扩展: 接入 PaddleDetection 的属性识别 / 自训练模型
            for p in persons:
                evt = self._check_smoking(p, frame_idx, now)
                if evt:
                    events.append(evt)
                    self._stats["smoking_count"] += 1

        return events

    # ------------------------------------------------------------------
    # 4 类具体规则
    # ------------------------------------------------------------------

    def _check_fall_down(self, p: Detection, frame_idx: int, now: float) -> Optional[BehaviorEvent]:
        """摔倒: person bbox 高度 < 宽度 * 0.7（即横向比例）"""
        x1, y1, x2, y2 = p.bbox
        w = x2 - x1
        h = y2 - y1
        if w <= 0 or h <= 0:
            return None
        if p.score < self.FALLDOWN_MIN_SCORE:
            return None
        aspect = h / w
        if aspect >= self.FALLDOWN_ASPECT_RATIO:
            return None

        # 帧连续确认
        key = (p.track_id, "fall_down")
        buf = self._confirm_buffer[key]
        buf.append((now, {"aspect": round(aspect, 3), "w": int(w), "h": int(h)}))
        if len(buf) < self.FRAME_CONFIRM:
            return None

        # 冷却时间
        if not self._pass_cooldown(key, now):
            return None
        self._last_trigger[key] = now

        return BehaviorEvent(
            subtype="fall_down",
            track_id=p.track_id,
            confidence=round(min(1.0, p.score + 0.2), 3),
            bbox=p.bbox,
            context={
                "aspect_ratio": round(aspect, 3),
                "width": int(w),
                "height": int(h),
                "frame_idx": frame_idx,
                "confirmed_frames": len(buf),
            },
        )

    def _check_phone_call(
        self,
        p: Detection,
        cell_phones: List[Detection],
        frame_idx: int,
        now: float,
    ) -> Optional[BehaviorEvent]:
        """打电话: cell phone 中心距离 person 中心 < person 宽度 * 0.6"""
        if not cell_phones:
            return None
        if p.score < self.PHONECALL_MIN_SCORE:
            return None
        px, py = _center(p.bbox)
        pw = p.bbox[2] - p.bbox[0]
        ph = p.bbox[3] - p.bbox[1]
        threshold = min(pw, ph) * self.PHONECALL_DIST_RATIO

        # 找最近的 cell phone
        best_phone = None
        best_dist = float("inf")
        for phone in cell_phones:
            fpx, fpy = _center(phone.bbox)
            dist = ((px - fpx) ** 2 + (py - fpy) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_phone = phone

        if best_phone is None or best_dist > threshold:
            return None

        # 帧连续确认
        key = (p.track_id, "phone_call")
        buf = self._confirm_buffer[key]
        buf.append((now, {"dist": round(best_dist, 1), "phone_score": best_phone.score}))
        if len(buf) < self.FRAME_CONFIRM:
            return None

        if not self._pass_cooldown(key, now):
            return None
        self._last_trigger[key] = now

        return BehaviorEvent(
            subtype="phone_call",
            track_id=p.track_id,
            confidence=round(min(1.0, (p.score + best_phone.score) / 2 + 0.1), 3),
            bbox=p.bbox,
            context={
                "phone_bbox": best_phone.bbox,
                "phone_score": round(best_phone.score, 3),
                "distance_px": round(best_dist, 1),
                "frame_idx": frame_idx,
            },
        )

    def _check_fight(
        self,
        persons: List[Detection],
        frame_idx: int,
        frame_shape: tuple,
        now: float,
    ) -> List[BehaviorEvent]:
        """打架: 至少 2 person 中心距离 < min(h, w) * 0.10

        启发式: 互相接近的多人可能推搡/打架
        注意: 这会误判 "排队" 和 "朋友合影"，
              实际部署需结合 ROI / 时间窗口 / 运动剧烈程度判断
        """
        h, w = frame_shape[:2]
        threshold = min(h, w) * self.FIGHT_DIST_RATIO
        events = []
        # 两两配对
        for i in range(len(persons)):
            for j in range(i + 1, len(persons)):
                a, b = persons[i], persons[j]
                ax, ay = _center(a.bbox)
                bx, by = _center(b.bbox)
                dist = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
                if dist > threshold:
                    continue
                if a.score < self.FIGHT_MIN_SCORE or b.score < self.FIGHT_MIN_SCORE:
                    continue
                # 用最小 track_id 作为去重 key
                key = (min(a.track_id or 0, b.track_id or 0), "fight")
                buf = self._confirm_buffer[key]
                buf.append((now, {"dist": round(dist, 1), "pair": [a.track_id, b.track_id]}))
                if len(buf) < self.FRAME_CONFIRM:
                    continue
                if not self._pass_cooldown(key, now):
                    continue
                self._last_trigger[key] = now
                events.append(BehaviorEvent(
                    subtype="fight",
                    track_id=None,  # 多人事件无单一 track_id
                    confidence=round(min(1.0, (a.score + b.score) / 2 + 0.15), 3),
                    bbox=a.bbox,  # 用第一个人
                    context={
                        "persons": [a.track_id, b.track_id],
                        "distance_px": round(dist, 1),
                        "frame_idx": frame_idx,
                    },
                ))
        return events

    def _check_smoking(self, p: Detection, frame_idx: int, now: float) -> Optional[BehaviorEvent]:
        """抽烟: COCO 80 类无 cigarette，保留接口"""
        # 未来可扩展: 接入自训练小模型 / 行为识别
        return None

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------

    def _pass_cooldown(self, key: tuple, now: float) -> bool:
        last = self._last_trigger.get(key, 0)
        return (now - last) >= self.COOLDOWN_SEC

    def reset(self):
        """清空状态（新视频/新会话，保留累计统计）"""
        self._last_trigger.clear()
        self._confirm_buffer.clear()

    @property
    def stats(self) -> dict:
        return dict(self._stats)


# 单例工厂
_analyzer_singleton: Optional[BehaviorAnalyzer] = None


def get_analyzer() -> BehaviorAnalyzer:
    """获取全局单例分析器"""
    global _analyzer_singleton
    if _analyzer_singleton is None:
        _analyzer_singleton = BehaviorAnalyzer()
    return _analyzer_singleton


# ================================================================
# 自测（合成数据）
# ================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # 构造假 detection
    def make_det(class_name, bbox, score, track_id=None):
        # 用 COCO_CLASSES 找 class_id
        cid = COCO_CLASSES.index(class_name) if class_name in COCO_CLASSES else 0
        return Detection(
            track_id=track_id,
            bbox=bbox,
            score=score,
            class_id=cid,
            class_name=class_name,
        )

    FRAME = (720, 1280)  # h, w

    print("\n=== 自测: 4 类行为识别 ===\n")

    # 场景 1: 摔倒（宽 > 高, 比例 0.3）
    detections = [
        make_det("person", (100, 400, 500, 600), 0.85, track_id=1),  # w=400, h=200, ratio=0.5
    ]
    analyzer = get_analyzer()
    # 连续 4 帧确认（绕过 FRAME_CONFIRM）
    all_events = []
    for f in range(5):
        all_events.extend(analyzer.analyze(detections, frame_idx=f, frame_shape=FRAME))
    print(f"场景1 摔倒: 触发 {sum(1 for e in all_events if e.subtype == 'fall_down')} 次 (期望 1)")

    # 场景 2: 打电话（cell phone 在人身体中部 - 拿着手机）
    analyzer.reset()
    detections2 = [
        make_det("person", (100, 100, 200, 500), 0.9, track_id=2),  # w=100, h=400
        make_det("cell phone", (130, 270, 160, 300), 0.6, track_id=None),  # center (145, 285) 距离 person center ~15
    ]
    all_events2 = []
    for f in range(5):
        all_events2.extend(analyzer.analyze(detections2, frame_idx=f, frame_shape=FRAME))
    print(f"场景2 打电话: 触发 {sum(1 for e in all_events2 if e.subtype == 'phone_call')} 次")

    # 场景 3: 打架（2 人距离很近）
    analyzer.reset()
    detections3 = [
        make_det("person", (200, 200, 280, 480), 0.8, track_id=3),  # center (240, 340)
        make_det("person", (260, 210, 340, 490), 0.8, track_id=4),  # center (300, 350), dist ~60
    ]
    all_events3 = []
    for f in range(5):
        all_events3.extend(analyzer.analyze(detections3, frame_idx=f, frame_shape=FRAME))
    print(f"场景3 打架: 触发 {sum(1 for e in all_events3 if e.subtype == 'fight')} 次 (期望 1)")

    # 场景 4: 正常人（站立，h > w）
    analyzer.reset()
    detections4 = [
        make_det("person", (100, 100, 200, 500), 0.85, track_id=5),  # 站立: h=400, w=100
    ]
    all_events4 = []
    for f in range(5):
        all_events4.extend(analyzer.analyze(detections4, frame_idx=f, frame_shape=FRAME))
    print(f"场景4 正常人: 摔倒 {sum(1 for e in all_events4 if e.subtype == 'fall_down')} 次 (期望 0)")

    # 场景 5: 冷却时间（同 track 重复触发应被抑制）
    analyzer.reset()
    detections5 = [
        make_det("person", (100, 400, 500, 600), 0.85, track_id=10),  # 摔倒特征
    ]
    # 跑 20 帧（应有多个确认窗口，但冷却 5s 内只触发 1 次）
    all_events5 = []
    for f in range(20):
        all_events5.extend(analyzer.analyze(detections5, frame_idx=f, frame_shape=FRAME))
    print(f"场景5 冷却测试: 摔倒触发 {sum(1 for e in all_events5 if e.subtype == 'fall_down')} 次 (期望 1, 后续被冷却)")

    print(f"\n=== 统计: {analyzer.stats} ===")
    print("✓ 自测完成")
