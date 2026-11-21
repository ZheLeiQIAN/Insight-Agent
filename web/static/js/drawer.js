// drawer.js — V0.9 数据钻取详情抽屉
// 6 类入口 × 6 个内容渲染器，全部印刷感样式
// 全部 rAF 驱动，prefers-reduced-motion 兼容

import { drawSeriesChart, makeChartSeries, flipNumber } from './animations.js';

const REDUCED = typeof window !== 'undefined'
  && window.matchMedia
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

let _drawerOpen = false;
let _drawerNode = null;
let _backdropNode = null;
let _lastPicked = null;
let _escListener = null;

const ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII'];

// ============================================================
// 1) 组件入口
// ============================================================
export function openDrawer(opts = {}) {
  const { title = '详情', subtitle = '', content = '', footer = '', page = 'I' } = opts;
  closeDrawer(false);
  const root = document.getElementById('drawer-root') || document.body;

  // 背景
  const backdrop = document.createElement('div');
  backdrop.className = 'drawer-backdrop';
  root.appendChild(backdrop);
  if (!REDUCED) {
    requestAnimationFrame(() => backdrop.classList.add('in'));
  } else {
    backdrop.classList.add('in');
  }
  backdrop.addEventListener('click', () => closeDrawer());

  // 抽屉
  const drawer = document.createElement('aside');
  drawer.className = 'drawer';
  drawer.setAttribute('role', 'dialog');
  drawer.setAttribute('aria-modal', 'true');
  drawer.innerHTML = `
    <header class="drawer-head">
      <div class="dh-left">
        <div class="dh-roman">— ${page} —</div>
        <h3 class="dh-title">${escape(title)}</h3>
        ${subtitle ? `<div class="dh-sub">${escape(subtitle)}</div>` : ''}
      </div>
      <button class="dh-close" aria-label="关闭">×</button>
    </header>
    <div class="drawer-body">${content}</div>
    ${footer ? `<footer class="drawer-foot">${footer}</footer>` : ''}
    <div class="drawer-tail">— 详情页 · DETAIL —</div>
  `;
  root.appendChild(drawer);
  drawer.querySelector('.dh-close').addEventListener('click', () => closeDrawer());

  // 打开动画
  if (!REDUCED) {
    requestAnimationFrame(() => drawer.classList.add('in'));
  } else {
    drawer.classList.add('in');
  }

  // 列表项错开入场
  drawer.querySelectorAll('.drawer-list .item, .drawer-quote, .drawer-kpi').forEach((el, i) => {
    el.classList.add('drawer-row');
    if (!REDUCED) {
      el.style.animationDelay = `${Math.min(i, 12) * 30}ms`;
    }
  });

  // 内部饼图渲染（需要 canvas 已挂载）
  drawer.querySelectorAll('canvas[data-pie]').forEach((c) => {
    try {
      const slices = JSON.parse(c.dataset.pie);
      drawPieChart(c, slices);
    } catch (e) { /* noop */ }
  });
  drawer.querySelectorAll('canvas[data-spark]').forEach((c) => {
    try {
      const data = JSON.parse(c.dataset.spark);
      const series = makeChartSeries(Math.max(24, data.length));
      data.forEach((v) => series.push(v));
      drawSeriesChart(c, series, { label: true });
    } catch (e) { /* noop */ }
  });

  // 数字翻牌
  drawer.querySelectorAll('[data-flip-to]').forEach((el) => {
    flipNumber(el, 0, parseFloat(el.dataset.flipTo), 700);
  });

  // body 锁滚动
  document.body.style.overflow = 'hidden';

  // ESC
  _escListener = (e) => { if (e.key === 'Escape') closeDrawer(); };
  document.addEventListener('keydown', _escListener);

  _drawerNode = drawer;
  _backdropNode = backdrop;
  _drawerOpen = true;
}

export function closeDrawer(animate = true) {
  if (!_drawerOpen) return;
  if (_escListener) {
    document.removeEventListener('keydown', _escListener);
    _escListener = null;
  }
  document.body.style.overflow = '';
  if (_lastPicked) {
    _lastPicked.classList.remove('pick');
    _lastPicked = null;
  }

  const finalize = () => {
    if (_drawerNode) { _drawerNode.remove(); _drawerNode = null; }
    if (_backdropNode) { _backdropNode.remove(); _backdropNode = null; }
    _drawerOpen = false;
  };

  if (animate && !REDUCED && _drawerNode) {
    _drawerNode.classList.add('out');
    _backdropNode && _backdropNode.classList.add('out');
    setTimeout(finalize, 240);
  } else {
    finalize();
  }
}

export function isDrawerOpen() { return _drawerOpen; }

export function markPicked(el) {
  if (_lastPicked && _lastPicked !== el) _lastPicked.classList.remove('pick');
  if (el) {
    el.classList.add('pick');
    _lastPicked = el;
  }
}

// 切 tab 时强制关闭
export function bindTabCloseHook() {
  document.querySelectorAll('.tab').forEach((t) => {
    t.addEventListener('click', () => closeDrawer());
  });
}

// ============================================================
// 2) 辅助工具
// ============================================================
function escape(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function drawerSection(title, body) {
  return `<section class="drawer-section">
    <h4>${escape(title)}</h4>
    <div class="drawer-section-body">${body}</div>
  </section>`;
}

function drawerKpiStrip(items) {
  return `<div class="drawer-kpi-strip">${items.map((it) => `
    <div class="drawer-kpi">
      <div class="l">${escape(it.l)}</div>
      <div class="v" data-flip-to="${it.v}">${it.v}</div>
    </div>`).join('')}</div>`;
}

function drawerList(items, render) {
  return `<div class="drawer-list">${items.map(render).join('')}</div>`;
}

function drawerQuote(text, author, likes) {
  return `<blockquote class="drawer-quote">
    <p>${escape(text)}</p>
    <footer>— ${escape(author || '匿名')}${likes != null ? ` · ♥ ${likes}` : ''}</footer>
  </blockquote>`;
}

function timeAgo(min) {
  if (min < 60) return `${min} 分钟前`;
  if (min < 1440) return `${Math.floor(min / 60)} 小时前`;
  return `${Math.floor(min / 1440)} 天前`;
}

// ============================================================
// 3) 饼图（自绘）
// ============================================================
function drawPieChart(canvas, slices) {
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.round(rect.width * dpr);
  canvas.height = Math.round(rect.height * dpr);
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  const cx = w / 2, cy = h / 2, r = Math.min(w, h) * 0.42;
  const total = slices.reduce((s, x) => s + x.value, 0) || 1;
  let start = -Math.PI / 2;
  slices.forEach((s) => {
    const ang = (s.value / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, r, start, start + ang);
    ctx.closePath();
    ctx.fillStyle = s.color;
    ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.85)';
    ctx.lineWidth = 1.5 * dpr;
    ctx.stroke();
    start += ang;
  });
  // 中心白
  ctx.beginPath();
  ctx.arc(cx, cy, r * 0.55, 0, Math.PI * 2);
  ctx.fillStyle = 'var(--paper-pure)';
  ctx.fill();
  // 中心数字
  ctx.fillStyle = '#1B2A4E';
  ctx.font = `600 ${14 * dpr}px JetBrains Mono, monospace`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(total.toLocaleString(), cx, cy - 4 * dpr);
  ctx.font = `${9 * dpr}px JetBrains Mono, monospace`;
  ctx.fillStyle = 'rgba(27, 42, 78, 0.55)';
  ctx.fillText('TOTAL', cx, cy + 10 * dpr);
}

