// app.js — V0.8 网络数据洞察工作台
// 设计：编辑式运营中枢 + 视觉/动效全面升级
// 数据：demo 流动，真实 API 优先 / 脚本回退

import {
  flipNumber, gaugeValue, pulseRing, typewriter, rafTicker,
  makeChartSeries, drawSeriesChart, drawLeftToRightChart,
  revealOnView, inViewport,
} from './animations.js';
import {
  openDetailDrawer, closeDetailDrawer, markDetailPicked,
  renderKpiDetail, renderPlatformDetail, renderWordDetail,
  renderReportDetail, renderCrawlTaskDetail, renderChatSessionDetail,
  bindTabCloseHook,
} from './drawer.js';

// ============================================================
// 1) 静态数据：8 大平台配置（火锅店主题）
// ============================================================
const PLATFORMS = [
  { key: 'dianping', name: '大众点评',   short: '评', color: 'var(--dianping)', desc: '餐厅 · 评分 · 评价', samples: ['海底捞', '呷哺呷哺', '小龙坎'] },
  { key: 'meituan',  name: '美团',       short: '团', color: 'var(--meituan)',  desc: '团购 · 排队 · 套餐', samples: ['套餐', '代金券', '到店'] },
  { key: 'douyin',   name: '抖音',       short: '抖', color: 'var(--douyin)',   desc: '探店 · 直播',       samples: ['#火锅探店', '#深夜食堂', '#美食'] },
  { key: 'xiaohongshu', name: '小红书', short: '红', color: 'var(--xhs)',      desc: '种草 · 笔记',       samples: ['火锅推荐', '锅底测评', '菜品'] },
  { key: 'tmall',    name: '天猫',       short: '猫', color: 'var(--tmall)',    desc: '底料 · 食材 · 厨具', samples: ['牛油底料', '毛肚', '鸳鸯锅'] },
  { key: 'zhihu',    name: '知乎',       short: '知', color: 'var(--zhihu)',    desc: '问答 · 测评',       samples: ['海底捞怎么样', '火锅蘸料配方'] },
  { key: 'weibo',    name: '微博',       short: '微', color: 'var(--weibo)',    desc: '话题 · 热搜',       samples: ['#火锅', '#美食', '#排队'] },
  { key: 'web',      name: '通用网页',   short: '网', color: 'var(--web)',      desc: '门店 · 菜单 · 官网', samples: ['http://haidilao.com', '/menu'] },
];

const PLATFORM_STATS = {};
PLATFORMS.forEach((p) => {
  PLATFORM_STATS[p.key] = {
    rows: Math.floor(8000 + Math.random() * 30000),
    rate: (85 + Math.random() * 13).toFixed(1),
    status: Math.random() > 0.2 ? 'running' : (Math.random() > 0.5 ? 'idle' : 'error'),
    progress: Math.floor(20 + Math.random() * 70),
  };
});

// ============================================================
// 2) Demo 任务模板（火锅店主题）
// ============================================================
const TASK_SUBJECTS = [
  '大众点评 · 5 星好评采集', '美团 · 排队等候时长', '抖音 · 探店视频评论',
  '小红书 · 锅底种草笔记', '天猫 · 牛油底料评价', '知乎 · 海底捞服务体验',
  '微博 · #火锅# 话题抓取', '门店官网 · 菜单更新', '食材溯源 · 毛肚供应商', '客流热力 · 周末高峰',
];
const TASK_LOGS = [
  '正在解析第 1/12 页...', '过滤低质评论 24 条', '提取菜品标签 38 个',
  '写入 output/data/hotpot.xlsx', '转换格式 .json → .csv', '速率 32 条/s',
  '触发反爬, 降速 2s', '已合并 3 个分页结果', '持久化到本地 disk', '清洗完成, 准备入库',
];

// ============================================================
// 3) 词云关键词（火锅店主题）
// ============================================================
const CLOUD_WORDS = [
  { w: '海底捞',     s: 1, d: '+18%' }, { w: '服务',       s: 1, d: '+24%' },
  { w: '排队',       s: 2, d: '+34%' }, { w: '毛肚',       s: 2, d: '+12%' },
  { w: '锅底',       s: 1, d: '+9%'  }, { w: '麻辣',       s: 3, d: '+15%' },
  { w: '鸳鸯锅',     s: 2, d: '+22%' }, { w: '性价比',     s: 3, d: '+6%'  },
  { w: '蘸料',       s: 3, d: '+3%'  }, { w: '牛肉',       s: 4, d: '-2%'  },
  { w: '虾滑',       s: 3, d: '+19%' }, { w: '环境',       s: 2, d: '+11%' },
  { w: '服务员',     s: 3, d: '+8%'  }, { w: '呷哺呷哺',   s: 2, d: '+5%'  },
  { w: '小龙坎',     s: 1, d: '+17%' }, { w: '巴奴',       s: 3, d: '+4%'  },
  { w: '大龙燚',     s: 2, d: '+13%' }, { w: '凑凑',       s: 4, d: '+1%'  },
  { w: '谭鸭血',     s: 3, d: '+14%' }, { w: '珮姐',       s: 4, d: '+2%'  },
  { w: '排队两小时', s: 4, d: '+38%' }, { w: '等位',       s: 3, d: '+21%' },
  { w: '鸭血',       s: 4, d: '+1%'  }, { w: '黄喉',       s: 3, d: '+7%'  },
  { w: '午餐肉',     s: 2, d: '+5%'  }, { w: '金针菇',     s: 2, d: '-5%'  },
  { w: '土豆片',     s: 1, d: '+12%' }, { w: '等位送果盘', s: 3, d: '+9%'  },
  { w: '围裙',       s: 2, d: '+3%'  }, { w: '生日面',     s: 3, d: '+24%' },
];

// ============================================================
// 4) 演示报告（火锅店主题）
// ============================================================
const REPORTS_BASE = [
  { t: '海底捞 · 五一期间排队舆情分析', n: 18420, time: '8m32s', m: '12,847 条 · 8 平台聚合', tags: ['品牌舆情', '排队'], date: '2 小时前' },
  { t: '小红书 · 锅底种草笔记 · Top 50', n: 9380, time: '6m12s', m: '8,932 条 · 笔记聚合', tags: ['小红书', '种草'], date: '5 小时前' },
  { t: '大众点评 · 4.5 星以上门店对比', n: 12480, time: '5m24s', m: '15,221 条 · 门店横评', tags: ['大众点评', '对比'], date: '昨天 18:32' },
  { t: '抖音 · 探店直播互动率 · 季度', n: 6420, time: '4m48s', m: '5,128 条 · 互动分析', tags: ['抖音', '直播'], date: '昨天 11:08' },
  { t: '微博 · #深夜火锅# 话题趋势', n: 7820, time: '4m02s', m: '9,341 条 · 24h 监测', tags: ['微博', '热点'], date: '3 天前' },
  { t: '天猫 · 牛油底料销量榜 · 6 月', n: 4280, time: '3m36s', m: '4,512 条 · 销量排行', tags: ['天猫', '电商'], date: '4 天前' },
];
let REPORTS = [...REPORTS_BASE];
const REPORT_INCOMING = [
  { t: '美团 · 等位时长城市排行', n: 1240, time: '2m14s', src: 'meituan', m: '1,832 条 · 城市 Top 20', tags: ['美团', '排队'], date: '刚刚' },
  { t: '知乎 · 海底捞服务体验问答', n: 980, time: '1m48s', src: 'zhihu', m: '4,512 条 · 头部 KOL 38 位', tags: ['知乎', '问答'], date: '5 分钟前' },
  { t: 'B 站 · 火锅蘸料 vlog 评测', n: 1620, time: '2m32s', src: 'bilibili', m: '3,124 条 · 视频评测', tags: ['B 站', 'vlog'], date: '12 分钟前' },
];

