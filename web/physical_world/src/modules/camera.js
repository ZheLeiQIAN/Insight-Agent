// camera.js — 摄像头接入（V0.1：基础 getUserMedia）
// 阶段 B 将扩展：支持 RTSP、录像文件、切换设备

import { set } from './store.js';
import { emit } from './eventBus.js';

let stream = null;
let currentDeviceId = null;

export async function startCamera({ deviceId = null, video = {} } = {}) {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('当前浏览器不支持 getUserMedia');
  }
  // 识别"占位设备 ID"（如 "0" / "1"）：浏览器没有该 ID，会报 OverconstrainedError
  // 占位符时改用 facingMode: "user" 走默认摄像头
  const PLACEHOLDER_IDS = new Set(['', '0', '1', '2', '3', 'default']);
  const isPlaceholder = !deviceId || PLACEHOLDER_IDS.has(String(deviceId));
  const constraints = {
    video: isPlaceholder
      ? {
          facingMode: { ideal: 'user' },
          width: { ideal: 1280 },
          height: { ideal: 720 },
          ...video,
        }
      : { deviceId: { exact: deviceId }, ...video },
    audio: false,
  };
  let mediaStream;
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
  } catch (e) {
    // 如果 deviceId.exact 失败，自动回退到默认摄像头
    if (!isPlaceholder && e && (e.name === 'OverconstrainedError' || e.name === 'NotFoundError')) {
      console.warn('[camera] 指定 deviceId 失败，回退默认:', e.message);
      mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: 'user' },
          width: { ideal: 1280 },
          height: { ideal: 720 },
          ...video,
        },
        audio: false,
      });
    } else {
      throw e;
    }
  }
  stream = mediaStream;
  // 重新探测实际 deviceId（用于后续约束）
  const track = stream.getVideoTracks()[0];
  if (track) {
    const settings = track.getSettings();
    currentDeviceId = settings.deviceId || null;
  } else {
    currentDeviceId = deviceId;
  }
  const videoEl = document.getElementById('cam-video');
  if (videoEl) {
    videoEl.srcObject = stream;
    await videoEl.play().catch(() => {});
  }
  set('camera.active', true);
  set('camera.deviceId', currentDeviceId);
  emit('camera:started', { deviceId: currentDeviceId });
  return stream;
}

export function stopCamera() {
  if (stream) {
    for (const t of stream.getTracks()) t.stop();
    stream = null;
  }
  const videoEl = document.getElementById('cam-video');
  if (videoEl) videoEl.srcObject = null;
  set('camera.active', false);
  emit('camera:stopped');
}

export async function listDevices() {
  if (!navigator.mediaDevices?.enumerateDevices) return [];
  const all = await navigator.mediaDevices.enumerateDevices();
  return all.filter((d) => d.kind === 'videoinput');
}

export function getActiveStream() {
  return stream;
}
