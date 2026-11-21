/* ============================================
   DemoData — 城市维度 · 餐饮 Demo 数据生成器
   热区 = 城市商圈/餐饮聚集区 + 菜系标签
   源区 = 居住区/办公区/大学城（人流来源）
   ============================================ */

import { store } from './store.js';
import { bus } from './eventBus.js';

let _timers = [];

// 来源区类型（人流从哪里来）
const SOURCE_TYPES = {
  residential: { label: '居住区', color: '#4F7942' },
  office:      { label: '办公区', color: '#1B4A6B' },
  university:  { label: '大学城', color: '#8B1A1A' },
  transit:     { label: '交通枢纽', color: '#B8860B' },
};

// 来源区坐标（每个城市配 3-4 个来源区）
const SOURCE_ZONES = {
  天津: [
    { name: '南开居住区', type: 'residential', lngOff: -0.018, latOff: 0.012 },
    { name: '华苑产业园', type: 'office', lngOff: -0.022, latOff: -0.008 },
    { name: '海河教育园', type: 'university', lngOff: -0.025, latOff: -0.015 },
    { name: '天津站枢纽', type: 'transit', lngOff: 0.015, latOff: 0.010 },
  ],
  北京: [
    { name: '回龙观居住区', type: 'residential', lngOff: -0.015, latOff: 0.020 },
    { name: '中关村科技园', type: 'office', lngOff: -0.008, latOff: 0.012 },
    { name: '海淀大学城', type: 'university', lngOff: -0.018, latOff: 0.008 },
    { name: '北京南站枢纽', type: 'transit', lngOff: 0.005, latOff: -0.005 },
  ],
  上海: [
    { name: '闵行居住区', type: 'residential', lngOff: -0.020, latOff: -0.012 },
    { name: '张江科技园', type: 'office', lngOff: 0.018, latOff: -0.008 },
    { name: '松江大学城', type: 'university', lngOff: -0.028, latOff: -0.018 },
    { name: '虹桥枢纽', type: 'transit', lngOff: -0.010, latOff: 0.005 },
  ],
  深圳: [
    { name: '龙华居住区', type: 'residential', lngOff: 0.015, latOff: 0.018 },
    { name: '南山科技园', type: 'office', lngOff: -0.018, latOff: 0.006 },
    { name: '深大大学城', type: 'university', lngOff: -0.012, latOff: 0.012 },
    { name: '深圳北站枢纽', type: 'transit', lngOff: 0.010, latOff: 0.015 },
  ],
  广州: [
    { name: '番禺居住区', type: 'residential', lngOff: -0.018, latOff: -0.015 },
    { name: '天河科技园', type: 'office', lngOff: 0.015, latOff: -0.005 },
    { name: '大学城校区', type: 'university', lngOff: -0.022, latOff: -0.008 },
    { name: '广州南站枢纽', type: 'transit', lngOff: -0.015, latOff: -0.018 },
  ],
  成都: [
    { name: '高新居住区', type: 'residential', lngOff: -0.020, latOff: -0.010 },
    { name: '天府软件园', type: 'office', lngOff: 0.018, latOff: -0.012 },
    { name: '温江大学城', type: 'university', lngOff: -0.025, latOff: -0.018 },
    { name: '成都东站枢纽', type: 'transit', lngOff: 0.010, latOff: 0.008 },
  ],
  杭州: [
    { name: '余杭居住区', type: 'residential', lngOff: -0.018, latOff: 0.015 },
    { name: '滨江科技园', type: 'office', lngOff: 0.012, latOff: -0.012 },
    { name: '下沙大学城', type: 'university', lngOff: 0.022, latOff: -0.005 },
    { name: '杭州东站枢纽', type: 'transit', lngOff: 0.008, latOff: 0.008 },
  ],
};