// ============================================================
// 4) 数据字典（演示用 demo 数据）
// ============================================================
const KPI_DETAIL = {
  rows: {
    name: '累计采集 · COLLECTED',
    summary: '过去 24h 全平台采集吞吐量逐时变化。',
    sub: [
      { l: '24h 增量', v: 2341 },
      { l: '7d 增量', v: 18234 },
      { l: '30d 增量', v: 76421 },
      { l: '人均/小时', v: 1034 },
    ],
    series: [820, 740, 690, 612, 580, 510, 460, 420, 380, 450, 620, 880, 1240, 1380, 1290, 1180, 1340, 1410, 1280, 1160, 980, 880, 1020, 1100],
    text: '当前采集速度较昨日同时段 +12.4%，其中小红书与抖音双平台贡献 64%。',
  },
  jobs: {
    name: '任务数 · JOBS',
    summary: '实时爬取任务在「成功 / 失败 / 排队」三个状态上的分布。',
    sub: [
      { l: '成功', v: 32 },
      { l: '失败', v: 1 },
      { l: '排队', v: 5 },
      { l: '平均耗时', v: '4m12s' },
    ],
    pie: [
      { label: '成功', value: 32, color: '#2E7D32' },
      { label: '排队', value: 5, color: '#8B7355' },
      { label: '失败', value: 1, color: '#8B1A1A' },
    ],
    text: '失败任务集中在知乎反爬触发，建议降低并发到 2/账号。',
  },
  reports: {
    name: '报告 · REPORTS',
    summary: '过去 12 个月报告生成节奏。',
    sub: [
      { l: '本周', v: 6 },
      { l: '本月', v: 17 },
      { l: '热门模板', v: '品牌舆情' },
      { l: '平均字数', v: 3842 },
    ],
    series: [3, 5, 4, 8, 7, 11, 9, 14, 12, 17, 14, 17],
    text: '「品牌舆情」与「趋势追踪」是本月最受欢迎的两类模板。',
  },
  key: {
    name: 'AI Key · STATUS',
    summary: '当前 LLM 配置与调用状态。',
    sub: [
      { l: '模型', v: 'DeepSeek-V3' },
      { l: '今日调用', v: 142 },
      { l: 'Token 用量', v: '1.2M' },
      { l: '状态', v: '正常' },
    ],
    text: 'API Key 已配置并通过最近一次握手验证。剩余额度充足。',
  },
};

