// agentChat.js — V0.7 对话控制台
//
// 改动：
// - 真实模式下仍 POST /api/chat 调 DeepSeek
// - 离线/demo 模式：使用 demoData.matchScriptedReply() 给出"流动但非真实"回复
// - 预载脚本对话（首屏可见）
// - 快捷问题 chips

import { matchScriptedReply } from './demoData.js';

const $history = () => document.getElementById('chat-history');
const $input = () => document.getElementById('chat-input');
const $form = () => document.getElementById('chat-form');
const $send = () => document.getElementById('btn-send');
const $suggest = () => document.getElementById('chat-suggest');

let chatHistory = [];
let initialized = false;

// ============================================================
// 公开：初始化（可重复调用，tab 切换时重渲染）
// ============================================================
export function initAgentChat() {
  if (initialized) return;
  initialized = true;

  bindForm();
  renderSuggestChips();
  preloadScriptedChat();
  console.log('[agentChat] 初始化完成');
}

// ============================================================
// 表单
// ============================================================
function bindForm() {
  const form = $form();
  if (!form) return;
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const msg = $input().value;
    sendChat(msg);
  });
}

// ============================================================
// 快捷问题 chips
// ============================================================
const SUGGESTS = [
  '当前客流如何？',
  '最近有什么异常？',
  '什么商品最火？',
  '排队情况？',
  '生成今日报告',
];

function renderSuggestChips() {
  const wrap = $suggest();
  if (!wrap) return;
  wrap.innerHTML = SUGGESTS.map((s) => `<span class="chip" data-q="${s}">${s}</span>`).join('');
  wrap.querySelectorAll('.chip').forEach((c) => {
    c.addEventListener('click', () => sendChat(c.dataset.q));
  });
}

// ============================================================
// 预载脚本对话（首屏即可见"对话流"）
// ============================================================
function preloadScriptedChat() {
  const wrap = $history();
  if (!wrap) return;
  if (wrap.children.length > 0) return;  // 已存在则不重复

  addChatMsg('assistant',
    '👋 你好，我是 **Insight Agent 商业助手**。\n\n' +
    '可以问我：\n' +
    '· 当前等位 / 翻台情况\n' +
    '· 最近异常事件 / 异常行为\n' +
    '· 哪个菜品最火、库存如何\n' +
    '· 收银台排队 / 服务员到位情况\n\n' +
    '也可点击下方"生成阶段报告"获取完整 4 段式分析。',
    'Agent'
  );

  // 模拟几轮"用户↔Agent"对话
  setTimeout(() => addChatMsg('user', '现在等位情况怎么样？', 'You'), 800);
  setTimeout(() => addChatMsg('assistant',
    '当前等位 **12 桌**，预计等待 20 分钟。\n\n入口等位区已坐满，**卡座区 3 桌**用餐已超 70 分钟。建议：\n· 开放 2F 备用散台 4 桌\n· 主动询问加菜 / 准备买单\n· 收银台增开 1 号备用通道',
    'Agent'), 1800);
  setTimeout(() => addChatMsg('user', '有什么需要我关注的？', 'You'), 3000);
  setTimeout(() => addChatMsg('assistant',
    '检测到 2 条需要你关注：\n\n· **HIGH · 等位预警** —— 入口等位区已积压 8 桌\n· **HIGH · 异常行为** —— 包间商务客人长时间等待未点单\n\n均已通知领班跟进。详见左侧"实时建议"卡片。',
    'Agent'), 4200);
}

// ============================================================
// 消息渲染
// ============================================================
function addChatMsg(role, text, avatarText) {
  const wrap = $history();
  if (!wrap) return;
  const div = document.createElement('div');
  div.className = `chat-msg chat-${role}`;
  const initial = avatarText || (role === 'user' ? 'U' : 'AI');
  // Markdown-lite: **bold** → <strong>; \n → <br>
  const html = escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^·\s/gm, '· ')
    .replace(/\n/g, '<br>');
  div.innerHTML = `
    <div class="avatar">${initial}</div>
    <div>
      <div class="bubble">${html}</div>
      <div class="meta">${new Date().toLocaleTimeString('zh-CN', { hour12: false })} · ${role === 'user' ? 'YOU' : 'AGENT'}</div>
    </div>
  `;
  wrap.appendChild(div);
  wrap.scrollTop = wrap.scrollHeight;
}

function setLoading(loading) {
  const wrap = $history();
  if (!wrap) return;
  if (!loading) {
    const loader = wrap.querySelector('.chat-loading');
    if (loader) loader.remove();
    return;
  }
  const div = document.createElement('div');
  div.className = 'chat-msg chat-assistant chat-loading';
  div.innerHTML = `<div class="avatar">AI</div><div><div class="bubble"><span class="typing">思考中</span></div></div>`;
  wrap.appendChild(div);
  wrap.scrollTop = wrap.scrollHeight;
}

// ============================================================
// 发送
// ============================================================
async function sendChat(message) {
  if (!message || !message.trim()) return;
  message = message.trim();

  addChatMsg('user', message, 'You');
  chatHistory.push({ role: 'user', content: message });
  $input().value = '';
  setLoading(true);
  $send().disabled = true;

  // 优先尝试真实 API；失败回退到脚本
  let response = null;
  try {
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history: chatHistory.slice(0, -1) }),
    });
    if (resp.ok) {
      const data = await resp.json();
      if (data.ok && data.response) response = data.response;
    }
  } catch (_) {
    // 离线 → 用脚本
  }

  // 模拟轻微延迟，更有"思考"感
  await new Promise((r) => setTimeout(r, 600 + Math.random() * 800));

  if (!response) {
    response = matchScriptedReply(message);
  }

  setLoading(false);
  addChatMsg('assistant', response, 'Agent');
  chatHistory.push({ role: 'assistant', content: response });
  if (chatHistory.length > 12) chatHistory = chatHistory.slice(-12);
  $send().disabled = false;
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
