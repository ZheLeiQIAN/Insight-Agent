"""Insight Agent 物理世界分析 - Flask-SocketIO 入口 (V0.4 阶段 C2)
==============================================================

V0.3 阶段 C1: 集成 PaddleDetection (实际: OpenCV DNN + YOLOv4-tiny)
V0.4 阶段 C2: 行为识别 (摔倒/打电话/打架/抽烟) + 排队/滞留分析
- /api/video     POST 视频文件分析
- /api/stream    GET  实时摄像头配置
- /api/stats     GET  检测引擎统计
- /api/heatmap   GET  最新热区图
- /api/anomalies GET  最近异常行为事件
- /api/queue     GET  队列状态（所有 ROI）
- /api/dwell     GET  滞留分析（所有 ROI）
- /api/rules     GET  规则列表
- /api/run       POST 启动/停止实时检测
- Socket.IO      推送 detection / heatmap / agent_advice
"""
import os
import sys
import time
import logging
import threading
import tempfile
import base64
from collections import deque
from pathlib import Path

# 让后端能引用 Insight-Agent 根目录的现有模块
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_DIR))

from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit as sio_emit
from flask_cors import CORS
import cv2
import numpy as np

from event_schema import PhysicalEvent
from agent_bridge import ask_agent_for_event, chat_with_agent, generate_report
from trigger_rules import match_rule, list_rules
from event_window import get_window
from camera_manager import CameraManager, get_camera_manager
from config_store import ConfigStore, get_config_store
from auth import install_auth, AUTH_ENABLED as _AUTH_ENABLED

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("physical_backend")

# ================================================================
# Flask + SocketIO
# ================================================================

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
app.config["SECRET_KEY"] = "insight-agent-physical-dev"
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB 上传上限

# V0.6: 安装 API key 鉴权（如果 INSIGHT_API_KEY 已设置）
install_auth(app)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

START_TS = time.time()

# ================================================================
# 事件缓存（环形队列，最近 N 条）
# ================================================================
EVENT_BUFFER_SIZE = 200
_anomaly_buffer: deque = deque(maxlen=EVENT_BUFFER_SIZE)  # type=anomaly 事件
_queue_event_buffer: deque = deque(maxlen=EVENT_BUFFER_SIZE)  # type=queue 事件
_dwell_event_buffer: deque = deque(maxlen=EVENT_BUFFER_SIZE)  # type=dwell 事件
_event_lock = threading.Lock()

# ================================================================
# 检测引擎单例（懒加载）
# ================================================================

_pipeline = None
_pipeline_lock = threading.Lock()


def get_pipeline():
    """懒加载 MallPipeline（首次调用加载模型，~24MB YOLOv4-tiny）"""
    global _pipeline
    if _pipeline is None:
        with _pipeline_lock:
            if _pipeline is None:
                logger.info("懒加载 MallPipeline...")
                from pipelines.mall_pipeline import MallPipeline
                _pipeline = MallPipeline()
                # 默认 ROI（仅供演示用，真实部署需配置）
                _pipeline.add_roi("entrance", 0, 0, 1280, 100)         # 顶部
                _pipeline.add_roi("checkout", 1000, 400, 1280, 720)    # 右下
                _pipeline.add_roi("shelf_left", 0, 200, 400, 720)      # 左侧
                logger.info("✓ MallPipeline 就绪")
    return _pipeline


# ================================================================
# REST API
# ================================================================

@app.route("/api/healthz", methods=["GET"])
def healthz():
    return jsonify({
        "status": "ok",
        "service": "physical_world",
        "version": "0.5.0",
        "uptime_sec": round(time.time() - START_TS, 1),
        "pipeline_loaded": _pipeline is not None,
        "anomaly_buffer_count": len(_anomaly_buffer),
        "queue_event_buffer_count": len(_queue_event_buffer),
        "dwell_event_buffer_count": len(_dwell_event_buffer),
    })