const PLATFORM_DETAIL = {
  dianping: {
    name: '大众点评', icon: '评', color: '#FF6633',
    summary: '过去 24h 采集 24,830 条 · 平均 1,034 条/h · 成功率 96%',
    tasks: [
      { time: '14:23', subject: '海底捞 · 五一排队', status: 'done', rows: 234, duration: '4m32s' },
      { time: '13:51', subject: '巴奴毛肚火锅 · 服务', status: 'done', rows: 198, duration: '3m48s' },
      { time: '13:18', subject: '小龙坎 · 生日面', status: 'done', rows: 312, duration: '5m21s' },
      { time: '12:44', subject: '呷哺呷哺 · 翻台率', status: 'failed', rows: 0, duration: '0m12s' },
      { time: '12:09', subject: '海底捞 · 等位时长', status: 'done', rows: 421, duration: '6m12s' },
      { time: '11:32', subject: '珮姐老火锅 · 锅底', status: 'done', rows: 287, duration: '4m45s' },
      { time: '10:58', subject: '海底捞 · 围裙', status: 'done', rows: 198, duration: '3m21s' },
      { time: '10:21', subject: '海底捞 · 服务员', status: 'done', rows: 356, duration: '5m02s' },
      { time: '09:47', subject: '大龙燚 · 鸭血', status: 'done', rows: 264, duration: '4m18s' },
      { time: '09:12', subject: '谭鸭血 · 黄喉', status: 'done', rows: 312, duration: '5m01s' },
    ],
    pie: [
      { label: '成功', value: 38, color: '#2E7D32' },
      { label: '失败', value: 2, color: '#8B1A1A' },
      { label: '排队', value: 5, color: '#8B7355' },
    ],
  },
  meituan: {
    name: '美团', icon: '团', color: '#FFC300',
    summary: '过去 24h 采集 18,420 条 · 平均 768 条/h · 成功率 94%',
    tasks: [
      { time: '14:18', subject: '海底捞 · 套餐销量', status: 'done', rows: 198, duration: '3m48s' },
      { time: '13:42', subject: '巴奴 · 双人套餐', status: 'done', rows: 234, duration: '4m02s' },
      { time: '13:05', subject: '小龙坎 · 4 人套餐', status: 'done', rows: 187, duration: '3m21s' },
      { time: '12:33', subject: '呷哺呷哺 · 代金券', status: 'done', rows: 312, duration: '4m51s' },
      { time: '12:01', subject: '海底捞 · 学生折扣', status: 'failed', rows: 0, duration: '0m08s' },
      { time: '11:24', subject: '珮姐 · 排队等位', status: 'done', rows: 421, duration: '5m32s' },
      { time: '10:48', subject: '大龙燚 · 团购', status: 'done', rows: 264, duration: '4m12s' },
      { time: '10:12', subject: '凑凑 · 工作日午餐', status: 'done', rows: 198, duration: '3m32s' },
      { time: '09:38', subject: '海底捞 · 生日套餐', status: 'done', rows: 156, duration: '2m58s' },
      { time: '09:02', subject: '谭鸭血 · 到店核销', status: 'done', rows: 234, duration: '3m48s' },
    ],
    pie: [
      { label: '成功', value: 22, color: '#2E7D32' },
      { label: '失败', value: 1, color: '#8B1A1A' },
      { label: '排队', value: 3, color: '#8B7355' },
    ],
  },
  douyin: {
    name: '抖音', icon: '抖', color: '#161823',
    summary: '过去 24h 采集 12,840 条 · 平均 535 条/h · 成功率 92%',
    tasks: [
      { time: '14:09', subject: '#深夜火锅# 探店', status: 'done', rows: 142, duration: '2m48s' },
      { time: '13:32', subject: '海底捞 · 服务测评', status: 'done', rows: 198, duration: '3m21s' },
      { time: '13:01', subject: '巴奴 · 毛肚现场涮', status: 'failed', rows: 0, duration: '0m22s' },
      { time: '12:28', subject: '小龙坎 · 锅底测评', status: 'done', rows: 87, duration: '1m48s' },
      { time: '11:54', subject: '海底捞 · 生日面 vlog', status: 'done', rows: 234, duration: '3m52s' },
      { time: '11:18', subject: '大龙燚 · 排队日常', status: 'done', rows: 312, duration: '4m48s' },
      { time: '10:42', subject: '海底捞 · 等位送果盘', status: 'done', rows: 187, duration: '3m12s' },
      { time: '10:08', subject: '呷哺呷哺 · 1 人食', status: 'done', rows: 156, duration: '2m42s' },
      { time: '09:35', subject: '珮姐 · 抖音团购', status: 'done', rows: 198, duration: '3m18s' },
      { time: '09:01', subject: '海底捞 · 美甲服务', status: 'done', rows: 264, duration: '4m12s' },
    ],
    pie: [
      { label: '成功', value: 18, color: '#2E7D32' },
      { label: '失败', value: 1, color: '#8B1A1A' },
      { label: '排队', value: 2, color: '#8B7355' },
    ],
  },
  xiaohongshu: {
    name: '小红书', icon: '红', color: '#FF2442',
    summary: '过去 24h 采集 9,640 条 · 平均 402 条/h · 成功率 90%',
    tasks: [
      { time: '14:12', subject: '海底捞 · 隐藏吃法', status: 'done', rows: 198, duration: '2m18s' },
      { time: '13:42', subject: '巴奴 · 菌汤锅底', status: 'done', rows: 234, duration: '2m48s' },
      { time: '13:08', subject: '小龙坎 · 鸳鸯锅', status: 'done', rows: 187, duration: '2m12s' },
      { time: '12:38', subject: '海底捞 · 自助蘸料', status: 'done', rows: 156, duration: '1m52s' },
      { time: '12:01', subject: '呷哺呷哺 · 学生党', status: 'failed', rows: 0, duration: '0m14s' },
      { time: '11:24', subject: '凑凑 · 奶茶火锅', status: 'done', rows: 264, duration: '3m08s' },
      { time: '10:48', subject: '海底捞 · 围裙拍照', status: 'done', rows: 198, duration: '2m32s' },
      { time: '10:12', subject: '珮姐 · 复古装修', status: 'done', rows: 234, duration: '2m48s' },
      { time: '09:35', subject: '大龙燚 · 辣度挑战', status: 'done', rows: 187, duration: '2m18s' },
      { time: '09:01', subject: '谭鸭血 · 现切现涮', status: 'done', rows: 156, duration: '1m58s' },
    ],
    pie: [
      { label: '成功', value: 15, color: '#2E7D32' },
      { label: '失败', value: 1, color: '#8B1A1A' },
      { label: '排队', value: 2, color: '#8B7355' },
    ],
  },
  tmall: {
    name: '天猫', icon: '猫', color: '#FF0036',
    summary: '过去 24h 采集 8,920 条 · 平均 372 条/h · 成功率 95%',
    tasks: [
      { time: '14:21', subject: '牛油底料 · 销量榜', status: 'done', rows: 142, duration: '2m48s' },
      { time: '13:48', subject: '海底捞自热小火锅', status: 'done', rows: 198, duration: '3m21s' },
      { time: '13:18', subject: '鸳鸯锅 · 304 钢', status: 'done', rows: 234, duration: '3m52s' },
      { time: '12:42', subject: '电磁炉 · 嵌入式', status: 'done', rows: 187, duration: '3m08s' },
      { time: '12:08', subject: '海底捞 · 调味料', status: 'done', rows: 264, duration: '4m12s' },
      { time: '11:34', subject: '呷哺呷哺 · 速食', status: 'done', rows: 156, duration: '2m42s' },
      { time: '10:58', subject: '小龙坎 · 底料包', status: 'done', rows: 198, duration: '3m18s' },
      { time: '10:22', subject: '巴奴 · 毛肚速冻', status: 'done', rows: 234, duration: '3m48s' },
      { time: '09:48', subject: '海底捞 · 蘸料', status: 'done', rows: 187, duration: '3m02s' },
      { time: '09:12', subject: '谭鸭血 · 鸭血零食', status: 'done', rows: 156, duration: '2m38s' },
    ],
    pie: [
      { label: '成功', value: 14, color: '#2E7D32' },
      { label: '失败', value: 0, color: '#8B1A1A' },
      { label: '排队', value: 2, color: '#8B7355' },
    ],
  },
  zhihu: {
    name: '知乎', icon: '知', color: '#0084FF',
    summary: '过去 24h 采集 6,420 条 · 平均 268 条/h · 成功率 89%',
    tasks: [
      { time: '14:08', subject: '海底捞 · 服务体验', status: 'done', rows: 142, duration: '2m48s' },
      { time: '13:32', subject: '巴奴 · 食材差异', status: 'done', rows: 198, duration: '3m21s' },
      { time: '13:01', subject: '小龙坎 · 加盟模式', status: 'done', rows: 87, duration: '1m48s' },
      { time: '12:28', subject: '呷哺呷哺 · 翻台率', status: 'failed', rows: 0, duration: '0m18s' },
      { time: '11:54', subject: '海底捞 · 蘸料配方', status: 'done', rows: 234, duration: '3m52s' },
      { time: '11:18', subject: '大龙燚 · 锅底工艺', status: 'done', rows: 187, duration: '3m12s' },
      { time: '10:42', subject: '海底捞 · 食品安全', status: 'done', rows: 264, duration: '4m18s' },
      { time: '10:08', subject: '凑凑 · 奶茶融合', status: 'done', rows: 156, duration: '2m42s' },
      { time: '09:35', subject: '海底捞 · 生日面来源', status: 'done', rows: 198, duration: '3m18s' },
      { time: '09:01', subject: '珮姐老火锅 · 起源', status: 'done', rows: 234, duration: '3m48s' },
    ],
    pie: [
      { label: '成功', value: 10, color: '#2E7D32' },
      { label: '失败', value: 1, color: '#8B1A1A' },
      { label: '排队', value: 1, color: '#8B7355' },
    ],
  },
  weibo: {
    name: '微博', icon: '微', color: '#E6162D',
    summary: '过去 24h 采集 5,820 条 · 平均 242 条/h · 成功率 91%',
    tasks: [
      { time: '14:18', subject: '#深夜火锅# 热搜', status: 'done', rows: 142, duration: '2m18s' },
      { time: '13:42', subject: '海底捞 · 服务争议', status: 'done', rows: 198, duration: '2m48s' },
      { time: '13:08', subject: '巴奴 · 涨价讨论', status: 'done', rows: 234, duration: '3m02s' },
      { time: '12:34', subject: '小龙坎 · 加盟商维权', status: 'done', rows: 187, duration: '2m32s' },
      { time: '12:01', subject: '呷哺呷哺 · 翻台', status: 'failed', rows: 0, duration: '0m22s' },
      { time: '11:24', subject: '海底捞 · 等位体验', status: 'done', rows: 264, duration: '3m12s' },
      { time: '10:48', subject: '珮姐 · 重庆网红', status: 'done', rows: 198, duration: '2m42s' },
      { time: '10:12', subject: '大龙燚 · 成都发源', status: 'done', rows: 234, duration: '2m58s' },
      { time: '09:35', subject: '海底捞 · 美甲师', status: 'done', rows: 156, duration: '2m12s' },
      { time: '09:02', subject: '谭鸭血 · 鸭血真假', status: 'done', rows: 187, duration: '2m32s' },
    ],
    pie: [
      { label: '成功', value: 9, color: '#2E7D32' },
      { label: '失败', value: 1, color: '#8B1A1A' },
      { label: '排队', value: 2, color: '#8B7355' },
    ],
  },
  web: {
    name: '通用网页', icon: '网', color: '#1B2A4E',
    summary: '过去 24h 采集 4,920 条 · 平均 205 条/h · 成功率 87%',
    tasks: [
      { time: '14:12', subject: '海底捞官网 · 菜单更新', status: 'done', rows: 87, duration: '1m48s' },
      { time: '13:42', subject: '巴奴官网 · 门店查询', status: 'done', rows: 142, duration: '2m21s' },
      { time: '13:08', subject: '小龙坎 · 加盟页', status: 'done', rows: 198, duration: '2m52s' },
      { time: '12:34', subject: '呷哺呷哺 · 财报', status: 'done', rows: 156, duration: '2m18s' },
      { time: '12:01', subject: '海底捞 · 食品安全报告', status: 'failed', rows: 0, duration: '0m28s' },
      { time: '11:24', subject: '珮姐 · 媒体采访', status: 'done', rows: 187, duration: '2m42s' },
      { time: '10:48', subject: '大龙燚 · 品牌故事', status: 'done', rows: 134, duration: '2m02s' },
      { time: '10:12', subject: '海底捞 · 招聘信息', status: 'done', rows: 198, duration: '2m48s' },
      { time: '09:35', subject: '凑凑 · 母公司新闻', status: 'done', rows: 156, duration: '2m18s' },
      { time: '09:01', subject: '谭鸭血 · 创始人专访', status: 'done', rows: 142, duration: '2m08s' },
    ],
    pie: [
      { label: '成功', value: 7, color: '#2E7D32' },
      { label: '失败', value: 1, color: '#8B1A1A' },
      { label: '排队', value: 1, color: '#8B7355' },
    ],
  },
};

