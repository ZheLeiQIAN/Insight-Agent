// demoData.js — V0.7 流动 demo 数据生成器（餐饮·火锅门店版）
// 用途：让 UI 在没有真实数据时也能"活"起来
// 设计原则：
//   - 数字符合业务逻辑（等位 ≈ 8-30 桌，翻台率 ≈ 1.2-2.8）
//   - 事件有真实感（点餐 / 买单 / 等位 / 菜品关注）
//   - 有节奏（每 N 秒插入一条，不刷屏也不冷场）

import { emit } from './eventBus.js';

// ============================================================
// 1) 门店数字（等位/翻台/关注/事件）
// ============================================================
let _waitingCount = 12;
let _revenueMin = 3800;
let _interestCount = 6;
let _eventsPerHour = 0;

function jitter(value, min, max, step = 1) {
  const delta = (Math.random() - 0.5) * step * 2;
  return Math.max(min, Math.min(max, Math.round(value + delta)));
}

/**
 * 启动门店数字的"心跳"（每 2.5s 一次）
 */
export function startKpiHeartbeat() {
  setInterval(() => {
    _waitingCount = jitter(_waitingCount, 3, 35, 2);
    _revenueMin = jitter(_revenueMin, 2200, 6800, 200);
    _interestCount = jitter(_interestCount, 3, 12, 1);
    const trend = _waitingCount - 12;

    emit('demo:kpi', {
      persons: _waitingCount,
      dwell: _revenueMin,
      interest: _interestCount,
      events: _eventsPerHour,
      trend,
    });
  }, 2500);
}

// ============================================================
// 2) 行为事件流 — 火锅门店场景
// ============================================================
const PERSONAS = [
  { id: 'A', name: '情侣二人组' },
  { id: 'B', name: '家庭聚餐(4人)' },
  { id: 'C', name: '商务客人' },
  { id: 'D', name: '独自食客' },
  { id: 'E', name: '朋友聚会(3人)' },
];

const ZONES = ['入口等位区', '调料台', '卡座区', '包间', '收银台', '取餐区', '靠窗双人桌', '自助水果区'];

const GESTURE_TEMPLATES = [
  (p, z) => `${p.name} 在${z}招手示意加单`,
  (p, z) => `检测到 ${p.name} 在${z}竖起大拇指 → 满意信号`,
  (p, z) => `${p.name} 在${z}指向菜单上的招牌菜`,
  (p, z) => `${p.name} 在${z}比划"结账"手势`,
];

const FACE_TEMPLATES = [
  (p, z) => `${p.name} 入座${z}，微笑（置信度 0.85）`,
  (p, z) => `${p.name} 在${z}看到上菜露出惊喜表情`,
  (p, z) => `${p.name} 在${z}皱眉（疑似菜品不合口味）`,
  (p, z) => `${p.name} 在${z}火锅热气中大笑畅聊`,
];

const BEHAVIOR_TEMPLATES = [
  (p, z) => `<strong>${p.name}</strong> 在${z}频繁翻看菜单，犹豫点单`,
  (p, z) => `<strong>${p.name}</strong> 在${z}起身去调料台 3 次，蘸料狂热分子`,
  (p, z) => `<strong>${p.name}</strong> 在${z}拍照发朋友圈（菜品颜值在线）`,
  (p, z) => `${z} 有客人长时间招手但服务员未响应（>2min），建议关注`,
];

const INTEREST_TEMPLATES = [
  (p, z) => `${p.name} 注视 ${z} 招牌毛肚 5.2s，点单意向强烈`,
  (p, z) => `${p.name} 在${z}反复打量其他桌的鸳鸯锅底`,
  (p, z) => `${p.name} 阅读 ${z} 菜单推荐菜品（停留 8s）`,
];

const COUNT_TEMPLATES = [
  (n) => `等位区当前 ${n} 桌在等候，预计等待 15-20 分钟`,
  (n) => `过去 10 分钟新到 ${n} 桌客人入座`,
  (n) => `当前在店 ${n} 桌，上座率 ${Math.min(100, Math.round(n / 28 * 100))}%`,
];

