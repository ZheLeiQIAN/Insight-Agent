/* ============================================
   EventBus — 发布/订阅事件总线
   ============================================ */

class EventBus {
  constructor() {
    this._handlers = {};
  }

  on(event, handler) {
    if (!this._handlers[event]) this._handlers[event] = [];
    this._handlers[event].push(handler);
    return () => this.off(event, handler);
  }

  off(event, handler) {
    if (!this._handlers[event]) return;
    this._handlers[event] = this._handlers[event].filter(h => h !== handler);
  }

  emit(event, data) {
    if (!this._handlers[event]) return;
    this._handlers[event].forEach(h => {
      try { h(data); }
      catch (e) { console.error(`[bus] listener for "${event}" threw:`, e); }
    });
  }

  clear() {
    this._handlers = {};
  }
}

export const bus = new EventBus();