const WORD_DETAIL = {
  '海底捞': {
    count: 3124, sentiment: '正面 78% · 中性 16% · 负面 6%',
    trend: [12, 18, 24, 32, 28, 38, 45, 52, 68, 82, 96, 118, 142, 158, 142, 128, 134, 142, 128, 112, 98, 84, 76, 68],
    quotes: [
      { text: '海底捞的服务真的没得说，围裙、手机套、发圈全给你准备好。', author: '@吃货小张', likes: 312 },
      { text: '等位两小时也值了，锅底和毛肚都很新鲜。', author: '@排队的我', likes: 198 },
      { text: '生日面是真的有仪式感，寿星免费送。', author: '@小寿星', likes: 176 },
      { text: '价格偏贵，但体验值这个价。', author: '@性价比党', likes: 142 },
      { text: '服务员小哥哥真的太热情了，有点招架不住。', author: '@害羞的汤圆', likes: 98 },
    ],
  },
  '服务': {
    count: 2847, sentiment: '正面 84% · 中性 12% · 负面 4%',
    trend: [8, 12, 18, 24, 32, 38, 48, 56, 72, 88, 96, 112, 128, 142, 132, 118, 124, 128, 116, 102, 88, 78, 68, 58],
    quotes: [
      { text: '服务员看到茶水没了立刻就来加，细节到位。', author: '@细节控', likes: 234 },
      { text: '服务员全程微笑，过生日还给我唱生日歌。', author: '@过生日的小王', likes: 198 },
      { text: '服务比海底捞还要好，简直是火锅界的海底捞。', author: '@探店达人', likes: 156 },
      { text: '服务员手脚麻利，加汤换盘都很勤快。', author: '@常客老李', likes: 134 },
    ],
  },
  '排队': {
    count: 2138, sentiment: '正面 42% · 中性 28% · 负面 30%',
    trend: [4, 6, 10, 16, 22, 30, 38, 48, 58, 68, 78, 88, 96, 102, 98, 88, 92, 96, 86, 76, 66, 58, 48, 40],
    quotes: [
      { text: '周五晚上 6 点半取号，前面 38 桌，等了 2 小时。', author: '@周五晚餐', likes: 312 },
      { text: '等位的时候送果盘和小游戏，体验加分。', author: '@会吃的阿吉', likes: 198 },
      { text: '周末基本要排队，建议工作日去。', author: '@理智食客', likes: 156 },
      { text: '排队两小时进店 5 分钟吃完，太赶了。', author: '@赶时间的V', likes: 142 },
    ],
  },
  '毛肚': {
    count: 1872, sentiment: '正面 81% · 中性 14% · 负面 5%',
    trend: [4, 8, 12, 18, 24, 32, 42, 52, 64, 78, 92, 108, 118, 128, 122, 108, 112, 118, 104, 92, 78, 68, 58, 48],
    quotes: [
      { text: '毛肚七上八下涮出来最嫩，巴奴的毛肚确实不一样。', author: '@火锅老饕', likes: 248 },
      { text: '涮毛肚要 15 秒，时间过了就老了。', author: '@厨房小白', likes: 187 },
      { text: '毛肚一份 88 元偏贵，但口感值得。', author: '@品鉴家', likes: 142 },
      { text: '冰镇毛肚和现切毛肚不一样，强烈推荐现切。', author: '@现切达人', likes: 128 },
    ],
  },
  '锅底': {
    count: 1654, sentiment: '正面 76% · 中性 18% · 负面 6%',
    trend: [4, 6, 10, 16, 22, 30, 38, 48, 58, 68, 78, 88, 96, 102, 98, 88, 92, 96, 86, 76, 66, 58, 48, 40],
    quotes: [
      { text: '牛油锅底越煮越香，吃完衣服全是味。', author: '@香喷喷的我', likes: 198 },
      { text: '鸳鸯锅底一边辣一边菌汤，老人小孩都照顾到。', author: '@家庭聚餐', likes: 176 },
      { text: '锅底偏咸，建议少喝汤。', author: '@清淡党', likes: 142 },
      { text: '番茄锅底涮肥牛绝了，酸甜开胃。', author: '@番茄控', likes: 128 },
    ],
  },
  '麻辣': {
    count: 1432, sentiment: '正面 72% · 中性 16% · 负面 12%',
    trend: [2, 4, 8, 14, 20, 28, 36, 46, 58, 68, 78, 86, 96, 102, 96, 88, 92, 96, 88, 76, 66, 56, 48, 38],
    quotes: [
      { text: '麻辣锅底涮鸭血一绝，越煮越入味。', author: '@辣不怕', likes: 198 },
      { text: '微辣就够我吃三碗饭。', author: '@南方妹子', likes: 156 },
      { text: '麻辣度可以选，建议新手点微辣。', author: '@重庆妹子', likes: 142 },
    ],
  },
  '鸳鸯锅': {
    count: 1287, sentiment: '正面 86% · 中性 12% · 负面 2%',
    trend: [2, 4, 6, 10, 16, 22, 28, 36, 44, 54, 62, 72, 82, 88, 84, 76, 80, 84, 76, 66, 58, 48, 40, 32],
    quotes: [
      { text: '鸳鸯锅是我的最爱，辣和不辣都能满足。', author: '@折中的胃', likes: 198 },
      { text: '一锅两味太实用了，带不能吃辣的爸妈来。', author: '@孝顺儿女', likes: 176 },
      { text: '清汤那边可以涮蔬菜，营养均衡。', author: '@养生党', likes: 142 },
    ],
  },
  '性价比': {
    count: 1198, sentiment: '正面 64% · 中性 22% · 负面 14%',
    trend: [1, 2, 4, 8, 14, 20, 28, 36, 46, 56, 64, 72, 80, 86, 82, 74, 78, 82, 74, 64, 56, 46, 38, 30],
    quotes: [
      { text: '人均 150 元，比海底捞便宜很多。', author: '@学生党', likes: 198 },
      { text: '呷哺呷哺性价比最高，1 人食首选。', author: '@独食者', likes: 156 },
      { text: '海底捞偏贵，但服务值这个价。', author: '@消费观', likes: 134 },
    ],
  },
  '蘸料': {
    count: 1056, sentiment: '正面 78% · 中性 18% · 负面 4%',
    trend: [1, 2, 4, 6, 10, 14, 20, 26, 32, 40, 48, 56, 62, 68, 64, 58, 60, 64, 56, 48, 42, 34, 28, 22],
    quotes: [
      { text: '自助蘸料 8 元一位，麻酱 + 蒜泥 + 香菜是绝配。', author: '@蘸料艺术家', likes: 176 },
      { text: '油碟蘸料是川渝火锅的灵魂。', author: '@重庆人', likes: 142 },
      { text: '海底捞蘸料台丰富，水果也随便吃。', author: '@水果爱好者', likes: 128 },
    ],
  },
  '牛肉': {
    count: 968, sentiment: '正面 75% · 中性 18% · 负面 7%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '手切鲜牛肉现切现涮，每片都看得见纹路。', author: '@牛肉控', likes: 198 },
      { text: '肥牛卷涮 8 秒就熟，蘸麻酱超香。', author: '@涮肉行家', likes: 156 },
    ],
  },
  '虾滑': {
    count: 856, sentiment: '正面 82% · 中性 14% · 负面 4%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '手打虾滑 Q 弹，涮 1 分钟最嫩。', author: '@海鲜爱好者', likes: 156 },
      { text: '海底捞的虾滑配鱼子，绝配。', author: '@创意吃货', likes: 128 },
    ],
  },
  '环境': {
    count: 752, sentiment: '正面 70% · 中性 24% · 负面 6%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '珮姐老火锅装修有 80 年代重庆风格，氛围感拉满。', author: '@怀旧党', likes: 156 },
      { text: '海底捞灯光柔和，适合聚餐聊天。', author: '@家庭主妇', likes: 128 },
    ],
  },
  '服务员': {
    count: 698, sentiment: '正面 80% · 中性 14% · 负面 6%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '服务员小哥哥 5 分钟过来问 3 次需要加汤吗。', author: '@被照顾的我', likes: 142 },
      { text: '海底捞服务员会主动给小朋友送玩具。', author: '@带孩子的小王', likes: 128 },
    ],
  },
  '呷哺呷哺': {
    count: 642, sentiment: '正面 64% · 中性 24% · 负面 12%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '呷哺呷哺人均 70 元，学生党首选。', author: '@预算党', likes: 156 },
      { text: '呷哺呷哺 1 人食吧台设计太方便了。', author: '@独居青年', likes: 128 },
    ],
  },
  '小龙坎': {
    count: 587, sentiment: '正面 72% · 中性 18% · 负面 10%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '小龙坎牛油锅底浓郁，加汤要加老荫茶。', author: '@川渝胃', likes: 142 },
      { text: '小龙坎加盟商太多了，品控有点参差。', author: '@老食客', likes: 128 },
    ],
  },
  '巴奴': {
    count: 528, sentiment: '正面 81% · 中性 14% · 负面 5%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '巴奴毛肚 + 菌汤是绝配，食材差异化做得好。', author: '@食材主义者', likes: 198 },
      { text: '巴奴价格偏高，但确实吃得到好食材。', author: '@品质党', likes: 142 },
    ],
  },
  '大龙燚': {
    count: 478, sentiment: '正面 70% · 中性 22% · 负面 8%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '大龙燚成都发源，正宗川渝麻辣。', author: '@辣妹子', likes: 128 },
      { text: '大龙燚排队日常，工作日也很多人。', author: '@常客', likes: 98 },
    ],
  },
  '凑凑': {
    count: 432, sentiment: '正面 76% · 中性 18% · 负面 6%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '凑凑奶茶 + 火锅是创意组合，茶米茶超好喝。', author: '@奶茶火锅', likes: 198 },
      { text: '凑凑环境时尚，适合年轻人聚会。', author: '@95后', likes: 142 },
    ],
  },
  '谭鸭血': {
    count: 398, sentiment: '正面 73% · 中性 18% · 负面 9%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '谭鸭血开锅仪式很特别，要先解封再煮。', author: '@仪式感党', likes: 142 },
      { text: '鸭血嫩滑无腥味，确实和别家不一样。', author: '@鸭血品鉴', likes: 128 },
    ],
  },
  '珮姐': {
    count: 365, sentiment: '正面 78% · 中性 16% · 负面 6%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '珮姐重庆老火锅，9 宫格锅底很地道。', author: '@重庆妹子', likes: 198 },
      { text: '珮姐复古装修像 80 年代重庆，防空洞设计。', author: '@怀旧党', likes: 142 },
    ],
  },
  '排队两小时': {
    count: 342, sentiment: '正面 38% · 中性 24% · 负面 38%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '排队两小时进店 5 分钟吃完，建议错峰。', author: '@后悔党', likes: 198 },
      { text: '排队两小时值了，等位有果盘有跳棋。', author: '@会吃的', likes: 156 },
    ],
  },
  '等位': {
    count: 318, sentiment: '正面 56% · 中性 24% · 负面 20%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '等位送果盘送小零食，海底捞永远的神。', author: '@海底捞粉', likes: 156 },
      { text: '等位 30 分钟到 1 小时是常态。', author: '@周末党', likes: 128 },
    ],
  },
  '鸭血': {
    count: 287, sentiment: '正面 76% · 中性 18% · 负面 6%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '鸭血涮 2 分钟最嫩，谭鸭血必点。', author: '@鸭血控', likes: 128 },
    ],
  },
  '黄喉': {
    count: 256, sentiment: '正面 78% · 中性 16% · 负面 6%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '黄喉脆爽，涮 30 秒最佳。', author: '@脆爽党', likes: 128 },
    ],
  },
  '午餐肉': {
    count: 234, sentiment: '正面 72% · 中性 22% · 负面 6%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '午餐肉厚切涮出来外焦里嫩。', author: '@厚切爱好者', likes: 98 },
    ],
  },
  '金针菇': {
    count: 218, sentiment: '正面 70% · 中性 24% · 负面 6%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '金针菇要卷成卷涮，不然夹不住。', author: '@厨房小白', likes: 88 },
    ],
  },
  '土豆片': {
    count: 198, sentiment: '正面 80% · 中性 16% · 负面 4%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '土豆片要切超薄才好吃，3 秒就熟。', author: '@刀工党', likes: 98 },
    ],
  },
  '等位送果盘': {
    count: 178, sentiment: '正面 92% · 中性 6% · 负面 2%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '等位送果盘送跳棋，海底捞服务天花板。', author: '@被宠的食客', likes: 156 },
    ],
  },
  '围裙': {
    count: 156, sentiment: '正面 88% · 中性 10% · 负面 2%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '海底捞围裙拍照发小红书太出片了。', author: '@拍照党', likes: 142 },
    ],
  },
  '生日面': {
    count: 142, sentiment: '正面 96% · 中性 3% · 负面 1%',
    trend: [1, 2, 4, 6, 8, 12, 18, 24, 30, 38, 46, 54, 60, 66, 62, 56, 58, 62, 54, 46, 40, 32, 26, 20],
    quotes: [
      { text: '生日面真的有仪式感，寿星免费送。', author: '@小寿星', likes: 198 },
    ],
  },
};