// ============================================================
// 5) AI 对话脚本
// ============================================================
const SCRIPTED_REPLY = {
  triggers: [
    { q: /你好|hi|hello/i, a: '👋 你好！我是 Insight Agent 网络数据洞察助手。\n\n我可以帮你：\n· 解读已采集的网络 / 物理世界数据集\n· 对比不同平台 / 渠道的口碑\n· 提炼趋势、识别异常\n· 生成结构化报告\n\n试试问我："分析一下最近的小红书评论"' },
    { q: /怎么用|怎么开始|教程|help/i, a: '**使用流程（3 步）：**\n\n1. **数据采集**（顶部"采集" tab）\n   · 选择 8 大平台之一\n   · 或自然语言："爬知乎上关于 AI 的 100 条回答"\n\n2. **分析报告**（"分析" tab）\n   · 选择已采集的数据集\n   · 选择 6 种模板之一（快速扫描 / 品牌舆情 / 趋势等）\n\n3. **AI 追问**（"对话" tab）\n   · 对结果进行多轮对话深挖' },
    { q: /平台|支持.*爬|数据源/i, a: '**当前支持 8 大数据源：**\n\n| 平台 | 类型 | 适用场景 |\n|---|---|---|\n| 知网 (CNKI) | 学术 | 论文综述、引用分析 |\n| 豆瓣 | 评论 | 书影音口碑 |\n| 抖音 | 短视频 | 热点、流行趋势 |\n| 京东 | 电商 | 商品评价、价格 |\n| 天猫 | 电商 | 品牌、销量 |\n| 知乎 | 问答 | 观点、专业分析 |\n| 微博 | 话题 | 实时舆情 |\n| 通用网页 | URL | 任意站点 |\n\n真实模式下调用 DeepSeek-V3 解析自然语言任务参数。' },
    { q: /分析|报告|洞察/i, a: '**6 种分析模板：**\n\n1. **快速扫描** — 5 分钟看全貌，输出字段/缺失/词频\n2. **品牌舆情** — 情感 + 话题 + KOL 识别\n3. **趋势追踪** — 时序 + 演化 + 生命周期\n4. **竞品对比** — 多产品横评、差异化\n5. **主题挖掘** — LDA 聚类、隐藏话题\n6. **评论洞察** — 优缺点聚类、痛点亮点\n\n在"分析" tab 选文件 + 模板即可生成。' },
  ],
  fallback: '这是一个 demo 模式的问题。在真实模式下，系统会调用 DeepSeek-V3 给出基于实时数据的专业建议。\n\n你可以试试：\n· "怎么使用？"\n· "支持哪些平台？"\n· "有哪些分析模板？"\n· "分析一下最近的小红书评论"',
};

// ============================================================
// 6) 启动入口
// ============================================================
function bootstrap() {
  console.log('[app] 启动 v0.8 editorial · data workspace');
  initTabs();
  initCtaButtons();
  renderPlatformsGrid('platforms-grid');
  renderPlatformsGrid('crawl-platforms', { onClick: onSelectCrawler });
  renderCloud();
  renderReports();
  renderFileList('file-list');
  renderFileList('analysis-files', { onClick: onSelectAnalysisFile });
  renderChatSessions();
  renderChatSuggest();
  bindChatEvents();
  bindCrawlEvents();

  // 时钟
  startClock();
  // KPI 心跳（带翻牌）
  startKpiHeartbeat();
  // 任务流（带 ripple + 打字机）
  startTaskStream('task-stream');
  startTaskStream('crawl-tasks');
  // 词云微调（带滑入）
  startCloudTicker();
  // 折线图（环形 buffer + 实时追加 + 多线对比）
  initThroughputChart();
  // 启动粒子动画循环
  startParticleLoop();
  // 报告循环插入
  startReportTicker();
  // 拉取真实系统状态
  fetchSystemStatus();
  // V0.9 详情抽屉：绑定 4 类点击 → 抽屉
  bindDrawerEntries();
  // 切 tab 时自动关闭抽屉
  bindTabCloseHook();
  // 页脚子服务启动入口
  bindSubServiceLaunchers();
}

// ============================================================
// 7) Tab 切换
// ============================================================
function initTabs() {
  const tabs = document.querySelectorAll('.topbar-tabs .tab');
  const views = document.querySelectorAll('main.view');
  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.view;
      tabs.forEach((t) => t.classList.toggle('active', t === tab));
      views.forEach((v) => v.classList.toggle('active', v.id === `view-${target}`));
      if (target === 'overview') {
        // 重新绘制 chart（因为画布尺寸可能变）
        setTimeout(() => {
          const c = document.getElementById('chart-throughput');
          if (c && chartL2RState) {
            drawLeftToRightChart(c, [chartL2RState.dataTotal, chartL2RState.dataDY, chartL2RState.dataXHS, chartL2RState.dataMT], {
              maxLen: chartL2RState.maxLen,
              label: true,
              logScale: true,
              legend: ['总采集', '抖音', '小红书', '美团'],
              hiddenLines: chartL2RState.hiddenLines,
              chartMode: chartL2RState.chartMode,
            });
          }
        }, 80);
      }
    });
  });
}

function initCtaButtons() {
  document.querySelectorAll('[data-goto]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const v = btn.dataset.goto;
      const tab = document.querySelector(`.topbar-tabs .tab[data-view="${v}"]`);
      if (tab) {
        pulseRing(btn, { color: 'rgba(255,255,255,0.4)', size: 100 });
        tab.click();
      }
    });
  });
}

// ============================================================
// 8) 平台网格
// ============================================================
function renderPlatformsGrid(id, opts = {}) {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = PLATFORMS.map((p, i) => {
    const s = PLATFORM_STATS[p.key];
    return `
      <div class="platform-tile ${s.status} reveal" data-platform="${p.key}" style="animation-delay: ${i * 50}ms;">
        <div class="name">
          <span class="icon" style="background:${p.color};">${p.short}</span>
          ${p.name}
        </div>
        <div class="meta"><span>${p.desc}</span></div>
        <div class="meta">
          <span><span class="rows" data-rows="${p.key}">${s.rows.toLocaleString()}</span> 条</span>
          <span>成功率 <span style="color:var(--green);">${s.rate}%</span></span>
        </div>
        <div class="bar live" style="--w: ${s.progress}%;"></div>
      </div>
    `;
  }).join('');
  // 入场揭示
  el.querySelectorAll('.platform-tile').forEach((tile, i) => {
    setTimeout(() => tile.classList.add('revealed'), i * 50);
  });
  if (opts.onClick) {
    el.querySelectorAll('.platform-tile').forEach((tile) => {
      tile.addEventListener('click', () => {
        pulseRing(tile, { color: 'rgba(184, 26, 26, 0.18)', size: 100 });
        opts.onClick(tile.dataset.platform);
      });
    });
  }
}