@app.route("/api/info", methods=["GET"])
def info():
    return jsonify({
        "service": "physical_world",
        "version": "0.5.0",
        "endpoints": {
            "healthz": "/api/healthz",
            "info": "/api/info",
            "events": "/api/events (POST)",
            "video": "/api/video (POST multipart)",
            "stats": "/api/stats (GET)",
            "heatmap": "/api/heatmap (GET)",
            "anomalies": "/api/anomalies (GET)",
            "queue": "/api/queue (GET)",
            "dwell": "/api/dwell (GET)",
            "rules": "/api/rules (GET)",
            "chat": "/api/chat (POST {message, history?, roi_snapshot?})",
            "report": "/api/report (GET ?window_seconds=600)",
            "window_summary": "/api/window/summary (GET ?seconds=300)",
            "cameras": "/api/cameras (GET/POST), /api/cameras/<id> (DELETE)",
            "camera_rois": "/api/cameras/<id>/rois (GET/POST), /<name> (DELETE)",
            "config": "/api/config (GET/POST/PATCH/DELETE)",
            "run": "/api/run (POST {action:start|stop, source:0|rtsp|file})",
            "socketio": "/socket.io/",
        },
        "stages": {
            "A_skeleton": "ready",
            "B_browser_vision": "ready",
            "C_backend_detection": "ready",
            "C2_behavior_analysis": "ready",
            "D_agent_integration": "ready",
            "E_merchant_polish": "stub",
        },
        "rules_count": len(list_rules()),
    })


@app.route("/api/stats", methods=["GET"])
def stats():
    """检测引擎统计"""
    pipeline = get_pipeline()  # 懒加载
    return jsonify({"loaded": True, "stats": pipeline.human_pipeline.stats})


@app.route("/api/heatmap", methods=["GET"])
def heatmap():
    """最新热区图"""
    pipeline = get_pipeline()
    return jsonify({
        "loaded": True,
        "heatmap": {
            "w": pipeline.heatmap_grid_w,
            "h": pipeline.heatmap_grid_h,
            "max": float(pipeline.heatmap.max()),
            "data": pipeline.heatmap.tolist(),
        },
        "rois": {
            name: {
                "current": roi.current_count,
                "enters_total": roi.enter_count,
                "exits_total": roi.exit_count,
            }
            for name, roi in pipeline.rois.items()
        },
    })


@app.route("/api/anomalies", methods=["GET"])
def get_anomalies():
    """最近异常行为事件（V0.4: 摔倒/打电话/打架/抽烟）"""
    with _event_lock:
        events = list(_anomaly_buffer)
    # 支持过滤
    subtype_filter = request.args.get("subtype")
    if subtype_filter:
        events = [e for e in events if e.get("subtype") == subtype_filter]
    limit = int(request.args.get("limit", 50))
    return jsonify({
        "loaded": True,
        "count": len(events),
        "events": events[-limit:],
        "by_subtype": _count_by_subtype(events),
    })


@app.route("/api/queue", methods=["GET"])
def get_queue():
    """当前所有 ROI 的队列状态"""
    pipeline = get_pipeline()
    # 实时调用一次确保最新
    queues = {}
    for name, roi in pipeline.rois.items():
        queues[name] = {
            "current_length": roi.current_count,
            "max_length": roi.queue_max_length,
            "queueing": roi.current_count >= pipeline.QUEUE_THRESHOLD,
            "alerted": roi.queue_alerted,
            "alert_threshold": pipeline.QUEUE_THRESHOLD,
        }
    with _event_lock:
        recent_events = list(_queue_event_buffer)
    return jsonify({
        "loaded": True,
        "queues": queues,
        "threshold": pipeline.QUEUE_THRESHOLD,
        "alert_duration_sec": pipeline.QUEUE_ALERT_DURATION_SEC,
        "recent_alerts": recent_events[-20:],
    })


