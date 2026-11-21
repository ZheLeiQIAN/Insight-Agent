/* ============================================
   Dashboard V4 — 数字过冲 + 菜系条 + sparkline + 热区榜联动
   ============================================ */

import { bus } from './eventBus.js';
import { store } from './store.js';
import { computeHotspotRanking } from './behavior.js';
import { focusMarker } from './amap.js';

let _eventCount = 0;
let _kpiTargets = {};
let _kpiCurrent = {};
let _kpiTimer = null;
let _growthHistory = [];     // 增长率最近 30 个
let _sparkCanvas = null;
let _sparkCtx = null;

const CUISINE_HEX = {
  '火锅': '#B81E1E', '烧烤': '#D27814', '川菜': '#C82828',
  '粤菜': '#1E8250', '日料': '#1464A0', '韩餐': '#A03C78',
  '西餐': '#502864', '小吃': '#C8A014', '酒吧': '#643CB4',
  '本帮菜': '#A53A3A', '异国料理': '#6450A0', '综合餐饮': '#1B2A4E',
};

export function initDashboard() {
  bindEvents();
  bindTabs();
  bindControls();
  bindReport();
  initKpiCharts();
  startKpiAnimation();
}

function startKpiAnimation() {
  _kpiTimer = setInterval(() => {
    for (const [id, target] of Object.entries(_kpiTargets)) {
      if (_kpiCurrent[id] == null) _kpiCurrent[id] = target;
      // 过冲缓动：先冲过 target 再回拉
      const cur = _kpiCurrent[id];
      const diff = target - cur;
      _kpiCurrent[id] = cur + diff * 0.18;
      const el = document.getElementById(id);
      if (el && Math.abs(target - _kpiCurrent[id]) > 0.6) {
        el.textContent = Math.round(_kpiCurrent[id]);
      } else if (el) {
        if (Math.round(_kpiCurrent[id]) !== Math.round(cur)) {
          // 到达时触发过冲动画
          el.textContent = Math.round(target);
          el.classList.remove('bounce');
          void el.offsetWidth;
          el.classList.add('bounce');
        } else {
          el.textContent = Math.round(target);
        }
        _kpiCurrent[id] = target;
      }
    }
  }, 50);
}

function animateKpi(id, value) {
  const prev = _kpiCurrent[id];
  _kpiTargets[id] = value;
  if (prev == null) _kpiCurrent[id] = value;
}

