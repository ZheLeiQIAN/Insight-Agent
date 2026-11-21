/* ============================================
   AMap V4 — 高德地图核心 (学术风格)
   - 浅色底图 + 菜系图标标记 + InfoWindow 弹窗
   - 标记按入流量分级脉冲
   - 城市切换 fly + 遮罩
   ============================================ */

import { store } from './store.js';
import { bus } from './eventBus.js';

const CITY_CONFIG = {
  tianjin: { name: '天津', center: [117.1903, 39.1252], zoom: 15 },
  beijing: { name: '北京', center: [116.3974, 39.9092], zoom: 15 },
  shanghai: { name: '上海', center: [121.4737, 31.2304], zoom: 15 },
  shenzhen: { name: '深圳', center: [114.0579, 22.5431], zoom: 15 },
  guangzhou: { name: '广州', center: [113.2644, 23.1291], zoom: 15 },
  chengdu: { name: '成都', center: [104.0665, 30.5728], zoom: 15 },
  hangzhou: { name: '杭州', center: [120.1551, 30.2741], zoom: 15 },
};

const CUISINE_ICON = {
  '火锅': '🍲', '烧烤': '🔥', '川菜': '🌶', '粤菜': '🥘',
  '日料': '🍣', '韩餐': '🍱', '西餐': '🍷', '小吃': '🥟',
  '酒吧': '🍻', '本帮菜': '🍚', '异国料理': '🥐', '综合餐饮': '🍽',
};

const CUISINE_KEY = (s) => {
  if (!s) return 'default';
  const head = String(s).split('/')[0].trim();
  return CUISINE_ICON[head] ? head : 'default';
};

let _map = null;
let _heatLayer = null;
let _markers = [];
let _markerData = [];   // 与 _markers 一一对应：{hotspot, volume, el}
let _infoWindow = null;
let _currentCityKey = 'tianjin';
let _pendingHotspots = null;  // V4: 地图未就绪时缓存，热区生成后回放
let _pendingIncoming = null;
let _pendingHeatData = null;

export function initMap() {
  const container = document.getElementById('amapContainer');
  if (!container) { console.error('[AMap] 找不到地图容器'); return null; }

  const city = store.get('city');
  _currentCityKey = Object.keys(CITY_CONFIG).find(k => CITY_CONFIG[k].name === city.name) || 'tianjin';

  _map = new AMap.Map(container, {
    zoom: city.zoom,
    center: new AMap.LngLat(city.center[0], city.center[1]),
    mapStyle: 'amap://styles/light',
    features: ['bg', 'road', 'building', 'point'],
    viewMode: '2D',
    zooms: [11, 18],
  });

  _map.addControl(new AMap.Scale({ position: 'LB' }));
  _map.addControl(new AMap.ToolBar({ position: 'RT', liteStyle: true }));

  _infoWindow = new AMap.InfoWindow({
    isCustom: true,
    autoMove: true,
    offset: new AMap.Pixel(0, -28),
    closeWhenClickMap: true,
  });

  store.set('map.loaded', true);
  document.getElementById('mapDot')?.classList.add('live');
  bus.emit('map:loaded', _map);
  console.log('[AMap V4] 地图初始化完成 (浅色学术风格 + 菜系标记)');
  return _map;
}

export function getMap() { return _map; }

export function zoomIn() { _map && _map.setZoom(_map.getZoom() + 1); }
export function zoomOut() { _map && _map.setZoom(_map.getZoom() - 1); }
export function resetView() {
  if (!_map) return;
  const city = store.get('city');
  _map.setZoomAndCenter(city.zoom, new AMap.LngLat(city.center[0], city.center[1]));
}