const REPORT_DETAIL = {
  '海底捞 · 五一期间排队舆情分析': {
    meta: { date: '2026-05-30 14:23', rows: 18420, model: 'DeepSeek-V3', duration: '8m32s' },
    body: `**核心发现**

1. **海底捞** 五一期间累计被提及 **28,420** 次
2. **负面率 14.8%**，主要来自"等位 2 小时"话题
3. **小红书** 增速最快，环比 +34%

**情感分布**

· 正面 71.4% · 中性 13.8% · 负面 14.8%

**Top 5 话题词**

| # | 词 | 频次 | 情感 |
|---|---|---|---|
| 1 | 海底捞 | 3,124 | 正面 78% |
| 2 | 服务 | 2,847 | 正面 84% |
| 3 | 排队 | 2,138 | 中性 28% |
| 4 | 毛肚 | 1,872 | 正面 81% |
| 5 | 锅底 | 1,654 | 正面 76% |

**关键意见领袖 Top 3**

1. @吃货小张 — 互动 24.8K
2. @探店达人 — 互动 18.2K
3. @排队日常 — 互动 14.6K

**行动建议**

· 强化「等位送果盘 + 跳棋」心智
· 主推「生日面」免费仪式
· 借势「等位 30 分钟内」体验营销`,
    sections: ['核心发现', '情感分布', 'Top 5 话题词', 'KOL 识别', '行动建议'],
  },
  '小红书 · 锅底种草笔记 · Top 50': {
    meta: { date: '2026-05-29 11:08', rows: 9380, model: 'DeepSeek-V3', duration: '6m12s' },
    body: `**生命周期**

当前话题处于 **爆发期**。建议把握 1-2 周窗口期。

**预测**

· 1 周内热度 +28%
· 2 周后进入「成熟期」

**锅底 Top 3**

1. **牛油麻辣** 4.2K 收藏
2. **番茄锅底** 3.8K 收藏
3. **鸳鸯锅** 3.1K 收藏

**演化路径**

| 阶段 | 时间 | 热度 |
|---|---|---|
| 萌芽 | 04-15 | 12% |
| 成长 | 04-28 | 38% |
| 爆发 | 05-15 | 89% |
| 成熟 | 05-29 | 100% |`,
    sections: ['生命周期', '预测', '锅底 Top 3', '演化路径'],
  },
  '大众点评 · 4.5 星以上门店对比': {
    meta: { date: '2026-05-28 16:42', rows: 15221, model: 'DeepSeek-V3', duration: '5m24s' },
    body: `**品牌横评 · 4.5 星以上火锅门店**

| 品牌 | 门店数 | 平均评分 | 提及数 |
|---|---|---|---|
| 海底捞 | 1,243 | 4.7 | 28,420 |
| 巴奴 | 89 | 4.8 | 8,142 |
| 小龙坎 | 612 | 4.5 | 12,184 |
| 呷哺呷哺 | 845 | 4.6 | 9,820 |

**差异化洞察**

· 海底捞胜在「服务天花板」
· 巴奴胜在「食材差异化」
· 小龙坎胜在「加盟规模」
· 呷哺呷哺胜在「1 人食 + 性价比」`,
    sections: ['品牌横评', '差异化洞察'],
  },
  '抖音 · 探店直播互动率 · 季度': {
    meta: { date: '2026-05-27 19:15', rows: 6420, model: 'DeepSeek-V3', duration: '4m48s' },
    body: `**季度走势**

Q2 探店直播互动率环比 +18%。

**Top 5 直播间**

| 排名 | 直播间 | 互动率 |
|---|---|---|
| 1 | 海底捞官方 | 12.4% |
| 2 | 巴奴毛肚火锅 | 9.8% |
| 3 | 小龙坎 | 7.2% |
| 4 | 珮姐老火锅 | 5.6% |
| 5 | 大龙燚 | 4.8% |

**价位段**

· 100 元以下：呷哺呷哺 / 大龙燚
· 100-200 元：海底捞 / 小龙坎
· 200 元以上：巴奴 / 凑凑`,
    sections: ['季度走势', 'Top 5 直播间', '价位段'],
  },
  '微博 · #深夜火锅# 话题趋势': {
    meta: { date: '2026-05-26 10:33', rows: 9341, model: 'DeepSeek-V3', duration: '4m02s' },
    body: `**核心发现**

· 话题 #深夜火锅# 阅读量 **2.4 亿**
· 讨论量 38.6 万
· 原创比例 22%

**情感倾向**

· 正面 71% · 中性 22% · 负面 7%

**媒体来源分布**

· 用户 64% · 媒体 18% · 政府 4% · 其他 14%`,
    sections: ['核心发现', '情感倾向', '媒体来源分布'],
  },
  '天猫 · 牛油底料销量榜 · 6 月': {
    meta: { date: '2026-05-25 15:48', rows: 4512, model: 'DeepSeek-V3', duration: '3m36s' },
    body: `**6 月销量榜**

| 品牌 | 销量 | 好评率 | 价格带 |
|---|---|---|---|
| 海底捞自热 | 142K | 96% | ¥29-89 |
| 小龙坎底料 | 168K | 94% | ¥19-79 |
| 巴奴毛肚 | 87K | 91% | ¥39-129 |
| 大龙燚 | 98K | 89% | ¥25-89 |

**复购率**

海底捞 38% > 小龙坎 32% > 大龙燚 24% > 巴奴 18%`,
    sections: ['6 月销量榜', '复购率'],
  },
  '美团 · 等位时长城市排行': {
    meta: { date: '2026-05-30 18:42', rows: 1832, model: 'DeepSeek-V3', duration: '2m14s' },
    body: `**Top 10 城市等位时长**

| 排名 | 城市 | 平均等位 |
|---|---|---|
| 1 | 上海 | 138 分钟 |
| 2 | 北京 | 124 分钟 |
| 3 | 广州 | 116 分钟 |
| 4 | 成都 | 98 分钟 |
| 5 | 杭州 | 92 分钟 |
| 6 | 深圳 | 88 分钟 |
| 7 | 重庆 | 76 分钟 |
| 8 | 武汉 | 72 分钟 |
| 9 | 西安 | 64 分钟 |
| 10 | 南京 | 58 分钟 |

**洞察**

· 一线城市等位压力最大
· 川渝城市等位较短（火锅供给充足）`,
    sections: ['Top 10 城市', '洞察'],
  },
  '知乎 · 海底捞服务体验问答': {
    meta: { date: '2026-05-30 14:08', rows: 4512, model: 'DeepSeek-V3', duration: '1m48s' },
    body: `**核心问答 Top 3**

1. **"海底捞服务为什么好？"** — 142 个回答，赞同 8.2K
2. **"海底捞的服务员要做什么培训？"** — 89 个回答，赞同 5.6K
3. **"海底捞等位 2 小时值得吗？"** — 67 个回答，赞同 3.8K

**头部 KOL Top 5**

| 排名 | KOL | 粉丝 | 互动 |
|---|---|---|---|
| 1 | @海底捞研究所 | 248K | 24.8K |
| 2 | @服务体验官 | 142K | 18.2K |
| 3 | @餐饮观察 | 89K | 14.6K |
| 4 | @排队经济学 | 67K | 9.8K |
| 5 | @细节控 | 48K | 5.6K |`,
    sections: ['核心问答', '头部 KOL'],
  },
  'B 站 · 火锅蘸料 vlog 评测': {
    meta: { date: '2026-05-30 09:32', rows: 3124, model: 'DeepSeek-V3', duration: '2m32s' },
    body: `**Top 5 蘸料配方**

1. **麻酱 + 蒜泥 + 香菜 + 腐乳** — 4.8K 收藏
2. **油碟 + 香油 + 蒜泥 + 葱花** — 4.2K 收藏
3. **海鲜汁 + 蚝油 + 香菜 + 小米辣** — 3.6K 收藏
4. **番茄酱 + 辣椒酱 + 蒜泥** — 2.8K 收藏
5. **芝麻酱 + 辣油 + 葱花 + 花生碎** — 2.4K 收藏

**Top 3 视频**

| 排名 | UP主 | 播放 |
|---|---|---|
| 1 | @蘸料艺术家 | 124K |
| 2 | @火锅老饕 | 98K |
| 3 | @重庆人老王 | 76K |`,
    sections: ['Top 5 蘸料', 'Top 3 视频'],
  },
};

