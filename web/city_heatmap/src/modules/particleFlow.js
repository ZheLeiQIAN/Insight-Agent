/* ============================================
   ParticleFlow V4 — 叙事感·食客奔赴热区
   - 流向色 = 目标菜系色 (食客→火锅店的故事)
   - 二次贝塞尔曲线路径 (汇聚感)
   - 终点爆点 (Burst) + 流光底
   - 平滑 volume (消灭闪烁)
   - hover tooltip (来源→去向详情)
   ============================================ */

import { store } from './store.js';
import { bus } from './eventBus.js';
import { getMap } from './amap.js';

// ---------- 菜系色板（与 amap.js / dashboard 同步） ----------
const CUISINE_PALETTE = {
  '火锅':     { r: 184, g: 30,  b: 30  }, // #B81E1E 酒红
  '烧烤':     { r: 210, g: 120, b: 20  }, // #D27814 橙棕
  '川菜':     { r: 200, g: 40,  b: 40  }, // #C82828
  '粤菜':     { r: 30,  g: 130, b: 80  }, // #1E8250
  '日料':     { r: 20,  g: 100, b: 160 }, // #1464A0
  '韩餐':     { r: 160, g: 60,  b: 120 }, // #A03C78
  '西餐':     { r: 80,  g: 40,  b: 100 }, // #502864
  '小吃':     { r: 200, g: 160, b: 20  }, // #C8A014
  '酒吧':     { r: 100, g: 60,  b: 180 }, // #643CB4
  '本帮菜':   { r: 165, g: 58,  b: 58  }, // #A53A3A
  '异国料理': { r: 100, g: 80,  b: 130 },
  '综合餐饮': { r: 27,  g: 42,  b: 78  }, // --ink
  'default':  { r: 139, g: 26,  b: 26  }, // --accent
};

function parseCuisineKey(cuisineStr) {
  if (!cuisineStr) return 'default';
  // 取第一个 "/" 前的部分
  const head = String(cuisineStr).split('/')[0].trim();
  return CUISINE_PALETTE[head] ? head : 'default';
}

// ---------- 暴露给 demo 调参 ----------
const CFG = {
  particlesPerFlow: 6,    // 每条流向线同时存在的粒子数（系数）
  baseSpeed: 0.0042,      // 路径速度系数（0→1 每帧增量）
  sizeBase: 3.2,          // 粒子基础半径 (px)
  sizeJitter: 1.8,        // 粒子大小随机范围
  glow: 12,               // 外发光半径 (px)
  trailLen: 6,            // 拖尾点数
  bezierOffset: 0.55,     // 控制点法向偏移系数（0=直线，1=强烈弧线）
  dashAnim: 0.6,          // 流光速度
  burstThreshold: 0.82,   // t 超过此值进入爆点
  maxParticles: 800,      // 全局粒子上限
};
if (typeof window !== 'undefined') window.__particleCfg = CFG;

// ---------- 内部状态 ----------
let _canvas, _ctx, _animFrame, _visible = true;
let _flows = [];                 // 当前 active flows
let _flowStates = [];            // {flowIdx, currentVolume, particles[], lastBurstTs}
let _replayMode = false;         // 回放模式：粒子跳到快照位置不演完
let _hoverFlowIdx = -1;          // 当前 hover 的 flow
let _tooltipEl = null;
let _lastFrameTs = 0;
let _globalParticleCount = 0;

// ---------- 工具：贝塞尔二次曲线 ----------
function bezier2(p0, p1, p2, t) {
  const u = 1 - t;
  return {
    lng: u * u * p0.lng + 2 * u * t * p1.lng + t * t * p2.lng,
    lat: u * u * p0.lat + 2 * u * t * p1.lat + t * t * p2.lat,
  };
}

// 控制点：起止中点 + 法向偏移（视觉上"向终点汇聚"）
function computeControl(from, to) {
  const mx = (from.lng + to.lng) / 2;
  const my = (from.lat + to.lat) / 2;
  // 法向：垂直于 from->to 的单位向量
  const dx = to.lng - from.lng;
  const dy = to.lat - from.lat;
  const len = Math.hypot(dx, dy) || 1;
  const nx = -dy / len, ny = dx / len;
  const offset = CFG.bezierOffset * len * 0.9;
  return { lng: mx + nx * offset, lat: my + ny * offset };
}

