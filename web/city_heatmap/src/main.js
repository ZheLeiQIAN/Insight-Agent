/* ============================================
   main.js V4 — 城市热区图 · 城市餐饮洞察 启动
   ============================================ */

import { store } from './modules/store.js';
import { bus } from './modules/eventBus.js';
import { initMap, getMap, zoomIn, zoomOut, resetView, switchCity, setHeatLayer, toggleHeatLayer, updateHotspotMarkers } from './modules/amap.js';
import { initParticleFlow, startFlow, stopFlow, toggleFlow, setFlowConnections } from './modules/particleFlow.js';
import { startAnalysis, stopAnalysis, generateHeatData } from './modules/behavior.js';
import { initDashboard } from './modules/dashboard.js';
import { initAgentChat } from './modules/agentChat.js';
// V4.5: 删除时间轴回放 import
// import { initTimeline } from './modules/timeline.js';
import { connect } from './modules/eventStream.js';
import { startDemoData, stopDemoData } from './modules/demoData.js';

let _latestFlows = [];

async function init() {
  console.log('%cInsight Agent — 城市热区图 V4 · 城市餐饮洞察 启动', 'color:#8B1A1A;font-size:14px;');

  initDashboard();
  initAgentChat();
  initMap();
  // V4.5: 删除 initTimeline 调用
  // initTimeline({ stopDemoData, startDemoData });

  const map = getMap();
  if (!map) return;

  // 兼容 AMap 'complete' 事件可能错过（同步注册 vs 异步触发）
  const startEngines = () => {
    initParticleFlow(map);
    startFlow();
    startAnalysis(2500);
    document.getElementById('engineDot')?.classList.add('live');
    console.log('✅ 城市餐饮人群洞察系统就绪 (V4)');
  };
  // AMap v2.0: 监听 complete 事件 + 兜底 500ms 强制启动
  let _started = false;
  const safeStart = () => { if (!_started) { _started = true; startEngines(); } };
  map.on('complete', safeStart);
  setTimeout(safeStart, 500);

  startDemoData('天津');
  connect();

  // 控制事件
  bus.on('map:zoomIn', zoomIn);
  bus.on('map:zoomOut', zoomOut);
  bus.on('map:resetView', resetView);

  // 夜间模式切换
  document.getElementById('btnNightMode')?.addEventListener('click', () => {
    const btn = document.getElementById('btnNightMode');
    const isNight = document.body.classList.toggle('night');
    btn.textContent = isNight ? '☀️' : '🌙';
  });

  // Hero 区按钮
  document.getElementById('btnHeroHeat')?.addEventListener('click', () => {
    const ht = document.getElementById('btnToggleHeat');
    if (ht) ht.click();
  });
  document.getElementById('btnHeroFlow')?.addEventListener('click', () => {
    const fl = document.getElementById('btnToggleFlow');
    if (fl) fl.click();
  });

  bus.on('city:switch', (key) => {
    switchCity(key);
    stopDemoData();
    startDemoData(store.get('city.name'));
  });
  bus.on('heat:toggle', v => toggleHeatLayer(v));
  bus.on('flow:toggle', v => { toggleFlow(v); if (v) startFlow(); else stopFlow(); });

  // hotspots:updated → 同时更新 heatmap、markers、菜系 KPI、sparkline
  bus.on('hotspots:updated', hs => {
    setHeatLayer(generateHeatData(hs));
    // 透传入流量（每热区聚合），供标记按入流量分级脉冲
    const incoming = computeIncomingMap(_latestFlows);
    updateHotspotMarkers(hs, incoming);
  });
  bus.on('flows:updated', flows => {
    _latestFlows = flows;
    setFlowConnections(flows);
  });

  // V4.5: 删除时间轴回放 replay 事件
  // bus.on('hotspots:replay', hs => {...});
  // bus.on('flows:replay', flows => {...});

  // KPI 监听（数字动画由 dashboard.js 接管）
  // store.watch('dining.diners', v => ...);  // 由 dashboard.js 处理

  // FPS
  let frames = 0, last = performance.now();
  (function tick() {
    frames++;
    const now = performance.now();
    if (now - last >= 1000) {
      const el = document.getElementById('fpsCounter');
      if (el) el.textContent = Math.round(frames / ((now - last) / 1000));
      frames = 0; last = now;
    }
    requestAnimationFrame(tick);
  })();

  // 时间戳
  setInterval(() => {
    const el = document.getElementById('timestamp');
    if (el) el.textContent = new Date().toISOString().replace('T',' ').slice(0,19);
  }, 1000);
}

function computeIncomingMap(flows) {
  const m = {};
  for (const f of (flows || [])) {
    const name = f.to?.name;
    if (!name) continue;
    m[name] = (m[name] || 0) + (f.volume || 0);
  }
  return m;
}

document.addEventListener('DOMContentLoaded', init);

window.addEventListener('beforeunload', () => {
  stopAnalysis(); stopFlow(); stopDemoData();
});
