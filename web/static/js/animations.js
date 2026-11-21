// animations.js — V0.8 动效工具库
// 全部用 requestAnimationFrame 驱动，不依赖 jQuery / GSAP
// 全部支持 prefers-reduced-motion: reduce 禁用

const REDUCED = typeof window !== 'undefined'
  && window.matchMedia
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ============================================================
// 1) 数字翻牌（60-80ms 滚动）
// ============================================================
export function flipNumber(el, from, to, duration = 700, formatter = (v) => Math.round(v).toLocaleString()) {
  if (!el) return;
  if (REDUCED || from === to) {
    el.textContent = formatter(to);
    return;
  }
  const start = performance.now();
  const range = to - from;
  const ease = (t) => 1 - Math.pow(1 - t, 3);  // ease-out cubic

  function step(now) {
    const t = Math.min(1, (now - start) / duration);
    const v = from + range * ease(t);
    el.textContent = formatter(v);
    if (t < 1) requestAnimationFrame(step);
    else el.textContent = formatter(to);
  }
  requestAnimationFrame(step);
}

// ============================================================
// 2) 进度条平滑增长（0 → ratio）
//    element ::after width 从 0 平滑到 ratio*100%
// ============================================================
export function gaugeValue(el, ratio, duration = 800) {
  if (!el) return;
  if (REDUCED) {
    el.style.setProperty('--w', `${Math.round(ratio * 100)}%`);
    return;
  }
  const start = performance.now();
  const ease = (t) => 1 - Math.pow(1 - t, 2);

  function step(now) {
    const t = Math.min(1, (now - start) / duration);
    el.style.setProperty('--w', `${Math.round(ratio * ease(t) * 100)}%`);
    if (t < 1) requestAnimationFrame(step);
    else el.style.setProperty('--w', `${Math.round(ratio * 100)}%`);
  }
  requestAnimationFrame(step);
}

// ============================================================
// 3) 涟漪扩散（按钮 / 平台卡点击）
//    创建一个绝对定位的 .ring，从 0 scale + opacity 1 → 4 scale + 0
// ============================================================
export function pulseRing(el, opts = {}) {
  if (!el) return;
  if (REDUCED) return;
  const { color = 'rgba(139, 26, 26, 0.35)', size = 80, duration = 700 } = opts;
  // 元素需要 position: relative
  const rect = el.getBoundingClientRect();
  const ring = document.createElement('span');
  ring.className = 'pulse-ring';
  const dpr = window.devicePixelRatio || 1;
  Object.assign(ring.style, {
    position: 'absolute',
    left: '50%',
    top: '50%',
    width: `${size}px`,
    height: `${size}px`,
    marginLeft: `-${size / 2}px`,
    marginTop: `-${size / 2}px`,
    borderRadius: '50%',
    background: color,
    pointerEvents: 'none',
    transform: 'scale(0)',
    opacity: '1',
    transition: `transform ${duration}ms ease-out, opacity ${duration}ms ease-out`,
    zIndex: '0',
  });
  el.style.position = el.style.position || 'relative';
  el.style.overflow = 'hidden';
  el.appendChild(ring);
  // 强制重排
  void ring.offsetWidth;
  ring.style.transform = 'scale(4)';
  ring.style.opacity = '0';
  setTimeout(() => ring.remove(), duration);
}

// ============================================================
// 4) 打字机
// ============================================================
export function typewriter(el, text, opts = {}) {
  if (!el || !text) return Promise.resolve();
  if (REDUCED) {
    el.innerHTML = text;
    return Promise.resolve();
  }
  const { perChar = 25, startDelay = 0, cursor = '▍' } = opts;
  return new Promise((resolve) => {
    el.innerHTML = `<span class="tw-text"></span><span class="tw-cursor">${cursor}</span>`;
    const target = el.querySelector('.tw-text');
    const cur = el.querySelector('.tw-cursor');
    if (startDelay) {
      setTimeout(() => tick(), startDelay);
    } else {
      tick();
    }
    let i = 0;
    function tick() {
      // 跳过 HTML 标签（简单处理：遇到 < 就跳到 >）
      if (text[i] === '<') {
        const close = text.indexOf('>', i);
        if (close !== -1) {
          target.innerHTML = text.slice(0, close + 1);
          i = close + 1;
        }
      }
      if (i >= text.length) {
        // 闪烁光标直到隐藏
        if (cur) cur.style.animation = 'blink 0.8s infinite';
        setTimeout(() => cur && cur.remove(), 1200);
        resolve();
        return;
      }
      target.innerHTML = text.slice(0, i + 1);
      i++;
      setTimeout(tick, perChar);
    }
  });
}

// ============================================================
// 5) requestAnimationFrame 驱动 tick（用于循环动画）
//    返回 stop() 函数
// ============================================================
export function rafTicker(callback, fps = 30) {
  if (REDUCED) return () => {};
  const interval = 1000 / fps;
  let last = 0;
  let id = null;
  function tick(now) {
    if (now - last >= interval) {
      callback(now);
      last = now;
    }
    id = requestAnimationFrame(tick);
  }
  id = requestAnimationFrame(tick);
  return () => cancelAnimationFrame(id);
}