// ---------- 初始化 Canvas ----------
export function initParticleFlow(map) {
  const c = document.getElementById('amapContainer');
  if (!c) { console.error('[ParticleFlow] 找不到地图容器'); return; }
  // 清理旧 canvas
  const old = document.getElementById('particleCanvas');
  if (old) old.remove();

  _canvas = document.createElement('canvas');
  _canvas.id = 'particleCanvas';
  _canvas.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:auto;z-index:6;cursor:crosshair;';
  c.appendChild(_canvas);
  _ctx = _canvas.getContext('2d');

  function resize() { _canvas.width = c.clientWidth; _canvas.height = c.clientHeight; }
  resize();
  window.addEventListener('resize', resize);

  // tooltip
  ensureTooltip();

  // hover
  _canvas.addEventListener('mousemove', onHover);
  _canvas.addEventListener('mouseleave', () => { _hoverFlowIdx = -1; hideTooltip(); });

  // 外部事件：进入/退出回放模式
  bus.on('timeline:replay-enter', () => { _replayMode = true; });
  bus.on('timeline:replay-exit',  () => { _replayMode = false; });
}

// ---------- tooltip ----------
function ensureTooltip() {
  if (_tooltipEl) return;
  _tooltipEl = document.createElement('div');
  _tooltipEl.id = 'flowTooltip';
  _tooltipEl.className = 'flow-tooltip';
  _tooltipEl.style.cssText = 'position:absolute;z-index:50;pointer-events:none;opacity:0;transition:opacity 0.15s;';
  document.getElementById('amapContainer')?.appendChild(_tooltipEl);
}
function showTooltip(html, x, y) {
  if (!_tooltipEl) return;
  _tooltipEl.innerHTML = html;
  _tooltipEl.style.left = (x + 12) + 'px';
  _tooltipEl.style.top  = (y + 12) + 'px';
  _tooltipEl.style.opacity = '1';
}
function hideTooltip() { if (_tooltipEl) _tooltipEl.style.opacity = '0'; }

function onHover(e) {
  const rect = _canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left, my = e.clientY - rect.top;
  const map = getMap();
  if (!map) return;

  let hitIdx = -1, bestDist = 14; // 像素容差
  for (let i = 0; i < _flows.length; i++) {
    const f = _flows[i];
    const c = _flowStates[i];
    if (!f || !c) continue;
    const cur = Math.max(8, c.currentVolume); // 视觉宽度
    const samples = 12;
    let minD = Infinity;
    for (let s = 0; s <= samples; s++) {
      const t = s / samples;
      const pt = bezier2(f.from, f._ctrl, f.to, t);
      const px = map.lngLatToContainer(new AMap.LngLat(pt.lng, pt.lat));
      if (!px) continue;
      const d = Math.hypot(px.x - mx, px.y - my);
      if (d < minD) minD = d;
    }
    if (minD < Math.max(bestDist, cur * 0.4)) { hitIdx = i; break; }
  }

  if (hitIdx >= 0) {
    _hoverFlowIdx = hitIdx;
    const f = _flows[hitIdx];
    const cuisineKey = parseCuisineKey(f.to?.cuisine);
    const c = CUISINE_PALETTE[cuisineKey] || CUISINE_PALETTE.default;
    const colorHex = `rgb(${c.r},${c.g},${c.b})`;
    const cur = _flowStates[hitIdx].currentVolume.toFixed(0);
    const html = `
      <div class="flow-tip-title">
        <span class="dot" style="background:${colorHex};"></span>
        ${f.from?.name || '来源'} → ${f.to?.name || '热区'}
      </div>
      <div class="flow-tip-row"><span>菜系</span><b>${f.to?.cuisine || '综合'}</b></div>
      <div class="flow-tip-row"><span>当前流量</span><b>${cur} 人/分</b></div>
      <div class="flow-tip-row"><span>来源类型</span><b>${srcLabel(f.from?.type)}</b></div>
    `;
    showTooltip(html, mx, my);
    _canvas.style.cursor = 'pointer';
  } else {
    if (_hoverFlowIdx !== -1) hideTooltip();
    _hoverFlowIdx = -1;
    _canvas.style.cursor = 'crosshair';
  }
}

function srcLabel(t) {
  return ({ residential: '居住区', office: '办公区', university: '大学城', transit: '交通枢纽' })[t] || t || '—';
}

// ---------- 接收流向更新 ----------
export function setFlowConnections(flows) {
  _flows = (flows || []).map(f => {
    const ctrl = computeControl(f.from, f.to);
    return { ...f, _ctrl: ctrl };
  });
  // 同步 state
  for (let i = 0; i < _flows.length; i++) {
    if (!_flowStates[i]) {
      _flowStates[i] = { currentVolume: 0, particles: [], lastBurstTs: 0 };
    }
    _flowStates[i].targetVolume = _flows[i].volume || 0;
  }
  // 截断多余 state
  if (_flowStates.length > _flows.length) _flowStates.length = _flows.length;
}