// ============================================================
// 5) 6 个内容渲染器
// ============================================================

// --- 5.1 KPI ---
export function renderKpiDetail(kpiKey) {
  const d = KPI_DETAIL[kpiKey];
  if (!d) return { title: '未知 KPI', content: '' };
  const page = kpiKey === 'rows' ? 'I'
    : kpiKey === 'jobs' ? 'II'
    : kpiKey === 'reports' ? 'III'
    : 'IV';
  let body = drawerSection('摘要', `<p class="ds-text">${escape(d.summary)}</p>`);
  body += drawerSection('子指标', drawerKpiStrip(d.sub.map((s) => ({
    l: s.l, v: typeof s.v === 'number' ? s.v.toLocaleString() : s.v,
  }))));
  if (d.series) {
    body += drawerSection('时序 · 24h', `
      <div class="drawer-spark-wrap">
        <canvas data-spark='${JSON.stringify(d.series)}'></canvas>
      </div>
    `);
  }
  if (d.pie) {
    body += drawerSection('状态分布', `
      <div class="drawer-pie-row">
        <div class="drawer-pie-wrap">
          <canvas data-pie='${JSON.stringify(d.pie)}'></canvas>
        </div>
        <ul class="drawer-pie-legend">
          ${d.pie.map((s) => `<li><span class="dot" style="background:${s.color}"></span>${escape(s.label)} <strong>${s.value}</strong></li>`).join('')}
        </ul>
      </div>
    `);
  }
  body += drawerSection('解读', `<p class="ds-text">${escape(d.text)}</p>`);
  return {
    title: d.name,
    subtitle: `KPI ${page} · SITUATIONAL`,
    content: body,
    page,
  };
}