// 城市切换：fly + 遮罩 + 名称 marquee
export function switchCity(cityKey) {
  const config = CITY_CONFIG[cityKey];
  if (!config || !_map || cityKey === _currentCityKey) return;
  _currentCityKey = cityKey;

  store.set('city.name', config.name);
  store.set('city.center', config.center);
  store.set('city.zoom', config.zoom);

  // 名称 marquee
  const locEl = document.getElementById('cityLabel');
  if (locEl) {
    locEl.classList.add('swap');
    setTimeout(() => {
      locEl.textContent = '📍 ' + config.name;
      locEl.classList.remove('swap');
    }, 180);
  }

  // 遮罩层
  const container = document.getElementById('mapArea');
  const fade = document.createElement('div');
  fade.className = 'city-fade';
  fade.textContent = '· ' + config.name + ' ·';
  container?.appendChild(fade);
  setTimeout(() => fade.classList.add('fadeout'), 380);
  setTimeout(() => fade.remove(), 820);

  // fly：先 zoom-1（拉远）再回目标
  const curZoom = _map.getZoom();
  _map.setZoom(curZoom - 1.0, { duration: 600 });
  setTimeout(() => {
    _map.setZoomAndCenter(config.zoom, new AMap.LngLat(config.center[0], config.center[1]), { duration: 800 });
  }, 200);

  bus.emit('city:changed', config);
}

export function setHeatLayer(heatData) {
  if (!_map) { _pendingHeatData = heatData; return; }
  _pendingHeatData = heatData;
  flushPendingHeat();
}

function flushPendingHeat() {
  if (!_map) return;
  const heatData = _pendingHeatData;
  _pendingHeatData = null;
  if (!heatData || heatData.length === 0) return;
  if (_heatLayer) { _map.remove(_heatLayer); }
  _heatLayer = new AMap.HeatMap(_map, {
    radius: 40,
    opacity: [0.1, 0.7],
    gradient: {
      0.1: '#4F7942',
      0.3: '#B8860B',
      0.5: '#A53A3A',
      0.7: '#8B1A1A',
      0.9: '#5C1010',
    },
  });
  _heatLayer.setDataSet({ data: heatData, max: 100 });
}

export function toggleHeatLayer(visible) {
  if (_heatLayer) { visible ? _heatLayer.show() : _heatLayer.hide(); }
}

/* ---- 热区标记（菜系图标 + 入流量分级脉冲 + InfoWindow） ---- */
export function updateHotspotMarkers(hotspots, incomingMap = null) {
  if (!_map) {
    // V4: 地图未就绪时缓存，等地图加载后回放
    _pendingHotspots = hotspots;
    _pendingIncoming = incomingMap;
    return;
  }
  _pendingHotspots = hotspots;
  _pendingIncoming = incomingMap;
  doUpdateMarkers();
}

function doUpdateMarkers() {
  if (!_map) return;
  const hotspots = _pendingHotspots;
  const incomingMap = _pendingIncoming;
  if (!hotspots) return;
  _pendingHotspots = _pendingIncoming = null;

  _markers.forEach(m => _map.remove(m));
  _markers = [];
  _markerData = [];

  hotspots.forEach((h) => {
    const cuisineKey = CUISINE_KEY(h.cuisine);
    const icon = CUISINE_ICON[cuisineKey] || '📍';
    const volume = (incomingMap && incomingMap[h.name]) || h.value || 30;
    const tier = volume >= 50 ? 'high' : volume >= 20 ? 'mid' : 'low';
    const size = 28 + Math.min(12, volume / 12);

    const dom = document.createElement('div');
    dom.className = `hotspot-marker cui-${cuisineKey}`;
    dom.dataset.cuisine = cuisineKey;
    dom.dataset.incoming = tier;
    dom.style.width = size + 'px';
    dom.style.height = size + 'px';
    dom.innerHTML = `<span class="marker-pulse"></span><span class="marker-icon">${icon}</span>`;

    const marker = new AMap.Marker({
      position: new AMap.LngLat(h.lng, h.lat),
      offset: new AMap.Pixel(-size / 2, -size / 2),
      content: dom,
      zIndex: 100 + Math.round(volume),
    });
    marker.setMap(_map);
    _markers.push(marker);
    _markerData.push({ hotspot: h, volume, el: dom, marker });

    // 点击弹 InfoWindow
    marker.on('click', () => openMarkerPopup(h, volume, marker));
  });
}