function bindEvents() {
  const list = document.getElementById('eventList');
  const countEl = document.getElementById('eventCountLabel');

  bus.on('event:new', (evt) => {
    _eventCount++;
    if (countEl) countEl.textContent = `今日 ${_eventCount} 件`;
    if (!list) return;
    pushEventRow(list, evt);
  });

  // 冷启动：先注入 7 条历史事件，避免页面空白
  if (list && list.children.length === 0) {
    seedInitialEvents(list, 7);
  }

  // 热区榜（V4 卡片化）
  const hsList = document.getElementById('hotspotList');
  const _CUISINE_ICON = { '火锅':'🍲', '烧烤':'🍢', '川菜':'🌶️', '粤菜':'🥟', '日料':'🍣', '韩餐':'🥩', '西餐':'🍝', '小吃':'🥟', '酒吧':'🍷', '本帮菜':'🥘', '异国料理':'🌍', '综合餐饮':'🍴', '咖啡':'☕', '麻辣':'🌶️', '小龙虾':'🦞', '烤鸭':'🦆', '京菜':'🥘', '粤菜/海鲜':'🦞', '潮汕牛肉':'🥩', '快餐':'🍱', '海鲜':'🦞', '甜品':'🍰', '简餐':'🍱', '轻食':'🥗', '夜市':'🍢', '天津菜':'🥟', '高端餐饮':'🍷', '商务餐饮':'💼', '高端商务餐':'💼' };
  bus.on('hotspots:updated', (hs) => {
    if (!hsList) return;
    const ranked = computeHotspotRanking(hs);
    const maxV = Math.max(...ranked.map(h => h.value), 1);
    _latestHotspots = ranked;   // V4.5: 缓存给 KPI 环形图用
    hsList.innerHTML = ranked.map((h, i) => {
      const rc = i < 3 ? `top${i + 1}` : '';
      const ch = h.change > 0 ? 'up' : 'down';
      const sign = h.change > 0 ? '+' : '';
      const barW = Math.max(8, Math.min(100, (h.value / maxV) * 100));
      const ck = _cuisineKey(h.cuisine);
      const color = CUISINE_HEX[ck] || '#6B7280';
      const icon = _CUISINE_ICON[ck] || '🍽️';
      const occupancy = Math.min(98, 60 + Math.round((h.value || 0) / 1.4));
      const tier = h.value >= 50 ? 'high' : h.value >= 20 ? 'mid' : 'low';
      const crown = i === 0 ? '<span class="crown">👑</span>' : '';
      // V4.5: 派生 9 项洞察
      const ins = computeHotspotInsights(h);
      const queueTier = ins.queueMin >= 25 ? 'high' : '';
      const typeColor = _TYPE_COLORS[ins.type] || '#6B7280';
      const typeLabel = _TYPE_LABEL[ins.type] || ins.type;
      const peakLabel = _PEAK_LABEL[ins.peak] || ins.peak;
      const sparkPath = sparklinePath(ins.sparkData, 60, 14);
      return `<div class="hotspot-card ${i === 0 ? 'first' : ''}" data-name="${h.name}" data-cuisine="${h.cuisine}">
        <div class="hs-side" style="background:${color};"></div>

        <div class="hs-rank ${rc}">${h.rank}</div>
        <div class="hs-icon" style="background:${color}20;color:${color};">${icon}</div>
        <div class="hs-body">
          <div class="hs-row1">
            <span class="hs-name" title="${h.name} · ${h.cuisine}">${h.name}</span>
            ${crown}
            <span class="hs-tag" style="color:${color};background:${color}1A;">${h.cuisine}</span>
          </div>
          <div class="hs-row2">
            <div class="hs-bar"><div class="hs-bar-fill" style="width:${barW}%;background:linear-gradient(90deg, ${color}55, ${color});"></div></div>
            <span class="hs-occ" data-tier="${tier}" title="上座率">${occupancy}%</span>
          </div>
          <div class="hs-row3">
            <span class="hs-count"><b>${Math.round(h.value)}</b><i>人/分</i></span>
            <span class="hs-change ${ch}">${sign}${h.change}%</span>
            <span class="hs-dot ${tier}"></span>
          </div>
          <div class="hs-row4" title="客单价 / 翻台率 / 排队等位">
            <div class="hs-extra spend">
              <span class="hs-extra-label">客单价</span>
              <span class="hs-extra-val">¥${ins.avgSpend}<i class="unit">/人</i></span>
            </div>
            <div class="hs-extra turnover">
              <span class="hs-extra-label">翻台率</span>
              <span class="hs-extra-val">${ins.turnover}<i class="unit">次/桌</i></span>
            </div>
            <div class="hs-extra queue ${queueTier}">
              <span class="hs-extra-label">排队</span>
              <span class="hs-extra-val">${ins.queueMin}<i class="unit">分</i></span>
            </div>
          </div>
          <div class="hs-row5" title="商圈类型 / 高峰时段 / 距最近来源区 / 6 时段趋势">
            <span class="hs-type-pill" style="--type-color:${typeColor};color:${typeColor};background:${typeColor}10;">${typeLabel}</span>
            <span class="hs-peak-tag ${ins.peak}">${peakLabel}</span>
            <span class="hs-dist">距 ${ins.distKm} km</span>
            <svg class="hs-sparkline" viewBox="0 0 60 14" preserveAspectRatio="none" aria-label="6 时段趋势">
              <path d="${sparkPath}" stroke="${color}" />
            </svg>
          </div>
        </div>
      </div>`;
    }).join('') || '<div class="empty-tip">暂无热区数据</div>';

    // 联动：点击 → focusMarker
    hsList.querySelectorAll('.hotspot-card').forEach(item => {
      item.addEventListener('click', () => {
        const name = item.getAttribute('data-name');
        focusMarker(name);
        // 视觉反馈
        hsList.querySelectorAll('.hotspot-card').forEach(c => c.classList.remove('active'));
        item.classList.add('active');
        setTimeout(() => item.classList.remove('active'), 1800);
      });
    });
  });

  // Agent 建议
  const advList = document.getElementById('adviceList');
  
  // 冷启动：先注入 2 条历史建议（带实时推送指示器）
  if (advList && advList.children.length === 0) {
    // 加一个实时指示器
    const liveBar = document.createElement('div');
    liveBar.className = 'advice-live-bar';
    liveBar.innerHTML = '<span class="dot live"></span> 实时推送中 <span class="advice-live-ts" id="adviceLiveTs">—</span>';
    advList.appendChild(liveBar);
    seedInitialAdvices(advList);
  }

  // 定期流入新建议（每 8-15s 一条）
  let _adviceTimer = null;
  const ADVICE_POOL = [
    { priority: 'high', title: '等位溢出预警', desc: '滨江道商圈火锅店等位超 30 分钟，较 1h 前 +23%。建议启动分流预案：开放 2F 备用区 + 推送等位优惠券。' },
    { priority: 'medium', title: '城西供给缺口扩大', desc: '中北镇餐饮需求指数 +18%，品牌火锅店入驻率为 0。建议关注 8 月新开商业体招商窗口期。' },
    { priority: 'low', title: '夜经济窗口期', desc: '22:00 后搜索指数 +31%，周边营业店铺仅 14%。建议延长营业时间 + 深夜限定套餐。' },
    { priority: 'medium', title: '暴雨预警应对', desc: '未来 3h 降雨概率 70%，预计堂食客流下降 35%。建议提前增加外卖运力 + 推出雨天专属折扣。' },
    { priority: 'high', title: '热门菜系库存告急', desc: '招牌毛肚当日销量已达 82%，库存仅剩 28 份。建议：① 紧急补货 ② 前台限时推荐替代品。' },
    { priority: 'low', title: '会员日活动建议', desc: '周三会员日转化率 7.2% > 平日 4.1%。建议本周末加推"双倍积分 + 满 200 减 30"活动。' },
  ];
  let _advicePoolIdx = 0;

  function scheduleNextAdvice() {
    _adviceTimer = setTimeout(() => {
      const a = ADVICE_POOL[_advicePoolIdx % ADVICE_POOL.length];
      _advicePoolIdx++;
      bus.emit('advice:new', a);
      // 更新时间戳
      const ts = document.getElementById('adviceLiveTs');
      if (ts) ts.textContent = new Date().toLocaleTimeString('zh-CN', { hour12: false });
      scheduleNextAdvice();
    }, 8000 + Math.random() * 7000);
  }
  scheduleNextAdvice();

  bus.on('advice:new', (a) => {
    if (!advList) return;
    const pm = { high: '高优先级', medium: '中优先级', low: '低优先级' };
    const colorMap = { high: 'var(--red)', medium: 'var(--amber)', low: 'var(--green)' };
    const el = document.createElement('div');
    el.className = 'advice-item';
    el.style.opacity = '0';
    el.style.transform = 'translateY(-6px)';
    el.innerHTML = `<div class="advice-meta ${a.priority}" style="display:flex; align-items:center; gap:8px;">
      <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:${colorMap[a.priority]};"></span>${pm[a.priority]}
    </div>
      <div class="advice-title">${a.title}</div>
      <div class="advice-desc">${a.desc}</div>`;
    advList.insertBefore(el, advList.firstChild);

    requestAnimationFrame(() => {
      el.style.transition = 'all 0.4s cubic-bezier(0.16, 1, 0.3, 1)';
      el.style.opacity = '1';
      el.style.transform = 'translateY(0)';
    });

    while (advList.children.length > 8) advList.removeChild(advList.lastChild);
  });

  // KPI 数字动画绑定
  bus.on('hotspots:updated', () => {
    const d = store.get('dining');
    animateKpi('kpiDiners', d.diners);
    animateKpi('kpiHotspots', d.hotspotCount);
    const gel = document.getElementById('kpiGrowth');
    const v = d.growthRate;
    if (gel) {
      gel.textContent = (v >= 0 ? '+' : '') + v + '%';
      gel.className = 'kpi-trend ' + (v >= 0 ? 'up' : 'down');
    }
    // sparkline
    pushGrowth(v);
    drawSparkline();
    // V4.5: 实时客流柱状图 + 热区 4 类型 4 段堆叠条
    pushDiners(d.diners);
    drawDinersBars();
    drawHotspotStack(_latestHotspots);
  });

  // 菜系条
  bus.on('cuisine:updated', (share) => {
    renderCuisineBars(share);
    const top = Object.entries(share).sort((a, b) => b[1] - a[1])[0];
    if (top) {
      const el = document.getElementById('kpiCuisine');
      if (el) el.textContent = top[0];
    }
  });

  // 流向矩阵
  bus.on('flows:updated', flows => { _latestMatrixFlows = flows; renderFlowMatrix(); });
  bus.on('hotspots:updated', () => { if (_latestMatrixFlows.length) renderFlowMatrix(); });
}