const QUEUE_TEMPLATES = [
  () => `<strong>等位区排起长队</strong>，当前 8 桌等候，预计 25 分钟`,
  () => `等位压力缓解，当前仅 3 桌在等`,
];

const TYPES = ['gesture', 'face', 'interest', 'count', 'behavior'];
const TPL = {
  gesture: GESTURE_TEMPLATES,
  face:    FACE_TEMPLATES,
  interest: INTEREST_TEMPLATES,
  count:   COUNT_TEMPLATES,
  behavior: BEHAVIOR_TEMPLATES,
};

let _lastEvent = 0;
const MIN_GAP_MS = 1800;
const MAX_GAP_MS = 5000;

function rand(min, max) { return Math.random() * (max - min) + min; }

function pickEvent() {
  const type = TYPES[Math.floor(Math.random() * TYPES.length)];
  const persona = PERSONAS[Math.floor(Math.random() * PERSONAS.length)];
  const zone = ZONES[Math.floor(Math.random() * ZONES.length)];
  const tpl = TPL[type][Math.floor(Math.random() * TPL[type].length)];
  let text, conf;
  if (type === 'count') {
    text = tpl(_waitingCount);
    conf = 1.0;
  } else {
    text = tpl(persona, zone);
    conf = 0.6 + Math.random() * 0.35;
  }
  return { type, text, confidence: conf };
}

// 启动时一次性预热 5 条历史事件，按时间倒序依次排好
// 这样卡片高度在页面打开时就已经稳定，避免事件一条条蹦出导致高度抖动
function seedInitialEvents() {
  const now = Date.now();
  const seeded = [];
  // 时间间隔：2s/4s/6s/8s/10s 之前
  const offsets = [2000, 4000, 6000, 8000, 10000];
  for (let i = 0; i < offsets.length; i++) {
    const evt = pickEvent();
    seeded.push({ ts: now - offsets[i], ...evt });
    _eventsPerHour++;
  }
  // 按时间从旧到新发送，让 UI 从下往上自然堆叠
  seeded.sort((a, b) => a.ts - b.ts);
  for (const evt of seeded) {
    emit('demo:event', evt);
  }
}

export function startEventStream() {
  // 先把历史事件灌满，再开新的 tick
  seedInitialEvents();
  function next() {
    const evt = pickEvent();
    _eventsPerHour++;
    emit('demo:event', { ts: Date.now(), ...evt });
    if (Math.random() < 0.06) {
      const tpl = QUEUE_TEMPLATES[Math.floor(Math.random() * QUEUE_TEMPLATES.length)];
      emit('demo:event', { ts: Date.now() + 1, type: 'behavior', text: tpl(), confidence: 0.92 });
    }
    setTimeout(next, rand(MIN_GAP_MS, MAX_GAP_MS));
  }
  setTimeout(next, 1200);
}

