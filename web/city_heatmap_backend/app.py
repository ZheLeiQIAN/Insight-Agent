"""Insight Agent — 城市热区图 后端服务
Flask-SocketIO @ :9531

REST API:
  GET  /api/healthz         — 健康检查
  GET  /api/info            — 系统信息
  POST /api/events          — 接收人群事件
  GET  /api/heatmap         — 热力图数据
  POST /api/analyze         — 触发行为分析
  POST /api/chat            — Agent 对话
  POST /api/report          — 生成阶段报告
  GET  /api/history         — 事件历史

WebSocket:
  crowd_event   — 服务端→客户端：人群事件推送
  agent_advice  — 服务端→客户端：Agent 建议推送
  heatmap_update— 服务端→客户端：热力图更新
  event         — 客户端→服务端：上报事件
  chat          — 客户端→服务端：对话消息
"""

import sys
import json
import logging
import time
import uuid
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS

from behavior_analyzer import BehaviorAnalyzer, compute_heatmap_data
from agent_bridge import analyze_events_with_llm, generate_report

# =============================================
# Flask 应用初始化
# =============================================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'city-heatmap-secret-v09'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

# 分析引擎
analyzer = BehaviorAnalyzer()

# 内存存储
_event_store = []
_advice_store = []
_heatmap_store = []
_snapshot_store = []  # V4: 时间轴回放快照

MAX_STORE = 200
MAX_SNAPSHOTS = 60

# =============================================
# REST API
# =============================================

@app.route('/api/healthz')
def healthz():
    return jsonify({
        'status': 'ok',
        'service': 'city-heatmap-backend',
        'time': datetime.now().isoformat(),
        'version': '0.9.0',
    })


@app.route('/api/info')
def info():
    return jsonify({
        'service': 'Insight Agent — 城市热区图分析后端 V4',
        'version': '0.9.4',
        'endpoints': [
            'GET  /api/healthz',
            'GET  /api/info',
            'POST /api/events',
            'GET  /api/heatmap',
            'POST /api/analyze',
            'POST /api/chat',
            'POST /api/report',
            'GET  /api/history',
            'GET  /api/snapshots  (V4)',
            'POST /api/snapshots  (V4)',
        ],
        'features': [
            '高德地图人群热力图',
            '人群粒子流动画（菜系色 · 贝塞尔曲线 · 终点爆点）',
            '密度/流向/热区/异常 四维分析',
            'Agent 智能建议 (DeepSeek 餐饮上下文)',
            '实时 WebSocket 推送',
            'V4 时间轴回放 (snapshot_record)',
        ],
    })


@app.route('/api/events', methods=['POST'])
def receive_events():
    """接收前端上报的人群事件"""
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    event = {
        'event_id': str(uuid.uuid4())[:8],
        'timestamp': datetime.now().isoformat(),
        **data,
    }
    _event_store.append(event)
    if len(_event_store) > MAX_STORE:
        _event_store.pop(0)

    # 通过 WebSocket 广播
    socketio.emit('crowd_event', event)

    # 触发 LLM 分析
    recent_events = _event_store[-10:]
    advices = analyze_events_with_llm(recent_events)
    for adv in advices:
        advice = {
            'advice_id': str(uuid.uuid4())[:8],
            'timestamp': datetime.now().isoformat(),
            **adv,
        }
        _advice_store.append(advice)
        if len(_advice_store) > MAX_STORE:
            _advice_store.pop(0)
        socketio.emit('agent_advice', advice)

    return jsonify({'status': 'ok', 'event_id': event['event_id']})


@app.route('/api/heatmap', methods=['GET'])
def get_heatmap():
    """获取当前热力图数据"""
    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'data': _heatmap_store,
    })


