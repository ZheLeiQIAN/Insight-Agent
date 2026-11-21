// gesture.js — MediaPipe Hands 手势识别
// 6 种手势: 竖拇指(thumbs_up) / 点赞(thumbs_down) / 食指指向(point) /
//          双手张开(open_hand) / 握拳(fist) / OK圈手(ok_sign)
//
// 关键点 (MediaPipe Hands 21 点):
//   0  = 手腕
//   1-4 = 拇指 (CMC/MCP/IP/TIP)
//   5-8 = 食指
//   9-12 = 中指
//   13-16 = 无名指
//   17-20 = 小指
//
// 几何判定:
//   手指伸直:  tip.y < pip.y (图像坐标 y 向下)
//   手指弯曲:  tip.y > pip.y
//   拇指伸直:  tip.x 远离 wrist.x

import { emit } from './eventBus.js';
import { loadMediaPipe, locateFile } from './mediapipeLoader.js';
import { set } from './store.js';

let hands = null;
let initialized = false;
let lastGesture = null;
let lastGestureTs = 0;
let stableFrames = 0;
const STABLE_FRAMES_NEEDED = 3;        // 连续 N 帧同一手势才触发
const GESTURE_COOLDOWN_MS = 800;       // 同手势冷却时间

const GESTURE_INTENT = {
  thumbs_up:    'satisfied',
  thumbs_down:  'dissatisfied',
  point:        'inquiry',
  open_hand:    'consult',
  fist:         'firm',
  ok_sign:      'purchase_intent',
};

/**
 * 初始化 MediaPipe Hands
 * @param {HTMLVideoElement} videoEl - 摄像头 video 元素
 * @param {Function} onResults - 结果回调 (results) => void
 */
export async function initGestureDetector(videoEl, onResults) {
  if (initialized) return true;
  const { Hands } = await loadMediaPipe(['Hands', 'DrawingUtils']);
  if (!Hands) {
    console.warn('[gesture] MediaPipe Hands 加载失败');
    return false;
  }

  hands = new Hands({ locateFile: locateFile });
  hands.setOptions({
    maxNumHands: 2,
    modelComplexity: 1,
    minDetectionConfidence: 0.6,
    minTrackingConfidence: 0.5,
  });
  hands.onResults((results) => {
    onGestureResults(results);
    onResults?.(results);
  });
  initialized = true;
  set('model.gesture', true);
  console.log('[gesture] MediaPipe Hands 就绪');
  return true;
}

function onGestureResults(results) {
  if (!results.multiHandLandmarks || results.multiHandLandmarks.length === 0) {
    if (lastGesture !== null) {
      stableFrames = 0;
      lastGesture = null;
    }
    return;
  }
  for (const hand of results.multiHandLandmarks) {
    const handedness = results.multiHandedness?.[0]?.label || 'Right';
    const gesture = detectGesture(hand, handedness);
    if (gesture === lastGesture) {
      stableFrames++;
    } else {
      stableFrames = 1;
      lastGesture = gesture;
    }
    if (stableFrames === STABLE_FRAMES_NEEDED) {
      const now = Date.now();
      if (now - lastGestureTs >= GESTURE_COOLDOWN_MS) {
        lastGestureTs = now;
        const event = {
          type: 'gesture',
          subtype: gesture,
          confidence: 0.85,
          intent: GESTURE_INTENT[gesture] || 'unknown',
          handedness,
          source: 'browser',
        };
        emit('detection:gesture', event);
      }
    }
  }
}

/**
 * 手势判定（基于 21 关键点几何）
 * 借鉴并扩展自 gesture-recognition 经典算法
 */
function detectGesture(lm, handedness) {
  // 手指伸直判定
  const indexExt  = isFingerExtended(lm, 5, 6, 8);
  const middleExt = isFingerExtended(lm, 9, 10, 12);
  const ringExt   = isFingerExtended(lm, 13, 14, 16);
  const pinkyExt  = isFingerExtended(lm, 17, 18, 20);
  const thumbExt  = isThumbExtended(lm, handedness);

  // 拇指指向上下：基于 thumb tip 相对 wrist 的位置
  const thumbUp = lm[4].y < lm[0].y - 0.10;
  const thumbDown = lm[4].y > lm[0].y + 0.10;

  const extendedCount = [indexExt, middleExt, ringExt, pinkyExt].filter(Boolean).length;

  // OK 手势：拇指与食指相触，其他伸直
  const thumbIndexDist = Math.hypot(lm[4].x - lm[8].x, lm[4].y - lm[8].y);
  if (thumbIndexDist < 0.05 && middleExt && ringExt && pinkyExt) {
    return 'ok_sign';
  }

  // 握拳：4 指都弯
  if (extendedCount === 0) {
    if (thumbUp) return 'thumbs_up';
    if (thumbDown) return 'thumbs_down';
    return 'fist';
  }

  // 食指指向：仅食指伸直
  if (indexExt && !middleExt && !ringExt && !pinkyExt) {
    return 'point';
  }

  // 张开：四指都伸直
  if (extendedCount === 4) {
    return 'open_hand';
  }

  return null;
}

function isFingerExtended(lm, mcpIdx, pipIdx, tipIdx) {
  // 手指伸直: tip 到 wrist 的距离 > pip 到 wrist 的距离
  const wrist = lm[0];
  const tipDist = Math.hypot(lm[tipIdx].x - wrist.x, lm[tipIdx].y - wrist.y);
  const pipDist = Math.hypot(lm[pipIdx].x - wrist.x, lm[pipIdx].y - wrist.y);
  return tipDist > pipDist * 1.10; // 加一点阈值抗噪
}

function isThumbExtended(lm, handedness) {
  // 拇指弯曲: tip 与 index_mcp 距离
  const wrist = lm[0];
  const tipDist = Math.hypot(lm[4].x - wrist.x, lm[4].y - wrist.y);
  // 右手: 拇指 tip 在手腕左侧
  // 左手: 拇指 tip 在手腕右侧
  const ref = handedness === 'Right' ? -1 : 1;
  return lm[4].x * ref < lm[0].x * ref && tipDist > 0.15;
}

export function isGestureReady() { return initialized; }

/**
 * 单帧推理入口（被主循环调用）
 */
export async function processFrame(videoEl) {
  if (!initialized || !hands) return null;
  if (!videoEl || videoEl.readyState < 2) return null;
  try {
    await hands.send({ image: videoEl });
  } catch (e) {
    console.warn('[gesture] processFrame:', e.message);
  }
  return null;
}