function renderCuisineBars(share) {
  const host = document.getElementById('cuisineBars');
  if (!host) return;
  const entries = Object.entries(share)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);
  host.innerHTML = entries.map(([k, v]) => {
    const color = CUISINE_HEX[k] || '#6B7280';
    return `<div class="cuisine-bar" title="${k}">
      <span class="cb-name">${k}</span>
      <div class="cb-track"><div class="cb-fill" style="width:${Math.min(100, v)}%; background:${color};"></div></div>
      <span class="cb-pct">${v}%</span>
    </div>`;
  }).join('');
}

// ===== 事件流：注入新行 / 冷启动种子 =====
function pushEventRow(list, evt) {
  const el = document.createElement('div');
  el.className = 'event-item';
  el.style.opacity = '0';
  el.style.transform = 'translateX(-8px)';
  el.innerHTML = `<span class="event-icon">${evt.icon}</span>
    <span class="event-time">${new Date(evt.time).toLocaleTimeString('zh-CN', {hour:'2-digit',minute:'2-digit',second:'2-digit'})}</span>
    <span class="event-desc">${evt.desc}</span>
    <span class="event-badge ${evt.severity}">${evt.label}</span>`;
  list.insertBefore(el, list.firstChild);
  requestAnimationFrame(() => {
    el.style.transition = 'all 0.35s cubic-bezier(0.16, 1, 0.3, 1)';
    el.style.opacity = '1';
    el.style.transform = 'translateX(0)';
  });
  while (list.children.length > 40) list.removeChild(list.lastChild);
}

const SEED_EVENTS = [
  { icon: '🔥', severity: 'high',   label: '高峰预警', desc: '滨江道商圈火锅客流升至 312 人/分，等位 25min' },
  { icon: '📈', severity: 'medium', label: '菜系激增', desc: '小吃类餐饮搜索量 +28%，城西中北镇出现新热区' },
  { icon: '🍢', severity: 'low',    label: '流向转移', desc: '白领客群从奥城转向五大道，影响烧烤 12%' },
  { icon: '🌃', severity: 'medium', label: '夜宵活跃', desc: '22:00 后夜市档口客流 +35%，日料烤串热销' },
  { icon: '⚠️', severity: 'high',   label: '供给不足', desc: '海河教育园学生群体 2万+ 无品牌火锅店，3km 空白' },
  { icon: '🍲', severity: 'low',    label: '翻台加速', desc: '奥城川菜午市翻台 2.3 次，高于昨日 18%' },
  { icon: '💧', severity: 'low',    label: '外卖波动', desc: '烧烤外卖单量回落 6%，午后茶饮 +15% 平衡' },
];

function seedInitialEvents(list, n) {
  const now = Date.now();
  const events = [];
  for (let i = n - 1; i >= 0; i--) {
    const t = SEED_EVENTS[i % SEED_EVENTS.length];
    events.push({ ...t, time: now - i * 38 * 1000 });   // 38s 一条，倒序
  }
  // 倒序插入（最新的在顶部）
  events.forEach(evt => pushEventRow(list, evt));
  _eventCount = n;
  const countEl = document.getElementById('eventCountLabel');
  if (countEl) countEl.textContent = `今日 ${_eventCount} 件`;
}

// ===== 建议：冷启动种子（5 条 · 与热门区域 TOP 5 对齐） =====
const SEED_ADVICES = [
  {
    priority: 'high',
    title: '启动高峰分流预案',
    desc: '滨江道商圈火锅客流持续上升，等位超 25 分钟。建议：① 增加 1-2 个临时等位区 ② 备菜/锅底提前 1.5h 启动 ③ 拼桌优先大桌。',
  },
  {
    priority: 'high',
    title: '暴雨天气应对预案',
    desc: '未来 3h 降雨概率 75%，预计堂食客流下降 35%。建议：① 提前增加外卖运力 ② 推出雨天专属折扣 ③ 抖音直播引流。',
  },
  {
    priority: 'medium',
    title: '城西板块供给空白',
    desc: '中北镇—张家窝常住人口 8 万，无品牌火锅店。建议：① 选址社区底商 ② 一人食 / 家庭客双 SKU ③ 首店补贴拉新。',
  },
  {
    priority: 'medium',
    title: '差异化品类机会',
    desc: '全市轻食沙拉搜索量 +35%，但供给仅占 6%。建议 ① 选址写字楼/瑜伽馆周边 ② 主打"减脂火锅 + 沙拉吧"组合 ③ 月卡订阅 199 元拉复购。',
  },
  {
    priority: 'medium',
    title: '热门菜系库存告急',
    desc: '招牌毛肚当日销量已达 82%，库存仅剩 28 份。建议：① 紧急补货 ② 前台限时推荐替代品 ③ 调整菜单推荐排序。',
  },
  {
    priority: 'low',
    title: '夜经济延时收益',
    desc: '22:00 后营业店铺仅 12%，而夜间餐饮搜索 +22%。建议 ① 核心商圈延长营业至 02:00 ② 推深夜限定"小龙虾+精酿"套餐 ③ 网红直播引流。',
  },
  {
    priority: 'low',
    title: '外卖产品线拓展',
    desc: '火锅外卖渗透率仅 5%（受配送限制），但"火锅冒菜化"+"单人份酸菜鱼"已成破局点。建议 ① 上线 38-58 元单人套餐 ② 入驻美团/饿了么 ③ 预制菜 B 端供货。',
  },
  {
    priority: 'low',
    title: '会员日活动建议',
    desc: '周三会员日转化率 7.2% > 平日 4.1%。建议本周末加推"双倍积分 + 满 200 减 30"活动，配合抖音探店推送。',
  },
];