// ============================================================
// 9) 词云
// ============================================================
function renderCloud() {
  const el = document.getElementById('cloud');
  if (!el) return;
  el.innerHTML = CLOUD_WORDS.map((w) => {
    const dir = w.d.startsWith('-') ? 'down' : '';
    return `<span class="word s${w.s}" data-w="${w.w}">${w.w}<span class="delta ${dir}">${w.d}</span></span>`;
  }).join('');
}

function startCloudTicker() {
  setInterval(() => {
    const el = document.getElementById('cloud');
    if (!el) return;
    const words = el.querySelectorAll('.word .delta');
    if (!words.length) return;
    const w = words[Math.floor(Math.random() * words.length)];
    const v = (Math.random() * 40 - 10).toFixed(0);
    const sign = v >= 0 ? '+' : '';
    w.textContent = `${sign}${v}%`;
    w.classList.toggle('down', v < 0);
    // 触发动画
    w.classList.remove('swap');
    void w.offsetWidth;
    w.classList.add('swap');
  }, 2500);
}

// ============================================================
// 10) 报告列表
// ============================================================
function renderReports() {
  const el = document.getElementById('report-list');
  if (!el) return;
  el.innerHTML = REPORTS.map((r) => reportItemHtml(r)).join('');
}

function reportItemHtml(r) {
  return `
    <li class="report-item">
      <div class="ic"><span class="ico">📄</span><span>HTML</span></div>
      <div class="info">
        <div class="t">${escapeHtml(r.t)}</div>
        <div class="m">${escapeHtml(r.m)} · ${r.date}</div>
        <div class="tags">${r.tags.map((t) => `<span class="tag">${t}</span>`).join('')}</div>
      </div>
      <div class="actions">
        <button class="btn btn-ghost">查看</button>
      </div>
    </li>
  `;
}

let reportIdx = 0;
function startReportTicker() {
  setInterval(() => {
    const list = document.getElementById('report-list');
    if (!list) return;
    const next = REPORT_INCOMING[reportIdx % REPORT_INCOMING.length];
    reportIdx++;
    const li = document.createElement('div');
    li.innerHTML = reportItemHtml(next);
    const node = li.firstElementChild;
    node.classList.add('just-in');
    list.insertBefore(node, list.firstChild);
    while (list.children.length > 8) list.removeChild(list.lastChild);
  }, 8000);
}

// ============================================================
// 11) 文件列表（火锅店主题）
// ============================================================
const DEMO_FILES = [
  { n: '大众点评-海底捞-门店-2026-05.xlsx',     s: '18,420 条', d: '2 小时前', ic: 'XLS', size: '1.8 MB' },
  { n: '小红书-锅底种草-笔记-2026-05.csv',       s: '9,380 条',  d: '5 小时前', ic: 'CSV', size: '1.1 MB' },
  { n: '抖音-火锅探店-视频-2026-05.json',        s: '6,420 条',  d: '昨天',    ic: 'JSON', size: '3.4 MB' },
  { n: '天猫-牛油底料-销量-2026-06.json',        s: '4,280 条',  d: '2 天前',  ic: 'JSON', size: '892 KB' },
  { n: '美团-等位时长-城市-2026-05.xlsx',        s: '12,180 条', d: '3 天前',  ic: 'XLS', size: '2.1 MB' },
  { n: '微博-深夜火锅-话题-2026-06.json',        s: '7,820 条',  d: '4 天前',  ic: 'JSON', size: '1.6 MB' },
];

function renderFileList(id, opts = {}) {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = DEMO_FILES.map((f, i) => `
    <div class="file-tile reveal" data-file="${f.n}" style="animation-delay: ${i * 30}ms;">
      <div class="ic">${f.ic}</div>
      <div class="info">
        <div class="n">${escapeHtml(f.n)}</div>
        <div class="m">${f.s} · ${f.d}</div>
      </div>
      <div class="size">${f.size}</div>
    </div>
  `).join('');
  el.querySelectorAll('.file-tile').forEach((t, i) => {
    setTimeout(() => t.classList.add('revealed'), i * 30);
  });
  if (opts.onClick) {
    el.querySelectorAll('.file-tile').forEach((t) => {
      t.addEventListener('click', () => {
        pulseRing(t, { color: 'rgba(184, 26, 26, 0.12)', size: 80 });
        opts.onClick(t.dataset.file);
      });
    });
  }
}

let selectedAnalysisFile = null;
function onSelectAnalysisFile(name) {
  selectedAnalysisFile = name;
  document.querySelectorAll('#analysis-files .file-tile').forEach((t) => {
    t.classList.toggle('active', t.dataset.file === name);
  });
  document.getElementById('selected-file-meta').textContent = name;
  // 触发选中文件的 sub-tab 渲染
  if (typeof window.renderActiveSubTab === 'function') {
    window.renderActiveSubTab(name);
  }
}

// ============================================================
// 12) KPI 心跳（jobs/reports 翻牌；rows 由图表驱动）
// ============================================================
let _kpiJobs = 38;
let _kpiReports = 17;

function startKpiHeartbeat() {
  setText('kpi-jobs', _kpiJobs);
  setText('kpi-reports', _kpiReports);
  let prevJobs = 0, prevReports = 0;
  setInterval(() => {
    const jobsDelta = Math.random() > 0.7 ? 1 : 0;
    _kpiJobs = Math.max(20, _kpiJobs + jobsDelta - (Math.random() > 0.9 ? 1 : 0));
    flipNumber(document.getElementById('kpi-jobs'), prevJobs, _kpiJobs, 400);
    flipNumber(document.getElementById('kpi-reports'), prevReports, _kpiReports, 400);
    prevJobs = _kpiJobs;
    prevReports = _kpiReports;
  }, 3000);
}

