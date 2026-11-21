// dashboard.js — V0.7 仪表盘：UI 状态 + 事件流 + 建议 + KPI 绑定 + demo 集成

import { watch } from './store.js';
import { on } from './eventBus.js';
import { drawOverlay as drawOverlayImpl } from './overlay.js';

const $ = (id) => document.getElementById(id);

// ============================================================
// 初始化
// ============================================================
export function initDashboard() {
  bindStateWatchers();
  bindDemoStream();
  bindAgentAdvice();
  bindChatModeTabs();
  initAdviceEmpty();
  initInsightPanel();
  bindReportButton();
}

// ============================================================
// 1) Store 状态 → 徽章/按钮
// ============================================================
function bindStateWatchers() {
  watch('connection.connected', (v) => {
    setDot('dot-system', v ? 'live' : 'err', v ? '已连接' : '离线');
  });
  watch('camera.active', (v) => {
    setDot('dot-cam', v ? 'live' : 'err', v ? '在线' : '离线');
    $('btn-start-cam').disabled = !!v;
    $('btn-stop-cam').disabled = !v;
    $('video-placeholder').style.display = v ? 'none' : 'flex';
    $('cam-meta').textContent = v
      ? `CH-01 · LOCAL · ${$('cam-video')?.videoWidth || 1280}×${$('cam-video')?.videoHeight || 720}`
      : 'CH-01 · 待连接';
  });
  watch('model.ready', (v) => {
    setDot('dot-model', v ? 'live' : 'warn', v ? '就绪' : '加载中');
  });
}

function setDot(id, cls, _label) {
  const el = $(id);
  if (!el) return;
  el.className = 'dot ' + cls;
}

// ============================================================
// 2) 事件流（demo + 真实合并）
// ============================================================
function bindDemoStream() {
  // 监听 demo 数据
  on('demo:kpi', (kpi) => {
    const p = $('kpi-persons');
    if (p && p.textContent !== String(kpi.persons)) p.textContent = kpi.persons;
    const d = $('kpi-dwell');
    if (d && d.textContent !== String(kpi.dwell)) d.textContent = kpi.dwell;
    const i = $('kpi-interest');
    if (i && i.textContent !== String(kpi.interest)) i.textContent = kpi.interest;
    const e = $('kpi-events');
    if (e) e.textContent = kpi.events;
    const trend = $('kpi-persons-trend');
    if (trend) {
      if (kpi.trend > 0) {
        trend.className = 'trend up';
        trend.textContent = `↑ ${kpi.trend}`;
      } else if (kpi.trend < 0) {
        trend.className = 'trend down';
        trend.textContent = `↓ ${Math.abs(kpi.trend)}`;
      } else {
        trend.className = 'trend';
        trend.textContent = '— 0';
      }
    }
  });

  on('demo:event', (evt) => {
    appendEvent({
      ts: evt.ts,
      type: evt.type,
      subtype: stripHtml(evt.text).slice(0, 36),
      text: evt.text,
      confidence: evt.confidence,
    });
  });

  on('demo:advice', (a) => {
    appendAdvice(a);
  });

  // 真实事件（来自 detection: 通道）
  on('detection:gesture', (evt) => appendEvent({ ts: Date.now(), type: 'gesture', subtype: evt.subtype, confidence: evt.confidence }));
  on('detection:face',    (evt) => appendEvent({ ts: Date.now(), type: 'face',    subtype: evt.subtype, confidence: evt.confidence }));
  on('detection:count',   (evt) => appendEvent({ ts: Date.now(), type: 'count',   subtype: `人数 ${evt.persons}`, confidence: 1 }));
  on('detection:interest',(evt) => appendEvent({ ts: Date.now(), type: 'interest',subtype: `注视 ${evt.zone}`, confidence: evt.confidence }));
}

function appendEvent(evt) {
  const list = $('event-list');
  if (!list) return;
  const empty = list.querySelector('.timeline-empty');
  if (empty) empty.remove();

  const li = document.createElement('li');
  const ts = new Date(evt.ts || Date.now()).toLocaleTimeString('zh-CN', { hour12: false });
  const type = evt.type || 'event';
  const text = evt.text || evt.subtype || '';
  const conf = evt.confidence ? ` · ${(evt.confidence * 100).toFixed(0)}%` : '';
  li.innerHTML = `
    <span class="ts">${ts}</span>
    <div class="body">
      <span class="type ${type}">${typeLabel(type)}</span>
      <span class="text">${text}</span>
      <span class="meta">CH-01${conf}</span>
    </div>
  `;
  list.insertBefore(li, list.firstChild);
  while (list.children.length > 50) list.removeChild(list.lastChild);
}

function typeLabel(type) {
  return ({
    gesture: 'GESTURE · 手势',
    face:    'EXPRESSION · 表情',
    behavior:'BEHAVIOR · 行为',
    interest:'INTEREST · 关注',
    count:   'FOOTFALL · 客流',
  })[type] || 'EVENT';
}

function stripHtml(s) {
  return String(s || '').replace(/<[^>]*>/g, '');
}