// ---------- 启动 / 暂停 ----------
export function startFlow() {
  if (_animFrame) return;
  _lastFrameTs = performance.now();
  tick(_lastFrameTs);
}
export function stopFlow() {
  if (_animFrame) { cancelAnimationFrame(_animFrame); _animFrame = null; }
  _flowStates = []; _globalParticleCount = 0;
  if (_ctx) _ctx.clearRect(0, 0, _canvas.width, _canvas.height);
}
export function toggleFlow(v) { _visible = v; if (!v) stopFlow(); }

// ---------- 主循环 ----------
function tick(ts) {
  if (!_visible || !_ctx) { _animFrame = requestAnimationFrame(tick); return; }
  const map = getMap();
  if (!map) { _animFrame = requestAnimationFrame(tick); return; }

  const dt = Math.min(40, ts - _lastFrameTs) / 16.67; // 归一到 60fps 帧
  _lastFrameTs = ts;

  // 1) 平滑 volume
  for (let i = 0; i < _flowStates.length; i++) {
    const s = _flowStates[i];
    const t = s.targetVolume || 0;
    s.currentVolume += (t - s.currentVolume) * 0.12 * dt;
    if (Math.abs(t - s.currentVolume) < 0.3) s.currentVolume = t;
  }

  // 2) 调整粒子数（按需新增/淘汰）
  syncParticles();

  // 3) 推进粒子位置
  advanceParticles(dt);

  // 4) 绘制
  _ctx.clearRect(0, 0, _canvas.width, _canvas.height);
  drawFlowLight();
  drawParticles(map);
  drawEndpointBurst(map);

  // 5) KPI 推流：当前食客总数
  const diners = Math.round(_flows.reduce((s, f) => s + (f.volume || 0), 0) * 8 + 30);
  store.set('dining.diners', diners);

  _animFrame = requestAnimationFrame(tick);
}

// 粒子数 = particlesPerFlow * volume / 60，按需增删
function syncParticles() {
  for (let i = 0; i < _flowStates.length; i++) {
    const s = _flowStates[i];
    const target = Math.max(2, Math.round(CFG.particlesPerFlow * s.currentVolume / 30));
    const arr = s.particles;
    // 增
    while (arr.length < target && _globalParticleCount < CFG.maxParticles) {
      arr.push({
        t: Math.random() * 0.7,           // 起始位置错开
        speed: (CFG.baseSpeed * (0.8 + Math.random() * 0.5)),
        size: CFG.sizeBase + Math.random() * CFG.sizeJitter,
        jitter: Math.random(),
        fading: false, fadeA: 1,
      });
      _globalParticleCount++;
    }
    // 减
    while (arr.length > target && arr.length > 0) {
      const p = arr.pop();
      if (p) _globalParticleCount--;
    }
  }
}

function advanceParticles(dt) {
  for (let i = 0; i < _flowStates.length; i++) {
    const s = _flowStates[i];
    for (let j = s.particles.length - 1; j >= 0; j--) {
      const p = s.particles[j];
      if (_replayMode) continue; // 回放时不演
      p.t += p.speed * dt;
      if (p.t >= 1) p.t -= 1; // 循环
    }
  }
}

// ---------- 绘制：流光底 ----------
function drawFlowLight() {
  const map = getMap();
  if (!map) return;
  for (let i = 0; i < _flows.length; i++) {
    const f = _flows[i];
    const s = _flowStates[i];
    if (!f || !s) continue;

    const c = CUISINE_PALETTE[parseCuisineKey(f.to?.cuisine)] || CUISINE_PALETTE.default;
    const cur = Math.max(2, s.currentVolume);
    const alpha = Math.min(0.45, 0.10 + cur / 200);
    const width = 1 + Math.min(4, cur / 30);

    // 采样 24 个点画贝塞尔
    const pts = [];
    for (let k = 0; k <= 24; k++) {
      const t = k / 24;
      const pt = bezier2(f.from, f._ctrl, f.to, t);
      const px = map.lngLatToContainer(new AMap.LngLat(pt.lng, pt.lat));
      if (px) pts.push(px);
    }
    if (pts.length < 2) continue;

    // 基础虚线
    _ctx.save();
    _ctx.setLineDash([4, 8]);
    _ctx.lineDashOffset = -((performance.now() / 60) * CFG.dashAnim);
    _ctx.beginPath();
    _ctx.moveTo(pts[0].x, pts[0].y);
    for (let k = 1; k < pts.length; k++) _ctx.lineTo(pts[k].x, pts[k].y);
    _ctx.strokeStyle = `rgba(${c.r},${c.g},${c.b},${alpha * 0.6})`;
    _ctx.lineWidth = width;
    _ctx.stroke();
    _ctx.restore();

    // hover 加粗高亮
    if (i === _hoverFlowIdx) {
      _ctx.save();
      _ctx.beginPath();
      _ctx.moveTo(pts[0].x, pts[0].y);
      for (let k = 1; k < pts.length; k++) _ctx.lineTo(pts[k].x, pts[k].y);
      _ctx.strokeStyle = `rgba(${c.r},${c.g},${c.b},${alpha * 1.6})`;
      _ctx.lineWidth = width + 2.5;
      _ctx.stroke();
      _ctx.restore();
    }
  }
}

