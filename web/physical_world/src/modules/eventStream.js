// eventStream.js — WebSocket 客户端（连接后端 Flask-SocketIO @ 9529）
// 协议: { ts, type, subtype, confidence, bbox?, context? }

import { io } from 'socket.io-client';
import { set } from './store.js';
import { emit } from './eventBus.js';

let socket = null;
let url = null;

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://127.0.0.1:9529';

export function connect() {
  if (socket && socket.connected) return socket;
  url = BACKEND_URL;
  socket = io(url, {
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionAttempts: Infinity,
  });

  socket.on('connect', () => {
    console.log('[eventStream] 已连接', url);
    set('connection.connected', true);
    set('connection.url', url);
    emit('connection:open', { url });
  });

  socket.on('disconnect', (reason) => {
    console.log('[eventStream] 断开', reason);
    set('connection.connected', false);
    emit('connection:close', { reason });
  });

  socket.on('connect_error', (err) => {
    console.warn('[eventStream] 连接错误', err.message);
  });

  // 监听后端推送事件
  socket.on('event', (evt) => {
    emit('event:in', evt);
  });
  socket.on('agent_advice', (advice) => {
    emit('agent:advice', advice);
  });
  socket.on('heatmap', (data) => {
    emit('heatmap:update', data);
  });
  socket.on('health', (h) => {
    set('backend.health', h);
  });

  return socket;
}

export function disconnect() {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
}

export function sendEvent(evt) {
  if (!socket || !socket.connected) return false;
  socket.emit('event', {
    ts: Date.now(),
    source: 'browser',
    ...evt,
  });
  return true;
}

export function getSocket() {
  return socket;
}

export function isConnected() {
  return !!socket && socket.connected;
}
