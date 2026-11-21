"""配置存储（V0.6 阶段 E1）

商家配置（除摄像头外的其他配置）:
- 事件触发阈值
- LLM 模型选择
- 报告生成参数
- 自定义规则覆盖

持久化: ~/.insight_agent/physical_config.json
"""
import json
import logging
import threading
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def _default_config_path() -> Path:
    home = Path.home()
    config_dir = home / ".insight_agent"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "physical_config.json"


DEFAULT_CONFIG = {
    "version": "0.6.0",
    "llm": {
        "model": "deepseek-v4-flash",
        "temperature": 0.5,
        "max_tokens": 800,
        "enabled": True,
    },
    "alerts": {
        "anomaly_threshold": 3,  # 每分钟 N 个异常事件触发高优先级告警
        "queue_threshold": 3,  # 排队人数阈值
        "queue_alert_seconds": 5.0,  # 排队告警持续时长
        "dwell_alert_seconds": 60.0,  # 滞留告警时长
    },
    "report": {
        "default_window_seconds": 600,  # 默认 10 分钟
        "auto_generate_interval_sec": 0,  # 0=不自动生成
    },
    "rules": {
        "custom_overrides": {},  # 商家可覆盖内置规则
    },
    "ui": {
        "theme": "dark",  # dark/light
        "default_view": "dashboard",  # dashboard/event/heatmap
    },
}


class ConfigStore:
    """配置存储"""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or _default_config_path()
        self._config: Dict = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
                logger.info("加载配置: %s", self.config_path)
                return
            except Exception as e:
                logger.warning("加载配置失败: %s", e)
        self._config = json.loads(json.dumps(DEFAULT_CONFIG))  # 深拷贝
        self.save()

    def save(self):
        with self._lock:
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(self._config, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning("保存配置失败: %s", e)

    def get(self, key: str, default=None):
        """获取值（支持 'llm.model' 嵌套）"""
        with self._lock:
            parts = key.split(".")
            val = self._config
            for p in parts:
                if isinstance(val, dict) and p in val:
                    val = val[p]
                else:
                    return default
            return val

    def set(self, key: str, value):
        """设置值（支持嵌套）"""
        with self._lock:
            parts = key.split(".")
            d = self._config
            for p in parts[:-1]:
                if p not in d or not isinstance(d[p], dict):
                    d[p] = {}
                d = d[p]
            d[parts[-1]] = value
        self.save()

    def all(self) -> dict:
        """返回所有配置"""
        with self._lock:
            return dict(self._config)

    def reset(self):
        with self._lock:
            self._config = json.loads(json.dumps(DEFAULT_CONFIG))
        self.save()


_store: Optional[ConfigStore] = None


def get_config_store() -> ConfigStore:
    global _store
    if _store is None:
        _store = ConfigStore()
    return _store


# ================================================================
# 自测
# ================================================================

if __name__ == "__main__":
    import sys
    import tempfile
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    print("=== 自测: ConfigStore ===\n")
    tmp = Path(tempfile.gettempdir()) / "test_config.json"
    if tmp.exists():
        tmp.unlink()
    store = ConfigStore(config_path=tmp)
    print(f"llm.model: {store.get('llm.model')}")
    print(f"alerts.queue_threshold: {store.get('alerts.queue_threshold')}")

    # 设置
    store.set("alerts.queue_threshold", 5)
    store.set("ui.theme", "light")
    print(f"\n修改后:")
    print(f"  queue_threshold: {store.get('alerts.queue_threshold')}")
    print(f"  theme: {store.get('ui.theme')}")

    # 重新加载
    store2 = ConfigStore(config_path=tmp)
    print(f"\n重新加载后:")
    print(f"  queue_threshold: {store2.get('alerts.queue_threshold')}")
    print(f"  theme: {store2.get('ui.theme')}")

    # 重置
    store2.reset()
    print(f"\n重置后:")
    print(f"  queue_threshold: {store2.get('alerts.queue_threshold')}")

    print("\n✓ 自测完成")
    if tmp.exists():
        tmp.unlink()
