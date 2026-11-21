"""事件滑动窗口（V0.5 阶段 D1）

线程安全的事件缓存，供 LLM 增强时注入上下文。

特点:
- 环形队列，固定容量
- 按类型/时间窗过滤
- 汇总统计（按 subtype 分组）
"""
import logging
import threading
import time
from collections import deque, Counter
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class EventWindow:
    """事件滑动窗口

    用法:
        window = EventWindow(maxlen=100)
        window.add(event_dict)
        recent = window.recent(seconds=30)
        summary = window.summary()
    """

    def __init__(self, maxlen: int = 200):
        self._buffer: deque = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._stats = {
            "total_added": 0,
            "total_dropped": 0,
        }

    def add(self, event: dict) -> None:
        """添加事件到窗口"""
        if not isinstance(event, dict):
            return
        # 确保有时间戳
        if "ts" not in event:
            event["ts"] = int(time.time() * 1000)
        with self._lock:
            # 容量满时弹出
            if len(self._buffer) >= self._buffer.maxlen:
                self._stats["total_dropped"] += 1
            self._buffer.append(event)
            self._stats["total_added"] += 1

    def recent(self, seconds: Optional[float] = None, limit: int = 50,
               event_type: Optional[str] = None) -> List[dict]:
        """获取最近的事件

        Args:
            seconds: 仅返回最近 N 秒内的（None=全部）
            limit: 最多返回多少条
            event_type: 仅返回指定类型（如 "anomaly"/"queue"/"dwell"）
        """
        with self._lock:
            events = list(self._buffer)
        # 类型过滤
        if event_type:
            events = [e for e in events if e.get("type") == event_type]
        # 时间窗
        if seconds is not None and seconds > 0:
            cutoff_ms = int((time.time() - seconds) * 1000)
            events = [e for e in events if e.get("ts", 0) >= cutoff_ms]
        # 按时间倒序
        events.sort(key=lambda e: e.get("ts", 0), reverse=True)
        return events[:limit]

    def count_by_subtype(self, seconds: Optional[float] = None,
                        event_type: Optional[str] = None) -> Dict[str, int]:
        """按 subtype 统计事件数"""
        events = self.recent(seconds=seconds, limit=9999, event_type=event_type)
        counter = Counter(e.get("subtype", "?") for e in events)
        return dict(counter)

    def summary(self, seconds: Optional[float] = 300) -> dict:
        """汇总窗口内容（用于 LLM 上下文）"""
        with self._lock:
            total = len(self._buffer)
        recent_events = self.recent(seconds=seconds, limit=9999)
        return {
            "window_size": total,
            "in_last_seconds": len(recent_events),
            "by_type": self.count_by_type(seconds=seconds),
            "by_subtype": self.count_by_subtype(seconds=seconds),
            "anomaly_subtypes": self.count_by_subtype(seconds=seconds, event_type="anomaly"),
            "queue_subtypes": self.count_by_subtype(seconds=seconds, event_type="queue"),
            "stats": dict(self._stats),
        }

    def count_by_type(self, seconds: Optional[float] = None) -> Dict[str, int]:
        """按 type 统计"""
        events = self.recent(seconds=seconds, limit=9999)
        return dict(Counter(e.get("type", "?") for e in events))

    def clear(self) -> None:
        """清空窗口"""
        with self._lock:
            self._buffer.clear()
            for k in self._stats:
                self._stats[k] = 0

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._buffer)

    def __len__(self) -> int:
        return self.size


# ================================================================
# 全局单例
# ================================================================
_window: Optional[EventWindow] = None


def get_window() -> EventWindow:
    """获取全局事件窗口"""
    global _window
    if _window is None:
        _window = EventWindow(maxlen=200)
    return _window


# ================================================================
# 自测
# ================================================================
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    print("=== 自测: EventWindow ===\n")

    w = EventWindow(maxlen=10)

    # 添加 5 个不同类型事件
    for i in range(5):
        w.add({
            "type": "anomaly",
            "subtype": "fall_down" if i % 2 == 0 else "fight",
            "ts": int(time.time() * 1000) + i,
            "track_id": i,
        })

    print(f"窗口大小: {w.size}")
    print(f"汇总: {w.summary()}")
    print(f"近 60s anomaly 数: {len(w.recent(seconds=60, event_type='anomaly'))}")

    # 测试容量限制
    for i in range(15):
        w.add({"type": "count", "subtype": "person_increase", "ts": int(time.time() * 1000)})
    print(f"\n添加 15 个后窗口大小（max=10）: {w.size}")
    print(f"stats: {w._stats}")

    print("\n✓ 自测完成")