// ============================================================
// 3) Agent 建议 — 每 3s 出一条（火锅门店版，模板丰富，避免停滞）
// ============================================================
const ADVISORY_TEMPLATES = [
  {
    priority: 'high',
    intent: '等位预警 · HIGH',
    text: `<strong>入口等位区</strong>已积压 8 桌，预计等待超 25 分钟。建议：<br>· 开放 2F 备用散台 4 桌<br>· 推送等位优惠券安抚客人<br>· 提供免费小食延长耐心`,
    actions: ['开放备用散台', '推送等位券', '提供小食饮品'],
    reasoning: '等位桌数 > 6 且翻台预测 18min/桌',
  },
  {
    priority: 'medium',
    intent: '翻台机会 · MEDIUM',
    text: `卡座区 3 桌客人已用餐超过 70 分钟，仅剩锅底未加菜。 <br>建议服务员<strong>主动询问加菜或准备买单</strong>，缩短翻台间隙。`,
    actions: ['主动询问加菜', '准备结账流程', '翻台快速清洁'],
    reasoning: '用餐时长 > 70min + 停单状态 > 8min',
  },
  {
    priority: 'low',
    intent: '服务提升 · LOW',
    text: `调料台区域排队 3 人但无人补料。<strong>蒜泥即将见底</strong>。建议：<br>· 通知后厨补料<br>· 高峰期安排专人看管调料区`,
    actions: ['通知补料', '安排专人'],
    reasoning: '调料台驻留 > 3 人 + 补料间隔超 15min',
  },
  {
    priority: 'medium',
    intent: '菜品关注 · MEDIUM',
    text: `<strong>招牌毛肚</strong>在最近 15 分钟内被 6 桌客人点单，好评率 92%。建议：<br>· 提前备货确保不断供<br>· 可尝试向犹豫客人推荐毛肚套餐`,
    actions: ['提前备货', '向犹豫客人推荐', '推送限时套餐'],
    reasoning: '点单率 + 好评率双高 + 库存预警',
  },
  {
    priority: 'high',
    intent: '异常行为 · HIGH',
    text: `<strong>商务客人</strong>在包间频繁看表且未动锅底 10 分钟。疑似在等迟到的客人。<br>建议：温和询问是否需要先上小菜或饮品。`,
    actions: ['询问上小菜饮品', '预留上菜时间'],
    reasoning: '入座未点单 + 频繁看表 + 浏览手机',
  },
  {
    priority: 'medium',
    intent: '客流转化 · MEDIUM',
    text: `入口处<strong>情侣二人组</strong>驻足菜单 45 秒未决定，已对 3 个 SKU 反复比较。建议：<br>· 服务员主动迎宾<br>· 推荐<strong>鸳鸯锅底 + 双人套餐</strong>（销量 TOP 3）`,
    actions: ['主动迎宾', '推荐双人套餐', '赠送小份试吃'],
    reasoning: '驻足时长 > 40s + SKU 切换 ≥ 3',
  },
  {
    priority: 'low',
    intent: '好评机会 · LOW',
    text: `检测到<strong>家庭聚餐(4人)</strong>在卡座区对<strong>虾滑</strong>竖起大拇指，满意度信号强。<br>建议：趁热询问是否需要加单 / 是否愿意扫码好评。`,
    actions: ['询问加单', '推送好评卡', '赠送果盘'],
    reasoning: '正向微表情 + 停留时长 + 翻看菜单',
  },
  {
    priority: 'high',
    intent: '安全预警 · HIGH',
    text: `<strong>调料台</strong>区域<strong>朋友聚会(3人)</strong>疑似醉酒，动作幅度大、声音嘈杂，已超过正常分贝。<br>建议：领班巡查、安抚情绪、提醒勿浪费食材。`,
    actions: ['领班巡查', '温和提醒', '赠送醒酒茶'],
    reasoning: '行为异常 + 持续 3min + 服务员未介入',
  },
  {
    priority: 'medium',
    intent: '加单机会 · MEDIUM',
    text: `<strong>包间</strong>客人已涮完第 2 轮食材，但锅底水位明显下降。建议：<br>· 服务员<strong>主动加汤</strong><br>· 询问是否需要追加<strong>牛肉 / 鸭血</strong>`,
    actions: ['主动加汤', '推荐加单', '送一份小吃'],
    reasoning: '锅底水位 ↓ + 用餐轮次 ≥ 2 + 桌面空盘率高',
  },
  {
    priority: 'low',
    intent: '会员转化 · LOW',
    text: `<strong>独自食客</strong>在收银台结账时未使用会员卡。建议：<br>· 收银员口头推荐<strong>储值卡 99 抵 120</strong><br>· 推送公众号领新人券`,
    actions: ['推荐储值卡', '推送新人券', '引导加企微'],
    reasoning: '非会员 + 单次消费 ≥ ¥98',
  },
  {
    priority: 'medium',
    intent: '动线优化 · MEDIUM',
    text: `取餐区与调料台之间<strong>客流通行密度 +28%</strong>，出现轻微拥堵。建议：<br>· 调整<strong>自助水果区</strong>位置<br>· 临时加设引导牌`,
    actions: ['调整动线', '加设引导牌', '增加临时保洁'],
    reasoning: '热区密度 ↑ 28% 且持续 6min',
  },
  {
    priority: 'high',
    intent: '菜品缺货 · HIGH',
    text: `<strong>鸭肠</strong>已被 11 桌点单（库存仅剩 3 份），即将售罄。建议：<br>· 立即通知后厨补货<br>· 前台暂时下架该 SKU 入口`,
    actions: ['通知补货', '暂时下架', '推送替代品'],
    reasoning: '点单率 11 / 库存 3，剩余可供应 < 8min',
  },
  {
    priority: 'low',
    intent: '桌台清洁 · LOW',
    text: `<strong>卡座区 5 号桌</strong>已清桌 4 分钟但尚未翻台。系统判定为<strong>清洁延迟</strong>。建议：保洁员优先处理，恢复上座率。`,
    actions: ['优先清洁', '通知领班', '检查餐具'],
    reasoning: '清桌 → 上桌时长 > 4min（行业基线 2.5min）',
  },
  {
    priority: 'medium',
    intent: '天气营销 · MEDIUM',
    text: `室外温度骤降至 8°C，<strong>火锅</strong>相关搜索量 +42%。建议：<br>· 推送<strong>暖锅 6.8 折</strong>短信给附近 1.5km 老客<br>· 门口立牌更新"暖暖锅"主题`,
    actions: ['推送暖锅券', '更新门口立牌', '开启双倍积分'],
    reasoning: '气温骤降 + 同商圈搜索 ↑ + 周末晚高峰临近',
  },
  {
    priority: 'high',
    intent: '儿童安全 · HIGH',
    text: `检测到<strong>卡座区</strong>有<strong>儿童独自离开座位</strong> 1.2m，附近有上菜通道。建议：<br>· 服务员立即拦截<br>· 提醒家长看护`,
    actions: ['立即拦截', '提醒家长', '设置防撞'],
    reasoning: '儿童位移 + 临边距离 < 1.5m + 高峰时段',
  },
];

