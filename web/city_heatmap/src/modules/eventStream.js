/* ============================================
   EventStream — Socket.IO 客户端连接后端
   负责：与后端 9531 端口建立 WebSocket 连接
   ============================================ */

import { bus } from './eventBus.js';

let _socket = null;
let _connected = false;

/**
 * 连接后端
 */
export function connect() {
  try {
    // 使用 Vite proxy，同源访问
    _socket = io({
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 2000,
      reconnectionAttempts: 10,
    });

    _socket.on('connect', () => {
      _connected = true;
      document.getElementById('sysStatus')?.classList.replace('yellow', 'green');
      console.log('[Socket] 已连接到后端 :9531');
      bus.emit('socket:connected');
    });

    _socket.on('disconnect', () => {
      _connected = false;
      document.getElementById('sysStatus')?.classList.replace('green', 'yellow');
      console.log('[Socket] 与后端断开');
      bus.emit('socket:disconnected');
    });

    // 接收后端推送的人群分析事件
    _socket.on('crowd_event', (event) => {
      bus.emit('event:backend', event);
    });

    // 接收后端 Agent 建议
    _socket.on('agent_advice', (advice) => {
      bus.emit('advice:new', advice);
    });

    // 接收后端热区数据
    _socket.on('heatmap_update', (data) => {
      bus.emit('heatmap:backend', data);
    });

    // V4: 接收后端广播的快照（多端同步 / 后端主导模式）
    _socket.on('snapshot_record', (snap) => {
      bus.emit('snapshot:from-backend', snap);
    });

    // 连接状态灯
    _socket.on('health', (data) => {
      if (data?.status === 'ok') {
        document.getElementById('sysStatus')?.classList.replace('yellow', 'green');
      }
    });

  } catch (err) {
    console.warn('[Socket] 连接失败 (demo模式继续):', err.message);
    document.getElementById('sysStatus')?.classList.add('yellow');
  }
}

/**
 * 向后端发送对话消息
 */
export function sendChat(message, callback) {
  if (_socket && _connected) {
    _socket.emit('chat', { message }, callback);
  }
}

export default { connect, sendChat };
