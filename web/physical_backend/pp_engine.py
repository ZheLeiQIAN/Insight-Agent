"""PaddleDetection 推理引擎（V0.3 阶段 C1：OpenCV DNN + YOLOv4-tiny）

设计要点:
- 接口与 PaddleDetection 完全兼容（process_frame 返回 list[Detection]）
- V0.3 阶段 C1: 使用 OpenCV DNN + YOLOv4-tiny（24MB，CPU 实时）
- 阶段 C2: 可热切换 PaddleDetection (PP-YOLOE-l + paddle inference)
- 模型下载：首次使用自动从官方源下载并缓存

Detection 数据类:
- track_id: 跟踪 ID（由 pipeline 分配）
- bbox: (x1, y1, x2, y2)
- score: 置信度
- class_name: 类别名（COCO）
- class_id: 类别 ID
"""
import logging
import os
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional
import numpy as np
import cv2

logger = logging.getLogger(__name__)

# 模型缓存目录
MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_DIR.mkdir(exist_ok=True)

# 模型下载源（YOLOv4-tiny: 小、快、80类COCO）
MODEL_URLS = {
    "yolov4-tiny.weights": "https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v4_pre/yolov4-tiny.weights",
    "yolov4-tiny.cfg": "https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4-tiny.cfg",
    "coco.names": "https://raw.githubusercontent.com/AlexeyAB/darknet/master/data/coco.names",
}
MODEL_SIZE_MB = {"yolov4-tiny.weights": 22.6, "yolov4-tiny.cfg": 0.005, "coco.names": 0.001}


@dataclass
class Detection:
    track_id: Optional[int] = None
    bbox: tuple = (0, 0, 0, 0)  # (x1, y1, x2, y2)
    score: float = 0.0
    class_id: int = 0
    class_name: str = ""
    source: str = "backend"

    def to_dict(self):
        return asdict(self)

    def is_person(self) -> bool:
        return self.class_name == "person" and self.score >= 0.5


def download_models(force: bool = False) -> None:
    """下载 YOLOv4-tiny 模型权重与配置（如果本地不存在）"""
    for filename, url in MODEL_URLS.items():
        target = MODEL_DIR / filename
        if target.exists() and target.stat().st_size > 0 and not force:
            continue
        size_mb = MODEL_SIZE_MB.get(filename, 0)
        logger.info("下载模型 %s (~%.1fMB) → %s", filename, size_mb, target)
        try:
            urllib.request.urlretrieve(url, target)
            logger.info("  ✓ %s (%.1fKB)", filename, target.stat().st_size / 1024)
        except Exception as e:
            logger.error("  ✗ 下载失败 %s: %s", filename, e)
            raise


class PPEngine:
    """行人/通用物体检测引擎（V0.3: OpenCV DNN YOLOv4-tiny）

    阶段 C2 切换: 实例化 PaddleDetectionPPEngine (PP-YOLOE-l)
    """

    def __init__(self, model_dir: Optional[str] = None, device: str = "CPU", conf_threshold: float = 0.5):
        self.model_dir = Path(model_dir) if model_dir else MODEL_DIR
        self.device = device
        self.conf_threshold = conf_threshold
        self.nms_threshold = 0.4
        self.net = None
        self.class_names: List[str] = []
        self.loaded = False
        self.backend_name = "OpenCV-DNN:YOLOv4-tiny"
        self._frame_count = 0
        self._infer_total_ms = 0.0

    def load(self) -> "PPEngine":
        """加载模型（首次会下载）"""
        download_models()
        weights = self.model_dir / "yolov4-tiny.weights"
        cfg = self.model_dir / "yolov4-tiny.cfg"
        names_file = self.model_dir / "coco.names"

        if not weights.exists() or not cfg.exists():
            raise FileNotFoundError(f"模型文件缺失: {weights}, {cfg}")

        # 加载类别名
        with open(names_file, "r", encoding="utf-8") as f:
            self.class_names = [line.strip() for line in f if line.strip()]
        logger.info("加载 COCO 类别: %d 类", len(self.class_names))

        # 加载网络
        self.net = cv2.dnn.readNetFromDarknet(str(cfg), str(weights))
        if self.device == "GPU":
            try:
                self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
                self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
            except Exception as e:
                logger.warning("GPU 后端不可用，回退 CPU: %s", e)
        else:
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

        # 输出层
        self._output_layers = [self.net.getLayerNames()[i - 1] for i in self.net.getUnconnectedOutLayers()]
        self.loaded = True
        logger.info("✓ %s 引擎就绪 (device=%s)", self.backend_name, self.device)
        return self

    def infer(self, frame: np.ndarray) -> List[Detection]:
        """单帧推理 → 返回所有物体检测（V0.3: 不含跟踪 ID）"""
        if not self.loaded:
            return []
        if frame is None or frame.size == 0:
            return []

        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (416, 416), swapRB=True, crop=False)
        self.net.setInput(blob)

        import time
        t0 = time.time()
        layer_outputs = self.net.forward(self._output_layers)
        infer_ms = (time.time() - t0) * 1000
        self._infer_total_ms += infer_ms
        self._frame_count += 1

        boxes, confidences, class_ids = [], [], []
        for output in layer_outputs:
            for detection in output:
                scores = detection[5:]
                class_id = int(np.argmax(scores))
                confidence = float(scores[class_id])
                if confidence > self.conf_threshold:
                    box = detection[0:4] * np.array([w, h, w, h])
                    (center_x, center_y, width, height) = box.astype("int")
                    x = int(center_x - width / 2)
                    y = int(center_y - height / 2)
                    boxes.append([x, y, int(width), int(height)])
                    confidences.append(confidence)
                    class_ids.append(class_id)

        idxs = cv2.dnn.NMSBoxes(boxes, confidences, self.conf_threshold, self.nms_threshold)
        detections: List[Detection] = []
        if len(idxs) > 0:
            for i in idxs.flatten():
                (x, y, ww, hh) = boxes[i]
                class_name = self.class_names[class_ids[i]] if class_ids[i] < len(self.class_names) else "?"
                detections.append(Detection(
                    bbox=(max(0, x), max(0, y), min(w, x + ww), min(h, y + hh)),
                    score=round(confidences[i], 3),
                    class_id=class_ids[i],
                    class_name=class_name,
                ))
        return detections

    def warmup(self, h: int = 416, w: int = 416):
        """预热（消除首次推理 JIT 延迟）"""
        if not self.loaded:
            return
        dummy = np.zeros((h, w, 3), dtype=np.uint8)
        self.infer(dummy)
        self._frame_count = 0
        self._infer_total_ms = 0.0

    @property
    def avg_infer_ms(self) -> float:
        if self._frame_count == 0:
            return 0.0
        return self._infer_total_ms / self._frame_count

    def stats(self) -> dict:
        return {
            "backend": self.backend_name,
            "device": self.device,
            "loaded": self.loaded,
            "frame_count": self._frame_count,
            "avg_infer_ms": round(self.avg_infer_ms, 1),
            "class_count": len(self.class_names),
        }


_engine_singleton: Optional[PPEngine] = None


def get_engine(device: str = "CPU", conf: float = 0.5) -> PPEngine:
    """获取全局单例引擎（首次调用加载模型）"""
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = PPEngine(device=device, conf_threshold=conf).load()
    return _engine_singleton


def reload_engine(device: str = "CPU", conf: float = 0.5) -> PPEngine:
    """重新加载引擎（切换设备/置信度时使用）"""
    global _engine_singleton
    _engine_singleton = PPEngine(device=device, conf_threshold=conf).load()
    return _engine_singleton