function pushAdviceRow(list, a) {
  const pm = { high: '高优先级', medium: '中优先级', low: '低优先级' };
  const colorMap = { high: 'var(--red)', medium: 'var(--amber)', low: 'var(--green)' };
  const el = document.createElement('div');
  el.className = 'advice-item';
  el.style.opacity = '0';
  el.style.transform = 'translateY(-6px)';
  el.innerHTML = `<div class="advice-meta ${a.priority}" style="display:flex; align-items:center; gap:8px;">
    <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:${colorMap[a.priority]};"></span>${pm[a.priority]}
  </div>
    <div class="advice-title">${a.title}</div>
    <div class="advice-desc">${a.desc}</div>`;
  list.insertBefore(el, list.firstChild);
  requestAnimationFrame(() => {
    el.style.transition = 'all 0.4s cubic-bezier(0.16, 1, 0.3, 1)';
    el.style.opacity = '1';
    el.style.transform = 'translateY(0)';
  });
}

function seedInitialAdvices(list) {
  // 倒序：最不紧急在前，最紧急在后（视觉上紧急的在最上面）
  [...SEED_ADVICES].reverse().forEach(a => pushAdviceRow(list, a));
}

/* ---- sparkline ---- */
function initSparkline() {
  _sparkCanvas = document.getElementById('growthSparkline');
  if (!_sparkCanvas) return;
  _sparkCtx = _sparkCanvas.getContext('2d');
  resizeSpark();
  window.addEventListener('resize', resizeSpark);
}
function resizeSpark() {
  if (!_sparkCanvas) return;
  const w = _sparkCanvas.clientWidth || 200;
  _sparkCanvas.width = w * 2;     // retina
  _sparkCanvas.height = 64;
  _sparkCanvas.style.height = '32px';
  drawSparkline();
}
function pushGrowth(v) {
  _growthHistory.push(v);
  if (_growthHistory.length > 30) _growthHistory.shift();
}
function drawSparkline() {
  if (!_sparkCtx || !_sparkCanvas) return;
  const w = _sparkCanvas.width, h = _sparkCanvas.height;
  _sparkCtx.clearRect(0, 0, w, h);
  if (_growthHistory.length < 2) return;
  const min = Math.min(..._growthHistory, -10);
  const max = Math.max(..._growthHistory, 10);
  const range = (max - min) || 1;
  const stepX = w / Math.max(1, _growthHistory.length - 1);
  const padY = 8;

  // 零线
  const zeroY = h - padY - ((0 - min) / range) * (h - padY * 2);
  _sparkCtx.strokeStyle = 'rgba(27, 42, 78, 0.12)';
  _sparkCtx.lineWidth = 1;
  _sparkCtx.beginPath();
  _sparkCtx.moveTo(0, zeroY); _sparkCtx.lineTo(w, zeroY); _sparkCtx.stroke();

  // 折线
  _sparkCtx.strokeStyle = '#8B1A1A';
  _sparkCtx.lineWidth = 1.6;
  _sparkCtx.beginPath();
  _growthHistory.forEach((v, i) => {
    const x = i * stepX;
    const y = h - padY - ((v - min) / range) * (h - padY * 2);
    if (i === 0) _sparkCtx.moveTo(x, y); else _sparkCtx.lineTo(x, y);
  });
  _sparkCtx.stroke();

  // 末端圆点
  const last = _growthHistory[_growthHistory.length - 1];
  const lx = (_growthHistory.length - 1) * stepX;
  const ly = h - padY - ((last - min) / range) * (h - padY * 2);
  _sparkCtx.beginPath();
  _sparkCtx.arc(lx, ly, 5, 0, Math.PI * 2);
  _sparkCtx.fillStyle = '#8B1A1A';
  _sparkCtx.fill();
  _sparkCtx.beginPath();
  _sparkCtx.arc(lx, ly, 2, 0, Math.PI * 2);
  _sparkCtx.fillStyle = '#FAFAF7';
  _sparkCtx.fill();
}