// 监听地图就绪，回放缓存
bus.on('map:loaded', () => { doUpdateMarkers(); flushPendingHeat(); });

function openMarkerPopup(h, volume, marker) {
  const cuisineKey = CUISINE_KEY(h.cuisine);
  const cuisineName = h.cuisine || '综合餐饮';
  const occupancy = Math.min(98, 60 + Math.round((volume || 0) / 1.5));
  const suggest = pickSuggestionForCuisine(cuisineName, h.name);

  const html = `
    <div class="marker-popup">
      <div class="popup-title">${esc(h.name)}</div>
      <div class="popup-meta">${esc(cuisineName)} · 当前热力 ${Math.round(h.value || volume)}</div>
      <div class="popup-row"><span>入流量</span><b>${Math.round(volume)} 人/分</b></div>
      <div class="popup-row"><span>上座率</span><b>${occupancy}%</b></div>
      <div class="popup-row"><span>预计等位</span><b>${Math.max(0, Math.round(volume * 0.4))} 分钟</b></div>
      <div class="popup-suggest">${esc(suggest)}</div>
    </div>
  `;
  _infoWindow && _infoWindow.setContent(html);
  _infoWindow && _infoWindow.open(_map, marker.getPosition());
}

function pickSuggestionForCuisine(cuisine, name) {
  const map = {
    '火锅': `${name} 火锅客流高位，建议：① 增加 1-2 个临时等位区 ② 备菜/锅底消耗提前 1.5h 启动 ③ 大桌优先拼桌。`,
    '烧烤': `${name} 烧烤时段，建议：① 烤位排程优化（按桌位分配烤师）② 酒水组合促销拉高客单 ③ 户外位夏季提前开台。`,
    '川菜': `${name} 川菜客流高，建议：① 辣度分档菜单（微/中/特）② 午市套餐提效率 ③ 招牌菜食材按 1.3 倍备货。`,
    '粤菜': `${name} 粤菜讲究现做，建议：① 茶点+正餐分线出餐 ② 午市茶位翻台 1.5 次 ③ 烧腊档口排队引导。`,
    '日料': `${name} 日料客流，建议：① 寿司吧台/包间两线分流 ② 套餐替代单点 ③ 限时午市套餐 38 分钟出餐。`,
    '西餐': `${name} 西餐高峰，建议：① 前置点单二维码 ② 客座等位赠小食 ③ 酒水 8 折保客单。`,
    '小吃': `${name} 小吃快出，建议：① 招牌单品限量发售 ② 收银台+取餐分流 ③ 夜市档口延长至 23:30。`,
    '酒吧': `${name} 夜经济活跃，建议：① 主理人/乐队档排满 ② 酒水 2-3 人套餐 ③ 提前接受 22:00 后订位。`,
    '本帮菜': `${name} 本帮客流，建议：① 招牌老味道+新菜组合 ② 银发客群午后 7 折 ③ 家庭客 4 人套餐。`,
  };
  for (const k of Object.keys(map)) {
    if (cuisine.includes(k)) return map[k];
  }
  return `${name} 当前客流良好，建议保持现有排班与备货节奏，关注 30min 后流向预测再调整。`;
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

// 外部调用：高亮某标记（来自热区榜点击）
export function focusMarker(name) {
  let target = null;
  for (const m of _markerData) {
    if (m.hotspot.name === name) { target = m; break; }
  }
  if (!target) return;
  _markerData.forEach(m => m.el.classList.remove('focused'));
  void target.el.offsetWidth;
  target.el.classList.add('focused');
  _map.panTo([target.hotspot.lng, target.hotspot.lat]);
  setTimeout(() => target.el.classList.remove('focused'), 1600);
}


export default { initMap, getMap, zoomIn, zoomOut, resetView, switchCity, setHeatLayer, toggleHeatLayer, updateHotspotMarkers, focusMarker };
