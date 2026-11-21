"""多路摄像头管理器（V0.6 阶段 E1）

特性:
- 多路摄像头注册/启用/禁用
- 每路独立 ROI 列表
- 配置持久化到 ~/.insight_agent/physical_cameras.json
- 启动时自动恢复

设计:
- 纯数据层（不直接开视频流，由 pipeline.process 主动调用）
- 给商家可配置多路摄像头的能力
"""
import json
import logging
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _default_config_path() -> Path:
    """配置文件路径"""
    home = Path.home()
    config_dir = home / ".insight_agent"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "physical_cameras.json"


class CameraConfig:
    """单路摄像头配置"""

    def __init__(
        self,
        camera_id: str,
        name: str,
        source: str = "0",  # 0 / 1 / rtsp://... / file.mp4
        enabled: bool = True,
        fps_target: int = 15,
        rois: Optional[List[dict]] = None,
        notes: str = "",
    ):
        self.camera_id = camera_id
        self.name = name
        self.source = source
        self.enabled = enabled
        self.fps_target = fps_target
        self.rois = rois or []
        self.notes = notes

    def to_dict(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "source": self.source,
            "enabled": self.enabled,
            "fps_target": self.fps_target,
            "rois": self.rois,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CameraConfig":
        return cls(
            camera_id=d.get("camera_id", ""),
            name=d.get("name", d.get("camera_id", "")),
            source=d.get("source", "0"),
            enabled=bool(d.get("enabled", True)),
            fps_target=int(d.get("fps_target", 15)),
            rois=d.get("rois", []) or [],
            notes=d.get("notes", ""),
        )


class CameraManager:
    """多路摄像头管理器"""

    DEFAULT_CAMERAS = [
        {
            "camera_id": "cam_main",
            "name": "主入口",
            "source": "0",
            "enabled": True,
            "fps_target": 15,
            "rois": [
                {"name": "entrance", "bbox": [0, 350, 600, 700], "kind": "area"},
                {"name": "checkout", "bbox": [100, 100, 400, 500], "kind": "area"},
            ],
            "notes": "默认主摄像头 - 笔记本内置或 USB 摄像头",
        },
    ]

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or _default_config_path()
        self._cameras: Dict[str, CameraConfig] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        """从配置文件加载"""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                with self._lock:
                    self._cameras.clear()
                    for c in data.get("cameras", []):
                        cfg = CameraConfig.from_dict(c)
                        if cfg.camera_id:
                            self._cameras[cfg.camera_id] = cfg
                logger.info("加载 %d 路摄像头配置: %s", len(self._cameras), self.config_path)
                return
            except Exception as e:
                logger.warning("加载摄像头配置失败: %s", e)
        # 加载默认
        with self._lock:
            self._cameras.clear()
            for c in self.DEFAULT_CAMERAS:
                cfg = CameraConfig.from_dict(c)
                self._cameras[cfg.camera_id] = cfg
        self.save()
        logger.info("使用默认摄像头配置: %d 路", len(self._cameras))

    def save(self):
        """保存到配置文件"""
        with self._lock:
            data = {
                "cameras": [c.to_dict() for c in self._cameras.values()],
            }
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("保存摄像头配置失败: %s", e)

    def list_cameras(self) -> List[dict]:
        """列出所有摄像头"""
        with self._lock:
            return [c.to_dict() for c in self._cameras.values()]

    def get_camera(self, camera_id: str) -> Optional[CameraConfig]:
        with self._lock:
            return self._cameras.get(camera_id)

    def upsert_camera(self, cfg_dict: dict) -> dict:
        """添加/更新摄像头"""
        if not cfg_dict.get("camera_id"):
            raise ValueError("camera_id 不能为空")
        cfg = CameraConfig.from_dict(cfg_dict)
        with self._lock:
            self._cameras[cfg.camera_id] = cfg
        self.save()
        return cfg.to_dict()

    def delete_camera(self, camera_id: str) -> bool:
        need_save = False
        with self._lock:
            if camera_id in self._cameras:
                del self._cameras[camera_id]
                need_save = True
        if need_save:
            self.save()
            return True
        return False

    def list_rois(self, camera_id: str) -> List[dict]:
        """获取某路摄像头的 ROI 列表"""
        cam = self.get_camera(camera_id)
        return cam.rois if cam else []

    def upsert_roi(self, camera_id: str, roi_dict: dict) -> Optional[dict]:
        """添加/更新 ROI"""
        cam = self.get_camera(camera_id)
        if not cam:
            return None
        name = roi_dict.get("name")
        if not name:
            raise ValueError("ROI name 不能为空")
        # 找现有 ROI（短暂持锁）
        need_save = False
        with self._lock:
            for i, r in enumerate(cam.rois):
                if r.get("name") == name:
                    cam.rois[i] = roi_dict
                    need_save = True
                    break
            else:
                cam.rois.append(roi_dict)
                need_save = True
        if need_save:
            self.save()
        return roi_dict

    def delete_roi(self, camera_id: str, roi_name: str) -> bool:
        cam = self.get_camera(camera_id)
        if not cam:
            return False
        with self._lock:
            new_rois = [r for r in cam.rois if r.get("name") != roi_name]
            changed = len(new_rois) != len(cam.rois)
            cam.rois = new_rois
        if changed:
            self.save()
        return changed


_manager: Optional[CameraManager] = None


def get_camera_manager() -> CameraManager:
    global _manager
    if _manager is None:
        _manager = CameraManager()
    return _manager


# ================================================================
# 自测
# ================================================================

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    print("=== 自测: CameraManager ===\n")
    # 用临时路径
    import tempfile
    tmp = Path(tempfile.gettempdir()) / "test_cams.json"
    if tmp.exists():
        tmp.unlink()
    mgr = CameraManager(config_path=tmp)
    print(f"初始摄像头数: {len(mgr.list_cameras())}")
    for c in mgr.list_cameras():
        print(f"  - {c['camera_id']}: {c['name']} (rois={len(c['rois'])})")

    # 添加
    mgr.upsert_camera({
        "camera_id": "cam_2",
        "name": "收银台",
        "source": "rtsp://192.168.1.100/stream1",
        "fps_target": 20,
    })
    print(f"\n添加后: {len(mgr.list_cameras())} 路")

    # ROI
    mgr.upsert_roi("cam_2", {"name": "checkout_area", "bbox": [100, 100, 500, 500]})
    print(f"cam_2 ROI 数: {len(mgr.list_rois('cam_2'))}")

    # 删除
    mgr.delete_camera("cam_2")
    print(f"删除后: {len(mgr.list_cameras())} 路")

    print("\n✓ 自测完成")
    if tmp.exists():
        tmp.unlink()