/* V4.5 增强 — 实时客流柱状图 */
let _dinersHistory = [];
let _dinersCanvas = null;
let _dinersCtx = null;
function initDinersBars() {
  _dinersCanvas = document.getElementById('dinersBars');
  if (!_dinersCanvas) return;
  _dinersCtx = _dinersCanvas.getContext('2d');
  resizeDiners();
  window.addEventListener('resize', resizeDiners);
}
function resizeDiners() {
  if (!_dinersCanvas) return;
  const w = _dinersCanvas.clientWidth || 200;
  _dinersCanvas.width = w * 2;
  _dinersCanvas.height = 44;
  _dinersCanvas.style.height = '22px';
  drawDinersBars();
}
function pushDiners(v) {
  // V4.5.1: 启动时先回填 24 个伪随机历史，让首屏就有可视柱子
  if (_dinersHistory.length === 0) {
    const base = v || 2400;
    for (let i = 0; i < 24; i++) {
      const drift = Math.sin(i * 0.55) * 0.18;
      const noise = (Math.random() - 0.5) * 0.22;
      const trend = 0.85 + (i / 24) * 0.3;     // 微微上行趋势
      _dinersHistory.push(Math.round(base * (trend + drift + noise)));
    }
    return;
  }
  _dinersHistory.push(v);
  if (_dinersHistory.length > 24) _dinersHistory.shift();
}
function drawDinersBars() {
  if (!_dinersCtx || !_dinersCanvas) return;
  const w = _dinersCanvas.width, h = _dinersCanvas.height;
  _dinersCtx.clearRect(0, 0, w, h);
  if (_dinersHistory.length < 2) return;
  const max = Math.max(..._dinersHistory, 1);
  const min = Math.min(..._dinersHistory, 0);
  const range = (max - min) || 1;
  const n = _dinersHistory.length;
  const slot = w / 24;
  const barW = slot * 0.7;
  const padY = 4;

  // 基线
  _dinersCtx.strokeStyle = 'rgba(27, 42, 78, 0.10)';
  _dinersCtx.lineWidth = 1;
  _dinersCtx.beginPath();
  _dinersCtx.moveTo(0, h - padY); _dinersCtx.lineTo(w, h - padY); _dinersCtx.stroke();

  // 24 个槽，最右为最新
  for (let i = 0; i < 24; i++) {
    const slotIdx = i - (24 - n);
    if (slotIdx < 0) continue;
    const v = _dinersHistory[slotIdx];
    const x = i * slot + (slot - barW) / 2;
    const barH = Math.max(2, ((v - min) / range) * (h - padY * 2));
    const y = h - padY - barH;
    const isLast = slotIdx === n - 1;
    _dinersCtx.fillStyle = isLast ? '#8B1A1A' : 'rgba(184, 30, 30, 0.42)';
    _dinersCtx.beginPath();
    // 圆角矩形
    const r = Math.min(2, barW / 2, barH);
    _dinersCtx.moveTo(x + r, y);
    _dinersCtx.lineTo(x + barW - r, y);
    _dinersCtx.quadraticCurveTo(x + barW, y, x + barW, y + r);
    _dinersCtx.lineTo(x + barW, h - padY);
    _dinersCtx.lineTo(x, h - padY);
    _dinersCtx.lineTo(x, y + r);
    _dinersCtx.quadraticCurveTo(x, y, x + r, y);
    _dinersCtx.closePath();
    _dinersCtx.fill();
  }
}

/* V4.5.1 增强 — 热区 4 商圈类型 4 段堆叠条（横排占比） */
const _HS_TYPE_COLOR = {
  composite: '#8B1A1A',   // 综合型 — 酒红
  residential: '#4F7942',  // 居住型 — 墨绿
  office: '#1B4A6B',      // 办公型 — 藏青
  scenic: '#B47914',       // 景区型 — 古金
};
const _HS_TYPE_LABEL = {
  composite: '综合', residential: '居住', office: '办公', scenic: '景区',
};
function drawHotspotStack(hotspots) {
  const bar = document.getElementById('hsTypeBar');
  const legend = document.getElementById('hsTypeLegend');
  if (!bar || !legend) return;
  // 统计 4 个 type
  const counts = { composite: 0, residential: 0, office: 0, scenic: 0 };
  (hotspots || []).forEach(h => {
    const ins = computeHotspotInsights(h);
    if (counts[ins.type] !== undefined) counts[ins.type]++;
  });
  const sum = counts.composite + counts.residential + counts.office + counts.scenic;
  // 4 段堆叠条
  const order = ['composite', 'residential', 'office', 'scenic'];
  bar.innerHTML = order.map(k => {
    const v = counts[k];
    if (v === 0) return `<div class="seg empty" style="background:${_HS_TYPE_COLOR[k]};"></div>`;
    const pct = sum > 0 ? Math.round((v / sum) * 100) : 0;
    return `<div class="seg" data-type="${k}" data-count="${v}"
                 style="background:${_HS_TYPE_COLOR[k]};"
                 title="${_HS_TYPE_LABEL[k]}型热区 ${v} 个（占 ${pct}%）">
      <span class="v">${v}<i style="opacity:.65;font-style:normal;font-size:8px;"> 个</i></span>
    </div>`;
  }).join('');
  // 图例
  legend.innerHTML = order.map(k => {
    const v = counts[k];
    const pct = sum > 0 ? Math.round((v / sum) * 100) : 0;
    return `<span class="li"><span class="dot" style="background:${_HS_TYPE_COLOR[k]};"></span>${_HS_TYPE_LABEL[k]} ${v} (${pct}%)</span>`;
  }).join('');
}

function initKpiCharts() {
  initSparkline();
  initDinersBars();
}

function bindTabs() {
  document.querySelectorAll('.console-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.console-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      document.querySelectorAll('.console-panel').forEach(p => p.classList.add('hidden'));
      const id = 'panel' + tab.dataset.tab[0].toUpperCase() + tab.dataset.tab.slice(1);
      document.getElementById(id)?.classList.remove('hidden');
    });
  });
}

let _matrixFlows = [];
let _latestMatrixFlows = [];
let _matrixFilter = { srcType: 'all', cuisine: 'all' };  // V4 过滤
let _matrixLastHotNames = [];
let _latestHotspots = [];   // V4.5: 给 KPI 环形图用的最新热点数据

