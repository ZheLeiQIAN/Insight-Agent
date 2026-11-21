"""V0.4 端到端验证: MallPipeline + 行为识别

构造 4 类行为视频（合成图），验证:
1. /api/video 上传后产生 anomaly 事件
2. /api/anomalies 返回事件
3. /api/queue 返回队列状态
4. /api/dwell 返回滞留分析

策略: 直接调用 MallPipeline.process()，不通过 HTTP
"""
import sys
import os
import time
import numpy as np

sys.path.insert(0, '/Users/qianzhelei/Desktop/Insight Agent BP初稿/Insight-Agent-main/web/physical_backend')

from pp_engine import Detection
from pipelines.mall_pipeline import MallPipeline
from pipelines.pphuman_pipeline import PPHumanPipeline
from pipelines.behavior import COCO_CELL_PHONE_ID


def make_person(bbox, score=0.85):
    return Detection(bbox=bbox, score=score, class_id=0, class_name="person")


def make_phone(bbox, score=0.6):
    return Detection(bbox=bbox, score=score, class_id=COCO_CELL_PHONE_ID, class_name="cell phone")


class MockEngine:
    """Mock 引擎返回固定 detection 序列（每帧不同以模拟视频）"""

    def __init__(self, frames):
        self.frames = frames  # List[List[Detection]]
        self.idx = 0
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
        if self.idx < len(self.frames):
            d = self.frames[self.idx]
            self.idx += 1
            return d
        return self.frames[-1]

    def stats(self):
        return {"backend": "MockEngine", "loaded": True, "frame_count": self._frame_count}


# 构造 4 类行为的 10 帧视频
FRAMES = []
for f in range(10):
    detections = [
        # 摔倒: w=400, h=200, aspect=0.5
        make_person((100, 400, 500, 600), score=0.85),
        # 打电话: person + phone 重叠
        make_person((700, 100, 800, 500), score=0.9),
        make_phone((720, 280, 760, 320), score=0.6),
        # 打架: 2 person 接近
        make_person((200, 200, 280, 480), score=0.8),
        make_person((260, 210, 340, 490), score=0.8),
        # 正常站立 person（不应触发任何异常）
        make_person((900, 100, 1000, 500), score=0.9),
    ]
    FRAMES.append(detections)


print("=" * 60)
print("V0.4 端到端验证: MallPipeline + 行为识别")
print("=" * 60)

# 用 mock engine 构造 PPHumanPipeline
mock_engine = MockEngine(FRAMES)
pp_pipeline = PPHumanPipeline(engine=mock_engine, enable_behavior=True)
# 构造 MallPipeline
mall = MallPipeline(human_pipeline=pp_pipeline)
# 添加 ROI（包含摔倒的 ROI = entrance，包含 person 集中的 ROI = checkout）
mall.add_roi("entrance", 0, 350, 600, 700)  # 摔倒区域
mall.add_roi("checkout", 100, 100, 400, 500)  # 打架区域
mall.add_roi("phone_zone", 600, 100, 900, 500)  # 打电话区域

frame = np.zeros((720, 1280, 3), dtype=np.uint8)

# 跑 10 帧
all_events_by_frame = []
all_queues_per_frame = []
all_dwell_per_frame = []
for f in range(10):
    result = mall.process(frame)
    all_events_by_frame.append(result["events"])
    all_queues_per_frame.append(result["queues"])
    all_dwell_per_frame.append(result["dwell"])

# 汇总
print("\n=== 事件汇总 ===")
all_events = []
for f, events in enumerate(all_events_by_frame):
    for e in events:
        e_copy = dict(e, frame_idx=f)
        all_events.append(e_copy)

by_type = {}
for e in all_events:
    t = e.get("type", "?")
    by_type[t] = by_type.get(t, 0) + 1
print(f"  总事件数: {len(all_events)}")
print(f"  按类型: {by_type}")

# 验证 anomaly 事件
anomaly_events = [e for e in all_events if e.get("type") == "anomaly"]
print(f"\n  anomaly 事件数: {len(anomaly_events)}")
subtype_count = {}
for e in anomaly_events:
    s = e.get("subtype", "?")
    subtype_count[s] = subtype_count.get(s, 0) + 1