// ============================================================
// 13) 任务流（ripple + 打字机）
// ============================================================
function startTaskStream(id) {
  // 首次启动：立即种子 3 条初始事件，固定高度
  function seedInitial() {
    const list = document.getElementById(id);
    if (!list) return;
    const empty = list.querySelector('.task-empty');
    if (empty) empty.remove();
    for (let i = 0; i < 3; i++) {
      const p = PLATFORMS[Math.floor(Math.random() * PLATFORMS.length)];
      const subj = TASK_SUBJECTS[Math.floor(Math.random() * TASK_SUBJECTS.length)];
      const log = TASK_LOGS[Math.floor(Math.random() * TASK_LOGS.length)];
      const ts = new Date(Date.now() - (3 - i) * 2000).toLocaleTimeString('zh-CN', { hour12: false });
      const rows = Math.floor(Math.random() * 1500) + 50;
      const rate = (85 + Math.random() * 14).toFixed(0);
      const li = document.createElement('li');
      li.className = 'task-row';
      li.innerHTML = `
        <span class="ts">${ts}</span>
        <div class="body">
          <div class="head">
            <span class="src" style="background:${p.color};">${p.short}</span>
            <span class="subj">${subj}</span>
          </div>
          <div class="log">→ ${log}</div>
          <div class="progress live" style="--w: ${Math.floor(40 + Math.random() * 50)}%;"></div>
        </div>
        <div class="stat">
          <div class="n">${rows.toLocaleString()}</div>
          <div class="rate">${rate}%</div>
        </div>
      `;
      list.appendChild(li);
    }
  }
  seedInitial();

  function tick() {
    const list = document.getElementById(id);
    if (!list) return setTimeout(tick, 1000);
    const empty = list.querySelector('.task-empty');
    if (empty) empty.remove();

    const p = PLATFORMS[Math.floor(Math.random() * PLATFORMS.length)];
    const subj = TASK_SUBJECTS[Math.floor(Math.random() * TASK_SUBJECTS.length)];
    const log = TASK_LOGS[Math.floor(Math.random() * TASK_LOGS.length)];
    const ts = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    const rows = Math.floor(Math.random() * 1500) + 50;
    const rate = (85 + Math.random() * 14).toFixed(0);
    const rateClass = rate >= 90 ? '' : (rate >= 80 ? 'low' : 'bad');
    const status = Math.random() > 0.1 ? 'running' : 'error';
    const progressPct = status === 'error' ? Math.floor(Math.random() * 30) : Math.floor(40 + Math.random() * 50);

    const li = document.createElement('li');
    li.className = 'task-row just-in';
    li.innerHTML = `
      <span class="ts">${ts}</span>
      <div class="body">
        <div class="head">
          <span class="src" style="background:${p.color};">${p.short}</span>
          <span class="subj">${subj}</span>
        </div>
        <div class="log">→ ${log}</div>
        <div class="progress ${status === 'error' ? 'failed' : 'progress live'}" style="--w: ${progressPct}%;"></div>
      </div>
      <div class="stat">
        <div class="n">${rows.toLocaleString()}</div>
        <div class="rate ${rateClass}">${rate}%</div>
      </div>
    `;
    list.insertBefore(li, list.firstChild);
    while (list.children.length > 30) list.removeChild(list.lastChild);

    setTimeout(tick, 1500 + Math.random() * 2500);
  }
  setTimeout(tick, 800);
}

// ============================================================
// 14) 折线图（4线对比 + 交互增强）
// ============================================================
let chartL2RState = null;
let particleRaf = null;

