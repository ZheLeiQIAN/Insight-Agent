// mediapipeLoader.js — 动态加载 MediaPipe Hands / FaceMesh / Camera Utils
// 借鉴 自 参考-多模态数字图书馆/js/interaction.js#loadMediaPipe
// 使用 CDN 加载 UMD bundle（避免 Vite + ESM + WASM 兼容问题）

const CDN_BASE = 'https://cdn.jsdelivr.net/npm/@mediapipe';
const SCRIPTS = {
  Hands: `${CDN_BASE}/hands/hands.js`,
  FaceMesh: `${CDN_BASE}/face_mesh/face_mesh.js`,
  Camera: `${CDN_BASE}/camera_utils/camera_utils.js`,
  DrawingUtils: `${CDN_BASE}/drawing_utils/drawing_utils.js`,
};

let loadingPromise = null;
let loaded = { Hands: false, FaceMesh: false, Camera: false, DrawingUtils: false };

function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) {
      resolve();
      return;
    }
    const s = document.createElement('script');
    s.src = src;
    s.crossOrigin = 'anonymous';
    s.onload = () => resolve();
    s.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(s);
  });
}

/**
 * 加载 MediaPipe 模块。多次调用会复用同一个 Promise。
 * @param {string[]} modules - 需要加载的模块名: 'Hands' | 'FaceMesh' | 'Camera' | 'DrawingUtils'
 * @returns {Promise<{Hands, FaceMesh, Camera, DrawingUtils}>}
 */
export async function loadMediaPipe(modules = ['Hands', 'FaceMesh', 'Camera', 'DrawingUtils']) {
  if (!loadingPromise) {
    loadingPromise = (async () => {
      for (const m of modules) {
        if (!SCRIPTS[m]) continue;
        if (loaded[m] || window[m]) {
          loaded[m] = true;
          continue;
        }
        try {
          await loadScript(SCRIPTS[m]);
          loaded[m] = !!window[m];
        } catch (e) {
          console.warn(`[mediapipeLoader] 加载 ${m} 失败:`, e);
          loaded[m] = false;
        }
      }
      return {
        Hands: window.Hands,
        FaceMesh: window.FaceMesh,
        Camera: window.Camera,
        DrawingUtils: window.DrawingUtils,
      };
    })();
  }
  return loadingPromise;
}

export function isLoaded(name) {
  return loaded[name] || !!window[name];
}

export function locateFile(name) {
  return `${CDN_BASE}/${name}`;
}