let _advisoryIdx = 0;

function pickAdvisory() {
  const tpl = ADVISORY_TEMPLATES[_advisoryIdx % ADVISORY_TEMPLATES.length];
  _advisoryIdx++;
  return { ts: Date.now(), ...tpl };
}

// 启动时一次性预热 5 条历史建议，时间从旧到新 emit
function seedInitialAdvices() {
  const now = Date.now();
  const offsets = [12000, 24000, 36000, 48000, 60000]; // 12s/24s/36s/48s/60s 之前
  for (let i = 0; i < offsets.length; i++) {
    const tpl = ADVISORY_TEMPLATES[(_advisoryIdx + i) % ADVISORY_TEMPLATES.length];
    emit('demo:advice', { ts: now - offsets[i], ...tpl });
  }
  _advisoryIdx += offsets.length;
}

export function startAdvisoryStream() {
  // 先把历史建议灌满 5 条，再开新 tick
  seedInitialAdvices();
  // 每 3s 出一条新建议
  setInterval(() => {
    emit('demo:advice', pickAdvisory());
  }, 3000);
}

// ============================================================
// 4) Agent 对话脚本（火锅门店版）
// ============================================================
export const SCRIPTED_CHAT = {
  triggers: [
    { q: /等位|排队|多少.*桌|人多/, a: '当前等位 **12 桌**，预计等待 20 分钟。入口等位区已坐满。建议开放 2F 备用散台。' },
    { q: /异常|投诉|打架|不满/,     a: '过去 15 分钟内检测到 **1 次异常**：包间商务客人长时间等待未点单。均已通知领班关注。' },
    { q: /关注|热销|招牌|什么.*火/, a: '最近 20 分钟最热门：<br>· **招牌毛肚** 被 6 桌点单<br>· **鸳鸯锅底** 被 8 桌选择<br>· **虾滑** 好评率 94% 建议提前备货。' },
    { q: /翻台|翻桌|周转/,        a: '当前翻台率 **2.1 次/晚**（目标 2.5），卡座区 3 桌已用餐超 70 分钟，建议主动询问加菜或买单。' },
    { q: /收银|买单|结账/,          a: '收银台当前 2 人排队，状态通畅。今日客单价约 **¥186/人**，较昨日 +5%。' },
    { q: /报告|总结|今日/,          a: '正在生成今日阶段报告...<br>📊 接待 82 桌（+8% vs 昨日）<br>💰 预估营收 ¥1.52 万（+12%）<br>🔥 招牌毛肚售出 46 份<br>⚠️ 等位预警 2 次（已处理 2）<br>💡 建议：加强 2F 散台准备迎接晚高峰' },
  ],
  fallback: '这是一个 demo 模式的问题。真实模式下会调用 DeepSeek-V4 给出基于实时事件的专业建议。你可以试试问："现在多少桌等位？"、"什么菜最火？" 或 "翻台率多少？"',
};

