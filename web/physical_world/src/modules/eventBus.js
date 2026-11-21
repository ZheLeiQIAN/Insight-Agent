// 借鉴 自 参考-多模态数字图书馆/eventBus.js
// 极简事件总线，支持事件订阅、发布、取消订阅

const subscribers = new Map(); // event -> Set<callback>

export function on(event, callback) {
  if (!subscribers.has(event)) {
    subscribers.set(event, new Set());
  }
  subscribers.get(event).add(callback);
  return () => off(event, callback);
}

export function off(event, callback) {
  const set = subscribers.get(event);
  if (set) {
    set.delete(callback);
    if (set.size === 0) subscribers.delete(event);
  }
}

export function emit(event, payload) {
  const set = subscribers.get(event);
  if (!set) return;
  for (const cb of set) {
    try {
      cb(payload);
    } catch (e) {
      console.error(`[eventBus] handler for "${event}" threw:`, e);
    }
  }
}

export function clear() {
  subscribers.clear();
}
