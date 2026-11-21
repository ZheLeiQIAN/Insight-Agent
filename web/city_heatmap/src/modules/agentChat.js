/* ============================================
   AgentChat V4 — 14 快捷芯片 · 头像 · 上下文条 · 三点 loading · markdown
   ============================================ */

import { bus } from './eventBus.js';
import { store } from './store.js';
import { sendChat } from './eventStream.js';

const CHIPS = [
  { row: '运营视角', items: [
    '哪个商圈现在餐饮客流最大？',
    '什么菜系目前最受欢迎？',
    '火锅翻台率',
    '夜宵时段活跃度',
    '外卖渗透率',
    '近1小时趋势',
  ]},
  { row: '投资视角', items: [
    '哪些区域餐饮供给不足？',
    '商圈饱和度排行',
    '近一周餐饮热度趋势如何？',
    '哪里适合开火锅新店？',
    '菜系空白洼地',
    '一人食火锅潜力',
    '生成当前餐饮热度分析报告',
  ]},
];

const MOCK = {
  '哪个商圈现在餐饮客流最大？': '根据实时数据，餐饮客流最大的商圈是滨江道商圈（火锅/烧烤类集中），其次是五大道景区（西餐/咖啡类）和奥城商业区（日料/韩餐类）。滨江道当前人均等位约 25 分钟，建议错峰前往。',
  '什么菜系目前最受欢迎？': '当前全市菜系热度排行：1) 火锅 38% 2) 烧烤 22% 3) 川菜 14% 4) 日料 10% 5) 粤菜 8%。火锅依然占据绝对优势，但烧烤增速最快（+15% vs 上周）。',
  '哪些区域餐饮供给不足？': '经分析，以下区域存在明显餐饮空白：1) 城西中北镇—张家窝板块（常住人口 8 万，无品牌火锅店）2) 海河教育园区（学生群体 2 万+，缺乏性价比餐饮）3) 空港经济区（白领午餐供给不足）。上述区域属于高潜力餐饮洼地。',
  '近一周餐饮热度趋势如何？': '过去 7 天趋势：1) 火锅搜索热度稳定，排名不变 2) 烧烤/小龙虾搜索量 +28%，进入旺季 3) 轻食沙拉 +35%，健康餐饮意识提升 4) 深夜餐饮（22:00 后）搜索 +22%，夜经济活跃。整体呈"品质升级 + 场景多元化"趋势。',
  '哪里适合开火锅新店？': '基于餐饮饱和度分析：1) **不建议**：滨江道商圈（火锅密度 23 家/km²，红海）2) **推荐**：城西中北镇板块（0 家火锅 / 8 万人口，蓝海）3) **关注**：海河教育园区（可主打"学生价火锅 + 社交场景"）。建议差异化定位为"一人食火锅"或"火锅 + 精酿"模式。',
  '火锅翻台率': '本市火锅翻台率：**午市 2.1 次**、**晚市 1.8 次**。滨江道/五大道商圈翻台峰值 2.6 次，但伴随人均等位 22min。建议通过线上排号 + 提前点单把高峰平移到 11:30 / 17:30。',
  '夜宵时段活跃度': '22:00 后活跃 TOP3 商圈：九眼桥（成都）35%、外滩（上海）28%、三里屯（北京）26%。本市滨江道/意风区夜宵搜索 +22%，但 22:00 后营业店铺仅 12%，延长营业时间的边际收益高。',
  '外卖渗透率': '本市外卖渗透率：火锅 5%（受配送难度限制）、烧烤 18%、小吃 32%、轻食 41%。火锅"冒菜化" + 单人份酸菜鱼/烤肉饭是外卖突破口。',
  '近1小时趋势': '近 60 分钟：① 滨江道火锅客流 +18% ② 意风区西餐 -8% ③ 五大道咖啡 +12%。建议把夜班备菜向滨江道倾斜，五大道区可考虑晚市买一送一咖啡。',
  '商圈饱和度排行': '饱和度（店铺密度/客单）：① 滨江道 0.92（红海）② 王府井 0.85 ③ 春熙路 0.81 ④ 五大道 0.66 ⑤ 钱江新城 0.55。新入局者建议在 0.55-0.70 区间的商圈做差异化。',
  '菜系空白洼地': '按菜系×商圈矩阵识别：① 海河教育园 × 烧烤（客单 80-120）② 城西中北镇 × 粤菜早茶 ③ 张家窝 × 日料 ④ 空港 × 高端商务餐。四大洼地，竞争密度均低于阈值。',
  '一人食火锅潜力': '一人食火锅近 90 天搜索 +54%，客单 38-58 元。写字楼/大学城周边最具潜力。建议 SKU 精简到 12 款（3 锅底 + 9 食材），出餐 < 6 分钟。',
  '生成当前餐饮热度分析报告': '请点击右下"阶段报告"标签 → "生成阶段报告"按钮获取完整结构化报告（含客流/商圈/菜系/投资四段）。',
};

