"""集成测试: pphuman_pipeline + behavior analyzer

mock PPEngine 返回固定 detection 列表，验证 process_with_events 产生 anomaly 事件
"""
import sys
import numpy as np
from dataclasses import dataclass
from typing import List

sys.path.insert(0, '/Users/qianzhelei/Desktop/Insight Agent BP初稿/Insight-Agent-main/web/physical_backend')

from pp_engine import PPEngine, Detection
from pipelines.pphuman_pipeline import PPHumanPipeline
from pipelines.behavior import COCO_CELL_PHONE_ID, get_analyzer


@dataclass
class MockEngine(PPEngine):
    mock_detections: List[List[Detection]] = None
    _frame_idx: int = 0

    def __init__(self, mock_detections):
        self.mock_detections = mock_detections
        self.loaded = True
        self.backend_name = "MockEngine"
        self.class_names = ["person", "cell phone"]
        self.conf_threshold = 0.4
        self.nms_threshold = 0.4
        self._frame_count = 0
        self._infer_total_ms = 0.0
        self.net = None

    def infer(self, frame):
        self._frame_count += 1
        idx = min(self._frame_idx, len(self.mock_detections) - 1)
        self._frame_idx += 1
        return self.mock_detections[idx]

    def stats(self):
        return {"backend": "MockEngine", "loaded": True, "frame_count": self._frame_count}


def make_person(bbox, score=0.85, track_id=None):
    return Detection(
        track_id=track_id,
        bbox=bbox,
        score=score,
        class_id=0,
        class_name="person",
    )


def make_phone(bbox, score=0.6, track_id=None):
    return Detection(
        track_id=track_id,
        bbox=bbox,
        score=score,
        class_id=COCO_CELL_PHONE_ID,
        class_name="cell phone",
    )


# 4 类行为的合成帧（8 帧）
FRAMES = []
for f in range(8):
    detections = [
        # 摔倒: w=400, h=200, aspect=0.5 < 0.7
        make_person((100, 400, 500, 600), score=0.85),
        # 打电话: person + phone 离得很近
        make_person((700, 100, 800, 500), score=0.9),
        make_phone((720, 280, 760, 320), score=0.6),
        # 打架: 2 个 person 距离 < 100px
        make_person((200, 200, 280, 480), score=0.8),
        make_person((260, 210, 340, 490), score=0.8),
    ]
    FRAMES.append(detections)


print("=== 集成测试: 4 类行为识别 → anomaly 事件 ===\n")

mock_engine = MockEngine(mock_detections=FRAMES)
behavior_analyzer = get_analyzer()
behavior_analyzer.reset()
pipeline = PPHumanPipeline(engine=mock_engine, enable_behavior=True)

frame = np.zeros((720, 1280, 3), dtype=np.uint8)

all_anomaly_events = []
for f in range(8):
    result = pipeline.process_with_events(frame)
    anomaly = [e for e in result["events"] if e.get("type") == "anomaly"]
    if anomaly:
        print(f"  第{f}帧: anomaly 事件 {[(e.get('subtype'), e.get('track_id')) for e in anomaly]}")
        all_anomaly_events.extend(anomaly)

print(f"\n总 anomaly 事件数: {len(all_anomaly_events)}")
subtype_counts = {}
for e in all_anomaly_events:
    subtype_counts[e["subtype"]] = subtype_counts.get(e["subtype"], 0) + 1
print(f"  按 subtype: {subtype_counts}")

print("\n=== 验证 ===")
expected = {"fall_down": ">=1", "phone_call": ">=1", "fight": ">=1"}
all_pass = True
for subtype, cond in expected.items():
    actual = subtype_counts.get(subtype, 0)
    if cond == ">=1" and actual >= 1:
        print(f"  ✓ {subtype}: {actual} 次 (>=1)")
    else:
        print(f"  ✗ {subtype}: {actual} 次 (期望 {cond})")
        all_pass = False

if all_pass:
    print("\n✅ 集成测试通过")
else:
    print("\n❌ 集成测试失败")
    sys.exit(1)