// ============================================================
// 3) Agent 建议
// ============================================================
function bindAgentAdvice() {
  on('agent:advice', (a) => appendAdvice(a));
}

function initAdviceEmpty() {
  const el = $('agent-advice');
  if (el && !el.children.length) {
    el.innerHTML = `
      <div class="advice-card placeholder">
        <div class="head">
          <span class="pri low">DEMO</span>
          <span class="intent">演示模式 · 等待事件触发</span>
        </div>
        <div class="text">系统启动后，将自动从事件流中提炼建议。<br>在 demo 模式下，约每 3 秒注入一条模拟建议。</div>
      </div>
    `;
  }
}

function appendAdvice(advice) {
  const el = $('agent-advice');
  if (!el) return;
  // 首次插入真实建议时，移除 DEMO 占位卡
  const placeholder = el.querySelector('.advice-card.placeholder');
  if (placeholder) placeholder.remove();

  // 不再删除旧记录——新建议叠加在顶部，旧建议通过滚动查看
  // 上限仅作"防爆内存"用，触发时通过滚动条提示用户回看历史
  const HARD_CAP = 200;
  while (el.children.length >= HARD_CAP) el.removeChild(el.lastChild);

  const card = document.createElement('div');
  const pri = (advice.priority || 'low').toLowerCase();
  card.className = `advice-card priority-${pri}`;
  card.innerHTML = `
    <div class="head">
      <span class="pri ${pri}">${pri.toUpperCase()}</span>
      <span class="intent">${escapeHtml(advice.intent || '建议')}</span>
      <span style="margin-left:auto; color: var(--ink-faint); font-size: 9px;">${new Date(advice.ts || Date.now()).toLocaleTimeString('zh-CN', { hour12: false })}</span>
    </div>
    <div class="text">${advice.text || ''}</div>
    ${advice.actions && advice.actions.length
      ? `<div class="actions">${advice.actions.map((a) => `<span class="tag">${escapeHtml(a)}</span>`).join('')}</div>`
      : ''}
    ${advice.reasoning
      ? `<div class="reasoning">${escapeHtml(advice.reasoning)}</div>`
      : ''}
  `;
  el.insertBefore(card, el.firstChild);
  // 默认滚到顶部（新建议视角）
  el.scrollTop = 0;

  // 计数
  _adviceCount++;
  updateAdviceCount();
}

let _adviceCount = 0;
function updateAdviceCount() {
  const c = $('advice-count');
  if (c) c.textContent = _adviceCount > 99 ? '99+' : _adviceCount;
}

// ============================================================
// 4.6) 聊天模式切换：对话 / 智能洞察 / 阶段报告
// ============================================================
function bindChatModeTabs() {
  const tabs = document.querySelectorAll('.mode-tab');
  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      tabs.forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      const mode = tab.dataset.mode;
      document.querySelectorAll('.chat-mode-body').forEach((body) => {
        const matches = body.dataset.modeBody === mode;
        if (matches) body.removeAttribute('hidden');
        else body.setAttribute('hidden', '');
      });
      if (mode === 'insight') refreshInsightPanel();
    });
  });
}

// ============================================================
// 4.7) 智能洞察面板
// ============================================================
const FLOW_HISTORY = [];   // 客流历史
const LOAD_HISTORY = [];   // 服务压力历史
const HOT_LIST = [
  { name: '包间：商务客人频繁看表', count: 8, pct: 92 },
  { name: '调料台：排队 3+ 未补料', count: 6, pct: 78 },
  { name: '卡座 3 桌：用餐 > 70min', count: 4, pct: 65 },
  { name: '入口等位：8 桌等候', count: 4, pct: 60 },
  { name: '包间：儿童位移告警', count: 2, pct: 38 },
];
const DISH_LIST = [
  { name: '招牌毛肚', count: 11, pct: 95 },
  { name: '鸳鸯锅底', count: 8, pct: 82 },
  { name: '虾滑', count: 6, pct: 70 },
];

function initInsightPanel() {
  // 初始填充两条 sparkline 历史
  for (let i = 0; i < 24; i++) {
    FLOW_HISTORY.push(8 + Math.random() * 6);
    LOAD_HISTORY.push(20 + Math.random() * 18);
  }
  drawSpark('ic-spark-flow', FLOW_HISTORY, '#8B1A1A');
  drawSpark('ic-spark-load', LOAD_HISTORY, '#B45309');
  renderHotList();
  renderDishList();

  // 每 2.5s 更新一次数据
  setInterval(() => {
    FLOW_HISTORY.push(8 + Math.random() * 8);
    FLOW_HISTORY.shift();
    LOAD_HISTORY.push(20 + Math.random() * 22);
    LOAD_HISTORY.shift();
    // HOT 列表微抖
    HOT_LIST.forEach((h) => {
      h.count = Math.max(1, h.count + Math.round((Math.random() - 0.5) * 2));
      h.pct = Math.max(10, Math.min(100, h.pct + Math.round((Math.random() - 0.5) * 4)));
    });
    drawSpark('ic-spark-flow', FLOW_HISTORY, '#8B1A1A');
    drawSpark('ic-spark-load', LOAD_HISTORY, '#B45309');
    if (document.querySelector('.mode-tab.active')?.dataset.mode === 'insight') {
      renderHotList();
      renderDishList();
    }
  }, 2500);
}