// --- 5.2 平台 ---
export function renderPlatformDetail(platformKey) {
  const d = PLATFORM_DETAIL[platformKey];
  if (!d) return { title: '未知平台', content: '' };
  const pageMap = { dianping: 'I', meituan: 'II', douyin: 'III', xiaohongshu: 'IV', tmall: 'V', zhihu: 'VI', weibo: 'VII', web: 'VIII' };
  const page = pageMap[platformKey] || 'I';

  let body = drawerSection('平台概览', `
    <div class="ds-platform-hero">
      <div class="ds-pi" style="background:${d.color}">${d.icon}</div>
      <div>
        <div class="ds-pn">${escape(d.name)}</div>
        <div class="ds-ps">${escape(d.summary)}</div>
      </div>
    </div>
  `);

  body += drawerSection('状态分布', `
    <div class="drawer-pie-row">
      <div class="drawer-pie-wrap">
        <canvas data-pie='${JSON.stringify(d.pie)}'></canvas>
      </div>
      <ul class="drawer-pie-legend">
        ${d.pie.map((s) => `<li><span class="dot" style="background:${s.color}"></span>${escape(s.label)} <strong>${s.value}</strong></li>`).join('')}
      </ul>
    </div>
  `);

  body += drawerSection(`24h 任务流 · ${d.tasks.length} 条`, drawerList(d.tasks, (t) => {
    const statusCls = t.status === 'done' ? 'ok' : t.status === 'failed' ? 'fail' : 'queue';
    const statusText = t.status === 'done' ? '✓ 成功' : t.status === 'failed' ? '✗ 失败' : '… 排队';
    return `<div class="item task-item">
      <div class="ti">${escape(t.time)}</div>
      <div class="subj">${escape(t.subject)}</div>
      <div class="meta">
        <span class="status ${statusCls}">${statusText}</span>
        <span>${t.rows.toLocaleString()} 条</span>
        <span>${escape(t.duration)}</span>
      </div>
    </div>`;
  }));

  return {
    title: d.name,
    subtitle: `PLATFORM ${page} · ${d.tasks.length} TASKS · 24H`,
    content: body,
    page,
    footer: `<button class="btn btn-ghost">查看更多 →</button><button class="btn btn-primary">重新采集</button>`,
  };
}

// --- 5.3 词云词 ---
export function renderWordDetail(word, count) {
  const d = WORD_DETAIL[word] || {
    count: count || Math.floor(Math.random() * 200) + 50,
    sentiment: '正面 70% · 中性 24% · 负面 6%',
    trend: Array.from({ length: 24 }, (_, i) => Math.floor(Math.random() * 80) + 10),
    quotes: [
      { text: `关于"${word}"用户提到了相关场景。`, author: '@用户 A', likes: 124 },
      { text: `"${word}"是近期高频出现的关键词。`, author: '@用户 B', likes: 96 },
      { text: `评论区多次出现"${word}"相关讨论。`, author: '@用户 C', likes: 78 },
    ],
  };
  const idx = Object.keys(WORD_DETAIL).indexOf(word);
  const page = ROMAN[Math.max(0, idx)] || 'I';

  let body = drawerSection('关键词', `
    <div class="drawer-word-hero">
      <div class="dwh-word">${escape(word)}</div>
      <div class="dwh-meta">
        <div class="dwh-count">${d.count.toLocaleString()}</div>
        <div class="dwh-label">次提及 · MENTIONS</div>
      </div>
    </div>
  `);

  body += drawerSection('情感倾向', `<p class="ds-text">${escape(d.sentiment)}</p>`);

  body += drawerSection('出现时序 · 24h', `
    <div class="drawer-spark-wrap">
      <canvas data-spark='${JSON.stringify(d.trend)}'></canvas>
    </div>
  `);

  body += drawerSection(`代表性评论 · ${d.quotes.length} 条`, drawerList(d.quotes, (q) => drawerQuote(q.text, q.author, q.likes)));

  return {
    title: `"${word}"`,
    subtitle: `WORD ${page} · ${d.count.toLocaleString()} MENTIONS`,
    content: body,
    page,
  };
}