// ---------- 绘制：粒子 ----------
function drawParticles(map) {
  for (let i = 0; i < _flows.length; i++) {
    const f = _flows[i];
    const s = _flowStates[i];
    if (!f || !s) continue;
    const cuisineKey = parseCuisineKey(f.to?.cuisine);
    const c = CUISINE_PALETTE[cuisineKey] || CUISINE_PALETTE.default;

    for (const p of s.particles) {
      const pt = bezier2(f.from, f._ctrl, f.to, p.t);
      const px = map.lngLatToContainer(new AMap.LngLat(pt.lng, pt.lat));
      if (!px) continue;

      // 越接近终点，size 渐大、alpha 渐弱（爆点预备）
      let size = p.size;
      let alpha = 0.85;
      if (p.t > CFG.burstThreshold) {
        const k = (p.t - CFG.burstThreshold) / (1 - CFG.burstThreshold);
        size = p.size * (1 + 1.2 * k);
        alpha = 0.85 * (1 - 0.6 * k);
      }

      // 外发光
      _ctx.beginPath();
      _ctx.arc(px.x, px.y, CFG.glow, 0, Math.PI * 2);
      _ctx.fillStyle = `rgba(${c.r},${c.g},${c.b},${alpha * 0.10})`;
      _ctx.fill();

      // 主体
      _ctx.beginPath();
      _ctx.arc(px.x, px.y, size, 0, Math.PI * 2);
      _ctx.fillStyle = `rgba(${c.r},${c.g},${c.b},${alpha})`;
      _ctx.fill();

      // 白芯
      _ctx.beginPath();
      _ctx.arc(px.x, px.y, size * 0.32, 0, Math.PI * 2);
      _ctx.fillStyle = `rgba(255,255,255,${0.5 * alpha})`;
      _ctx.fill();
    }
  }
}

// ---------- 绘制：终点光环扩散 ----------
function drawEndpointBurst(map) {
  const now = performance.now();
  for (let i = 0; i < _flows.length; i++) {
    const f = _flows[i];
    const s = _flowStates[i];
    if (!f || !s) continue;
    if (s.currentVolume < 6) continue;
    const cuisineKey = parseCuisineKey(f.to?.cuisine);
    const c = CUISINE_PALETTE[cuisineKey] || CUISINE_PALETTE.default;
    const intensity = Math.min(1, s.currentVolume / 80);

    // 每 800ms 触发一次扩散
    if (!s.lastBurstTs) s.lastBurstTs = now;
    const elapsed = now - s.lastBurstTs;
    const cycle = 800;
    if (elapsed >= cycle) s.lastBurstTs = now;
    const phase = (elapsed % cycle) / cycle; // 0→1

    const pt = bezier2(f.from, f._ctrl, f.to, 1.0);
    const px = map.lngLatToContainer(new AMap.LngLat(pt.lng, pt.lat));
    if (!px) continue;

    // 渐隐圆环
    const r = 6 + phase * (28 + 20 * intensity);
    const a = (1 - phase) * 0.45 * intensity;
    _ctx.beginPath();
    _ctx.arc(px.x, px.y, r, 0, Math.PI * 2);
    _ctx.strokeStyle = `rgba(${c.r},${c.g},${c.b},${a})`;
    _ctx.lineWidth = 1.5;
    _ctx.stroke();

    // 核心亮点
    _ctx.beginPath();
    _ctx.arc(px.x, px.y, 4 + 2 * intensity, 0, Math.PI * 2);
    _ctx.fillStyle = `rgba(${c.r},${c.g},${c.b},${0.55 * intensity})`;
    _ctx.fill();
  }
}

export default { initParticleFlow, startFlow, stopFlow, toggleFlow, setFlowConnections };