/* V4.5: 热门区域洞察（模块顶层，让 KPI handler 的 drawHotspotDonut 也能访问） */
const _cuisineKey = (c) => (c || '').split('/')[0];
const _TYPE_COLORS = { composite: '#8B1A1A', residential: '#4F7942', office: '#1B4A6B', scenic: '#B47914' };
const _TYPE_LABEL  = { composite: '综合型', residential: '居住型', office: '办公型', scenic: '景区型' };
const _PEAK_LABEL  = { lunch: '午高峰', dinner: '晚高峰', night: '夜高峰' };
const _hashCode = (s) => { let h = 0; for (let i = 0; i < s.length; i++) { h = ((h << 5) - h) + s.charCodeAt(i); h |= 0; } return Math.abs(h); };
function computeHotspotInsights(h) {
  if (h.avgSpend != null && h.turnover != null && h.queueMin != null && h.peak && h.type && h.sparkData) {
    return {
      avgSpend: h.avgSpend, turnover: h.turnover, queueMin: h.queueMin,
      peak: h.peak, type: h.type,
      distKm: h.nearestSourceKm != null ? h.nearestSourceKm : 0,
      sparkData: h.sparkData,
    };
  }
  const seed = _hashCode(h.name || 'h');
  const rnd = (i) => ((seed * (i + 7)) % 100) / 100;
  const cuisineAvgSpend = { '火锅':85, '烧烤':75, '川菜':65, '粤菜':120, '日料':180, '韩餐':95, '西餐':150, '小吃':25, '酒吧':200, '本帮菜':90, '异国料理':140, '综合餐饮':70, '咖啡':35, '麻辣':60, '小龙虾':120, '烤鸭':160, '京菜':110, '快餐':30, '海鲜':180, '甜品':45, '简餐':35, '轻食':50, '夜市':20, '天津菜':55, '高端餐饮':260, '商务餐饮':180, '高端商务餐':280 };
  const ck = _cuisineKey(h.cuisine);
  const baseSpend = cuisineAvgSpend[ck] || 80;
  const value = h.value || 30;
  return {
    avgSpend: Math.round(baseSpend * (0.85 + rnd(1) * 0.4)),
    turnover: +(1.8 + (value / 80) + rnd(2) * 1.5).toFixed(1),
    queueMin: Math.round(value / 2.2 + rnd(3) * 12),
    peak: value >= 60 ? 'dinner' : (value >= 35 ? 'lunch' : 'night'),
    type: h.type || ['composite', 'residential', 'office', 'scenic'][seed % 4],
    distKm: +(0.6 + rnd(4) * 4.5).toFixed(1),
    sparkData: Array.from({ length: 6 }, (_, i) => +(0.5 + Math.sin((seed + i) * 0.7) * 0.3 + rnd(i + 10) * 0.5).toFixed(2)),
  };
}
function sparklinePath(data, w, h) {
  if (!data || data.length === 0) return '';
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const stepX = w / (data.length - 1);
  return data.map((v, i) => {
    const x = (i * stepX).toFixed(1);
    const y = (h - ((v - min) / range) * h).toFixed(1);
    return `${i === 0 ? 'M' : 'L'}${x},${y}`;
  }).join(' ');
}