@app.route('/api/analyze', methods=['POST'])
def run_analysis():
    """执行行为分析"""
    data = request.get_json(force=True, silent=True) or {}
    total_people = data.get('total_people', 100)
    hotspots = data.get('hotspots', [])
    density = data.get('density')

    snapshot = analyzer.analyze(total_people, hotspots, density)

    # 存储事件
    for e in snapshot.events:
        event_dict = {
            'event_id': e.event_id,
            'timestamp': e.timestamp,
            'event_type': e.event_type,
            'location': e.location,
            'description': e.description,
            'severity': e.severity,
            'icon': e.icon,
            'label': e.label,
        }
        _event_store.append(event_dict)
        socketio.emit('crowd_event', event_dict)

    # 更新热力图
    heatmap = compute_heatmap_data(hotspots)
    _heatmap_store.clear()
    _heatmap_store.extend(heatmap)
    socketio.emit('heatmap_update', {'data': heatmap})

    return jsonify({
        'status': 'ok',
        'timestamp': snapshot.timestamp,
        'total_people': snapshot.total_people,
        'density': snapshot.density,
        'hotspot_count': snapshot.hotspot_count,
        'anomaly_count': snapshot.anomaly_count,
        'event_count': len(snapshot.events),
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    """Agent 对话接口"""
    data = request.get_json(force=True, silent=True)
    if not data or 'message' not in data:
        return jsonify({'error': 'Missing message'}), 400

    message = data['message']
    config = {}
    try:
        from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
        config = {'api_key': LLM_API_KEY, 'base_url': LLM_BASE_URL, 'model': LLM_MODEL}
    except ImportError:
        pass

    if not config.get('api_key'):
        # 降级回复
        reply = f"当前监测区域内人流平稳，密度正常。关于「{message}」的建议：建议关注核心商圈的人流变化趋势，保持常规巡检频率。如需详细分析，请点击「生成报告」。"
        return jsonify({'reply': reply, 'mode': 'fallback'})

    try:
        from openai import OpenAI
        client = OpenAI(api_key=config['api_key'], base_url=config['base_url'])

        # 构建上下文
        recent_events = _event_store[-5:]
        context = "\n".join([
            f"- {e.get('description', '')}" for e in recent_events
        ]) if recent_events else "暂无事件"

        response = client.chat.completions.create(
            model=config['model'],
            messages=[
                {"role": "system", "content": f"你是城市人群行为分析智能体。当前事件:\n{context}"},
                {"role": "user", "content": message},
            ],
            temperature=0.5,
            max_tokens=400,
        )
        reply = response.choices[0].message.content.strip()
        return jsonify({'reply': reply, 'mode': 'llm'})
    except Exception as e:
        logger.warning(f"LLM 对话失败: {e}")
        return jsonify({
            'reply': f"抱歉，智能分析服务暂时不可用。当前系统监测正常。关于「{message}」，建议参考实时数据面板。",
            'mode': 'fallback',
        })


@app.route('/api/report', methods=['POST'])
def report():
    """生成阶段性分析报告"""
    data = request.get_json(force=True, silent=True) or {}
    snapshot = {
        'total_people': data.get('total_people', 100),
        'density': data.get('density', 50),
        'hotspot_count': data.get('hotspot_count', data.get('hotspots', []) and len(data['hotspots']) or 3),
        'anomaly_count': data.get('anomaly_count', 0),
    }
    report_text = generate_report(snapshot)

    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'report': report_text,
    })


@app.route('/api/history', methods=['GET'])
def history():
    """获取事件历史"""
    limit = request.args.get('limit', 50, type=int)
    return jsonify({
        'events': _event_store[-limit:],
        'advices': _advice_store[-limit:],
    })


@app.route('/api/snapshots', methods=['GET'])
def snapshots():
    """V4: 获取时间轴快照历史（最多 60 帧）"""
    limit = request.args.get('limit', 30, type=int)
    return jsonify({
        'snapshots': _snapshot_store[-limit:],
        'count': len(_snapshot_store),
    })


@app.route('/api/snapshots', methods=['POST'])
def push_snapshot():
    """V4: 前端推一帧完整快照进来（供时间轴回放）"""
    data = request.get_json(force=True, silent=True) or {}
    snap = {
        'snapshot_id': str(uuid.uuid4())[:8],
        'timestamp': datetime.now().isoformat(),
        't': data.get('t') or int(time.time() * 1000),
        **data,
    }
    _snapshot_store.append(snap)
    if len(_snapshot_store) > MAX_SNAPSHOTS:
        _snapshot_store.pop(0)
    # 广播给所有客户端（如果接入了多端）
    socketio.emit('snapshot_record', snap)
    return jsonify({'status': 'ok', 'snapshot_id': snap['snapshot_id'], 'count': len(_snapshot_store)})