// ============================================================
// 6) 折线图追加点（环形 buffer，左滚 + 渐变拖尾）
//    调用方需在外部维护 series 数组
// ============================================================
export function makeChartSeries(maxLen = 24) {
  return {
    data: [],
    maxLen,
    push(v) {
      this.data.push(v);
      if (this.data.length > this.maxLen) this.data.shift();
    },
  };
}

export function drawSeriesChart(canvas, series, opts = {}) {
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.round(rect.width * dpr);
  canvas.height = Math.round(rect.height * dpr);
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  const data = series.data;
  if (data.length < 2) return;

  const max = Math.max(...data) * 1.15;
  const min = 0;
  const padding = 40 * dpr;
  const xStep = (w - padding - 8 * dpr) / (series.maxLen - 1);
  // 我们让 data 按"序号"映射到 0..maxLen 区间：最左 = maxLen-data.length 位置
  const startIdx = series.maxLen - data.length;

  // 网格
  ctx.strokeStyle = 'rgba(15, 23, 42, 0.06)';
  ctx.lineWidth = 1 * dpr;
  for (let i = 0; i < 5; i++) {
    const y = (h - 30 * dpr) * (i / 4) + 10 * dpr;
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(w - 8 * dpr, y);
    ctx.stroke();
  }

  // Y 轴标签
  ctx.fillStyle = 'rgba(15, 23, 42, 0.4)';
  ctx.font = `${10 * dpr}px JetBrains Mono, monospace`;
  for (let i = 0; i < 5; i++) {
    const y = (h - 30 * dpr) * (i / 4) + 14 * dpr;
    const v = Math.round(max - (max - min) * (i / 4));
    ctx.fillText(v.toLocaleString(), 6 * dpr, y);
  }

  // X 轴
  for (let i = 0; i < series.maxLen; i += 4) {
    const x = padding + xStep * i;
    ctx.fillText(`${i}h`, x - 6 * dpr, h - 8 * dpr);
  }

  // 填充区域（最新点最右）
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, 'rgba(184, 26, 26, 0.18)');
  grad.addColorStop(1, 'rgba(184, 26, 26, 0)');
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.moveTo(padding + xStep * startIdx, h - 20 * dpr);
  for (let i = 0; i < data.length; i++) {
    const x = padding + xStep * (startIdx + i);
    const y = (h - 30 * dpr) * (1 - (data[i] - min) / (max - min)) + 10 * dpr;
    ctx.lineTo(x, y);
  }
  ctx.lineTo(padding + xStep * (startIdx + data.length - 1), h - 20 * dpr);
  ctx.closePath();
  ctx.fill();

  // 折线
  ctx.strokeStyle = '#8B1A1A';
  ctx.lineWidth = 2 * dpr;
  ctx.beginPath();
  for (let i = 0; i < data.length; i++) {
    const x = padding + xStep * (startIdx + i);
    const y = (h - 30 * dpr) * (1 - (data[i] - min) / (max - min)) + 10 * dpr;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // 末点闪烁
  const lastX = padding + xStep * (startIdx + data.length - 1);
  const lastY = (h - 30 * dpr) * (1 - (data[data.length - 1] - min) / (max - min)) + 10 * dpr;
  ctx.fillStyle = '#8B1A1A';
  ctx.beginPath();
  ctx.arc(lastX, lastY, 4 * dpr, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = 'rgba(184, 26, 26, 0.3)';
  ctx.lineWidth = 1.5 * dpr;
  ctx.beginPath();
  ctx.arc(lastX, lastY, 8 * dpr, 0, Math.PI * 2);
  ctx.stroke();

  if (opts.label) {
    ctx.fillStyle = 'rgba(15, 23, 42, 0.8)';
    ctx.font = `${10 * dpr}px JetBrains Mono, monospace`;
    ctx.fillText(`now · ${Math.round(data[data.length - 1]).toLocaleString()}/h`, lastX - 80 * dpr, lastY - 10 * dpr);
  }
}

// ============================================================
// V0.9+ · 折线图 · 「从左到右动态绘线」
// ============================================================
// data 数组从左到右依次填充（data[0]=最左，data[length-1]=最右）
// 适合演示"实时生成"的视觉效果
// maxLen 限定最大数据点数；empty 切换显示空态
//
// 增强版：支持多线对比、贝塞尔曲线、峰值标记、粒子效果
// ============================================================

// ============================================================
// 平滑曲线：Cardinal Spline（通过所有数据点）
// ============================================================
// 对 segment P[i]→P[i+1]，用前后点 P[i-1] 和 P[i+2] 推导控制点
// tension: 0=直线, 0.5=均匀, 1=很弯
// ============================================================
function cardinalControlPoints(p0, p1, p2, p3, tension = 0.5) {
  const t = tension;
  return [
    { x: p1.x + (p2.x - p0.x) / 6 * t, y: p1.y + (p2.y - p0.y) / 6 * t },
    { x: p2.x - (p3.x - p1.x) / 6 * t, y: p2.y - (p3.y - p1.y) / 6 * t },
  ];
}

function drawSmoothLine(ctx, points, dpr) {
  if (points.length < 2) return;
  const n = points.length;
  ctx.moveTo(points[0].x, points[0].y);
  if (n === 2) {
    ctx.lineTo(points[1].x, points[1].y);
    return;
  }
  // 首段: 用 p0,p0,p1,p2
  let [cp1, cp2] = cardinalControlPoints(points[0], points[0], points[1], points[2]);
  ctx.bezierCurveTo(cp1.x, cp1.y, cp2.x, cp2.y, points[1].x, points[1].y);
  // 中间段
  for (let i = 1; i < n - 2; i++) {
    [cp1, cp2] = cardinalControlPoints(points[i - 1], points[i], points[i + 1], points[i + 2]);
    ctx.bezierCurveTo(cp1.x, cp1.y, cp2.x, cp2.y, points[i + 1].x, points[i + 1].y);
  }
}

function drawSmoothArea(ctx, points, baseY, dpr) {
  if (points.length < 2) return;
  const n = points.length;
  ctx.moveTo(points[0].x, baseY);
  ctx.lineTo(points[0].x, points[0].y);
  if (n === 2) {
    ctx.lineTo(points[1].x, points[1].y);
    ctx.lineTo(points[1].x, baseY);
    ctx.closePath();
    return;
  }
  // 首段
  let [cp1, cp2] = cardinalControlPoints(points[0], points[0], points[1], points[2]);
  ctx.bezierCurveTo(cp1.x, cp1.y, cp2.x, cp2.y, points[1].x, points[1].y);
  // 中间段
  for (let i = 1; i < n - 2; i++) {
    [cp1, cp2] = cardinalControlPoints(points[i - 1], points[i], points[i + 1], points[i + 2]);
    ctx.bezierCurveTo(cp1.x, cp1.y, cp2.x, cp2.y, points[i + 1].x, points[i + 1].y);
  }
  // 回到基线
  ctx.lineTo(points[n - 1].x, baseY);
  ctx.closePath();
}

// ============================================================
// 增强粒子系统（长拖尾 + 发光 + 丰富色彩）
// ============================================================
class ParticleSystem {
  constructor() {
    this.particles = [];
    this.lastEmit = 0;
  }

  emit(x, y, color, intensity = 1, burst = false) {
    const count = burst ? Math.floor(6 * intensity) : Math.floor(2 * intensity);
    for (let i = 0; i < count; i++) {
      const angle = burst ? Math.random() * Math.PI * 2 : (Math.random() - 0.5) * 1.5 + Math.PI * 0.75;
      const speed = burst ? 1 + Math.random() * 3 : 0.3 + Math.random() * 1.5;
      this.particles.push({
        x, y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - (burst ? 1 : 0.5),
        life: 1,
        decay: burst ? 0.015 + Math.random() * 0.02 : 0.008 + Math.random() * 0.015,
        size: burst ? 1.5 + Math.random() * 2.5 : 1 + Math.random() * 2,
        color,
        trail: [],
      });
    }
  }

  update() {
    this.particles = this.particles.filter(p => {
      p.trail.push({ x: p.x, y: p.y });
      if (p.trail.length > 8) p.trail.shift();
      p.x += p.vx;
      p.y += p.vy;
      p.vy += 0.03;
      p.vx *= 0.98;
      p.life -= p.decay;
      return p.life > 0;
    });
  }

  draw(ctx, dpr) {
    this.particles.forEach(p => {
      // 拖尾
      if (p.trail.length > 1) {
        ctx.globalAlpha = p.life * 0.2;
        ctx.strokeStyle = p.color;
        ctx.lineWidth = p.size * 0.5 * dpr;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(p.trail[0].x, p.trail[0].y);
        for (let i = 1; i < p.trail.length; i++) {
          ctx.lineTo(p.trail[i].x, p.trail[i].y);
        }
        ctx.stroke();
      }
      // 发光光晕
      ctx.globalAlpha = p.life * 0.15;
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size * 3 * dpr, 0, Math.PI * 2);
      ctx.fill();
      // 核心
      ctx.globalAlpha = p.life * 0.7;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size * dpr, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.globalAlpha = 1;
  }
}

const particleSystem = new ParticleSystem();

export function drawLeftToRightChart(canvas, data, opts = {}) {
  if (!canvas) return;
  const maxLen = opts.maxLen || 24;
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  if (rect.width === 0) return;
  canvas.width = Math.round(rect.width * dpr);
  canvas.height = Math.round(rect.height * dpr);
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;

  // ===== 增大左边界给Y轴标签留足空间 =====
  const padding = 56 * dpr;
  const xStep = (w - padding - 8 * dpr) / (maxLen - 1);
  const baseY = h - 32 * dpr;

  // 首次绘制标记（入场动画用）
  if (!canvas._hasDrawn) {
    canvas._hasDrawn = true;
    canvas._drawProgress = 0;
    canvas._drawTarget = 0;
  }

  // 入场动画进度
  const entryAnimate = opts.entryAnimate !== false;
  if (entryAnimate && canvas._drawProgress !== undefined) {
    canvas._drawTarget = 1;
    canvas._drawProgress = Math.min(1, (canvas._drawProgress || 0) + 0.04);
  } else {
    canvas._drawProgress = 1;
  }
  const drawRatio = canvas._drawProgress || 1;

  // 离屏 Canvas 缓存（网格）
  const cacheKey = `off_${canvas.width}_${canvas.height}_${maxLen}_${dpr}`;
  if (!canvas._offCanvas || canvas._offCacheKey !== cacheKey) {
    const off = document.createElement('canvas');
    off.width = canvas.width;
    off.height = canvas.height;
    const octx = off.getContext('2d');

    octx.fillStyle = '#FAFAF7';
    octx.fillRect(0, 0, off.width, off.height);

    octx.strokeStyle = 'rgba(15, 23, 42, 0.035)';
    octx.lineWidth = 0.5 * dpr;
    for (let i = 0; i < 6; i++) {
      const y = baseY * (i / 5) + 10 * dpr;
      octx.beginPath();
      octx.moveTo(padding, y);
      octx.lineTo(w - 8 * dpr, y);
      octx.stroke();
    }

    const gridStep = maxLen >= 48 ? 6 : 3;
    octx.strokeStyle = 'rgba(15, 23, 42, 0.025)';
    for (let i = 0; i < maxLen; i += gridStep) {
      const x = padding + xStep * i;
      octx.beginPath();
      octx.moveTo(x, 10 * dpr);
      octx.lineTo(x, baseY);
      octx.stroke();
    }

    canvas._offCanvas = off;
    canvas._offCacheKey = cacheKey;
  }

  ctx.drawImage(canvas._offCanvas, 0, 0);

  const hiddenSet = opts.hiddenLines || new Set();

  // ===== 空态 =====
  if (!data || data.length < 2) {
    ctx.strokeStyle = 'rgba(15, 23, 42, 0.12)';
    ctx.setLineDash([4 * dpr, 4 * dpr]);
    ctx.beginPath();
    ctx.moveTo(padding, h / 2);
    ctx.lineTo(w - 8 * dpr, h / 2);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = 'rgba(15, 23, 42, 0.4)';
    ctx.font = `500 ${12 * dpr}px JetBrains Mono, monospace`;
    ctx.textAlign = 'center';
    const dots = '.'.repeat(Math.floor(Date.now() / 600) % 4);
    ctx.fillText(`正在采集数据 · collecting${dots}`, w / 2, h / 2 - 10 * dpr);
    ctx.fillStyle = 'rgba(15, 23, 42, 0.2)';
    ctx.font = `${9 * dpr}px JetBrains Mono, monospace`;
    ctx.fillText('数据到达后自动绘制趋势', w / 2, h / 2 + 14 * dpr);
    ctx.textAlign = 'start';
    requestAnimationFrame(() => drawLeftToRightChart(canvas, data, opts));
    return;
  }

  const allRaw = Array.isArray(data[0]) ? data : [data];
  const lines = allRaw;
  const allValues = lines.flat();
  if (allValues.length === 0) {
    ctx.fillStyle = 'rgba(15, 23, 42, 0.35)';
    ctx.font = `500 ${12 * dpr}px JetBrains Mono, monospace`;
    ctx.textAlign = 'center';
    ctx.fillText('正在采集数据 · collecting…', w / 2, h / 2 - 8 * dpr);
    ctx.textAlign = 'start';
    return;
  }

  // 分离总采集线和子线
  const totalLine = lines.length > 1 ? lines[0] : null;
  const subLines = lines.length > 1 ? lines.slice(1) : lines;
  const chartMode = opts.chartMode || 'channel';

  // Y轴范围：分渠道模式用子线，总览模式用总线
  let rawMax, rawMin;
  if (chartMode === 'total' && totalLine) {
    rawMax = Math.max(...totalLine) * 1.08;
    rawMin = Math.max(1, Math.min(...totalLine) * 0.8);
  } else {
    const sv = subLines.flat();
    rawMax = sv.length > 0 ? Math.max(...sv) * 1.15 : Math.max(...allValues) * 1.08;
    rawMin = Math.max(1, (sv.length > 0 ? Math.min(...sv) : Math.min(...allValues)) * 0.8);
  }

  const useLog = opts.logScale && rawMin > 0;
  const max = rawMax;
  const min = rawMin;

  const valToY = (v) => {
    if (useLog) {
      const logMin = Math.log(min);
      const logMax = Math.log(max);
      const ratio = (Math.log(v) - logMin) / (logMax - logMin);
      return baseY * (1 - ratio) + 10 * dpr;
    }
    return baseY * (1 - (v - min) / (max - min)) + 10 * dpr;
  };

  // ===== Y 轴标签（基于子线范围） =====
  ctx.fillStyle = 'rgba(15, 23, 42, 0.45)';
  ctx.font = `${10 * dpr}px JetBrains Mono, monospace`;
  ctx.textAlign = 'right';
  if (useLog) {
    const logSteps = [];
    let val = Math.round(min);
    while (val <= max * 1.05) {
      logSteps.push(val);
      val = Math.round(val * 2);
    }
    logSteps.forEach((v) => {
      const y = valToY(v);
      if (y > 16 * dpr && y < h - 12 * dpr) {
        ctx.fillText(Math.round(v).toLocaleString(), padding - 8 * dpr, y + 4 * dpr);
      }
    });
  } else {
    for (let i = 0; i < 5; i++) {
      const y = baseY * (i / 4) + 14 * dpr;
      const v = Math.round(max - (max - min) * (i / 4));
      ctx.fillText(v.toLocaleString(), padding - 8 * dpr, y);
    }
  }
  ctx.textAlign = 'start';

  // ===== X 轴标签（实际时间 HH:MM） =====
  const now = new Date();
  const labelStep = maxLen >= 48 ? 6 : 4;
  ctx.fillStyle = 'rgba(15, 23, 42, 0.35)';
  ctx.font = `${9 * dpr}px JetBrains Mono, monospace`;
  ctx.textAlign = 'center';
  for (let i = 0; i < maxLen; i += labelStep) {
    const x = padding + xStep * i;
    const offsetH = maxLen - 1 - i;
    const t = new Date(now.getTime() - offsetH * 60000); // 每分钟一个点
    const label = `${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}`;
    ctx.fillText(label, x, h - 6 * dpr);
  }
  ctx.textAlign = 'start';

  // ===== 时段区间标注（午间/晚间高峰） =====
  const nowH = now.getHours() * 60 + now.getMinutes();
  const annotationData = [
    { start: 11 * 60, end: 13 * 60, label: '午间高峰', color: 'rgba(184, 134, 11, 0.08)' },
    { start: 17 * 60, end: 19 * 60, label: '晚间高峰', color: 'rgba(139, 26, 26, 0.08)' },
  ];
  for (const ann of annotationData) {
    // 计算在可见范围的位置
    const visStart = nowH - (maxLen - 1); // 最左的分钟
    const visEnd = nowH;
    const annStart = Math.max(ann.start, visStart);
    const annEnd = Math.min(ann.end, visEnd);
    if (annStart >= annEnd) continue;
    const startIdx = maxLen - 1 - (nowH - annStart);
    const endIdx = maxLen - 1 - (nowH - annEnd);
    const x1 = padding + xStep * Math.max(0, startIdx);
    const x2 = padding + xStep * Math.min(maxLen - 1, endIdx);
    ctx.fillStyle = ann.color;
    ctx.fillRect(x1, 10 * dpr, x2 - x1, baseY - 10 * dpr);
    // 标签
    ctx.fillStyle = 'rgba(15, 23, 42, 0.25)';
    ctx.font = `500 ${8 * dpr}px JetBrains Mono, monospace`;
    ctx.textAlign = 'center';
    ctx.fillText(ann.label, (x1 + x2) / 2, baseY - 6 * dpr);
    ctx.textAlign = 'start';
  }

  // 线条配色
  const lineColors = [
    { stroke: '#8B1A1A', fill: 'rgba(139, 26, 26, ', glow: 'rgba(139, 26, 26, 0.25)', name: '总采集' },
    { stroke: '#161823', fill: 'rgba(22, 24, 35, ', glow: 'rgba(22, 24, 35, 0.20)', name: '抖音' },
    { stroke: '#FF2442', fill: 'rgba(255, 36, 66, ', glow: 'rgba(255, 36, 66, 0.20)', name: '小红书' },
    { stroke: '#B8860B', fill: 'rgba(184, 134, 11, ', glow: 'rgba(184, 134, 11, 0.20)', name: '美团' },
  ];

  // 暴露最新数据（基于总采集）
  if (totalLine && totalLine.length > 0) {
    canvas._latestValues = {
      total: Math.round(totalLine[totalLine.length - 1]) || 0,
      prevTotal: totalLine.length >= 2 ? Math.round(totalLine[totalLine.length - 1]) : 0,
    };
  }

  // 存数据供点击钻取
  canvas._chartData = {
    lines: lines.map((ld, li) => ({
      name: (opts.legend && opts.legend[li]) || `线${li + 1}`,
      color: lineColors[li % lineColors.length].stroke,
      data: ld.map((v, i) => {
        const offsetH = maxLen - 1 - i;
        const t = new Date(now.getTime() - offsetH * 60000);
        return { value: Math.round(v), time: `${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}` };
      }),
    })),
  };

  // 存储图例区域
  canvas._legendRegions = [];

  if (chartMode === 'channel') {
    // ===== 分渠道模式：总采集为背景填充 + 子线 =====
    if (totalLine && totalLine.length > 1 && !hiddenSet.has(0)) {
      const totalVisible = Math.max(2, Math.floor(totalLine.length * drawRatio));
      const totalPoints = totalLine.slice(0, totalVisible).map((v, i) => ({
        x: padding + xStep * i,
        y: valToY(Math.min(v, max)),
        value: v,
      }));
      const g = ctx.createLinearGradient(0, 0, 0, h);
      g.addColorStop(0, 'rgba(139, 26, 26, 0.07)');
      g.addColorStop(0.5, 'rgba(139, 26, 26, 0.03)');
      g.addColorStop(1, 'rgba(139, 26, 26, 0)');
      ctx.fillStyle = g;
      ctx.beginPath();
      drawSmoothArea(ctx, totalPoints, baseY, dpr);
      ctx.fill();
      ctx.strokeStyle = 'rgba(139, 26, 26, 0.15)';
      ctx.lineWidth = 1 * dpr;
      ctx.setLineDash([3 * dpr, 4 * dpr]);
      ctx.beginPath();
      for (let i = 0; i < totalPoints.length; i++) {
        const p = totalPoints[i];
        if (i === 0) ctx.moveTo(p.x, p.y);
        else ctx.lineTo(p.x, p.y);
      }
      ctx.stroke();
      ctx.setLineDash([]);
      const lastT = totalPoints[totalPoints.length - 1];
      ctx.fillStyle = 'rgba(139, 26, 26, 0.5)';
      ctx.font = `500 ${9 * dpr}px JetBrains Mono, monospace`;
      ctx.textAlign = 'right';
      ctx.fillText(`总 ${Math.round(lastT.value).toLocaleString()}/h`, w - 10 * dpr, 14 * dpr + 14 * dpr);
      ctx.textAlign = 'start';
    }

    // 子线
    subLines.forEach((lineData, subIdx) => {
      const lineIdx = totalLine ? subIdx + 1 : subIdx;
      if (hiddenSet.has(lineIdx)) return;
      const color = lineColors[lineIdx % lineColors.length];
      const visibleCount = Math.max(2, Math.floor(lineData.length * drawRatio));
      const visibleData = lineData.slice(0, visibleCount);
      const points = visibleData.map((v, i) => ({
        x: padding + xStep * i, y: valToY(v), value: v,
      }));

      const grad = ctx.createLinearGradient(0, 0, 0, h);
      grad.addColorStop(0, color.fill + '0.15)');
      grad.addColorStop(0.5, color.fill + '0.05)');
      grad.addColorStop(1, color.fill + '0)');
      ctx.fillStyle = grad;
      ctx.beginPath();
      drawSmoothArea(ctx, points, baseY, dpr);
      ctx.fill();

      ctx.shadowColor = color.glow;
      ctx.shadowBlur = 6 * dpr;
      ctx.strokeStyle = color.stroke;
      ctx.lineWidth = 2.5 * dpr;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.beginPath();
      drawSmoothLine(ctx, points, dpr);
      ctx.stroke();
      ctx.shadowColor = 'transparent';
      ctx.shadowBlur = 0;

      let maxVal = -Infinity, minVal = Infinity;
      let maxPoint = null, minPoint = null;
      points.forEach(p => {
        if (p.value > maxVal) { maxVal = p.value; maxPoint = p; }
        if (p.value < minVal) { minVal = p.value; minPoint = p; }
      });
      if (maxPoint && points.length > 3) {
        ctx.fillStyle = color.stroke;
        ctx.font = `600 ${9 * dpr}px JetBrains Mono, monospace`;
        ctx.fillText(`↑ ${Math.round(maxPoint.value).toLocaleString()}`, maxPoint.x - 22 * dpr, maxPoint.y - 12 * dpr);
        ctx.beginPath();
        ctx.arc(maxPoint.x, maxPoint.y, 5 * dpr, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = 'rgba(255,255,255,0.8)';
        ctx.lineWidth = 1.5 * dpr;
        ctx.stroke();
        particleSystem.emit(maxPoint.x, maxPoint.y, color.stroke, 0.8, false);
      }
      if (minPoint && points.length > 3 && minPoint !== maxPoint) {
        ctx.fillStyle = 'rgba(15, 23, 42, 0.45)';
        ctx.font = `500 ${9 * dpr}px JetBrains Mono, monospace`;
        ctx.fillText(`↓ ${Math.round(minPoint.value).toLocaleString()}`, minPoint.x - 22 * dpr, minPoint.y + 18 * dpr);
      }

      points.forEach((p, i) => {
        if (i % 4 === 0 || i === points.length - 1) {
          ctx.fillStyle = color.stroke;
          ctx.beginPath();
          ctx.arc(p.x, p.y, 2.5 * dpr, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = 'rgba(255,255,255,0.6)';
          ctx.lineWidth = 1 * dpr;
          ctx.stroke();
        }
      });

      const lastPoint = points[points.length - 1];
      const pulseRadius = 10 * dpr + Math.sin(Date.now() / 350) * 3 * dpr;
      ctx.strokeStyle = color.fill + '0.35)';
      ctx.lineWidth = 1 * dpr;
      ctx.beginPath();
      ctx.arc(lastPoint.x, lastPoint.y, pulseRadius, 0, Math.PI * 2);
      ctx.stroke();

      ctx.fillStyle = color.stroke;
      ctx.beginPath();
      ctx.arc(lastPoint.x, lastPoint.y, 4.5 * dpr, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.85)';
      ctx.lineWidth = 2 * dpr;
      ctx.stroke();

      if (opts.label && subIdx === 0) {
        ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
        ctx.font = `600 ${10 * dpr}px JetBrains Mono, monospace`;
        const label = `now · ${Math.round(lastPoint.value).toLocaleString()}/h`;
        const tw = ctx.measureText(label).width;
        const bx = lastPoint.x - tw / 2 - 8 * dpr;
        const by = lastPoint.y - 22 * dpr;
        ctx.fillStyle = 'rgba(255,255,255,0.9)';
        ctx.beginPath();
        ctx.roundRect(bx - 4 * dpr, by - 2 * dpr, tw + 16 * dpr, 18 * dpr, 4 * dpr);
        ctx.fill();
        ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
        ctx.fillText(label, bx + 4 * dpr, by + 12 * dpr);
      }

      if (entryAnimate && drawRatio < 1 && subIdx === 0) {
        particleSystem.emit(lastPoint.x, lastPoint.y, color.stroke, 0.5, false);
      }
    });
  } else if (chartMode === 'total' && totalLine) {
    // ===== 总览模式：仅显示总采集线 =====
    const visibleCount = Math.max(2, Math.floor(totalLine.length * drawRatio));
    const visibleData = totalLine.slice(0, visibleCount);
    const color = { stroke: '#8B1A1A', fill: 'rgba(139, 26, 26, ', glow: 'rgba(139, 26, 26, 0.25)' };
    const points = visibleData.map((v, i) => ({
      x: padding + xStep * i, y: valToY(v), value: v,
    }));

    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, 'rgba(139, 26, 26, 0.12)');
    grad.addColorStop(0.5, 'rgba(139, 26, 26, 0.04)');
    grad.addColorStop(1, 'rgba(139, 26, 26, 0)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    drawSmoothArea(ctx, points, baseY, dpr);
    ctx.fill();

    ctx.shadowColor = color.glow;
    ctx.shadowBlur = 6 * dpr;
    ctx.strokeStyle = color.stroke;
    ctx.lineWidth = 3 * dpr;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.beginPath();
    drawSmoothLine(ctx, points, dpr);
    ctx.stroke();
    ctx.shadowColor = 'transparent';
    ctx.shadowBlur = 0;

    let maxVal = -Infinity, minVal = Infinity;
    let maxPoint = null, minPoint = null;
    points.forEach(p => {
      if (p.value > maxVal) { maxVal = p.value; maxPoint = p; }
      if (p.value < minVal) { minVal = p.value; minPoint = p; }
    });
    if (maxPoint && points.length > 3) {
      ctx.fillStyle = color.stroke;
      ctx.font = `600 ${9 * dpr}px JetBrains Mono, monospace`;
      ctx.fillText(`↑ ${Math.round(maxPoint.value).toLocaleString()}`, maxPoint.x - 22 * dpr, maxPoint.y - 12 * dpr);
      ctx.beginPath();
      ctx.arc(maxPoint.x, maxPoint.y, 5 * dpr, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.8)';
      ctx.lineWidth = 1.5 * dpr;
      ctx.stroke();
    }

    const lastPoint = points[points.length - 1];
    const pulseRadius = 12 * dpr + Math.sin(Date.now() / 350) * 3 * dpr;
    ctx.strokeStyle = 'rgba(139, 26, 26, 0.3)';
    ctx.lineWidth = 1 * dpr;
    ctx.beginPath();
    ctx.arc(lastPoint.x, lastPoint.y, pulseRadius, 0, Math.PI * 2);
    ctx.stroke();

    ctx.fillStyle = color.stroke;
    ctx.beginPath();
    ctx.arc(lastPoint.x, lastPoint.y, 5 * dpr, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.85)';
    ctx.lineWidth = 2 * dpr;
    ctx.stroke();

    if (opts.label) {
      ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
      ctx.font = `600 ${10 * dpr}px JetBrains Mono, monospace`;
      const label = `总采集 · ${Math.round(lastPoint.value).toLocaleString()}/h`;
      const tw = ctx.measureText(label).width;
      const bx = lastPoint.x - tw / 2 - 8 * dpr;
      const by = lastPoint.y - 22 * dpr;
      ctx.fillStyle = 'rgba(255,255,255,0.9)';
      ctx.beginPath();
      ctx.roundRect(bx - 4 * dpr, by - 2 * dpr, tw + 16 * dpr, 18 * dpr, 4 * dpr);
      ctx.fill();
      ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
      ctx.fillText(label, bx + 4 * dpr, by + 12 * dpr);
    }
  }

  particleSystem.update();
  particleSystem.draw(ctx, dpr);

  // 图例
  if (lines.length > 1 && opts.legend) {
    const legendY = 14 * dpr;
    let legendX = w - 10 * dpr;
    [...opts.legend].reverse().forEach((name, i) => {
      const realIdx = lines.length - 1 - i;
      const color = lineColors[realIdx % lineColors.length];
      const isHidden = hiddenSet.has(realIdx);
      ctx.font = `500 ${9 * dpr}px JetBrains Mono, monospace`;
      const textWidth = ctx.measureText(name).width;
      const itemWidth = textWidth + 22 * dpr;
      legendX -= itemWidth;

      ctx.fillStyle = isHidden ? 'rgba(15, 23, 42, 0.03)' : 'rgba(15, 23, 42, 0.06)';
      ctx.beginPath();
      ctx.roundRect(legendX - 4 * dpr, legendY - 8 * dpr, itemWidth, 18 * dpr, 4 * dpr);
      ctx.fill();

      ctx.fillStyle = isHidden ? 'rgba(15, 23, 42, 0.2)' : color.stroke;
      ctx.fillRect(legendX, legendY - 2 * dpr, 14 * dpr, 3 * dpr);

      ctx.fillStyle = isHidden ? 'rgba(15, 23, 42, 0.35)' : 'rgba(15, 23, 42, 0.7)';
      ctx.fillText(name, legendX + 18 * dpr, legendY + 1 * dpr);

      canvas._legendRegions.push({
        x: legendX - 4 * dpr, y: legendY - 8 * dpr,
        w: itemWidth, h: 18 * dpr,
        idx: realIdx, name,
      });
    });
    canvas.style.cursor = 'default';
  }

  // 十字线 + tooltip
  if (opts.mouse && lines[0] && lines[0].length > 1) {
    const mx = opts.mouse.x;
    const my = opts.mouse.y;
    const nearestIdx = Math.round((mx - padding) / xStep);
    const clampedIdx = Math.max(0, Math.min(lines[0].length - 1, nearestIdx));
    const cx = padding + xStep * clampedIdx;

    ctx.strokeStyle = 'rgba(15, 23, 42, 0.15)';
    ctx.lineWidth = 1 * dpr;
    ctx.setLineDash([4 * dpr, 4 * dpr]);
    ctx.beginPath();
    ctx.moveTo(cx, 10 * dpr);
    ctx.lineTo(cx, baseY);
    ctx.stroke();
    ctx.setLineDash([]);

    const lineNames = opts.legend || ['1', '2', '3', '4'];
    let tooltipLines = [];
    lines.forEach((ld, li) => {
      if (hiddenSet.has(li) || clampedIdx >= ld.length) return;
      const color = lineColors[li % lineColors.length];
      const vy = valToY(ld[clampedIdx]);
      ctx.fillStyle = color.stroke;
      ctx.beginPath();
      ctx.arc(cx, vy, 4 * dpr, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1.5 * dpr;
      ctx.stroke();
      tooltipLines.push({ name: lineNames[li], value: Math.round(ld[clampedIdx]).toLocaleString(), color: color.stroke });
    });

    if (tooltipLines.length > 0) {
      const lineH = 18 * dpr;
      const pad = 10 * dpr;
      const tw = 140 * dpr;
      const th = tooltipLines.length * lineH + pad * 2;
      let tx = cx + 14 * dpr;
      let ty = my > h / 2 ? 20 * dpr : baseY - th - 40 * dpr;
      if (tx + tw > w - 8 * dpr) tx = cx - tw - 14 * dpr;

      ctx.fillStyle = 'rgba(255, 255, 255, 0.95)';
      ctx.strokeStyle = 'rgba(15, 23, 42, 0.12)';
      ctx.lineWidth = 1 * dpr;
      ctx.beginPath();
      ctx.roundRect(tx, ty, tw, th, 4 * dpr);
      ctx.fill();
      ctx.stroke();

      ctx.textAlign = 'start';
      tooltipLines.forEach((tl, ti) => {
        const ly = ty + pad + ti * lineH + lineH * 0.7;
        ctx.fillStyle = tl.color;
        ctx.fillRect(tx + pad, ly - 3 * dpr, 8 * dpr, 3 * dpr);
        ctx.fillStyle = 'rgba(15, 23, 42, 0.7)';
        ctx.font = `500 ${10 * dpr}px JetBrains Mono, monospace`;
        ctx.fillText(`${tl.name}  ${tl.value}`, tx + pad + 14 * dpr, ly + 1 * dpr);
      });
    }
  }
}

// ============================================================
// 7) 视口入场动画
// ============================================================
export function revealOnView(el, opts = {}) {
  if (!el || REDUCED) return;
  const { threshold = 0.1, rootMargin = '0px', once = true, className = 'revealed' } = opts;
  el.classList.add('reveal');
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add(className);
        if (once) io.unobserve(entry.target);
      } else if (!once) {
        entry.target.classList.remove(className);
      }
    });
  }, { threshold, rootMargin });
  io.observe(el);
}

// ============================================================
// 工具：元素是否在视口内
// ============================================================
export function inViewport(el) {
  if (!el) return false;
  const r = el.getBoundingClientRect();
  return r.top < window.innerHeight && r.bottom > 0;
}

// ============================================================
// 工具：favicon 上画动态小点（可选）
// ============================================================
export function setFaviconState(color = '#8B1A1A') {
  let link = document.querySelector("link[rel*='icon']");
  if (!link) {
    link = document.createElement('link');
    link.rel = 'icon';
    document.head.appendChild(link);
  }
  // 用 data-uri 简单点
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><circle cx='16' cy='16' r='14' fill='${color}'/></svg>`;
  link.href = 'data:image/svg+xml,' + encodeURIComponent(svg);
}
