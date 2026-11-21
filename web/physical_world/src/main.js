// main.js — V0.7 应用入口
//
// 架构：
//   1. 启动 demo 数据流（让 UI 立刻"活"起来）
//   2. 启动热区图动画
//   3. 初始化 dashboard + agentChat
//   4. 启动时钟
//   5. 启动后端连接（失败不影响 demo）
//   6. 摄像头 + 真实模型（按用户点击）

import { set, get, watch } from './modules/store.js';
import { emit, on } from './modules/eventBus.js';
import { startCamera, stopCamera, getActiveStream } from './modules/camera.js';
import { initGestureDetector, processFrame as processGesture, isGestureReady } from './modules/gesture.js';
import { initFaceDetector, processFrame as processFace, isFaceReady } from './modules/face.js';
import { initDetector, processFrame as processDetect, isDetectorReady } from './modules/quickDetect.js';
import { connect, sendEvent, isConnected } from './modules/eventStream.js';
import { initDashboard, drawOverlay } from './modules/dashboard.js';
import { initAgentChat } from './modules/agentChat.js';
import {
  startKpiHeartbeat,
  startEventStream,
  startAdvisoryStream,
  startHeatmapAnimation,
  startClock,
} from './modules/demoData.js';

const videoEl = () => document.getElementById('cam-video');
const overlayEl = () => document.getElementById('overlay');

let mainLoopId = null;
let lastGestureResult = null;
let lastFaceResult = null;
let lastDetectResult = null;
let lastGestureLabels = [];
let lastFaceLabels = [];

// ============================================================
// 启动
// ============================================================
async function bootstrap() {
  console.log('[app] 启动 v0.7 editorial');

  // 1) UI 渲染
  initDashboard();
  initAgentChat();

  // 2) 启动 demo 数据流（立即让 UI "活" 起来）
  startClock();
  startKpiHeartbeat();
  startEventStream();
  startAdvisoryStream();

  // 3) 启动热区图动画
  const heatCanvas = document.getElementById('heatmap');
  if (heatCanvas) startHeatmapAnimation(heatCanvas);

  // 4) 连接后端（失败也不影响 demo）
  try { connect(); } catch (e) { console.warn('[app] 后端连接失败，使用纯 demo 模式'); }

  // 5) 绑定按钮
  document.getElementById('btn-start-cam')?.addEventListener('click', onStartCamera);
  document.getElementById('btn-stop-cam')?.addEventListener('click', onStopCamera);

  // 5.1) Hero 区按钮
  document.getElementById('btn-start-cam-hero')?.addEventListener('click', onStartCamera);
  document.querySelector('[data-tab-goto="insight"]')?.addEventListener('click', () => {
    const tab = document.querySelector('.mode-tab[data-mode="insight"]');
    if (tab) tab.click();
  });

  // 5.5) 绑定外部子服务启动器（页脚 launcher）
  bindSubServiceLaunchers();

  // 6) 监听检测事件，转发到后端
  wireDetectionEvents();

  // 7) 监听 KPI 状态
  watch('count.persons', (v) => {
    const el = document.getElementById('kpi-persons');
    if (el) el.textContent = v ?? 0;
  });
}

// ============================================================
// 子服务启动器：页脚链接点击时，先 POST 主工作台 (9527) 启动子服务，
// 再打开对应子页面，避免用户看到 connection refused。
// ============================================================
function bindSubServiceLaunchers() {
  const MAIN = 'http://127.0.0.1:9527';
  const LAUNCH_MAP = {
    'city-heatmap': { endpoint: '/api/start-city-heatmap',  port: 9530, label: '城市热区' },
  };
  document.querySelectorAll('a[data-launch]').forEach((a) => {
    a.addEventListener('click', (e) => {
      const key = a.dataset.launch;
      const cfg = LAUNCH_MAP[key];
      if (!cfg) return; // 没配置就走默认行为
      e.preventDefault();
      const url = a.href; // 保留 target=_blank 的目标地址
      // 1) 唤起主工作台启动对应子服务（失败也不阻塞跳转）
      fetch(MAIN + cfg.endpoint, { method: 'POST' })
        .catch(() => {/* 主工作台未起也允许打开 */})
        .finally(() => {
          // 2) 打开子页面（新标签）
          window.open(url, '_blank');
          // 3) 用户反馈
          console.log(`[launcher] ${cfg.label} → ${url}`);
        });
    });
  });
}