export function matchScriptedReply(message) {
  for (const t of SCRIPTED_CHAT.triggers) {
    if (t.q.test(message)) return t.a;
  }
  return SCRIPTED_CHAT.fallback;
}

// ============================================================
// 5) 热区图 — 餐饮门店平面热力场（V2 精细化版）
// ============================================================

// 门店区域定义（相对坐标 0-1）
const HEAT_ZONES = [
  { id: 'kitchen',  label: '厨房',       en: 'KITCHEN',    x: 0.50, y: 0.10, w: 0.40, h: 0.16, color: '#6B7280' },
  { id: 'booth',    label: '卡座区',     en: 'BOOTH',      x: 0.20, y: 0.38, w: 0.30, h: 0.26, color: '#1B2A4E' },
  { id: 'window',   label: '靠窗双人桌', en: 'WINDOW',     x: 0.62, y: 0.38, w: 0.28, h: 0.26, color: '#1B2A4E' },
  { id: 'vip',      label: '包间',       en: 'VIP',        x: 0.68, y: 0.70, w: 0.22, h: 0.14, color: '#1B2A4E' },
  { id: 'waiting',  label: '等位区',     en: 'WAITING',    x: 0.08, y: 0.75, w: 0.18, h: 0.18, color: '#B8860B' },
  { id: 'cashier',  label: '收银台',     en: 'CASHIER',    x: 0.40, y: 0.82, w: 0.16, h: 0.10, color: '#1B4A6B' },
  { id: 'sauce',    label: '调料台',     en: 'SAUCE BAR',  x: 0.82, y: 0.12, w: 0.12, h: 0.10, color: '#4F7942' },
];

// 热力斑 block（带抖动 + 脉冲）
const HEAT_BLOBS = [
  { z: 'booth',  x: 0.25, y: 0.38, vx: 0.0010, vy: 0.0012, intensity: 0.75, radius: 0.18, phase: 0 },
  { z: 'window', x: 0.70, y: 0.40, vx: 0.0008, vy: 0.0015, intensity: 0.70, radius: 0.16, phase: 1.2 },
  { z: 'waiting',x: 0.12, y: 0.82, vx: 0.0020, vy: 0.0005, intensity: 0.85, radius: 0.12, phase: 2.5 },
  { z: 'vip',    x: 0.75, y: 0.72, vx: 0.0015, vy: 0.0010, intensity: 0.55, radius: 0.11, phase: 0.8 },
  { z: 'sauce',  x: 0.86, y: 0.16, vx: 0.0012, vy: 0.0018, intensity: 0.50, radius: 0.09, phase: 3.1 },
  { z: 'kitchen',x: 0.55, y: 0.08, vx: 0.0005, vy: 0.0008, intensity: 0.90, radius: 0.10, phase: 1.8 },
];