// 城市商圈库 (名称 + 菜系标签)
const DISTRICTS = {
  天津: [
    { name: '滨江道商圈',   cuisine: '火锅/烧烤',  lngOff: 0.005,  latOff: 0.002 },
    { name: '五大道景区',   cuisine: '西餐/咖啡',  lngOff: -0.008, latOff: 0.004 },
    { name: '意式风情区',   cuisine: '异国料理',  lngOff: 0.012,  latOff: -0.003 },
    { name: '鼓楼文化街',   cuisine: '天津菜/小吃',lngOff: -0.004, latOff: 0.006 },
    { name: '奥城商业区',   cuisine: '日料/韩餐',  lngOff: -0.015, latOff: -0.005 },
    { name: '大悦城商圈',   cuisine: '综合餐饮',   lngOff: 0.010,  latOff: -0.007 },
  ],
  北京: [
    { name: '王府井商圈',   cuisine: '烤鸭/京菜',  lngOff: 0.008,  latOff: 0.003 },
    { name: '三里屯街区',   cuisine: '酒吧/西餐',  lngOff: 0.018,  latOff: -0.002 },
    { name: '簋街美食街',   cuisine: '麻辣/小龙虾',lngOff: 0.012,  latOff: -0.006 },
    { name: '国贸CBD',      cuisine: '高端商务餐',  lngOff: 0.020,  latOff: -0.010 },
    { name: '南锣鼓巷',     cuisine: '小吃/文创',   lngOff: 0.005,  latOff: 0.008 },
  ],
  上海: [
    { name: '南京路商圈',   cuisine: '本帮菜/综合',lngOff: 0.008,  latOff: 0.002 },
    { name: '外滩观景区',   cuisine: '高端餐饮',     lngOff: 0.014,  latOff: -0.001 },
    { name: '新天地街区',   cuisine: '酒吧/西餐',    lngOff: 0.006,  latOff: -0.005 },
    { name: '静安寺商圈',   cuisine: '日料/甜品',    lngOff: -0.005, latOff: 0.003 },
    { name: '徐家汇商圈',   cuisine: '综合餐饮',     lngOff: -0.012, latOff: -0.008 },
  ],
  深圳: [
    { name: '华强北商圈',   cuisine: '潮汕牛肉/快餐',lngOff: 0.005,  latOff: 0.004 },
    { name: '海岸城商圈',   cuisine: '粤菜/海鲜',   lngOff: -0.010, latOff: -0.005 },
    { name: '东门步行街',   cuisine: '小吃/夜市',   lngOff: 0.012,  latOff: 0.002 },
    { name: '南山科技园',   cuisine: '简餐/轻食',   lngOff: -0.018, latOff: 0.006 },
    { name: '福田CBD',      cuisine: '商务餐饮',     lngOff: 0.002,  latOff: -0.008 },
  ],
  广州: [
    { name: '天河CBD',      cuisine: '综合餐饮',    lngOff: 0.010,  latOff: -0.004 },
    { name: '北京路商圈',   cuisine: '粤菜/烧腊',   lngOff: 0.004,  latOff: 0.002 },
    { name: '上下九商圈',   cuisine: '小吃/甜品',   lngOff: -0.002, latOff: 0.006 },
    { name: '琶洲展馆区',   cuisine: '会展餐饮',     lngOff: 0.020,  latOff: -0.012 },
    { name: '珠江新城',     cuisine: '高端餐饮',     lngOff: 0.008,  latOff: -0.006 },
  ],
  成都: [
    { name: '春熙路商圈',   cuisine: '火锅/川菜',  lngOff: 0.006,  latOff: 0.003 },
    { name: '宽窄巷子',     cuisine: '川菜/小吃',  lngOff: -0.004, latOff: 0.006 },
    { name: '锦里古街',     cuisine: '小吃/特产',  lngOff: -0.008, latOff: -0.005 },
    { name: '太古里商圈',   cuisine: '轻奢餐饮',    lngOff: 0.012,  latOff: -0.002 },
    { name: '九眼桥酒吧街', cuisine: '酒吧/夜宵',  lngOff: 0.015,  latOff: -0.008 },
  ],
  杭州: [
    { name: '西湖景区',     cuisine: '杭帮菜/龙井',lngOff: -0.005, latOff: 0.008 },
    { name: '武林广场',     cuisine: '综合餐饮',    lngOff: 0.008,  latOff: -0.002 },
    { name: '钱江新城',     cuisine: '商务餐饮',    lngOff: 0.018,  latOff: -0.010 },
    { name: '河坊街',       cuisine: '小吃/老字号',lngOff: -0.008, latOff: 0.002 },
    { name: '湖滨银泰',     cuisine: '轻食/甜品',  lngOff: 0.002,  latOff: 0.004 },
  ],
};

const CUISINE_TYPES = ['火锅', '烧烤', '川菜', '粤菜', '日料', '韩餐', '西餐', '本帮菜', '小吃', '酒吧'];