@app.route("/api/dwell", methods=["GET"])
def get_dwell():
    """所有 ROI 的滞留分析"""
    pipeline = get_pipeline()
    import time as _t
    now = _t.time()
    dwell_data = {}
    for name, roi in pipeline.rois.items():
        # 累加仍在 ROI 内的 track
        current_total = roi.dwell_total_seconds
        active = []
        for tid, start in roi._dwell_start.items():
            duration = now - start
            active.append({"track_id": tid, "duration_sec": round(duration, 1)})
            current_total += duration
        dwell_data[name] = {
            "total_dwell_sec": round(current_total, 1),
            "max_track_id": roi.dwell_max_track_id,
            "max_dwell_sec": round(roi.dwell_max_seconds, 1),
            "unique_visitors": len(roi.dwell_seconds_per_track),
            "active_in_roi": len(roi._dwell_start),
            "active_dwell": active[:10],
        }
    with _event_lock:
        recent_events = list(_dwell_event_buffer)
    return jsonify({
        "loaded": True,
        "dwell": dwell_data,
        "recent_events": recent_events[-20:],
    })


@app.route("/api/rules", methods=["GET"])
def get_rules():
    """列出所有规则"""
    return jsonify({
        "loaded": True,
        "count": len(list_rules()),
        "rules": list_rules(),
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    """与 Agent 对话（V0.5 阶段 D）

    Body:
        {
            "message": "用户消息",
            "history": [{"role": "user/assistant", "content": "..."}] (可选),
            "roi_snapshot": {"entrance": {"current": 5}} (可选)
        }
    """
    body = request.get_json(silent=True) or {}
    user_message = body.get("message", "").strip()
    if not user_message:
        return jsonify({"ok": False, "error": "message 不能为空"}), 400

    history = body.get("history")
    roi_snapshot = body.get("roi_snapshot")

    # 如果前端没传 roi_snapshot，从 pipeline 实时取
    if not roi_snapshot:
        try:
            pipeline = get_pipeline()
            roi_snapshot = {
                name: {
                    "current": roi.current_count,
                    "enters_total": roi.enter_count,
                    "exits_total": roi.exit_count,
                }
                for name, roi in pipeline.rois.items()
            }
        except Exception:
            roi_snapshot = None

    result = chat_with_agent(user_message, roi_snapshot=roi_snapshot, history=history)
    return jsonify(result)


@app.route("/api/report", methods=["GET"])
def report():
    """生成阶段分析报告（V0.5 阶段 D）

    Query:
        window_seconds=600 (默认 10 分钟)
    """
    try:
        window_seconds = int(request.args.get("window_seconds", 600))
    except ValueError:
        window_seconds = 600
    window_seconds = max(60, min(3600, window_seconds))  # 限制 1 分钟 ~ 1 小时

    # 取 ROI 快照
    roi_snapshot = None
    try:
        pipeline = get_pipeline()
        roi_snapshot = {
            name: {
                "current": roi.current_count,
                "enters_total": roi.enter_count,
                "exits_total": roi.exit_count,
            }
            for name, roi in pipeline.rois.items()
        }
    except Exception:
        pass

    result = generate_report(window_seconds=window_seconds, roi_snapshot=roi_snapshot)
    return jsonify(result)


@app.route("/api/window/summary", methods=["GET"])
def window_summary():
    """事件窗口摘要"""
    try:
        seconds = int(request.args.get("seconds", 300))
    except ValueError:
        seconds = 300
    return jsonify(get_window().summary(seconds=seconds))


# ================================================================
# V0.6: 多路摄像头 + 配置
# ================================================================

@app.route("/api/cameras", methods=["GET"])
def list_cameras():
    """列出所有摄像头"""
    mgr = get_camera_manager()
    return jsonify({
        "loaded": True,
        "count": len(mgr.list_cameras()),
        "cameras": mgr.list_cameras(),
    })


@app.route("/api/cameras", methods=["POST"])
def upsert_camera():
    """添加/更新摄像头"""
    body = request.get_json(silent=True) or {}
    try:
        cfg = get_camera_manager().upsert_camera(body)
        return jsonify({"ok": True, "camera": cfg})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/cameras/<camera_id>", methods=["DELETE"])
def delete_camera(camera_id: str):
    """删除摄像头"""
    ok = get_camera_manager().delete_camera(camera_id)
    return jsonify({"ok": ok})


@app.route("/api/cameras/<camera_id>/rois", methods=["GET"])
def list_rois(camera_id: str):
    """列出摄像头 ROI"""
    mgr = get_camera_manager()
    rois = mgr.list_rois(camera_id)
    return jsonify({"loaded": True, "camera_id": camera_id, "rois": rois})


@app.route("/api/cameras/<camera_id>/rois", methods=["POST"])
def upsert_roi(camera_id: str):
    """添加/更新 ROI"""
    body = request.get_json(silent=True) or {}
    try:
        roi = get_camera_manager().upsert_roi(camera_id, body)
        if roi is None:
            return jsonify({"ok": False, "error": "摄像头不存在"}), 404
        return jsonify({"ok": True, "roi": roi})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/cameras/<camera_id>/rois/<roi_name>", methods=["DELETE"])
def delete_roi(camera_id: str, roi_name: str):
    """删除 ROI"""
    ok = get_camera_manager().delete_roi(camera_id, roi_name)
    return jsonify({"ok": ok})


@app.route("/api/config", methods=["GET"])
def get_config():
    """读取商家配置"""
    return jsonify({
        "loaded": True,
        "config": get_config_store().all(),
    })


@app.route("/api/config", methods=["POST", "PATCH"])
def update_config():
    """更新商家配置（key 支持嵌套如 'alerts.queue_threshold'）"""
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "body 必须是 dict"}), 400
    store = get_config_store()
    updated = []
    for k, v in body.items():
        if not isinstance(k, str) or not k:
            continue
        store.set(k, v)
        updated.append(k)
    return jsonify({"ok": True, "updated": updated, "config": store.all()})


