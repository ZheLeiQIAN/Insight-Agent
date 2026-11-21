// quickDetect.js — TensorFlow.js COCO-SSD 轻量物体检测
// 主要用于实时人数估算（不进 PaddleDetection 时的降级方案）

import * as tf from '@tensorflow/tfjs';
import * as cocoSsd from '@tensorflow-models/coco-ssd';
import { emit } from './eventBus.js';
import { set } from './store.js';

let model = null;
let ready = false;
let lastCount = 0;
let lastCountTs = 0;
const COUNT_COOLDOWN_MS = 1500;

export async function initDetector() {
  if (ready) return true;
  try {
    await tf.ready();
    model = await cocoSsd.load({ base: 'lite_mobilenet_v2' });
    ready = true;
    set('model.detector', true);
    console.log('[quickDetect] COCO-SSD 就绪');
    return true;
  } catch (e) {
    console.error('[quickDetect] 加载失败:', e);
    return false;
  }
}

/**
 * 检测 person 类
 * @param {HTMLVideoElement} videoEl
 * @returns {Promise<{persons: number, detections: Array}>}
 */
export async function detect(videoEl) {
  if (!ready || !model) return { persons: 0, detections: [] };
  if (!videoEl || videoEl.readyState < 2) return { persons: 0, detections: [] };
  try {
    const predictions = await model.detect(videoEl, 20, 0.5);
    const persons = predictions.filter((p) => p.class === 'person');
    return { persons: persons.length, detections: persons };
  } catch (e) {
    console.warn('[quickDetect] 检测失败:', e);
    return { persons: 0, detections: [] };
  }
}

/**
 * 单帧推理入口（被主循环调用）
 * 周期性推送人数变化事件
 */
export async function processFrame(videoEl) {
  if (!ready) return null;
  const result = await detect(videoEl);
  const now = Date.now();

  if (result.persons !== lastCount) {
    if (now - lastCountTs >= COUNT_COOLDOWN_MS) {
      lastCount = result.persons;
      lastCountTs = now;
      emit('detection:count', {
        type: 'count',
        subtype: result.persons > lastCount ? 'person_increase' : 'person_decrease',
        persons: result.persons,
        change: result.persons - lastCount,
        source: 'browser',
        detections: result.detections.map((d) => ({
          bbox: d.bbox,
          score: d.score,
        })),
      });
    }
  } else {
    // 周期性推送（用于仪表盘持续更新）
    set('count.persons', result.persons);
  }
  return result;
}

export function isDetectorReady() { return ready; }