const QUICK_REPLIES = ['再深入一点', '看看具体数字', '用一句话总结', '给出 3 条建议'];

let _msgSeq = 0;
let _lastMsgTime = 0;  // V4.6: 上一条消息时间戳，用于会话分隔
const SESSION_GAP_MS = 2 * 60 * 1000;

function fmtTime(ts) {
  const d = new Date(ts);
  return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
}

function maybeSessionDivider(now) {
  if (!_lastMsgTime || (now - _lastMsgTime) <= SESSION_GAP_MS) return '';
  const gapMin = Math.round((now - _lastMsgTime) / 60000);
  const ago = gapMin < 60 ? `${gapMin} 分钟前` : `${Math.floor(gapMin/60)} 小时前`;
  return `<div class="chat-session-divider">${fmtTime(now)} · ${ago}</div>`;
}

export function initAgentChat() {
  const chipsEl = document.getElementById('quickChips');
  if (!chipsEl) return;
  chipsEl.innerHTML = CHIPS.map(row => `
    <div class="quick-chips-row">
      <div class="row-label">${row.row}</div>
      ${row.items.map(c => `<span class="quick-chip">${c}</span>`).join('')}
    </div>
  `).join('');

  chipsEl.addEventListener('click', e => {
    const t = e.target.closest('.quick-chip');
    if (t) { addUser(t.textContent); reply(t.textContent); }
  });

  document.getElementById('btnSend')?.addEventListener('click', send);
  document.getElementById('chatInput')?.addEventListener('keydown', e => { if (e.key === 'Enter') send(); });

  // 清空按钮
  document.getElementById('btnClearChat')?.addEventListener('click', clearChat);

  // 上下文条（实时更新）
  updateContextBar();
  bus.on('hotspots:updated', updateContextBar);
  bus.on('cuisine:updated', updateContextBar);

  // 冷启动欢迎语
  seedWelcome();
}

function seedWelcome() {
  const c = document.getElementById('chatMessages');
  if (!c || c.children.length > 0) return;
  addAgent('👋 你好！我是 **Insight Agent 城市餐饮智能体**。当前监测 **' + (store.get('city.name') || '天津') + '** 共 ' + (store.get('dining.hotspotCount') || 0) + ' 个餐饮热区，最热门菜系 **' + (store.get('dining.topCuisine') || '火锅') + '**。\n\n你可以：\n• 直接在下方面板选快捷问题\n• 或在下方输入框中自由提问\n\n我会基于实时数据（客流、流向、菜系矩阵、商圈分析）给你可执行的运营/投资建议。', { quickReplies: ['看客流最大商圈', '哪些区域适合开新店', '近一周趋势如何'] });
}

function updateContextBar() {
  const el = document.getElementById('chatContext');
  if (!el) return;
  const city = store.get('city.name') || '天津';
  const topCuisine = store.get('dining.topCuisine') || '火锅';
  const count = store.get('dining.hotspotCount') || 0;
  const diners = store.get('dining.diners') || 0;
  el.innerHTML = `<span class="ctx-pill"><i>📍</i>${city}</span>
    <span class="ctx-pill"><i>🍲</i>${topCuisine}</span>
    <span class="ctx-pill"><i>🏪</i>${count} 热区</span>
    <span class="ctx-pill"><i>👥</i>${diners} 人</span>`;
}

function send() {
  const inp = document.getElementById('chatInput');
  if (!inp || !inp.value.trim()) return;
  const text = inp.value.trim(); inp.value = '';
  addUser(text); reply(text);
}

function clearChat() {
  const c = document.getElementById('chatMessages');
  if (!c) return;
  c.innerHTML = '';
  seedWelcome();
}

function reply(q) {
  // 1) MOCK 直接命中
  if (MOCK[q]) {
    setTimeout(() => addAgent(MOCK[q], { quickReplies: QUICK_REPLIES.slice(0, 3) }), 280 + Math.random() * 320);
    return;
  }
  // 2) loading + LLM fallback
  const loadingId = addLoading();
  const d = store.get('dining');
  const fallback = `感谢关注${store.get('city.name')}餐饮市场。当前全市实时餐饮客流 ${d.diners} 人，识别餐饮热区 ${d.hotspotCount} 个，最热门菜系为 ${d.topCuisine}。关于「${q}」，建议查看实时数据面板或生成阶段报告获取详细分析。`;

  let resolved = false;
  try {
    sendChat(q, (resp) => {
      if (resolved) return;
      resolved = true;
      replaceLoading(loadingId, resp?.reply || fallback);
    });
  } catch (err) { /* noop */ }

  setTimeout(() => {
    if (resolved) return;
    resolved = true;
    replaceLoading(loadingId, fallback);
  }, 3500);
}