@app.route("/api/config", methods=["DELETE"])
def reset_config():
    """重置为默认配置"""
    get_config_store().reset()
    return jsonify({"ok": True, "config": get_config_store().all()})


def _count_by_subtype(events: list) -> dict:
    """按 subtype 统计事件数"""
    out = {}
    for e in events:
        s = e.get("subtype", "?")
        out[s] = out.get(s, 0) + 1
    return out


@app.route("/api/video", methods=["POST"])
def analyze_video():
    """上传视频文件并分析

    支持: multipart/form-data with 'video' field
    """
    if "video" not in request.files:
        return jsonify({"error": "missing 'video' field"}), 400
    f = request.files["video"]
    if not f.filename:
        return jsonify({"error": "empty filename"}), 400

    # 保存到临时文件
    suffix = Path(f.filename).suffix or ".mp4"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        f.save(tmp.name)
        tmp_path = tmp.name
    finally:
        tmp.close()

    # 打开视频
    cap = cv2.VideoCapture(tmp_path)
    if not cap.isOpened():
        os.unlink(tmp_path)
        return jsonify({"error": f"cannot open video {f.filename}"}), 400

    # 限制最大帧数（防止 OOM）
    max_frames = int(request.form.get("max_frames", 200))
    sample_every = int(request.form.get("sample_every", 1))

    pipeline = get_pipeline()
    all_events = []
    all_tracks_per_frame = []
    frame_idx = 0
    t_start = time.time()
    fps_actual = 0.0

    try:
        while frame_idx < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % sample_every == 0:
                result = pipeline.process(frame)
                all_tracks_per_frame.append(len(result["tracks"]))
                for evt in result["events"]:
                    evt["frame_idx"] = frame_idx
                    evt["ts"] = int(time.time() * 1000)
                    all_events.append(evt)
                    # 写入 EventWindow + 类型化 buffer
                    get_window().add(evt)
                    with _event_lock:
                        if evt.get("type") == "anomaly":
                            _anomaly_buffer.append(evt)
                        elif evt.get("type") == "queue":
                            _queue_event_buffer.append(evt)
                        elif evt.get("type") == "dwell":
                            _dwell_event_buffer.append(evt)
            frame_idx += 1
        fps_actual = frame_idx / max(0.001, time.time() - t_start)
    finally:
        cap.release()
        os.unlink(tmp_path)

    # 统计事件类型
    by_type = {}
    for e in all_events:
        t = e.get("type", "?")
        by_type[t] = by_type.get(t, 0) + 1

    return jsonify({
        "ok": True,
        "filename": f.filename,
        "total_frames": frame_idx,
        "analyzed_frames": len(all_tracks_per_frame),
        "elapsed_sec": round(time.time() - t_start, 2),
        "fps_actual": round(fps_actual, 2),
        "max_persons_detected": max(all_tracks_per_frame) if all_tracks_per_frame else 0,
        "avg_persons": round(sum(all_tracks_per_frame) / max(1, len(all_tracks_per_frame)), 2),
        "events_count": len(all_events),
        "events_by_type": by_type,
        "events": all_events[:50],  # 限制返回数量
    })