function initThroughputChart() {
  const canvas = document.getElementById('chart-throughput');
  if (!canvas) return;

  const hiddenLines = new Set();
  let mouseX = -1, mouseY = -1;
  let mouseOnCanvas = false;

  chartL2RState = {
    canvas,
    dataDY: [],
    dataXHS: [],
    dataMT: [],
    dataTotal: [],
    maxLen: 48,
    stepMs: 200,
    idx: 0,
    lastTick: 0,
    hiddenLines,
    chartMode: 'channel', // 'channel' | 'total'
  };

  drawLeftToRightChart(canvas, [], { maxLen: chartL2RState.maxLen, label: true });

  if (chartL2RState.raf) cancelAnimationFrame(chartL2RState.raf);

  // 鼠标事件：十字线 + tooltip
  canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    mouseX = (e.clientX - rect.left) * (window.devicePixelRatio || 1);
    mouseY = (e.clientY - rect.top) * (window.devicePixelRatio || 1);
    mouseOnCanvas = true;

    // 检测图例点击区域
    if (canvas._legendRegions) {
      let inLegend = false;
      for (const r of canvas._legendRegions) {
        if (mouseX >= r.x && mouseX <= r.x + r.w && mouseY >= r.y && mouseY <= r.y + r.h) {
          inLegend = true;
          break;
        }
      }
      canvas.style.cursor = inLegend ? 'pointer' : 'crosshair';
    }
  });
  canvas.addEventListener('mouseleave', () => { mouseOnCanvas = false; });

  // 图例点击切换
  canvas.addEventListener('click', (e) => {
    if (!canvas._legendRegions) return;
    const rect = canvas.getBoundingClientRect();
    const cx = (e.clientX - rect.left) * (window.devicePixelRatio || 1);
    const cy = (e.clientY - rect.top) * (window.devicePixelRatio || 1);
    // 判断是否点击在图例上
    for (const r of canvas._legendRegions) {
      if (cx >= r.x && cx <= r.x + r.w && cy >= r.y && cy <= r.y + r.h) {
        if (hiddenLines.has(r.idx)) {
          hiddenLines.delete(r.idx);
        } else {
          hiddenLines.add(r.idx);
        }
        return;
      }
    }
    // 点击数据区域 → 钻取详情
    if (canvas._chartData && canvas._chartData.lines) {
      const data = canvas._chartData;
      const total = data.lines[0];
      if (total && total.data.length > 0) {
        const latest = total.data[total.data.length - 1];
        // 生成详情HTML
        let linesHtml = '';
        data.lines.forEach((line, i) => {
          const vals = line.data.slice(-10).map(d => d.value.toLocaleString()).join(' → ');
          linesHtml += `
            <div class="drawer-quote">
              <span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${line.color};margin-right:8px;vertical-align:middle;"></span>
              <strong>${line.name}</strong>
              <div style="font-family:var(--mono);font-size:11px;color:var(--ink-mute);margin-top:4px;">
                当前: <strong style="color:${line.color}">${latest.value.toLocaleString()}</strong> 条/h
                <span style="margin:0 8px">·</span>
                最近10个点: ${vals}
              </div>
            </div>`;
        });
        const content = `
          <div class="drawer-kpi">
            <div style="font-size:28px;font-family:var(--mono);font-weight:600;color:var(--accent);">${latest.value.toLocaleString()}</div>
            <div style="font-size:11px;color:var(--ink-mute);font-family:var(--mono);">当前采集速率 · 条/小时</div>
          </div>
          ${linesHtml}
          <div style="margin-top:12px;padding:10px 14px;background:var(--paper-cool);border-radius:var(--r);font-size:11px;color:var(--ink-mute);font-family:var(--serif);">
            💡 点击图例可切换线条显示 · 悬停查看各时间点数值
          </div>
        `;
        openDetailDrawer({
          title: `采集趋势 · ${latest.time}`,
          subtitle: 'CRAWL THROUGHPUT DETAIL',
          content,
          page: 'III',
        });
      }
    }
  });

  // ResizeObserver
  if (window.ResizeObserver) {
    const ro = new ResizeObserver(() => {
      if (chartL2RState && chartL2RState.dataTotal.length > 0) {
        drawLeftToRightChart(canvas,
          [chartL2RState.dataTotal, chartL2RState.dataDY, chartL2RState.dataXHS, chartL2RState.dataMT],
          { maxLen: chartL2RState.maxLen, label: true, logScale: true, legend: ['总采集', '抖音', '小红书', '美团'], hiddenLines, mouse: mouseOnCanvas ? { x: mouseX, y: mouseY } : null, chartMode: chartL2RState.chartMode }
        );
      }
    });
    ro.observe(canvas.parentElement || canvas);
  }

  // ===== 更真实的数据生成（周期性峰谷 + 午/晚高峰） =====
  const nextDY = (idx) => {
    const h = idx % 48;
    const base = 1800;
    // 午间小高峰 11:00-13:00 (h=22-26)
    const lunch = (h >= 22 && h <= 26) ? 1000 + Math.sin((h - 22) * 1.2) * 300 : 0;
    // 晚间大高峰 17:00-19:00 (h=34-38)  
    const dinner = (h >= 34 && h <= 38) ? 1800 + Math.sin((h - 34) * 1.0) * 500 : 0;
    // 夜间回落
    const night = (h >= 40 || h <= 6) ? -600 : 0;
    const sin = Math.sin((h - 8) * 0.3) * 400;
    const noise = (Math.random() - 0.5) * 300;
    return Math.max(600, base + lunch + dinner + night + sin + noise);
  };

  const nextXHS = (idx) => {
    const h = idx % 48;
    const base = 1200;
    // 下午茶时段 14:00-16:00 (h=28-32)
    const afternoon = (h >= 28 && h <= 32) ? 800 + Math.sin((h - 28) * 1.0) * 200 : 0;
    // 晚间高峰 18:00-21:00 (h=36-42)
    const evening = (h >= 36 && h <= 42) ? 1200 + Math.sin((h - 36) * 0.8) * 400 : 0;
    const sin = Math.sin((h - 2) * 0.25) * 300;
    const noise = (Math.random() - 0.5) * 250;
    return Math.max(400, base + afternoon + evening + sin + noise);
  };

  const nextMT = (idx) => {
    const h = idx % 48;
    const base = 800;
    const lunch = (h >= 22 && h <= 26) ? 500 + Math.sin((h - 22) * 1.2) * 150 : 0;
    const dinner = (h >= 34 && h <= 40) ? 800 + Math.sin((h - 34) * 0.9) * 300 : 0;
    const sin = Math.sin((h - 4) * 0.35) * 200;
    const noise = (Math.random() - 0.5) * 180;
    return Math.max(200, base + lunch + dinner + sin + noise);
  };

  // ===== 预填充初始数据（加载即看到图表） =====
  chartL2RState.dataDY = [];
  chartL2RState.dataXHS = [];
  chartL2RState.dataMT = [];
  chartL2RState.dataTotal = [];
  chartL2RState.idx = 0;
  chartL2RState.lastTick = performance.now();
  // 预填入 30 个点让首屏立即可见
  for (let i = 0; i < 30; i++) {
    const dy = nextDY(i);
    const xhs = nextXHS(i);
    const mt = nextMT(i);
    chartL2RState.dataDY.push(dy);
    chartL2RState.dataXHS.push(xhs);
    chartL2RState.dataMT.push(mt);
    chartL2RState.dataTotal.push(dy + xhs + mt);
    chartL2RState.idx++;
  }

  const step = (now) => {
    if (!chartL2RState) return;
    const s = chartL2RState;

    if (now - s.lastTick >= s.stepMs) {
      const dy = nextDY(s.idx);
      const xhs = nextXHS(s.idx);
      const mt = nextMT(s.idx);
      s.dataDY.push(dy);
      s.dataXHS.push(xhs);
      s.dataMT.push(mt);
      s.dataTotal.push(dy + xhs + mt);
      s.idx++;
      s.lastTick = now;

      while (s.dataDY.length > s.maxLen) {
        s.dataDY.shift();
        s.dataXHS.shift();
        s.dataMT.shift();
        s.dataTotal.shift();
      }
    }

    const mouse = mouseOnCanvas ? { x: mouseX, y: mouseY } : null;

    drawLeftToRightChart(canvas,
      [s.dataTotal, s.dataDY, s.dataXHS, s.dataMT],
      { maxLen: s.maxLen, label: true, logScale: true, legend: ['总采集', '抖音', '小红书', '美团'], hiddenLines, mouse, chartMode: s.chartMode }
    );

    // KPI 联动
    if (canvas._latestValues) {
      const v = canvas._latestValues;
      const delta = v.total - v.prevTotal;
      const kpiRows = document.getElementById('kpi-rows');
      const kpiTrend = document.getElementById('kpi-rows-trend');
      if (kpiRows) kpiRows.textContent = v.total.toLocaleString();
      if (kpiTrend) {
        const sign = delta >= 0 ? '+' : '';
        kpiTrend.textContent = `↑ ${sign}${delta.toLocaleString()}`;
      }
    }

    chartL2RState.raf = requestAnimationFrame(step);
  };

  chartL2RState.raf = requestAnimationFrame(step);

  // 模式切换按钮
  const toggle = document.getElementById('chart-mode-toggle');
  if (toggle) {
    toggle.addEventListener('click', () => {
      const s = chartL2RState;
      if (!s) return;
      s.chartMode = s.chartMode === 'channel' ? 'total' : 'channel';
      toggle.textContent = s.chartMode === 'channel' ? '📊 分渠道' : '📈 总览';
      toggle.classList.toggle('total', s.chartMode === 'total');
      document.getElementById('chart-unit').textContent = s.chartMode === 'channel' ? '条/小时' : '条/小时(总量)';
    });
  }
}

function startParticleLoop() {
  if (particleRaf) cancelAnimationFrame(particleRaf);

  const loop = () => {
    if (chartL2RState && chartL2RState.canvas && chartL2RState.dataTotal.length > 0) {
      const s = chartL2RState;
      drawLeftToRightChart(s.canvas,
        [s.dataTotal, s.dataDY, s.dataXHS, s.dataMT],
        { maxLen: s.maxLen, label: true, logScale: true, legend: ['总采集', '抖音', '小红书', '美团'], hiddenLines: s.hiddenLines, mouse: null, chartMode: s.chartMode }
      );
    }
    particleRaf = requestAnimationFrame(loop);
  };

  particleRaf = requestAnimationFrame(loop);
}

// ============================================================
// 15) 时钟
// ============================================================
function startClock() {
  setInterval(() => {
    const d = new Date();
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    setText('status-time', `${hh}:${mm}:${ss}`);
    setText('kpi-time', `今日 · ${hh}:${mm}`);
  }, 1000);
}

function setText(id, v) {
  const el = document.getElementById(id);
  if (el && el.textContent !== String(v)) el.textContent = v;
}

// ============================================================
// 16) 爬取 tab 交互（带分步解析 + 涟漪）
// ============================================================
let selectedCrawler = null;
function onSelectCrawler(key) {
  selectedCrawler = key;
  const p = PLATFORMS.find((p) => p.key === key);
  document.querySelectorAll('#crawl-platforms .platform-tile').forEach((t) => {
    t.classList.toggle('pick', t.dataset.platform === key);
    t.style.background = t.dataset.platform === key ? 'var(--paper-cool)' : '';
  });
  document.getElementById('param-target').textContent = p ? `${p.name} · ${p.desc}` : '未选择';
  if (p) document.getElementById('cfg-url').value = p.samples[0];
}