function renderFlowMatrix() {
  if (_latestMatrixFlows === undefined) { _latestMatrixFlows = []; }
  _matrixFlows = _latestMatrixFlows;
  const host = document.getElementById('flowMatrix');
  if (!host) return;

  // 应用过滤
  const flows = _matrixFlows.filter(f => {
    if (_matrixFilter.srcType !== 'all' && f.from?.type !== _matrixFilter.srcType) return false;
    if (_matrixFilter.cuisine !== 'all') {
      const ck = (f.to?.cuisine || '').split('/')[0];
      if (ck !== _matrixFilter.cuisine) return false;
    }
    return true;
  });

  if (!flows.length) {
    host.innerHTML = '<div class="empty-tip">当前过滤下暂无流向数据</div>';
    return;
  }

  // 提取独特来源区 / 热区 / 菜系
  const srcEntries = new Map();
  flows.forEach(f => { if (f.from?.name) srcEntries.set(f.from.name, f.from); });
  const hotEntries = new Map();
  flows.forEach(f => { if (f.to?.name) hotEntries.set(f.to.name, f.to); });
  const cuisineSet = new Set();
  flows.forEach(f => { if (f.to?.cuisine) cuisineSet.add(f.to.cuisine.split('/')[0]); });

  const srcArr = [...srcEntries.values()];
  // V4.5 优化：固定显示 5 个热区（与热门区域 TOP 5 对齐），按 value 降序
  const hotArr = [...hotEntries.values()]
    .sort((a, b) => (b.value || 0) - (a.value || 0))
    .slice(0, 5);
  if (!srcArr.length || !hotArr.length) {
    host.innerHTML = '<div class="empty-tip">流向数据不完整</div>';
    return;
  }
  _matrixLastHotNames = hotArr.map(h => h.name);

  // 矩阵数据
  const matrix = {};
  srcArr.forEach(s => { matrix[s.name] = {}; hotArr.forEach(h => { matrix[s.name][h.name] = 0; }); });
  flows.forEach(f => {
    const s = f.from?.name, h = f.to?.name;
    if (matrix[s] && matrix[s][h] !== undefined) matrix[s][h] += f.volume || 0;
  });
  const maxCell = Math.max(...flows.map(f => f.volume || 0), 1);

  // 来源区类型色
  const typeColors = { residential: '#4F7942', office: '#1B4A6B', university: '#8B1A1A', transit: '#B8860B' };

  // 菜系色 (按热区)
  const cuisineKey = (c) => (c || '').split('/')[0];
  const hotColor = (c) => CUISINE_HEX[cuisineKey(c)] || '#1B2A4E';

  // 渲染过滤 chips
  const allCuisines = [...new Set([..._matrixFlows].map(f => cuisineKey(f.to?.cuisine)).filter(Boolean))];
  const srcTypes = [
    { v: 'all', l: '全部来源' },
    { v: 'residential', l: '居住区' },
    { v: 'office', l: '办公区' },
    { v: 'university', l: '大学城' },
    { v: 'transit', l: '交通枢纽' },
  ];

  // 概览
  const totalVol = flows.reduce((s, f) => s + (f.volume || 0), 0);
  const topPair = flows.reduce((m, f) => (f.volume || 0) > (m.volume || 0) ? f : m, {});

  // 渲染
  let html = `<div class="matrix-toolbar">
    <div class="matrix-chips">
      ${srcTypes.map(t => `<button class="mchip ${_matrixFilter.srcType === t.v ? 'active' : ''}" data-type="${t.v}">${t.l}</button>`).join('')}
    </div>
    <div class="matrix-chips">
      <button class="mchip ${_matrixFilter.cuisine === 'all' ? 'active' : ''}" data-cuisine="all">全部菜系</button>
      ${allCuisines.map(c => `<button class="mchip ${_matrixFilter.cuisine === c ? 'active' : ''}" data-cuisine="${c}" style="--cui:${CUISINE_HEX[c] || '#1B2A4E'};">${c}</button>`).join('')}
    </div>
  </div>
  <div class="matrix-summary-modern">
    <div class="ms-card">
      <div class="ms-icon">📊</div>
      <div class="ms-body">
        <div class="ms-val">${Math.round(totalVol).toLocaleString()}</div>
        <div class="ms-label">总流量（人/分）</div>
      </div>
    </div>
    <div class="ms-card">
      <div class="ms-icon">🔀</div>
      <div class="ms-body">
        <div class="ms-val">${flows.length}</div>
        <div class="ms-label">活跃流向</div>
      </div>
    </div>
    <div class="ms-card">
      <div class="ms-icon">🏆</div>
      <div class="ms-body">
        <div class="ms-val" style="font-size:12px;font-family:var(--serif);">${topPair.from?.name || '-'}→${topPair.to?.name || '-'}</div>
        <div class="ms-label">主路径</div>
      </div>
    </div>
  </div>
  <div class="matrix-table-wrap"><table class="matrix-table"><thead><tr>
    <th class="th-src">来源 \\\\ 热区</th>
    ${hotArr.map(h => `<th class="th-hot" style="--cui:${hotColor(h.cuisine)};">
      <span class="th-name">${h.name.slice(0, 4)}</span>
      <span class="th-cuisine">${h.cuisine || ''}</span>
    </th>`).join('')}
    <th class="th-total">合计</th>
  </tr></thead><tbody>`;

  srcArr.forEach(s => {
    const typeColor = typeColors[s.type] || '#6B7280';
    const total = hotArr.reduce((sum, h) => sum + (matrix[s.name][h.name] || 0), 0);
    html += `<tr>
      <td class="td-src">
        <span class="src-dot" style="background:${typeColor};"></span>
        <span class="src-name">${s.name}</span>
        <span class="src-type">${({residential:'居住', office:'办公', university:'大学', transit:'枢纽'})[s.type] || s.type}</span>
      </td>`;
    hotArr.forEach(h => {
      const v = matrix[s.name][h.name] || 0;
      const a = Math.min(1, v / Math.max(60, maxCell));
      const cColor = hotColor(h.cuisine);
      const rgb = hexToRgb(cColor);
      const tip = `${s.name} → ${h.name}\\n${h.cuisine || ''}\\n流量 ${Math.round(v)} 人/分`;
      html += `<td class="td-val" style="background:rgba(${rgb.join(',')}, ${0.06 + a * 0.5});" title="${tip}">
        <div class="cell-bar-wrap"><div class="cell-bar" style="width:${a * 100}%;background:${cColor};"></div></div>
        <span class="v-num">${Math.round(v)}</span>
        <span class="v-pct">${total > 0 ? Math.round((v / total) * 100) : 0}%</span>
      </td>`;
    });
    html += `<td class="td-total">
      <div class="total-bar"><div class="total-bar-fill" style="width:${Math.min(100, total / 6)}%;background:${typeColor};"></div></div>
      <span class="total-num">${Math.round(total)}</span>
    </td></tr>`;
  });
  html += '</tbody></table></div>';

  // ===== 热门流向排行 TOP 5 =====
  const rankedFlows = [...flows].sort((a, b) => (b.volume || 0) - (a.volume || 0)).slice(0, 5);
  const maxFlowVol = Math.max(...rankedFlows.map(f => f.volume || 0), 1);
  html += `<div class="flow-rank-section">
    <div class="flow-rank-title">🏆 热门流向排行 TOP 5</div>
    ${rankedFlows.map((f, i) => {
      const pct = (f.volume || 0) / maxFlowVol * 100;
      const cColor = CUISINE_HEX[cuisineKey(f.to?.cuisine)] || '#1B2A4E';
      const medal = ['🥇','🥈','🥉','4️⃣','5️⃣'][i] || '';
      return `<div class="flow-rank-item">
        <span class="fr-medal">${medal}</span>
        <span class="fr-path"><strong>${f.from?.name || '?'}</strong> → <strong>${f.to?.name || '?'}</strong></span>
        <span class="fr-cuisine" style="color:${cColor};">${f.to?.cuisine || ''}</span>
        <div class="fr-bar-wrap"><div class="fr-bar" style="width:${pct}%;background:${cColor};"></div></div>
        <span class="fr-val">${Math.round(f.volume || 0)}</span>
      </div>`;
    }).join('')}
  </div>`;

  // ===== 菜系流量分布 =====
  const cuisineTotals = {};
  flows.forEach(f => {
    const ck = cuisineKey(f.to?.cuisine);
    if (ck) cuisineTotals[ck] = (cuisineTotals[ck] || 0) + (f.volume || 0);
  });
  const totalCuisineVol = Object.values(cuisineTotals).reduce((a, b) => a + b, 0) || 1;
  const sortedCuisines = Object.entries(cuisineTotals).sort((a, b) => b[1] - a[1]);
  if (sortedCuisines.length > 0) {
    html += `<div class="flow-cuisine-section">
      <div class="flow-rank-title">🍽️ 菜系流量分布</div>
      <div class="cuisine-dist-grid">
        ${sortedCuisines.map(([ck, vol]) => {
          const pct = vol / totalCuisineVol * 100;
          const cc = CUISINE_HEX[ck] || '#1B2A4E';
          return `<div class="cuisine-dist-item">
            <span class="cd-dot" style="background:${cc};"></span>
            <span class="cd-name">${ck}</span>
            <div class="cd-bar-wrap"><div class="cd-bar" style="width:${pct}%;background:${cc};"></div></div>
            <span class="cd-pct">${Math.round(pct)}%</span>
            <span class="cd-val">${Math.round(vol)}</span>
          </div>`;
        }).join('')}
      </div>
    </div>`;
  }

  // ===== 来源类型占比 =====
  const typeTotals = {};
  flows.forEach(f => {
    const t = f.from?.type || 'other';
    typeTotals[t] = (typeTotals[t] || 0) + (f.volume || 0);
  });
  const typeNames = { residential: '居住区', office: '办公区', university: '大学城', transit: '交通枢纽', other: '其他' };
  const typeTotalVol = Object.values(typeTotals).reduce((a, b) => a + b, 0) || 1;
  const sortedTypes = Object.entries(typeTotals).sort((a, b) => b[1] - a[1]);
  html += `<div class="flow-rank-section">
    <div class="flow-rank-title">🏠 来源类型占比</div>
    <div class="cuisine-dist-grid">
      ${sortedTypes.map(([t, vol]) => {
        const pct = vol / typeTotalVol * 100;
        const tc = typeColors[t] || '#6B7280';
        return `<div class="cuisine-dist-item">
          <span class="cd-dot" style="background:${tc};"></span>
          <span class="cd-name">${typeNames[t] || t}</span>
          <div class="cd-bar-wrap"><div class="cd-bar" style="width:${pct}%;background:${tc};"></div></div>
          <span class="cd-pct">${Math.round(pct)}%</span>
          <span class="cd-val">${Math.round(vol)}</span>
        </div>`;
      }).join('')}
    </div>
  </div>`;

  // ===== 目标热区排名 =====
  const destTotals = {};
  flows.forEach(f => {
    const dn = f.to?.name || '未知';
    destTotals[dn] = (destTotals[dn] || 0) + (f.volume || 0);
  });
  const maxDestVol = Math.max(...Object.values(destTotals), 1);
  const sortedDests = Object.entries(destTotals).sort((a, b) => b[1] - a[1]);
  html += `<div class="flow-rank-section">
    <div class="flow-rank-title">🎯 目标热区排名</div>
    <div class="cuisine-dist-grid">
      ${sortedDests.slice(0, 6).map(([dn, vol]) => {
        const pct = vol / maxDestVol * 100;
        return `<div class="cuisine-dist-item">
          <span class="cd-dot" style="background:var(--accent);"></span>
          <span class="cd-name">${dn}</span>
          <div class="cd-bar-wrap"><div class="cd-bar" style="width:${pct}%;background:var(--accent);"></div></div>
          <span class="cd-pct">${Math.round(pct)}%</span>
          <span class="cd-val">${Math.round(vol)}</span>
        </div>`;
      }).join('')}
    </div>
  </div>`;

  host.innerHTML = html;

  // 绑定 chip
  host.querySelectorAll('.mchip').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.type !== undefined) _matrixFilter.srcType = btn.dataset.type;
      if (btn.dataset.cuisine !== undefined) _matrixFilter.cuisine = btn.dataset.cuisine;
      renderFlowMatrix();
    });
  });
}

