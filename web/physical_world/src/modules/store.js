// 借鉴 自 参考-多模态数字图书馆/store.js
// 极简响应式状态管理，支持 dot path（store.set('cam.enabled', true)）

import { emit } from './eventBus.js';

const state = {};
const subscribers = new Map(); // path -> Set<callback>

function getPath(path) {
  return path.split('.');
}

function getValue(obj, parts) {
  let cur = obj;
  for (const p of parts) {
    if (cur == null) return undefined;
    cur = cur[p];
  }
  return cur;
}

function setValue(obj, parts, value) {
  let cur = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    const p = parts[i];
    if (typeof cur[p] !== 'object' || cur[p] === null) cur[p] = {};
    cur = cur[p];
  }
  cur[parts[parts.length - 1]] = value;
}

function notifyWatchers(parts, value) {
  const fullPath = parts.join('.');
  for (const [path, set] of subscribers) {
    if (path === fullPath || fullPath.startsWith(path + '.') || path.startsWith(fullPath + '.')) {
      for (const cb of set) {
        try { cb(getValue(state, parts), value); } catch (e) { console.error(e); }
      }
    }
  }
}

export function get(path) {
  if (!path) return { ...state };
  return getValue(state, getPath(path));
}

export function set(path, value) {
  const parts = getPath(path);
  setValue(state, parts, value);
  notifyWatchers(parts, value);
  emit('state:changed', { path, value });
}

export function watch(path, callback) {
  if (!subscribers.has(path)) subscribers.set(path, new Set());
  subscribers.get(path).add(callback);
  return () => {
    const set = subscribers.get(path);
    if (set) set.delete(callback);
  };
}

export function reset() {
  for (const k of Object.keys(state)) delete state[k];
  subscribers.clear();
  emit('state:reset');
}