function bindCrawlEvents() {
  document.getElementById('btn-start-crawl')?.addEventListener('click', () => {
    if (!selectedCrawler) return alert('请先选择平台');
    const p = PLATFORMS.find((p) => p.key === selectedCrawler);
    pulseRing(document.getElementById('btn-start-crawl'), { color: 'rgba(255,255,255,0.5)', size: 100 });
    console.log('[crawl] 启动:', p.name, document.getElementById('cfg-url').value);
  });

  document.getElementById('btn-nl')?.addEventListener('click', () => {
    const v = document.getElementById('nl-input').value.trim();
    if (!v) return;
    const el = document.getElementById('nl-result');
    el.style.display = 'block';
    el.innerHTML = '';
    runNlParseSteps(v, el);
  });
}

function runNlParseSteps(text, container) {
  const platform = guessPlatform(text);
  const steps = [
    { num: 1, t: '分词 · tokenize', body: text.split(/\s+/).map((w) => `<span class="nl-token">${escapeHtml(w)}</span>`).join(' ') },
    { num: 2, t: '识别平台 · platform detection', body: `→ <strong style="color:var(--accent);">${platform}</strong>` },
    { num: 3, t: '解析参数 · extract params', body: '关键词: <strong>' + escapeHtml(text) + '</strong> · 最大数: <strong>100</strong> · 类型: <strong>问答</strong>' },
    { num: 4, t: '启动 · ✓ ready', body: '<strong style="color:var(--green);">任务已加入队列，等待执行</strong>' },
  ];
  container.innerHTML = '';
  steps.forEach((s, i) => {
    setTimeout(() => {
      const div = document.createElement('div');
      div.className = 'nl-step';
      div.innerHTML = `<span class="step-num">${s.num}</span>${escapeHtml(s.t)}<div style="margin-top: 4px; color: var(--ink-mute);">${s.body}</div>`;
      container.appendChild(div);
      // 触发动画
      setTimeout(() => div.classList.add('active'), 30);
    }, i * 450);
  });
}

function guessPlatform(text) {
  if (/知乎|怎么|如何|为什么/.test(text)) return '知乎 (zhihu)';
  if (/豆瓣|书|电影|影评/.test(text)) return '豆瓣 (douban)';
  if (/微博|热搜|话题/.test(text)) return '微博 (weibo)';
  if (/抖音|视频|直播/.test(text)) return '抖音 (douyin)';
  if (/京东|jd|价格|评价/.test(text)) return '京东 (jd)';
  if (/淘宝|天猫|店铺|品牌/.test(text)) return '天猫 (tmall)';
  if (/论文|学术|综述|研究/.test(text)) return '知网 (cnki)';
  return '通用网页 (web)';
}

// ============================================================
// 17) 分析模板（保留兼容，但实际渲染走 analysis.js）
// ============================================================
const TPL_OUTPUT = {
  quick: { t: '快速扫描', body: '**海底捞 · 大众点评数据集**\n\n· 文件: `大众点评-海底捞-门店-2026-05.xlsx`\n· 总条数: **18,420**\n· 字段: 6 个（content / author / rating / time / likes / source）\n· 时间范围: 2026-04-28 ~ 2026-05-31\n· 缺失率: 0.3%\n\n**Top 10 高频词**\n\n| # | 词 | 频次 |\n|---|---|---|\n| 1 | 服务 | 3,124 |\n| 2 | 排队 | 2,847 |\n\n**情感分布**\n· 正面 71.4% · 中性 21.2% · 负面 7.4%' },
  brand: { t: '品牌舆情', body: '**海底捞 vs 巴奴 · 品牌舆情分析**\n\n**核心发现**\n\n1. **海底捞** 提及率最高（28.4%），负面集中在"等位时长"\n2. **巴奴** 正向率最高（91%），核心卖点"毛肚+菌汤"\n3. **小龙坎** 增速最快，环比 +42%\n\n**行动建议**\n\n· 优化"等位体验"是海底捞关键杠杆\n· 巴奴可强化"食材差异化"心智\n· 小龙坎可借势"年轻化"营销' },
  trend: { t: '趋势追踪', body: '**海底捞排队话题趋势**\n\n**生命周期阶段**\n\n当前话题处于 **稳定期**。\n\n**预测**\n\n· 1 周内热度 +12%（端午假期）\n· 2 周后进入"波动期"' },
  competitive: { t: '竞品对比', body: '**海底捞 vs 巴奴 vs 小龙坎 · Q2 评分对比**\n\n| 品牌 | 评分 | 提及数 | 净推荐 |\n|---|---|---|---|\n| 海底捞 | 4.7 | 28k | +62% |\n| 巴奴 | 4.8 | 8k | +71% |\n| 小龙坎 | 4.5 | 18k | +48% |' },
  topic: { t: '主题挖掘', body: '**LDA 主题聚类 · 8 个隐藏话题**\n\n1. 服务态度（24.3%）\n2. 锅底口味（19.1%）\n3. 排队体验（16.2%）\n4. 菜品新鲜（12.8%）\n5. 价格感知（10.4%）\n6. 环境氛围（8.7%）\n7. 蘸料搭配（5.4%）\n8. 食材溯源（3.1%）' },
  review: { t: '评论洞察', body: '**海底捞评论聚类**\n\n🔴 痛点：等位 2 小时 / 价格偏高 / 锅底重复使用\n🟢 亮点：服务态度 / 生日面 / 等位送果盘 / 围裙' },
};

function bindAnalysisTpls() {
  // 占位：sub-tab 由 analysis.js 接管
  document.querySelectorAll('.tpl-tile').forEach((t) => {
    t.addEventListener('click', () => {
      if (!selectedAnalysisFile) return alert('请先选择数据文件');
      pulseRing(t, { color: 'rgba(184, 26, 26, 0.18)', size: 100 });
    });
  });
}

function formatMdLite(s) {
  return escapeHtml(s)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^(\|.+\|)$/gm, (m) => `<div style="font-family: var(--mono); font-size: 11px; line-height: 1.6;">${m}</div>`)
    .replace(/^·\s/gm, '· ')
    .replace(/\n/g, '<br>');
}

// ============================================================
// 18) AI 对话（打字机 + 消息入场增强）
// ============================================================
const DEMO_SESSIONS = [
  { id: 's1', t: '海底捞 · 五一排队舆情', p: '正面率 71% · 服务提及 24%...', m: '6 轮', time: '2 小时前' },
  { id: 's2', t: '美团 vs 大众点评 · 评分对比', p: '美团 4.6 vs 点评 4.7...', m: '4 轮', time: '昨天' },
  { id: 's3', t: '小红书 · 锅底种草笔记', p: 'Top 3 牛油 · 番茄 · 鸳鸯...', m: '8 轮', time: '3 天前' },
];