# ================================================================
# 实时检测控制
# ================================================================

_run_state = {
    "running": False,
    "source": None,
    "thread": None,
    "stop_event": None,
}


def _detection_loop(source, stop_event, max_frames=None):
    """实时检测循环（独立线程）"""
    cap = cv2.VideoCapture(source if not isinstance(source, int) else int(source))
    if not cap.isOpened():
        logger.error("无法打开视频源: %s", source)
        socketio.emit("event", {
            "ts": int(time.time() * 1000),
            "type": "error",
            "subtype": "source_open_failed",
            "source": "backend",
        })
        return

    pipeline = get_pipeline()
    frame_count = 0
    last_emit_ts = 0
    EMIT_INTERVAL_MS = 200  # 限流：每 200ms 推一次结果

    logger.info("实时检测循环启动: source=%s", source)

    try:
        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                if isinstance(source, int):
                    logger.warning("摄像头帧读取失败，退出循环")
                    break
                else:
                    # 视频文件结尾
                    break
            frame_count += 1
            if max_frames and frame_count > max_frames:
                break

            # 推理
            result = pipeline.process(frame)
            now_ms = int(time.time() * 1000)

            if now_ms - last_emit_ts >= EMIT_INTERVAL_MS:
                last_emit_ts = now_ms
                socketio.emit("detection_frame", {
                    "ts": now_ms,
                    "frame_idx": frame_count,
                    "persons": len(result["tracks"]),
                    "events": result["events"][:5],
                    "rois": result["rois"],
                    "queues": result.get("queues", {}),
                    "dwell": result.get("dwell", {}),
                    "fps": result["stats"]["engine"]["avg_infer_ms"],
                })
                # 推送事件
                for evt in result["events"]:
                    evt_with_ts = {**evt, "ts": now_ms}
                    socketio.emit("event", evt_with_ts)
                    # 写入 EventWindow + 类型化 buffer
                    get_window().add(evt_with_ts)
                    with _event_lock:
                        if evt.get("type") == "anomaly":
                            _anomaly_buffer.append(evt_with_ts)
                        elif evt.get("type") == "queue":
                            _queue_event_buffer.append(evt_with_ts)
                        elif evt.get("type") == "dwell":
                            _dwell_event_buffer.append(evt_with_ts)
                    # 规则匹配
                    if "type" in evt and "subtype" in evt:
                        physical_evt = PhysicalEvent(
                            type=evt.get("type", ""),
                            subtype=evt.get("subtype", ""),
                            confidence=0.8,
                            source="backend",
                            context={k: v for k, v in evt.items() if k not in ("type", "subtype", "source")},
                        )
                        advice = ask_agent_for_event(physical_evt)
                        if advice:
                            socketio.emit("agent_advice", advice.to_dict())

                # 热区图
                socketio.emit("heatmap", result["heatmap"])
    finally:
        cap.release()
        _run_state["running"] = False
        logger.info("实时检测循环结束，共处理 %d 帧", frame_count)


