/* ============================================
   Behavior — 城市餐饮维度 · 行为分析引擎
   事件类型：菜系偏好/商圈客流/热度转移/热区形成/深夜餐饮
   ============================================ */

import { store } from './store.js';
import { bus } from './eventBus.js';

const EVENT_TYPES = {
  cuisine_surge:    { icon: '🍲', label: '菜系激增',  severity: 'high' },
  district_peak:    { icon: '🔥', label: '商圈高峰',  severity: 'high' },
  heat_shift:       { icon: '🔄', label: '热度转移',  severity: 'medium' },
  new_hotspot:      { icon: '📍', label: '新热区形成',severity: 'medium' },
  flow_predict:     { icon: '🔮', label: '流向预测',  severity: 'high' },
  cuisine_shift:    { icon: '📊', label: '口味变迁',  severity: 'medium' },
  night_dining:     { icon: '🌙', label: '深夜餐饮',  severity: 'low' },
  weekend_surge:    { icon: '📈', label: '周末暴涨',  severity: 'medium' },
  local_preference: { icon: '🏠', label: '本地偏好',  severity: 'low' },
  density_warning:  { icon: '⚠️', label: '过密预警',  severity: 'high' },
  cold_zone:        { icon: '❄️', label: '餐饮洼地',  severity: 'low' },
  source_feed:      { icon: '🏘️', label: '来源洞察',  severity: 'medium' },
};

let _timer = null;
let _history = [];
let _latestFlows = [];

// 监听流向更新
import { bus as eventBus } from './eventBus.js';
eventBus.on('flows:updated', flows => { _latestFlows = flows; });

export function startAnalysis(ms = 2500) {
  if (_timer) return;
  _timer = setInterval(() => {
    const result = run();
    result.events.forEach(e => addEvent(e));
    bus.emit('analysis:updated', result);
  }, ms);
  console.log('[Behavior] 城市餐饮分析引擎启动');
}

export function stopAnalysis() {
  if (_timer) { clearInterval(_timer); _timer = null; }
}