function renderChatSessions() {
  const el = document.getElementById('chat-sessions');
  if (!el) return;
  el.innerHTML = DEMO_SESSIONS.map((s) => `
    <div class="chat-session-card" data-sid="${s.id}">
      <div class="st">${escapeHtml(s.t)}</div>
      <div class="sp">${escapeHtml(s.p)}</div>
      <div class="sm">
        <span>${s.m}</span>
        <span>${s.time}</span>
      </div>
    </div>
  `).join('');
  el.querySelectorAll('.chat-session-card').forEach((c) => {
    c.addEventListener('click', () => {
      pulseRing(c, { color: 'rgba(184, 26, 26, 0.12)', size: 80 });
      selectSession(c.dataset.sid);
    });
  });
}

let currentSession = null;
let chatMessages = [];
function selectSession(id) {
  currentSession = DEMO_SESSIONS.find((s) => s.id === id);
  if (!currentSession) return;
  document.querySelectorAll('.chat-session-card').forEach((c) => {
    c.classList.toggle('active', c.dataset.sid === id);
  });
  document.getElementById('chat-title').textContent = currentSession.t;
  chatMessages = SESSION_HISTORIES[id] || [];
  document.getElementById('chat-meta').textContent = `${chatMessages.length} 条消息`;
  renderChatMessages();
}

const SESSION_HISTORIES = {
  s1: [
    { role: 'user',    t: '海底捞在五一期间的排队舆情整体如何？' },
    { role: 'assistant', t: '整体正面率 **71.4%**（高于行业均值 65%），表现稳健。\n\n**Top 3 正面话题**：服务态度、等位送果盘、生日面\n\n**Top 3 负面话题**：等位 2 小时、价格偏高、锅底口味下降' },
    { role: 'user',    t: '哪些城市的负面率最高？' },
    { role: 'assistant', t: '负面率 Top 3 城市：\n1. **上海** 18.4%（等位超时 32%）\n2. **北京** 14.2%（价格争议 28%）\n3. **广州** 12.8%（口味争议 19%）' },
  ],
  s2: [
    { role: 'user',    t: '美团和大众点评上火锅门店的评分对比？' },
    { role: 'assistant', t: '美团均分 **4.6**（样本 12,184 条），大众点评均分 **4.7**（样本 18,420 条），差异 -0.1。\n\n大众点评更严格，差评率高出 4.3%，但 5 星率也更高。' },
  ],
  s3: [
    { role: 'user',    t: '小红书锅底种草笔记里 Top 3 是什么？' },
    { role: 'assistant', t: '按收藏量 Top 3：\n1. **牛油麻辣** 4.2K 收藏\n2. **番茄锅底** 3.8K 收藏\n3. **鸳鸯锅** 3.1K 收藏\n\n鸳鸯锅笔记增长率最快，环比 +48%。' },
  ],
};

function renderChatMessages() {
  const el = document.getElementById('chat-messages');
  if (!el) return;
  if (!chatMessages.length) {
    el.innerHTML = '<div style="color: var(--ink-faint); font-style: italic; font-family: var(--serif); text-align: center; padding: 32px 0;">— 暂无消息 —</div>';
    return;
  }
  el.innerHTML = chatMessages.map((m) => chatRowHtml(m, false)).join('');
  el.scrollTop = el.scrollHeight;
}

function chatRowHtml(m, boost = true) {
  const avCls = m.role === 'user' ? 'chat-avatar-user' : 'chat-avatar-ai';
  const avText = m.role === 'user' ? '我' : 'AI';
  const bubCls = m.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-ai';
  const name = m.role === 'user' ? '我' : 'AI 分析师';
  return `
    <div class="chat-row chat-row-${m.role} ${boost ? 'boost-in' : ''}">
      <div class="chat-avatar ${avCls}">${avText}</div>
      <div class="chat-bubble-wrap">
        <div class="chat-meta">${name} · ${new Date().toLocaleTimeString('zh-CN', { hour12: false })}</div>
        <div class="chat-bubble ${bubCls}">${formatMdLite(m.t)}</div>
      </div>
    </div>
  `;
}

const SUGGESTS = [
  '海底捞排队舆情如何？', 'Top 5 高频锅底', '哪些品牌被提及最多？',
  '负面话题有哪些？', '生成完整报告',
];

function renderChatSuggest() {
  const el = document.getElementById('chat-suggest');
  if (!el) return;
  el.innerHTML = SUGGESTS.map((s) => `<span class="chip" data-q="${s}">${s}</span>`).join('');
  el.querySelectorAll('.chip').forEach((c) => {
    c.addEventListener('click', () => {
      pulseRing(c, { color: 'rgba(27, 42, 78, 0.18)', size: 60 });
      if (!currentSession) { alert('请先选择会话'); return; }
      sendChatMessage(c.dataset.q);
    });
  });
}

function bindChatEvents() {
  const input = document.getElementById('chat-input');
  const hint = document.getElementById('chat-hint');
  if (input) {
    input.addEventListener('input', () => {
      hint.textContent = `${input.value.length} 字`;
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (input.value.trim()) sendChatMessage(input.value);
      }
    });
  }
  document.getElementById('btn-chat-send')?.addEventListener('click', () => {
    if (input && input.value.trim()) sendChatMessage(input.value);
  });
  document.getElementById('btn-new-chat')?.addEventListener('click', () => {
    const name = prompt('新建会话名称：', '新分析会话');
    if (!name) return;
    const id = 's' + (DEMO_SESSIONS.length + 1);
    DEMO_SESSIONS.unshift({ id, t: name, p: '— 新会话 —', m: '0 轮', time: '刚刚' });
    renderChatSessions();
    selectSession(id);
  });
  document.getElementById('btn-back-chat')?.addEventListener('click', () => {
    currentSession = null;
    chatMessages = [];
    document.querySelectorAll('.chat-session-card').forEach((c) => c.classList.remove('active'));
    document.getElementById('chat-title').textContent = '— 选择会话 —';
    document.getElementById('chat-meta').textContent = '0 条消息';
    renderChatMessages();
  });
}

async function sendChatMessage(text) {
  if (!currentSession) return;
  const input = document.getElementById('chat-input');
  const trimmed = text.trim();
  if (!trimmed) return;
  chatMessages.push({ role: 'user', t: trimmed });
  if (input) input.value = '';
  document.getElementById('chat-hint').textContent = '0 字';
  renderChatMessages();

  // 真实 API
  let response = null;
  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: trimmed, history: chatMessages.slice(0, -1) }),
    });
    if (r.ok) {
      const j = await r.json();
      if (j.ok && j.response) response = j.response;
    }
  } catch (_) { /* ignore */ }

  await new Promise((r) => setTimeout(r, 600 + Math.random() * 600));
  if (!response) response = matchReply(trimmed);

  // 打字机：先把整个行渲染（empty 气泡），再逐字填充
  const el = document.getElementById('chat-messages');
  el.insertAdjacentHTML('beforeend', chatRowHtml({ role: 'assistant', t: '' }, true));
  el.scrollTop = el.scrollHeight;
  const lastBubble = el.querySelector('.chat-row:last-child .chat-bubble');
  await typewriter(lastBubble, formatMdLite(response), { perChar: 22 });

  chatMessages.push({ role: 'assistant', t: response });
  document.getElementById('chat-meta').textContent = `${chatMessages.length} 条消息`;
  el.scrollTop = el.scrollHeight;
}