# =============================================
# WebSocket 事件处理
# =============================================

@socketio.on('connect')
def handle_connect():
    logger.info(f'Client connected')
    emit('health', {'status': 'ok', 'service': 'city-heatmap'})


@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f'Client disconnected')


@socketio.on('snapshot_push')
def handle_snapshot_push(data):
    """V4: 客户端通过 WS 推一帧快照"""
    snap = {
        'snapshot_id': str(uuid.uuid4())[:8],
        'timestamp': datetime.now().isoformat(),
        't': int(time.time() * 1000),
        **(data or {}),
    }
    _snapshot_store.append(snap)
    if len(_snapshot_store) > MAX_SNAPSHOTS:
        _snapshot_store.pop(0)
    # 广播给所有客户端（含本端，便于多端同步）
    socketio.emit('snapshot_record', snap)


@socketio.on('event')
def handle_event(data):
    """接收客户端上报的人群事件"""
    event = {
        'event_id': str(uuid.uuid4())[:8],
        'timestamp': datetime.now().isoformat(),
        **data,
    }
    _event_store.append(event)
    if len(_event_store) > MAX_STORE:
        _event_store.pop(0)

    # 广播给所有客户端
    socketio.emit('crowd_event', event)

    # LLM 分析
    recent_events = _event_store[-10:]
    advices = analyze_events_with_llm(recent_events)
    for adv in advices:
        advice = {
            'advice_id': str(uuid.uuid4())[:8],
            'timestamp': datetime.now().isoformat(),
            **adv,
        }
        _advice_store.append(advice)
        socketio.emit('agent_advice', advice)


@socketio.on('chat')
def handle_chat(data):
    """处理对话消息"""
    message = data.get('message', '')
    if not message:
        return

    config = {}
    try:
        from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
        config = {'api_key': LLM_API_KEY, 'base_url': LLM_BASE_URL, 'model': LLM_MODEL}
    except ImportError:
        pass

    if config.get('api_key'):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=config['api_key'], base_url=config['base_url'])
            response = client.chat.completions.create(
                model=config['model'],
                messages=[
                    {"role": "system", "content": "你是城市人群行为分析智能体，给出专业简洁的建议。"},
                    {"role": "user", "content": message},
                ],
                temperature=0.5,
                max_tokens=400,
            )
            reply = response.choices[0].message.content.strip()
            emit('chat_reply', {'reply': reply, 'mode': 'llm'})
            return
        except Exception as e:
            logger.warning(f"LLM 失败: {e}")

    emit('chat_reply', {
        'reply': f"智能分析暂不可用。当前监测区域人流正常。关于「{message}」，建议查看实时数据面板获取最新信息。",
        'mode': 'fallback',
    })


@socketio.on('generate_report')
def handle_generate_report(data):
    """生成报告"""
    snapshot = {
        'total_people': data.get('total_people', 100),
        'density': data.get('density', 50),
        'hotspot_count': data.get('hotspot_count', data.get('hotspots', []) and len(data['hotspots']) or 3),
        'anomaly_count': data.get('anomaly_count', 0),
    }
    report_text = generate_report(snapshot)
    emit('report_ready', {
        'timestamp': datetime.now().isoformat(),
        'report': report_text,
    })


# =============================================
# 启动
# =============================================

def start_server(host='127.0.0.1', port=9531):
    """启动服务器"""
    logger.info(f'🚀 城市热区图后端启动中... http://{host}:{port}')
    logger.info(f'   API 文档: http://{host}:{port}/api/info')
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='城市热区图后端服务')
    parser.add_argument('--host', default='127.0.0.1', help='监听地址')
    parser.add_argument('--port', type=int, default=9531, help='端口号')
    args = parser.parse_args()
    start_server(args.host, args.port)