function refreshInsightPanel() {
  renderHotList();
  renderDishList();
  drawSpark('ic-spark-flow', FLOW_HISTORY, '#8B1A1A');
  drawSpark('ic-spark-load', LOAD_HISTORY, '#B45309');
}

function drawSpark(canvasId, data, color) {
  const c = document.getElementById(canvasId);
  if (!c) return;
  const dpr = window.devicePixelRatio || 1;
  const rect = c.getBoundingClientRect();
  c.width = Math.max(80, Math.round(rect.width * dpr));
  c.height = Math.round(56 * dpr);
  const ctx = c.getContext('2d');
  ctx.clearRect(0, 0, c.width, c.height);
  if (!data.length) return;

  const w = c.width, h = c.height;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const stepX = w / (data.length - 1);

  // 区域填充
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, color + '55');
  grad.addColorStop(1, color + '00');
  ctx.beginPath();
  data.forEach((v, i) => {
    const x = i * stepX;
    const y = h - ((v - min) / span) * (h - 4 * dpr) - 2 * dpr;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.lineTo(w, h);
  ctx.lineTo(0, h);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // 折线
  ctx.beginPath();
  data.forEach((v, i) => {
    const x = i * stepX;
    const y = h - ((v - min) / span) * (h - 4 * dpr) - 2 * dpr;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5 * dpr;
  ctx.lineJoin = 'round';
  ctx.stroke();

  // 末点高亮
  const lastX = (data.length - 1) * stepX;
  const lastV = data[data.length - 1];
  const lastY = h - ((lastV - min) / span) * (h - 4 * dpr) - 2 * dpr;
  ctx.beginPath();
  ctx.arc(lastX, lastY, 3 * dpr, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
}

function renderHotList() {
  const ul = $('ic-hot');
  if (!ul) return;
  ul.innerHTML = HOT_LIST
    .sort((a, b) => b.pct - a.pct)
    .map(
      (h) =>
        `<li><span>${escapeHtml(h.name)}</span><span class="ic-bar"><span style="width:${h.pct}%"></span></span><span class="ic-num">${h.count}</span></li>`
    )
    .join('');
}
function renderDishList() {
  const ul = $('ic-dish');
  if (!ul) return;
  ul.innerHTML = DISH_LIST
    .map(
      (d) =>
        `<li><span>${escapeHtml(d.name)}</span><span class="ic-bar"><span style="width:${d.pct}%"></span></span><span class="ic-num">${d.count}</span></li>`
    )
    .join('');
}

// ============================================================
// 5) 阶段报告按钮绑定
// ============================================================
function bindReportButton() {
  const btn = document.getElementById('btn-report');
  if (btn) btn.addEventListener('click', generateDemoReport);
}

function generateDemoReport() {
  const area = document.getElementById('report-content');
  if (!area) return;
  area.innerHTML = '<div class="advice-card"><div class="text">⏳ 正在调用 DeepSeek-V4 生成报告...</div></div>';
  setTimeout(() => {
    area.innerHTML = `
      <div class="advice-card priority-low">
        <div class="head"><span class="pri low">REPORT</span><span class="intent">阶段报告 · 最近 10 分钟</span></div>
        <div class="text">
          <strong>§ 1 客流态势</strong><br>
          在店客流 17 人，主通道 6 人、服装区 A 5 人、收银台 4 人。较 1 小时前 +3，整体平稳。<br><br>
          <strong>§ 2 行为洞察</strong><br>
          10 分钟内检测到 12 次手势、9 次表情、3 次长时间驻留、2 次异常行为。微笑率 67%，满意度指标良好。<br><br>
          <strong>§ 3 异常与风险</strong><br>
          1 次疑似走失（试衣间外）+ 1 次货架 C 区长时间低头，已通知店员。<br><br>
          <strong>§ 4 商家建议</strong><br>
          · 主推商品 A（春季新款），关注度第一<br>
          · 收银台建议增开备用通道<br>
          · 美妆区\"试色+讲解\"组合拳持续保持
        </div>
        <div class="reasoning">DeepSeek-V4 · 4 段式 · 187 tokens · 耗时 1.2s</div>
      </div>
    `;
  }, 1500);
}

// ============================================================
// 6) Canvas 叠加（委托 overlay.js）
// ============================================================
export function drawOverlay(canvas, video, payloadOrGesture, faceResults) {
  if (video && typeof video !== 'string' && payloadOrGesture && typeof payloadOrGesture === 'object' && 'gestureResults' in payloadOrGesture) {
    drawOverlayImpl(canvas, video, payloadOrGesture);
    return;
  }
  drawOverlayImpl(canvas, video || canvas.parentElement.querySelector('video'), {
    gestureResults: payloadOrGesture,
    faceResults,
    detectResults: null,
    gestureLabels: [],
    faceLabels: [],
  });
}

// ============================================================
// 工具
// ============================================================
function escapeHtml(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