function matchReply(text) {
  for (const t of SCRIPTED_REPLY.triggers) {
    if (t.q.test(text)) return t.a;
  }
  return SCRIPTED_REPLY.fallback;
}

// ============================================================
// 19) 真实系统状态
// ============================================================
async function fetchSystemStatus() {
  try {
    const r = await fetch('/api/healthz');
    if (r.ok) {
      const d = await r.json();
      console.log('[app] 后端健康:', d);
    }
  } catch (_) {
    console.warn('[app] 后端不可达，纯 demo 模式');
    setDot('dot-system', 'idle');
  }
}

function setDot(id, cls) {
  const el = document.getElementById(id);
  if (el) el.className = 'dot ' + cls;
}

// ============================================================
// 20) 工具
// ============================================================
function escapeHtml(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// 暴露给 analysis.js
window.renderActiveSubTab = null;

// ============================================================
// 21) V0.9 · 详情抽屉绑定（6 类入口）
// ============================================================
function bindDrawerEntries() {
  // 4 个 KPI 卡（按顺序映射 rows / jobs / reports / key）
  const kpiMap = ['rows', 'jobs', 'reports', 'key'];
  document.querySelectorAll('#view-overview .kpi').forEach((k, i) => {
    const key = kpiMap[i] || 'rows';
    k.style.cursor = 'pointer';
    k.addEventListener('click', (e) => {
      pulseRing(k, { color: 'rgba(184, 26, 26, 0.18)', size: 120 });
      markDetailPicked(k);
      const r = renderKpiDetail(key);
      openDetailDrawer(r);
    });
  });

  // 概览 8 平台（无 onClick 时的兜底）
  document.querySelectorAll('#platforms-grid .platform-tile').forEach((tile) => {
    tile.style.cursor = 'pointer';
    tile.addEventListener('click', () => {
      pulseRing(tile, { color: 'rgba(184, 26, 26, 0.18)', size: 100 });
      markDetailPicked(tile);
      const r = renderPlatformDetail(tile.dataset.platform);
      openDetailDrawer(r);
    });
  });

  // 词云 30 词
  const cloud = document.getElementById('cloud');
  if (cloud) {
    cloud.style.cursor = 'pointer';
    cloud.addEventListener('click', (e) => {
      const word = e.target.closest('.word');
      if (!word) return;
      pulseRing(word, { color: 'rgba(184, 26, 26, 0.18)', size: 80 });
      markDetailPicked(word);
      const r = renderWordDetail(word.dataset.w);
      openDetailDrawer(r);
    });
  }

  // 报告列表（事件代理，含后续动态插入）
  const reportList = document.getElementById('report-list');
  if (reportList) {
    reportList.style.cursor = 'pointer';
    reportList.addEventListener('click', (e) => {
      const item = e.target.closest('.report-item');
      if (!item) return;
      pulseRing(item, { color: 'rgba(184, 26, 26, 0.10)', size: 100 });
      markDetailPicked(item);
      const title = item.querySelector('.t')?.textContent || '未命名报告';
      const meta = item.querySelector('.m')?.textContent || '';
      const m = meta.match(/([\d,]+)\s*条/);
      const rows = m ? parseInt(m[1].replace(/,/g, ''), 10) : 8000;
      const r = renderReportDetail({ title, rows, date: '2026-05-30', model: 'DeepSeek-V3' });
      openDetailDrawer(r);
    });
  }

  // 任务流（事件代理，含动态插入）
  ['task-stream', 'crawl-tasks'].forEach((listId) => {
    const list = document.getElementById(listId);
    if (!list) return;
    list.style.cursor = 'pointer';
    list.addEventListener('click', (e) => {
      const row = e.target.closest('.task-row');
      if (!row) return;
      pulseRing(row, { color: 'rgba(184, 26, 26, 0.12)', size: 80 });
      const ts = row.querySelector('.ts')?.textContent || '—';
      const subj = row.querySelector('.subj')?.textContent || '—';
      const src = row.querySelector('.src')?.textContent || '';
      const log = row.querySelector('.log')?.textContent || '';
      const rowsN = row.querySelector('.n')?.textContent || '0';
      const rate = row.querySelector('.rate')?.textContent || '';
      const isFail = row.querySelector('.progress.failed');
      const isProgress = row.querySelector('.progress.live');
      const task = {
        subject: subj, platform: src, time: ts, log,
        rows: parseInt(rowsN.replace(/,/g, ''), 10) || 0,
        rate,
        status: isFail ? 'failed' : (isProgress ? 'running' : 'done'),
        statusText: isFail ? '✗ 失败' : (isProgress ? '… 进行中' : '✓ 成功'),
        progress: isFail ? 30 : (isProgress ? 65 : 100),
      };
      const r = renderCrawlTaskDetail(task);
      openDetailDrawer(r);
    });
  });

  // AI 对话会话卡
  document.querySelectorAll('.chat-session-card').forEach((c) => {
    c.style.cursor = 'pointer';
    c.addEventListener('dblclick', () => {
      pulseRing(c, { color: 'rgba(184, 26, 26, 0.12)', size: 100 });
      const id = c.dataset.sid;
      const s = DEMO_SESSIONS.find((x) => x.id === id);
      const msgs = SESSION_HISTORIES[id] || [];
      const r = renderChatSessionDetail({
        id, title: s?.t, file: 'demo-data.xlsx', createdAt: s?.time, messages: msgs,
      });
      openDetailDrawer(r);
    });
  });
}

// ============================================================
// 页脚子服务启动
// ============================================================
function bindSubServiceLaunchers() {
  const apiMap = {
    'city-heatmap': { endpoint: '/api/start-city-heatmap', url: 'http://127.0.0.1:9530', label: '城市热区' },
    'physical':     { endpoint: '/api/start-physical',     url: 'http://127.0.0.1:9528', label: '物理世界' },
  };

  document.querySelectorAll('[data-launch]').forEach((lnk) => {
    lnk.addEventListener('click', async (e) => {
      e.preventDefault();
      const key = lnk.dataset.launch;
      const cfg = apiMap[key];
      if (!cfg) return;

      const origText = lnk.textContent;
      lnk.textContent = `${cfg.label} · 启动中…`;
      lnk.style.pointerEvents = 'none';
      lnk.style.opacity = '0.6';

      try {
        const r = await fetch(cfg.endpoint, { method: 'POST' });
        const j = await r.json();
        if (j.ok) {
          // 等待后端启动，2.5s 后打开前端
          setTimeout(() => {
            window.open(j.url || cfg.url, '_blank');
          }, 2500);
          lnk.textContent = `${cfg.label} · 已打开`;
        } else {
          lnk.textContent = `${cfg.label} · 失败`;
        }
      } catch (err) {
        lnk.textContent = `${cfg.label} · 错误`;
        console.warn(`[launch] ${key}:`, err);
      }

      setTimeout(() => {
        lnk.textContent = origText;
        lnk.style.pointerEvents = '';
        lnk.style.opacity = '';
      }, 3000);
    });
  });
}

// ============================================================
// 入口
// ============================================================
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', bootstrap);
} else {
  bootstrap();
}