function hexToRgb(hex) {
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return m ? [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)] : [0, 0, 0];
}

function bindControls() {
  document.getElementById('btnZoomIn')?.addEventListener('click', () => bus.emit('map:zoomIn'));
  document.getElementById('btnZoomOut')?.addEventListener('click', () => bus.emit('map:zoomOut'));
  document.getElementById('btnResetView')?.addEventListener('click', () => bus.emit('map:resetView'));
  const ht = document.getElementById('btnToggleHeat');
  ht?.addEventListener('click', () => { ht.classList.toggle('active'); bus.emit('heat:toggle', ht.classList.contains('active')); });
  const fl = document.getElementById('btnToggleFlow');
  fl?.addEventListener('click', () => { fl.classList.toggle('active'); bus.emit('flow:toggle', fl.classList.contains('active')); });
  document.getElementById('selCity')?.addEventListener('change', e => bus.emit('city:switch', e.target.value));
}

function bindReport() {
  document.getElementById('btnGenerateReport')?.addEventListener('click', () => {
    const d = document.getElementById('reportContent');
    if (!d) return;
    const top = document.querySelector('.hotspot-name')?.textContent || '核心商圈';
    const cuisine = document.getElementById('kpiCuisine')?.textContent || '--';
    const diners = document.getElementById('kpiDiners')?.textContent || '--';
    const growth = document.getElementById('kpiGrowth')?.textContent || '--';
    const hotspots = document.getElementById('kpiHotspots')?.textContent || '--';
    const city = store.get('city.name');
    d.innerHTML = `<h3>${city} 城市餐饮热度分析报告</h3>
      <p style="color:var(--ink-faint);font-size:12px;">生成时间：${new Date().toLocaleString('zh-CN')}</p>
      <hr/>
      <h4>一、客流概况</h4>
      <p>实时监测餐饮客流 <strong>${diners}</strong> 人，识别餐饮热区 <strong>${hotspots}</strong> 个，热门菜系 <strong>${cuisine}</strong>。客流增长率 <strong>${growth}</strong>（vs 昨日），处于活跃水平。</p>
      <h4>二、商圈热度分析</h4>
      <p>${top} 是当前餐饮热度最高的区域，覆盖 ${cuisine} 主导业态，入流量与上座率持续上升。</p>
      <h4>三、菜系竞争格局</h4>
      <p>${cuisine} 依然占据主要热度。建议关注：① 火锅区域差异化（一人食/小份）② 烧烤夜市档口延长 ③ 轻食沙拉/咖啡承接午市白领。</p>
      <h4>四、投资与运营参考</h4>
      <ul>
        <li>核心商圈 ${cuisine} 密度趋于饱和，建议差异化定位</li>
        <li>城西/中北镇/张家窝等新兴板块餐饮空白明显</li>
        <li>夏季户外餐饮（露台/夜市）即将迎来旺季</li>
        <li>外卖渠道可考虑"火锅冒菜化"/"烧烤单人份"轻量化产品线</li>
      </ul>`;
  });
}