// 桌子布局
const TABLES = (() => {
  const t = [];
  // 卡座区（6 张）
  for (let r = 0; r < 2; r++) {
    for (let c = 0; c < 3; c++) {
      t.push({ zone: 'booth', x: 0.10 + c * 0.09, y: 0.32 + r * 0.10, r: 0.025, occupied: Math.random() > 0.3 });
    }
  }
  // 靠窗区（4 张）
  for (let r = 0; r < 2; r++) {
    for (let c = 0; c < 2; c++) {
      t.push({ zone: 'window', x: 0.64 + c * 0.10, y: 0.34 + r * 0.10, r: 0.022, occupied: Math.random() > 0.4 });
    }
  }
  // 包间（2 间）
  t.push({ zone: 'vip', x: 0.71, y: 0.65, r: 0.03, occupied: Math.random() > 0.3, label: 'V1' });
  t.push({ zone: 'vip', x: 0.83, y: 0.65, r: 0.03, occupied: Math.random() > 0.3, label: 'V2' });
  return t;
})();

// 客流点（在门店内游走的 dots）
function createFlowDots(count) {
  const dots = [];
  for (let i = 0; i < count; i++) {
    dots.push({
      x: 0.1 + Math.random() * 0.8,
      y: 0.3 + Math.random() * 0.6,
      tx: 0.1 + Math.random() * 0.8,
      ty: 0.3 + Math.random() * 0.6,
      speed: 0.002 + Math.random() * 0.004,
      size: 1.5 + Math.random() * 2,
      alpha: 0.4 + Math.random() * 0.4,
      pause: 0,
    });
  }
  return dots;
}
let flowDots = createFlowDots(18);

function pickNewTarget(dot) {
  dot.tx = 0.08 + Math.random() * 0.84;
  dot.ty = 0.28 + Math.random() * 0.60;
  dot.speed = 0.002 + Math.random() * 0.005;
  dot.pause = 30 + Math.floor(Math.random() * 80);
}