print(f"  按 subtype: {subtype_count}")

# 验证 queue 状态
print("\n=== 队列状态（最后一帧） ===")
last_queues = all_queues_per_frame[-1]
for name, q in last_queues.items():
    print(f"  {name}: current={q['current_length']}, queueing={q['queueing']}")

# 验证 dwell 状态
print("\n=== 滞留分析（最后一帧） ===")
last_dwell = all_dwell_per_frame[-1]
for name, d in last_dwell.items():
    print(f"  {name}: total={d['total_dwell_sec']}s, max={d['max_dwell_sec']}s, visitors={d['unique_visitors']}")

# 测试场景: 增加更多人形成 queue
print("\n=== 排队检测测试 ===")
crowd_frames = []
for f in range(15):  # 15 帧
    crowd_detections = []
    # 5 个 person 在 entrance ROI 内
    for i in range(5):
        x = 50 + i * 100
        crowd_detections.append(make_person((x, 350, x + 80, 650), score=0.85))
    crowd_frames.append(crowd_detections)

# 重置 mall 和 pipeline
mock_engine2 = MockEngine(crowd_frames)
pp_pipeline2 = PPHumanPipeline(engine=mock_engine2, enable_behavior=True)
mall2 = MallPipeline(human_pipeline=pp_pipeline2)
mall2.add_roi("entrance", 0, 300, 1280, 700)

print(f"  队列阈值: {mall2.QUEUE_THRESHOLD}, 告警时长: {mall2.QUEUE_ALERT_DURATION_SEC}s")
print(f"  注入 5 人持续 15 帧（~0.5s）")
queue_alerts = []
for f in range(15):
    result = mall2.process(frame)
    queue_events = [e for e in result["events"] if e.get("type") == "queue"]
    if queue_events:
        queue_alerts.extend(queue_events)
        print(f"  第{f}帧: 队列告警 {[(e['zone'], e['length'], e.get('duration_sec')) for e in queue_events]}")

print(f"\n  队列告警总数: {len(queue_alerts)}")

# 验证
print("\n" + "=" * 60)
print("验证结果")
print("=" * 60)
checks = [
    ("anomaly 事件 >= 3", len(anomaly_events) >= 3),
    ("fall_down 触发", subtype_count.get("fall_down", 0) >= 1),
    ("phone_call 触发", subtype_count.get("phone_call", 0) >= 1),
    ("fight 触发", subtype_count.get("fight", 0) >= 1),
    ("ROI 进入事件 (roi_enter)", by_type.get("roi_enter", 0) > 0),
]

# 队列告警单独测：使用 sleep 模拟真实时间流逝
print("\n=== 队列告警测试（真实时间模拟）===")
import time as _t
mock_engine3 = MockEngine([crowd_frames[0]] * 100)  # 100 帧同内容
pp_pipeline3 = PPHumanPipeline(engine=mock_engine3, enable_behavior=True)
mall3 = MallPipeline(human_pipeline=pp_pipeline3)
mall3.add_roi("entrance", 0, 300, 1280, 700)
mall3.QUEUE_ALERT_DURATION_SEC = 0.5  # 测试用：缩短到 0.5s

print(f"  阈值: {mall3.QUEUE_THRESHOLD}, 告警时长: {mall3.QUEUE_ALERT_DURATION_SEC}s")
queue_alert_count = 0
t0 = _t.time()
while _t.time() - t0 < 1.0:
    result = mall3.process(frame)
    queue_events = [e for e in result["events"] if e.get("type") == "queue"]
    queue_alert_count += len(queue_events)
_t1 = _t.time() - t0
print(f"  真实耗时: {_t1:.2f}s, 队列告警触发: {queue_alert_count} 次")
checks.append(("队列告警触发 (sleep 1s)", queue_alert_count >= 1))

all_pass = True
for name, ok in checks:
    icon = "✓" if ok else "✗"
    print(f"  {icon} {name}")
    if not ok:
        all_pass = False

if all_pass:
    print("\n✅ V0.4 验证通过")
else:
    print("\n❌ V0.4 验证失败")
    sys.exit(1)