function addUser(t) {
  const c = document.getElementById('chatMessages');
  if (!c) return;
  const now = Date.now();
  const prefix = maybeSessionDivider(now);
  c.innerHTML += `${prefix}<div class="chat-msg user" data-seq="${_msgSeq++}">
    <div class="avatar user-avatar">我</div>
    <div class="bubble-col">
      <div class="bubble">${esc(t)}</div>
    </div>
  </div><div class="chat-msg-time">${fmtTime(now)}</div>`;
  _lastMsgTime = now;
  scrollToBottom();
}

function addAgent(t, opts = {}) {
  const c = document.getElementById('chatMessages');
  if (!c) return;
  const html = renderMarkdown(t);
  const qr = (opts.quickReplies || []).map(q => `<span class="quick-reply">${esc(q)}</span>`).join('');
  // V4.6: AI 思考过程折叠面板
  const thinking = opts.thinking ? `
    <details class="ai-thinking">
      <summary>思考过程</summary>
      <div class="ai-thinking-body">${esc(opts.thinking)}</div>
    </details>` : '';
  const now = Date.now();
  const prefix = maybeSessionDivider(now);
  c.innerHTML += `${prefix}<div class="chat-msg agent" data-seq="${_msgSeq++}">
    <div class="avatar agent-avatar">AI</div>
    <div class="bubble-col">
      ${thinking}
      <div class="bubble">${html}</div>
      ${qr ? `<div class="quick-replies">${qr}</div>` : ''}
    </div>
  </div><div class="chat-msg-time">${fmtTime(now)}</div>`;
  _lastMsgTime = now;
  scrollToBottom();
  if (qr) bindQuickReplies();
}

function bindQuickReplies() {
  document.querySelectorAll('.quick-reply').forEach(el => {
    el.onclick = () => {
      const t = el.textContent;
      addUser(t); reply(t);
    };
  });
}

function addLoading() {
  const c = document.getElementById('chatMessages');
  if (!c) return null;
  const id = 'loading-' + Date.now();
  c.innerHTML += `<div class="chat-msg agent" id="${id}">
    <div class="avatar agent-avatar">AI</div>
    <div class="bubble-col">
      <div class="bubble loading"><span class="dot1"></span><span class="dot2"></span><span class="dot3"></span></div>
    </div>
  </div>`;
  scrollToBottom();
  return id;
}

function replaceLoading(id, text) {
  if (!id) return addAgent(text);
  const el = document.getElementById(id);
  if (el) {
    const b = el.querySelector('.bubble');
    b.classList.remove('loading');
    b.innerHTML = renderMarkdown(text);
    scrollToBottom();
  } else {
    addAgent(text);
  }
}

// V4.6 增强 markdown：行内 code / 链接 / **加粗** / 列表 / 引用 / 换行
// 顺序很关键：先处理 code（避免被 ** 误伤）→ 链接 → **加粗** → 按行处理列表/引用
function renderMarkdown(s) {
  const escaped = esc(s);
  let html = escaped.replace(/`([^`]+?)`/g, '<code>$1</code>');
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');

  const lines = html.split('\n');
  const out = [];
  let inList = false, inQuote = false;
  for (const line of lines) {
    const t = line.trim();
    if (t.startsWith('> ')) {
      if (inList) { out.push('</ul>'); inList = false; }
      if (!inQuote) { out.push('<blockquote>'); inQuote = true; }
      out.push(t.slice(2));
    } else if (/^[-•*]\s+/.test(t)) {
      if (inQuote) { out.push('</blockquote>'); inQuote = false; }
      if (!inList) { out.push('<ul>'); inList = true; }
      out.push('<li>' + t.replace(/^[-•*]\s+/, '') + '</li>');
    } else {
      if (inList) { out.push('</ul>'); inList = false; }
      if (inQuote) { out.push('</blockquote>'); inQuote = false; }
      out.push(line);
    }
  }
  if (inList) out.push('</ul>');
  if (inQuote) out.push('</blockquote>');
  return out.join('').replace(/\n/g, '<br/>');
}

function scrollToBottom() {
  const c = document.getElementById('chatMessages');
  if (c) c.scrollTop = c.scrollHeight;
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