export function startHeatmapAnimation(canvas) {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;

  function resize() {
    const rect = canvas.getBoundingClientRect();
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
  }
  resize();
  window.addEventListener('resize', resize);

  let frame = 0;

  function step() {
    frame++;
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    if (w < 10 || h < 10) { requestAnimationFrame(step); return; }

    // 背景
    const bg = ctx.createLinearGradient(0, 0, 0, h);
    bg.addColorStop(0, '#F8F6F0');
    bg.addColorStop(1, '#F0EDE5');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);

    // 外框（双线）
    ctx.strokeStyle = 'rgba(27, 42, 78, 0.12)';
    ctx.lineWidth = 1 * dpr;
    ctx.strokeRect(4 * dpr, 4 * dpr, w - 8 * dpr, h - 8 * dpr);
    ctx.strokeStyle = 'rgba(27, 42, 78, 0.06)';
    ctx.strokeRect(8 * dpr, 8 * dpr, w - 16 * dpr, h - 16 * dpr);

    // ======= 1) 隔断 / 墙体 =======
    ctx.save();

    // 厨房隔断（顶部横墙）
    ctx.strokeStyle = 'rgba(27, 42, 78, 0.20)';
    ctx.lineWidth = 2 * dpr;
    ctx.setLineDash([6 * dpr, 4 * dpr]);
    ctx.beginPath();
    ctx.moveTo(8 * dpr, h * 0.22);
    ctx.lineTo(w * 0.55, h * 0.22);
    ctx.stroke();

    // 右墙（厨房右侧）
    ctx.beginPath();
    ctx.moveTo(w * 0.55, h * 0.22);
    ctx.lineTo(w * 0.55, h * 0.05);
    ctx.stroke();
    ctx.setLineDash([]);

    // 厨房出餐口（虚线半墙）
    ctx.strokeStyle = 'rgba(27, 42, 78, 0.12)';
    ctx.lineWidth = 1.5 * dpr;
    ctx.beginPath();
    ctx.moveTo(12 * dpr, h * 0.22);
    ctx.lineTo(w * 0.40, h * 0.22);
    ctx.stroke();

    // 包间隔断
    ctx.strokeStyle = 'rgba(139, 26, 26, 0.15)';
    ctx.lineWidth = 1.5 * dpr;
    ctx.beginPath();
    ctx.moveTo(w * 0.60, h * 0.58);
    ctx.lineTo(w * 0.60, h * 0.50);
    ctx.lineTo(w * 0.95, h * 0.50);
    ctx.stroke();

    // 入口标记（门）
    ctx.strokeStyle = 'rgba(139, 26, 26, 0.20)';
    ctx.lineWidth = 1.5 * dpr;
    ctx.beginPath();
    ctx.arc(10 * dpr, h * 0.78, 8 * dpr, -Math.PI * 0.4, Math.PI * 0.4);
    ctx.stroke();
    ctx.fillStyle = 'rgba(139, 26, 26, 0.10)';
    ctx.font = `${7 * dpr}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.fillText('入口', 16 * dpr, h * 0.78 + 12 * dpr);

    ctx.restore();

    // ======= 2) 热力梯度（底层） =======
    // 更新 blob 位置
    const time = frame * 0.02;
    for (const b of HEAT_BLOBS) {
      b.x += b.vx;
      b.y += b.vy;
      if (b.x < 0.06 || b.x > 0.94) b.vx *= -1;
      if (b.y < 0.06 || b.y > 0.94) b.vy *= -1;
      b.phase += 0.03;
    }

    // 径向梯度叠加
    const imgData = ctx.createImageData(w, h);
    const data = imgData.data;
    const cx = HEAT_BLOBS.map((b) => b.x * w);
    const cy = HEAT_BLOBS.map((b) => b.y * h);
    const rad2 = HEAT_BLOBS.map((b) => (b.radius * w) ** 2);
    const inten = HEAT_BLOBS.map((b) => {
      const pulse = 0.85 + 0.15 * Math.sin(b.phase);
      return b.intensity * pulse;
    });

    const STEP = 3;
    for (let y = 0; y < h; y += STEP) {
      for (let x = 0; x < w; x += STEP) {
        let v = 0;
        for (let k = 0; k < cx.length; k++) {
          const dx = x - cx[k], dy = y - cy[k];
          const d2 = dx * dx + dy * dy;
          v += inten[k] * Math.exp(-d2 / rad2[k]);
        }
        if (v < 0.04) continue;
        v = Math.min(1, v);
        const r = Math.round(184 * v + 245 * (1 - v));
        const g = Math.round(26 * v + 240 * (1 - v));
        const b2 = Math.round(26 * v + 235 * (1 - v));
        const a = Math.round(v * 120);
        for (let oy = 0; oy < STEP && y + oy < h; oy++) {
          for (let ox = 0; ox < STEP && x + ox < w; ox++) {
            const idx = ((y + oy) * w + (x + ox)) * 4;
            data[idx] = r;
            data[idx + 1] = g;
            data[idx + 2] = b2;
            data[idx + 3] = a;
          }
        }
      }
    }
    ctx.putImageData(imgData, 0, 0);

    // ======= 3) 桌子 + 占用状态 =======
    for (const t of TABLES) {
      const tx = t.x * w;
      const ty = t.y * h;
      const tr = t.r * w;

      // 桌底阴影
      ctx.beginPath();
      ctx.arc(tx + 1 * dpr, ty + 1 * dpr, tr, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0,0,0,0.06)';
      ctx.fill();

      if (t.occupied) {
        // 被占用的桌子：实心 + 脉冲光晕
        const pulse = 0.7 + 0.3 * Math.sin(time * 2 + tx * 0.1);
        const grad = ctx.createRadialGradient(tx, ty, 0, tx, ty, tr * 1.8);
        grad.addColorStop(0, `rgba(139, 26, 26, ${0.15 * pulse})`);
        grad.addColorStop(1, 'rgba(139, 26, 26, 0)');
        ctx.beginPath();
        ctx.arc(tx, ty, tr * 1.8, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(tx, ty, tr, 0, Math.PI * 2);
        ctx.fillStyle = '#8B1A1A';
        ctx.fill();
        ctx.strokeStyle = 'rgba(255,255,255,0.4)';
        ctx.lineWidth = 1 * dpr;
        ctx.stroke();
      } else {
        // 空桌：空心
        ctx.beginPath();
        ctx.arc(tx, ty, tr, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(27, 42, 78, 0.06)';
        ctx.fill();
        ctx.strokeStyle = 'rgba(27, 42, 78, 0.25)';
        ctx.lineWidth = 1 * dpr;
        ctx.stroke();
      }

      // VIP 包间标注
      if (t.label) {
        ctx.fillStyle = t.occupied ? '#8B1A1A' : 'rgba(107, 114, 128, 0.6)';
        ctx.font = `${7 * dpr}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.fillText(t.label, tx, ty - tr - 4 * dpr);
      }
    }

    // ======= 4) 客流点动画 =======
    for (const dot of flowDots) {
      if (dot.pause > 0) {
        dot.pause--;
        // 绘制静止的 dot
        const dx = dot.x * w;
        const dy = dot.y * h;
        ctx.beginPath();
        ctx.arc(dx, dy, dot.size * dpr, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(27, 42, 78, ${dot.alpha * 0.5})`;
        ctx.fill();
        continue;
      }

      // 移向目标
      const dx = dot.tx - dot.x;
      const dy = dot.ty - dot.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 0.005) {
        pickNewTarget(dot);
      } else {
        dot.x += (dx / dist) * dot.speed;
        dot.y += (dy / dist) * dot.speed;
      }

      const px = dot.x * w;
      const py = dot.y * h;

      // 拖尾效果小点
      ctx.beginPath();
      ctx.arc(px, py, dot.size * dpr, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(27, 42, 78, ${dot.alpha})`;
      ctx.fill();

      // 环境光晕
      ctx.beginPath();
      ctx.arc(px, py, dot.size * 2.5 * dpr, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(27, 42, 78, ${dot.alpha * 0.15})`;
      ctx.fill();
    }

    // ======= 5) 区域标签 =======
    ctx.save();
    for (const z of HEAT_ZONES) {
      const zx = z.x * w;
      const zy = z.y * h;
      ctx.fillStyle = 'rgba(27, 42, 78, 0.50)';
      ctx.font = `bold ${9 * dpr}px "Noto Sans SC", sans-serif`;
      ctx.textAlign = 'center';
      ctx.fillText(z.label, zx, zy);

      ctx.fillStyle = 'rgba(107, 114, 128, 0.45)';
      ctx.font = `${7 * dpr}px "JetBrains Mono", monospace`;
      ctx.fillText(z.en, zx, zy + 10 * dpr);
    }
    ctx.restore();

    requestAnimationFrame(step);
  }
  step();
}

// ============================================================
// 6) 时钟
// ============================================================
export function startClock() {
  setInterval(() => {
    const el = document.getElementById('status-time');
    if (!el) return;
    const d = new Date();
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    el.textContent = `${hh}:${mm}:${ss}`;
    const ts = document.getElementById('corner-ts');
    if (ts) {
      const d2 = new Date();
      ts.textContent = `${d2.getFullYear()}-${String(d2.getMonth() + 1).padStart(2, '0')}-${String(d2.getDate()).padStart(2, '0')}`;
    }
    const kt = document.getElementById('kpi-time');
    if (kt) kt.textContent = `今日 · ${hh}:${mm}`;
  }, 1000);
}
