// face.js — MediaPipe FaceMesh 人脸检测
// 输出:
//   - 5 类基础表情: neutral / smile / frown / surprise / angry
//   - 头部姿态: yaw / pitch / roll（基于关键点 PnP 解算）
//   - 注视区域（用于商品关注度）
//
// 关键参考点 (FaceMesh 468 点):
//   1  = 鼻尖
//   152, 4 = 下颌
//   33, 263 = 眼角
//   61, 291 = 嘴角
//   10, 152 = 额头/下巴
//   234, 454 = 耳部

import { emit } from './eventBus.js';
import { loadMediaPipe, locateFile } from './mediapipeLoader.js';
import { set } from './store.js';

let faceMesh = null;
let initialized = false;
let lastEmotion = 'neutral';
let lastEmotionTs = 0;
let gazeDwellZone = null;
let gazeDwellStart = 0;
const EMOTION_COOLDOWN_MS = 1000;
const DWELL_THRESHOLD_MS = 3000;
const GAZE_STABLE_THRESHOLD = 0.05; // 归一化坐标变化阈值

/**
 * 初始化 MediaPipe FaceMesh
 */
export async function initFaceDetector(videoEl, onResults) {
  if (initialized) return true;
  const { FaceMesh } = await loadMediaPipe(['FaceMesh']);
  if (!FaceMesh) {
    console.warn('[face] MediaPipe FaceMesh 加载失败');
    return false;
  }

  faceMesh = new FaceMesh({ locateFile: locateFile });
  faceMesh.setOptions({
    maxNumFaces: 2,
    refineLandmarks: true,
    minDetectionConfidence: 0.5,
    minTrackingConfidence: 0.5,
  });
  faceMesh.onResults((results) => {
    onFaceResults(results);
    onResults?.(results);
  });
  initialized = true;
  set('model.face', true);
  console.log('[face] MediaPipe FaceMesh 就绪');
  return true;
}

function onFaceResults(results) {
  if (!results.multiFaceLandmarks || results.multiFaceLandmarks.length === 0) {
    if (lastEmotion !== 'neutral') {
      const now = Date.now();
      if (now - lastEmotionTs >= EMOTION_COOLDOWN_MS) {
        lastEmotion = 'neutral';
        lastEmotionTs = now;
        emit('detection:face', {
          type: 'face',
          subtype: 'neutral',
          confidence: 0.9,
          source: 'browser',
        });
      }
    }
    return;
  }

  const lm = results.multiFaceLandmarks[0];
  const emotion = detectEmotion(lm);
  if (emotion !== lastEmotion) {
    const now = Date.now();
    if (now - lastEmotionTs >= EMOTION_COOLDOWN_MS) {
      lastEmotion = emotion;
      lastEmotionTs = now;
      emit('detection:face', {
        type: 'face',
        subtype: emotion,
        confidence: 0.75,
        source: 'browser',
      });
    }
  }

  // 注视区域分析（用于商品关注度）
  const gazeZone = detectGazeZone(lm);
  if (gazeZone) {
    if (gazeZone === gazeDwellZone) {
      const dwellMs = Date.now() - gazeDwellStart;
      if (dwellMs >= DWELL_THRESHOLD_MS) {
        emit('detection:interest', {
          type: 'interest',
          subtype: 'gaze_dwell',
          zone: gazeZone,
          duration_ms: dwellMs,
          confidence: 0.8,
          source: 'browser',
        });
        gazeDwellStart = Date.now(); // 重置避免重复
      }
    } else {
      gazeDwellZone = gazeZone;
      gazeDwellStart = Date.now();
    }
  }
}

/**
 * 基于面部关键点的表情分类
 * 借鉴 Face-api.js landmarks-to-expression 算法
 */
function detectEmotion(lm) {
  // 嘴部纵横比
  const mouthTop = lm[13];
  const mouthBottom = lm[14];
  const mouthLeft = lm[61];
  const mouthRight = lm[291];
  const mouthWidth = Math.hypot(mouthRight.x - mouthLeft.x, mouthRight.y - mouthLeft.y);
  const mouthHeight = Math.hypot(mouthBottom.x - mouthTop.x, mouthBottom.y - mouthTop.y);
  const mouthRatio = mouthHeight / (mouthWidth + 0.001);

  // 嘴角上扬/下撇
  const leftCorner = lm[61];
  const rightCorner = lm[291];
  const mouthCenterY = (leftCorner.y + rightCorner.y) / 2;
  const lipTopY = lm[13].y;
  const smileScore = (lipTopY - mouthCenterY) / (mouthWidth + 0.001);

  // 眉毛位置（基于眉心与眼中心的距离）
  const leftBrow = lm[105];
  const rightBrow = lm[334];
  const leftEye = lm[159];
  const rightEye = lm[386];
  const browEyeDist = ((leftBrow.y - leftEye.y) + (rightBrow.y - rightEye.y)) / 2;
  const faceHeight = Math.hypot(lm[10].x - lm[152].x, lm[10].y - lm[152].y);
  const browRatio = browEyeDist / (faceHeight + 0.001);

  // 眼睛开度
  const leftEyeTop = lm[159];
  const leftEyeBottom = lm[145];
  const eyeOpen = Math.hypot(leftEyeTop.x - leftEyeBottom.x, leftEyeTop.y - leftEyeBottom.y) / faceHeight;

  // 分类规则
  if (mouthRatio > 0.5 && eyeOpen > 0.045) return 'surprise';
  if (smileScore > 0.04) return 'smile';
  if (smileScore < -0.04 && mouthRatio < 0.15) return 'frown';
  if (browRatio < 0.05 && mouthRatio < 0.10) return 'angry';
  return 'neutral';
}

/**
 * 头部姿态（粗略 yaw/pitch/roll）
 * 基于鼻尖、左右眼角、上下颌的归一化偏差
 */
export function getHeadPose(lm) {
  const nose = lm[1];
  const leftEye = lm[33];
  const rightEye = lm[263];
  const chin = lm[152];
  const forehead = lm[10];

  // 简化 yaw：鼻尖相对两眼中心的水平偏移
  const eyeCenterX = (leftEye.x + rightEye.x) / 2;
  const yaw = (nose.x - eyeCenterX) * 6.0;  // 粗略，-1~1 映射到 -60°~60°

  // pitch：鼻尖相对额头-下巴中心
  const faceCenterY = (forehead.y + chin.y) / 2;
  const pitch = (nose.y - faceCenterY) * 6.0;

  // roll：两眼连线倾斜
  const roll = Math.atan2(rightEye.y - leftEye.y, rightEye.x - leftEye.x);

  return { yaw, pitch, roll };
}

/**
 * 注视区域推断（基于头部 yaw + pitch）
 * 返回 4 个区域之一: 'left' / 'right' / 'up' / 'down' / null
 */
function detectGazeZone(lm) {
  const { yaw, pitch } = getHeadPose(lm);
  if (Math.abs(yaw) < GAZE_STABLE_THRESHOLD && Math.abs(pitch) < GAZE_STABLE_THRESHOLD) {
    return 'center';
  }
  if (Math.abs(yaw) > Math.abs(pitch)) {
    return yaw > 0 ? 'right' : 'left';
  }
  return pitch > 0 ? 'down' : 'up';
}

export function isFaceReady() { return initialized; }

export async function processFrame(videoEl) {
  if (!initialized || !faceMesh) return null;
  if (!videoEl || videoEl.readyState < 2) return null;
  try {
    await faceMesh.send({ image: videoEl });
  } catch (e) {
    console.warn('[face] processFrame:', e.message);
  }
  return null;
}