// --- 5.4 报告 ---
export function renderReportDetail(report) {
  const d = REPORT_DETAIL[report.title] || {
    meta: { date: report.date || '2026-05-30', rows: 8000, model: 'DeepSeek-V3', duration: '3m00s' },
    body: report.body || `**${escape(report.title)}**\n\n基于 ${report.rows || 8000} 条数据的分析报告。\n\n**核心发现**\n\n1. 数据呈正态分布\n2. 关键话题集中在 5 个\n3. 情感倾向以正面为主`,
    sections: ['核心发现'],
  };
  const idx = Object.keys(REPORT_DETAIL).indexOf(report.title);
  const page = ROMAN[Math.max(0, idx)] || 'I';

  let body = drawerSection('报告元信息', `
    <div class="ds-meta-grid">
      <div class="ds-meta-item"><span class="l">日期</span><span class="v">${escape(d.meta.date)}</span></div>
      <div class="ds-meta-item"><span class="l">数据量</span><span class="v">${d.meta.rows.toLocaleString()} 条</span></div>
      <div class="ds-meta-item"><span class="l">模型</span><span class="v">${escape(d.meta.model)}</span></div>
      <div class="ds-meta-item"><span class="l">耗时</span><span class="v">${escape(d.meta.duration)}</span></div>
    </div>
  `);

  body += drawerSection('目录', `
    <ul class="ds-toc">
      ${d.sections.map((s, i) => `<li><span class="toc-n">${String(i + 1).padStart(2, '0')}</span>${escape(s)}</li>`).join('')}
    </ul>
  `);

  body += drawerSection('正文', formatMdLite(d.body));

  return {
    title: report.title,
    subtitle: `REPORT ${page} · ${d.meta.model}`,
    content: body,
    page,
    footer: `<button class="btn btn-ghost">复制 Markdown</button><button class="btn btn-primary">导出 HTML ↓</button>`,
  };
}

// --- 5.5 爬虫任务 ---
export function renderCrawlTaskDetail(task) {
  if (!task) return { title: '未知任务', content: '' };
  const page = 'I';
  const logs = task.logs || [
    `[${task.time || '14:23:01'}] 任务启动：${task.subject || '示例任务'}`,
    `[${task.time || '14:23:02'}] 加载页面：${task.url || 'https://example.com'}`,
    `[${task.time || '14:25:18'}] 已采集 ${Math.floor((task.rows || 234) * 0.4)} 条`,
    `[${task.time || '14:27:42'}] 已采集 ${Math.floor((task.rows || 234) * 0.8)} 条`,
    `[${task.time || '14:30:12'}] 采集完成 · 共 ${task.rows || 234} 条`,
  ];
  const progress = task.progress ?? (task.status === 'done' ? 100 : task.status === 'failed' ? 0 : 65);

  let body = drawerSection('任务信息', `
    <div class="ds-meta-grid">
      <div class="ds-meta-item"><span class="l">主题</span><span class="v">${escape(task.subject || '—')}</span></div>
      <div class="ds-meta-item"><span class="l">平台</span><span class="v">${escape(task.platform || '—')}</span></div>
      <div class="ds-meta-item"><span class="l">状态</span><span class="v">${escape(task.statusText || task.status || '—')}</span></div>
      <div class="ds-meta-item"><span class="l">进度</span><span class="v">${progress}%</span></div>
    </div>
    <div class="drawer-progress">
      <div class="dp-bar"><div class="dp-fill" style="width:${progress}%"></div></div>
    </div>
  `);

  body += drawerSection('执行日志', `
    <pre class="ds-log">${escape(logs.join('\n'))}</pre>
  `);

  return {
    title: task.subject || '任务详情',
    subtitle: `CRAWL TASK ${page} · ${task.platform || ''}`,
    content: body,
    page,
    footer: task.status === 'running' || task.status === 'queued'
      ? `<button class="btn btn-ghost" style="color:var(--red);">取消任务 ✕</button>`
      : `<button class="btn btn-primary">重新运行</button>`,
  };
}

// --- 5.6 AI 对话会话 ---
export function renderChatSessionDetail(session) {
  if (!session) return { title: '未知会话', content: '' };
  const page = 'I';
  const msgs = session.messages || [];
  const preview = msgs.slice(0, 4).map((m) => `
    <div class="chat-preview-row ${m.role}">
      <div class="cp-role">${m.role === 'user' ? '你' : 'AI'}</div>
      <div class="cp-text">${escape(m.content || '').slice(0, 120)}${(m.content || '').length > 120 ? '…' : ''}</div>
    </div>
  `).join('');

  let body = drawerSection('会话信息', `
    <div class="ds-meta-grid">
      <div class="ds-meta-item"><span class="l">文件</span><span class="v">${escape(session.file || '—')}</span></div>
      <div class="ds-meta-item"><span class="l">消息数</span><span class="v">${msgs.length}</span></div>
      <div class="ds-meta-item"><span class="l">开始时间</span><span class="v">${escape(session.createdAt || '—')}</span></div>
      <div class="ds-meta-item"><span class="l">模型</span><span class="v">DeepSeek-V3</span></div>
    </div>
  `);

  body += drawerSection('消息预览', preview || '<p class="ds-text" style="color:var(--ink-faint);font-style:italic;">暂无消息</p>');

  return {
    title: session.title || '会话详情',
    subtitle: `CHAT ${page} · ${msgs.length} MSGS`,
    content: body,
    page,
    footer: `<button class="btn btn-primary" data-goto-chat="${escape(session.id || '')}">继续对话 →</button>`,
  };
}

// ============================================================
// 6) 轻量 markdown 渲染（与 app.js 兼容）
// ============================================================
function formatMdLite(s) {
  return escape(s)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^(\|.+\|)$/gm, (m) => `<div class="md-table">${m}</div>`)
    .replace(/^>\s(.+)$/gm, '<blockquote class="md-quote">$1</blockquote>')
    .replace(/^(\d+)\.\s(.+)$/gm, '<div class="md-li"><span class="md-n">$1.</span>$2</div>')
    .replace(/^·\s(.+)$/gm, '<div class="md-li md-bullet">· $1</div>')
    .replace(/\n{2,}/g, '</p><p>')
    .replace(/^([^<].*)$/gm, (m) => m.startsWith('<') ? m : `<span class="md-line">${m}</span>`)
    .replace(/<p>/g, '<p class="ds-md-p">');
}

// ============================================================
// 7) 暴露给 app.js
// ============================================================
window.openDetailDrawer = openDrawer;
window.closeDetailDrawer = () => closeDrawer();
window.markDetailPicked = markPicked;
window.renderKpiDetail = renderKpiDetail;
window.renderPlatformDetail = renderPlatformDetail;
window.renderWordDetail = renderWordDetail;
window.renderReportDetail = renderReportDetail;
window.renderCrawlTaskDetail = renderCrawlTaskDetail;
window.renderChatSessionDetail = renderChatSessionDetail;
window.bindTabCloseHook = bindTabCloseHook;

// ESM 命名导出（给 app.js import 用 · 仅为别名）
// 注：renderKpiDetail / renderPlatformDetail / renderWordDetail /
//     renderReportDetail / renderCrawlTaskDetail / renderChatSessionDetail
//     / bindTabCloseHook / openDrawer / closeDrawer / markPicked
//     已在原位置 export function 声明，此处不重复
export { openDrawer as openDetailDrawer };
export { closeDrawer as closeDetailDrawer };
export { markPicked as markDetailPicked };