function run() {
  const d = store.get('dining');
  const diners = d.diners || 300;
  const hotspots = d.hotspots || [];
  const topCuisine = d.topCuisine || '火锅';
  const events = [];
  const now = Date.now();

  // 菜系激增
  if (diners > 800) {
    events.push({ type: 'cuisine_surge', time: now, location: '全市', desc: `${topCuisine}类餐饮客流激增至 ${diners} 人，热度远超其他菜系`, data: { diners, topCuisine } });
  }

  // 商圈高峰
  if (hotspots.length > 0 && hotspots[0].value > 80) {
    events.push({ type: 'district_peak', time: now, location: hotspots[0].name, desc: `${hotspots[0].name} 餐饮客流达峰值，${hotspots[0].cuisine || '综合'}类餐厅上座率超90%`, data: { hotspot: hotspots[0] } });
  }

  // 热度转移
  if (d._prevHotspots && d._prevHotspots.length > 0 && hotspots.length > 0) {
    if (hotspots[0].name !== d._prevHotspots[0]?.name) {
      events.push({ type: 'heat_shift', time: now, location: hotspots[0].name, desc: `餐饮热度从 ${d._prevHotspots[0].name} 转移至 ${hotspots[0].name}，后者客流 +${Math.round((hotspots[0].value - (d._prevHotspots[0]?.value || 50)) / (d._prevHotspots[0]?.value || 1) * 100)}%`, data: {} });
    }
  }

  // 新热区形成
  if (d._prevCount != null && hotspots.length > d._prevCount) {
    events.push({ type: 'new_hotspot', time: now, location: hotspots[hotspots.length - 1]?.name || '新区域', desc: `新增餐饮热区: ${hotspots[hotspots.length - 1]?.name}，该区域${hotspots[hotspots.length - 1]?.cuisine || '餐饮'}消费正在兴起`, data: {} });
  }

  // 深夜餐饮
  const hour = new Date().getHours();
  if ((hour >= 22 || hour <= 1) && diners > 150 && Math.random() < 0.3) {
    events.push({ type: 'night_dining', time: now, location: '夜经济区', desc: `深夜餐饮时段活跃，${topCuisine}类夜宵需求突出，酒吧/烧烤/大排档区域客流集中`, data: {} });
  }

  // 周末暴涨
  const day = new Date().getDay();
  if ((day === 0 || day === 6) && diners > 600 && Math.random() < 0.25) {
    events.push({ type: 'weekend_surge', time: now, location: '全市', desc: `周末餐饮客流同比平日 +35%，${topCuisine}成最大赢家`, data: {} });
  }

  // 本地偏好
  if (Math.random() < 0.15) {
    const local = { 天津: '煎饼果子/锅巴菜', 北京: '涮羊肉/烤鸭', 上海: '本帮菜/生煎', 深圳: '粤菜/潮汕牛肉火锅', 广州: '早茶/烧腊', 成都: '火锅/串串', 杭州: '杭帮菜/片儿川' };
    const city = store.get('city.name');
    const pref = local[city] || '本地特色';
    events.push({ type: 'local_preference', time: now, location: '本地餐饮', desc: `${city}本地偏好分析：${pref}仍是食客首选，占比${30 + Math.round(Math.random() * 20)}%`, data: {} });
  }

  // 过密预警
  if (hotspots.length === 1 && diners > 700) {
    events.push({ type: 'density_warning', time: now, location: hotspots[0].name, desc: `全市餐饮客流过度集中在 ${hotspots[0].name}，其他区域餐饮消费不足，建议引导分散`, data: {} });
  }

  // 餐饮洼地
  if (hotspots.length > 2 && Math.random() < 0.12) {
    events.push({ type: 'cold_zone', time: now, location: '城郊区域', desc: `城郊及新兴居住区餐饮供给不足，存在市场空白`, data: {} });
  }

  // ---- 流向预测 ----
  if (_latestFlows.length > 0 && Math.random() < 0.35) {
    const topFlow = [..._latestFlows].sort((a, b) => b.volume - a.volume)[0];
    if (topFlow) {
      events.push({
        type: 'flow_predict',
        time: now,
        location: topFlow.to.name,
        desc: `流向预测：来自${topFlow.from.name}的食客正大量涌向${topFlow.to.name}(${topFlow.to.cuisine})，预计该区域未来30分钟客流+${Math.round(topFlow.volume * 0.4)}%`,
        data: { from: topFlow.from.name, to: topFlow.to.name, volume: topFlow.volume },
      });
    }
  }

  // 来源洞察
  if (_latestFlows.length > 0 && Math.random() < 0.25) {
    const byType = {};
    _latestFlows.forEach(f => {
      byType[f.from.type] = (byType[f.from.type] || 0) + f.volume;
    });
    const topType = Object.entries(byType).sort((a, b) => b[1] - a[1])[0];
    const typeLabel = { residential: '居住区', office: '办公区', university: '大学城', transit: '交通枢纽' };
    if (topType) {
      events.push({
        type: 'source_feed',
        time: now,
        location: '全市',
        desc: `食客来源洞察：当前${typeLabel[topType[0]] || topType[0]}人群是餐饮消费主力，占比约${Math.round(topType[1] / _latestFlows.reduce((s,f)=>s+f.volume,0) * 100)}%`,
        data: { sourceType: topType[0] },
      });
    }
  }

  // 保存历史
  d._prevHotspots = [...hotspots];
  d._prevCount = hotspots.length;

  return { timestamp: now, diners, topCuisine, hotspotCount: hotspots.length, events };
}

function addEvent(evt) {
  const info = EVENT_TYPES[evt.type] || { icon: '📌', label: '未知', severity: 'low' };
  const enriched = { ...evt, icon: info.icon, label: info.label, severity: info.severity };
  _history.unshift(enriched);
  if (_history.length > 60) _history.pop();
  bus.emit('event:new', enriched);
}

export function computeHotspotRanking(hotspots) {
  if (!hotspots || !hotspots.length) return [];
  return [...hotspots].sort((a, b) => b.value - a.value).slice(0, 5).map((h, i) => ({
    rank: i + 1, name: h.name, value: h.value,
    cuisine: h.cuisine || '综合餐饮',
    change: Math.round((Math.random() - 0.35) * 25),
  }));
}

export function generateHeatData(hotspots) {
  return (hotspots || []).map(h => ({ lng: h.lng, lat: h.lat, count: h.value }));
}

export { EVENT_TYPES };

export default { startAnalysis, stopAnalysis, computeHotspotRanking, generateHeatData, EVENT_TYPES };
