/* ============================================
   Store — 城市餐饮维度 · 响应式状态管理
   ============================================ */

class Store {
  constructor(initial = {}) {
    this._state = JSON.parse(JSON.stringify(initial));
    this._watchers = {};
  }

  get(path) {
    return path.split('.').reduce((o, k) => (o != null ? o[k] : undefined), this._state);
  }

  set(path, value) {
    const keys = path.split('.');
    let obj = this._state;
    for (let i = 0; i < keys.length - 1; i++) {
      if (!(keys[i] in obj)) obj[keys[i]] = {};
      obj = obj[keys[i]];
    }
    const old = obj[keys[keys.length - 1]];
    obj[keys[keys.length - 1]] = value;
    this._notify(path, value, old);
  }

  watch(path, fn) {
    if (!this._watchers[path]) this._watchers[path] = [];
    this._watchers[path].push(fn);
  }

  _notify(path, value, old) {
    if (this._watchers[path]) {
      this._watchers[path].forEach(fn => fn(value, old));
    }
  }

  reset(initial) { this._state = JSON.parse(JSON.stringify(initial)); }
}

export const store = new Store({
  map: { loaded: false },
  city: { name: '天津', center: [117.1903, 39.1252], zoom: 15 },
  dining: {
    diners: 0,           // 全市实时餐饮客流
    topCuisine: '火锅',  // 当前最热门菜系
    cuisineShare: {},    // 菜系占比 {火锅:38, 烧烤:22, ...}
    hotspotCount: 0,     // 餐饮热区数
    growthRate: 0,       // 客流增长率 %
    hotspots: [],        // 餐饮热区列表
  },
  system: { sysOk: true, mapOk: true, engineOk: true },
  history: { length: 0 }, // 时间轴回放帧数（实际快照在 timeline.js 内部）
});