@app.route("/api/run", methods=["POST"])
def run_detection():
    """启动/停止实时检测

    body: {"action": "start"|"stop", "source": "0"|"rtsp://..."|"file:path"}
    """
    body = request.get_json(force=True, silent=True) or {}
    action = body.get("action", "start")
    source = body.get("source", "0")

    if action == "stop":
        if _run_state["stop_event"]:
            _run_state["stop_event"].set()
        return jsonify({"ok": True, "running": False})

    if _run_state["running"]:
        return jsonify({"error": "already running", "running": True}), 400

    # 解析 source
    if str(source).startswith("rtsp:"):
        real_source = str(source)
    elif str(source).startswith("file:"):
        real_source = str(source)[5:]
    else:
        real_source = int(source)  # 摄像头索引

    # 预热：先确保 pipeline 已加载（首次加载会下载模型）
    t0 = time.time()
    get_pipeline()
    logger.info("Pipeline 预热耗时 %.1fs", time.time() - t0)

    stop_event = threading.Event()
    _run_state.update({
        "running": True,
        "source": source,
        "stop_event": stop_event,
    })
    t = threading.Thread(
        target=_detection_loop,
        args=(real_source, stop_event),
        daemon=True,
    )
    _run_state["thread"] = t
    t.start()

    return jsonify({"ok": True, "running": True, "source": source})


# ================================================================
# 旧的事件 API（保留）
# ================================================================

@app.route("/api/events", methods=["POST"])
def post_event():
    try:
        data = request.get_json(force=True, silent=False) or {}
    except Exception as e:
        return jsonify({"error": f"invalid JSON: {e}"}), 400

    evt = PhysicalEvent(
        type=data.get("type", ""),
        subtype=data.get("subtype", ""),
        confidence=float(data.get("confidence", 0.0)),
        bbox=data.get("bbox"),
        track_id=data.get("track_id"),
        source=data.get("source", "http"),
        context=data.get("context", {}),
    )
    rule = match_rule(evt)
    advice = None
    if rule:
        advice = ask_agent_for_event(evt)
        if advice:
            socketio.emit("agent_advice", advice.to_dict())
    socketio.emit("event", evt.to_dict())
    return jsonify({
        "ok": True,
        "rule_matched": rule is not None,
        "advice": advice.to_dict() if advice else None,
    })


# ================================================================
# Socket.IO
# ================================================================

@socketio.on("connect")
def on_connect():
    logger.info("client connected: %s", request.sid)
    sio_emit("health", {"status": "connected", "version": "0.5.0"})


@socketio.on("disconnect")
def on_disconnect():
    logger.info("client disconnected: %s", request.sid)


@socketio.on("event")
def on_socket_event(data):
    if not isinstance(data, dict):
        return
    evt = PhysicalEvent(
        type=data.get("type", ""),
        subtype=data.get("subtype", ""),
        confidence=float(data.get("confidence", 0.0)),
        bbox=data.get("bbox"),
        track_id=data.get("track_id"),
        source="browser",
        context=data.get("context", {}),
    )
    logger.info("event from browser: %s:%s", evt.type, evt.subtype)
    rule = match_rule(evt)
    if rule:
        advice = ask_agent_for_event(evt)
        if advice:
            socketio.emit("agent_advice", advice.to_dict())
    socketio.emit("event", evt.to_dict())


@socketio.on("ping")
def on_ping(data):
    sio_emit("pong", {"ts": time.time(), "echo": data})


# ================================================================
# 入口
# ================================================================

if __name__ == "__main__":
    host = os.environ.get("PHYSICAL_BACKEND_HOST", "127.0.0.1")
    port = int(os.environ.get("PHYSICAL_BACKEND_PORT", "9529"))
    logger.info("物理世界后端启动: http://%s:%d (V0.5)", host, port)
    logger.info("健康检查: http://%s:%d/api/healthz", host, port)
    logger.info("检测 API: POST /api/video, /api/run")
    logger.info("分析 API: GET /api/anomalies, /api/queue, /api/dwell, /api/rules, /api/report, /api/window/summary")
    logger.info("对话 API: POST /api/chat")
    logger.info("WebSocket: ws://%s:%d/socket.io/", host, port)
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