function generateTick(city) {
  const districts = DISTRICTS[city] || DISTRICTS['天津'];
  const count = 5;  // 固定 5 个热门区域（与热门区域 TOP 5 对齐）
  const c = store.get('city.center');
  const hs = [];

  for (let i = 0; i < count; i++) {
    const d = districts[i];
    hs.push({
      lng: c[0] + d.lngOff + (Math.random() - 0.5) * 0.008,
      lat: c[1] + d.latOff + (Math.random() - 0.5) * 0.005,
      radius: 300 + Math.random() * 500,
      value: 30 + Math.random() * 70,
      name: d.name,
      cuisine: d.cuisine,
    });
  }

  const cuisineMap = {};
  CUISINE_TYPES.forEach(cuisine => {
    const matched = hs.filter(h => h.cuisine.includes(cuisine.split('/')[0]) || h.cuisine.includes(cuisine));
    cuisineMap[cuisine] = matched.reduce((s, h) => s + h.value, 0) + Math.random() * 20;
  });
  const total = Object.values(cuisineMap).reduce((s, v) => s + v, 0);
  const share = {};
  Object.entries(cuisineMap).forEach(([k, v]) => { share[k] = Math.round(v / total * 100); });
  const topEntry = Object.entries(share).sort((a, b) => b[1] - a[1])[0];

  store.set('dining.hotspots', hs);
  store.set('dining.cuisineShare', share);
  store.set('dining.topCuisine', topEntry[0]);
  store.set('dining.hotspotCount', count);
  store.set('dining.growthRate', Math.round((Math.random() * 20 - 5)));

  bus.emit('hotspots:updated', hs);
  bus.emit('cuisine:updated', share);

  const sources = SOURCE_ZONES[city] || SOURCE_ZONES['天津'];
  const flows = [];
  const hour = new Date().getHours();
  sources.forEach((src, si) => {
    const timeWeight = hour >= 11 && hour <= 13 ? [0.8, 0.6, 0.3, 0.5]
                     : hour >= 17 && hour <= 20 ? [0.7, 0.4, 0.6, 0.5]
                     : hour >= 21 ? [0.3, 0.1, 0.7, 0.3]
                     : [0.4, 0.3, 0.3, 0.4];
    const targets = hs.slice(0, Math.min(3, hs.length));
    targets.forEach((tgt, ti) => {
      if (Math.random() < 0.6 || flows.length === 0) {
        const baseW = timeWeight[si % 4] || 0.5;
        flows.push({
          from: { lng: c[0] + src.lngOff, lat: c[1] + src.latOff, name: src.name, type: src.type },
          to: { lng: tgt.lng, lat: tgt.lat, name: tgt.name, cuisine: tgt.cuisine },
          volume: Math.round(20 + Math.random() * 60 * baseW),
        });
      }
    });
  });

  bus.emit('flows:updated', flows);

  const sourceCoords = sources.map(s => ({
    lng: c[0] + s.lngOff, lat: c[1] + s.latOff, name: s.name, type: s.type,
  }));
  bus.emit('sources:updated', sourceCoords);

  const snap = {
    t: Date.now(), hotspots: hs, flows,
    diners: Math.round(flows.reduce((s, f) => s + (f.volume || 0), 0) * 8 + 30),
    topCuisine: topEntry[0], cuisineShare: share, hotspotCount: count,
    growthRate: Math.round((Math.random() * 20 - 5)),
  };
  bus.emit('snapshot:new', snap);
}

export function startDemoData(city = '天津') {
  // 立即生成首帧数据（不再等4秒）
  generateTick(city);

  // 热区数据更新 (每4秒)
  _timers.push(setInterval(() => generateTick(city), 4000));

  // Agent 城市级建议 (每10秒)
  _timers.push(setInterval(() => {
    const city = store.get('city.name');
    const advices = [
      { priority: 'high', title: `${city}餐饮供需分析`, desc: `${city}滨江道商圈火锅类餐饮需求旺盛，人均等位超25分钟。该区域火锅店铺密度已达临界点，建议关注五大道/奥城等新兴商圈布局差异化火锅品牌。` },
      { priority: 'high', title: '菜系空白区域发现', desc: '城西新兴居住区（中北镇—张家窝板块）餐饮供给严重不足，2公里内无品牌火锅/烧烤店，常住人口超8万，属于高潜力餐饮洼地。' },
      { priority: 'medium', title: '餐饮消费趋势洞察', desc: `过去7天${city}全市餐饮数据显示：川湘菜搜索量+28%、轻食沙拉+35%、深夜烧烤+22%。建议关注"辣味升级+健康轻食"双线趋势。` },
      { priority: 'medium', title: '商圈差异化竞争', desc: '滨江道火锅店铺已达23家（平均评分4.1），同质化严重。建议新入局者主打"一人食火锅"或"火锅+精酿"差异化定位，避开红海竞争。' },
      { priority: 'medium', title: '季节性消费预判', desc: '进入6月，本市户外餐饮（露台/大排档/夜市）搜索量月增40%。建议品牌提前布局户外餐位和夏季限定菜单（凉菜/冰品/啤酒）。' },
      { priority: 'low', title: '外卖潜力区域', desc: '大学城及高新产业园区域午间外卖订单密度最高，但火锅类外卖渗透率不足5%（受配送难度限制），建议开发"火锅冒菜化"外卖产品线。' },
      { priority: 'low', title: '深夜经济机会', desc: '22:00后仍在营业的餐饮店铺仅占全市12%，而夜间餐饮搜索量占比28%。建议在核心商圈延长营业时间或推出深夜限定菜单。' },
    ];
    const a = advices[Math.floor(Math.random() * advices.length)];
    bus.emit('advice:new', { ...a, time: Date.now() });
  }, 10000));

  // 时钟
  _timers.push(setInterval(() => {
    document.getElementById('timestamp').textContent = new Date().toLocaleString('zh-CN');
  }, 1000));
}

export function stopDemoData() {
  _timers.forEach(id => clearInterval(id));
  _timers = [];
}

export default { startDemoData, stopDemoData };