// ============================================================
// 真实检测事件 → 事件流（混入 demo）
// ============================================================
function wireDetectionEvents() {
  let gestureCount = 0;
  on('detection:gesture', (evt) => {
    gestureCount++;
    const idx = (evt.handedness === 'Left') ? 1 : 0;
    lastGestureLabels[idx] = evt.subtype;
    sendEvent(evt);
  });
  on('detection:face', (evt) => {
    lastFaceLabels[0] = evt.subtype;
    sendEvent(evt);
  });
  on('detection:count', (evt) => {
    lastDetectResult = evt;
    sendEvent(evt);
  });
  on('detection:interest', (evt) => {
    sendEvent(evt);
  });
}

// ============================================================
// 启动摄像头
// ============================================================
async function onStartCamera() {
  try {
    const sel = document.getElementById('source-select').value;
    if (sel.startsWith('rtsp') || sel.startsWith('file')) {
      alert('RTSP/录像文件支持在阶段 C 后端实现');
      return;
    }
    await startCamera({ deviceId: sel || null });
    await ensureModelsReady();
    startMainLoop();
  } catch (e) {
    console.error('[app] 启动摄像头失败:', e);
    alert('启动摄像头失败: ' + e.message + '\n请检查浏览器权限设置');
  }
}

async function ensureModelsReady() {
  set('model.ready', false);
  const v = videoEl();
  await initGestureDetector(v, (results) => { lastGestureResult = results; });
  await initFaceDetector(v, (results) => { lastFaceResult = results; });
  await initDetector();
  const ready = isGestureReady() || isFaceReady() || isDetectorReady();
  set('model.ready', ready);
  if (ready) console.log('[app] 至少一个模型就绪');
}

// ============================================================
// 主循环（每帧：推理 + 叠加 + 更新 FPS 角标）
// ============================================================
function startMainLoop() {
  if (mainLoopId) return;
  const v = videoEl();
  const o = overlayEl();
  if (!v || !o) return;
  o.width = v.clientWidth;
  o.height = v.clientHeight;

  let lastFps = performance.now();
  let frameCount = 0;
  let skelStat = '';

  const tick = async () => {
    if (!getActiveStream()) {
      mainLoopId = null;
      return;
    }
    if (v.readyState >= 2) {
      try {
        const [g, f, d] = await Promise.all([
          processGesture(v),
          processFace(v),
          processDetect(v),
        ]);
        if (d) lastDetectResult = d;
        // 统计骨架数
        const hN = lastGestureResult?.multiHandLandmarks?.length || 0;
        const fN = lastFaceResult?.multiFaceLandmarks?.length || 0;
        const pN = lastDetectResult?.detections?.length || 0;
        skelStat = `${hN} hand · ${fN} face · ${pN} person`;
        const ss = document.getElementById('skeleton-stat');
        if (ss) ss.innerHTML = `<span style="color:var(--wall-accent);">●</span> ${skelStat}`;

        drawOverlay(o, v, {
          gestureResults: lastGestureResult,
          faceResults: lastFaceResult,
          detectResults: lastDetectResult,
          gestureLabels: lastGestureLabels,
          faceLabels: lastFaceLabels,
        });
        frameCount++;
        const now = performance.now();
        if (now - lastFps >= 1000) {
          const cf = document.getElementById('corner-fps');
          if (cf) cf.textContent = `${frameCount} FPS`;
          frameCount = 0;
          lastFps = now;
        }
      } catch (e) {
        console.warn('[mainLoop] tick:', e);
      }
    }
    mainLoopId = requestAnimationFrame(tick);
  };
  mainLoopId = requestAnimationFrame(tick);
}

function onStopCamera() {
  if (mainLoopId) {
    cancelAnimationFrame(mainLoopId);
    mainLoopId = null;
  }
  stopCamera();
}

// ============================================================
// 入口
// ============================================================
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', bootstrap);
} else {
  bootstrap();
}
