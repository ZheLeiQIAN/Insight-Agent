// overlay.js — 实时视频叠加绘制（V0.7：PaddleDetection 风格骨架）
// 绘制内容：
//   - 人脸：完整网格（脸廓/眉/眼/鼻/唇）+ 表情标签
//   - 手部：21 关键点 + 完整骨架 + 手势标签
//   - 人数：COCO-SSD 检测框 + 置信度
//
// 关键点索引见 MediaPipe FaceMesh / Hands 官方文档

// ===== FaceMesh 拓扑（精简但完整的子集，覆盖五官） =====
const FACE_OVAL       = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109];
const LEFT_EYE        = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246];
const RIGHT_EYE       = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398];
const LEFT_EYEBROW    = [46, 53, 52, 51, 48, 115, 131, 132, 133, 116, 117, 123, 147, 213];
const RIGHT_EYEBROW   = [276, 283, 282, 295, 285, 336, 296, 334, 293, 300, 276, 337, 355, 371];
const NOSE            = [1, 2, 5, 4, 6, 19, 20, 94, 125, 141, 235, 31, 228, 229, 230, 231, 232, 233, 244, 245, 122, 6, 202, 214, 218, 237, 44, 45, 51, 4];
const LIPS_OUTER      = [61, 84, 17, 314, 405, 320, 307, 375, 321, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95, 78];
const LIPS_INNER      = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95];

// ===== Hands 骨架（MediaPipe Hands 21 点官方拓扑） =====
const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],            // 拇指
  [0, 5], [5, 6], [6, 7], [7, 8],            // 食指
  [5, 9], [9, 10], [10, 11], [11, 12],       // 中指
  [9, 13], [13, 14], [14, 15], [15, 16],     // 无名指
  [13, 17], [17, 18], [18, 19], [19, 20],    // 小指
  [0, 17],                                   // 手掌底部
];

// 颜色（PaddleDetection 风格绿色系 + 紫色手部 + 黄色人数）
const COLOR = {
  faceOval:    'rgba(34,197,94,0.85)',  // 脸廓 - 亮绿
  eyes:        'rgba(34,197,94,0.95)',  // 眼
  eyebrows:    'rgba(34,197,94,0.7)',
  nose:        'rgba(74,222,128,0.7)',
  lips:        'rgba(34,197,94,0.95)',
  facePoint:   'rgba(74,222,128,0.9)',
  handLand:    'rgba(168,85,247,0.95)', // 紫
  handBone:    'rgba(168,85,247,0.7)',
  handWrist:   'rgba(236,72,153,1)',
  bbox:        'rgba(234,179,8,0.95)',  // 黄
  label:       '#fff',
  labelBg:     'rgba(15,23,42,0.85)',
};

/**
 * 主入口：每帧调用
 * @param {HTMLCanvasElement} canvas
 * @param {HTMLVideoElement} video
 * @param {object} ctx - { gestureResults, faceResults, detectResults, gestureLabels, faceLabels }
 */
export function drawOverlay(canvas, video, payload) {
  if (!canvas || !video) return;
  const ctx = canvas.getContext('2d');
  resizeCanvas(canvas, video);
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // 计算视频实际绘制区域（处理 object-fit: contain 的 letterbox）
  const fit = computeFitRect(video, canvas);

  // 1) 人数检测框
  if (payload?.detectResults?.detections) {
    for (const det of payload.detectResults.detections) {
      drawPersonBBox(ctx, det, fit);
    }
  }

  // 2) 人脸网格
  if (payload?.faceResults?.multiFaceLandmarks) {
    const labels = payload.faceLabels || [];
    for (let i = 0; i < payload.faceResults.multiFaceLandmarks.length; i++) {
      const lm = payload.faceResults.multiFaceLandmarks[i];
      drawFaceMesh(ctx, lm, fit);
      if (labels[i]) drawLabel(ctx, lm, fit, labels[i], 'face');
    }
  }

  // 3) 手部骨架
  if (payload?.gestureResults?.multiHandLandmarks) {
    const handednessList = payload.gestureResults.multiHandedness || [];
    const labels = payload.gestureLabels || [];
    for (let i = 0; i < payload.gestureResults.multiHandLandmarks.length; i++) {
      const lm = payload.gestureResults.multiHandLandmarks[i];
      const handedness = handednessList[i]?.label || 'Hand';
      drawHandSkeleton(ctx, lm, fit);
      const text = labels[i] ? `${labels[i]} · ${handedness}` : handedness;
      drawLabel(ctx, lm, fit, text, 'hand');
    }
  }
}

/**
 * 让 canvas 的 backing store 与视频实际渲染区域匹配
 */
function resizeCanvas(canvas, video) {
  const dpr = window.devicePixelRatio || 1;
  const cw = video.clientWidth;
  const ch = video.clientHeight;
  if (canvas.width !== Math.round(cw * dpr) || canvas.height !== Math.round(ch * dpr)) {
    canvas.width = Math.round(cw * dpr);
    canvas.height = Math.round(ch * dpr);
  }
}

/**
 * 计算 object-fit: contain 后的视频实际绘制矩形
 * 关键点：归一化的 landmarks 坐标基于视频原始宽高（videoWidth/videoHeight）
 *         而 canvas 是显示尺寸，需要把 letterbox 偏移和缩放算清楚
 */
function computeFitRect(video, canvas) {
  const vw = video.videoWidth || 1280;
  const vh = video.videoHeight || 720;
  const cw = canvas.width;
  const ch = canvas.height;
  // contain 模式：保持宽高比，居中显示
  const scale = Math.min(cw / vw, ch / vh);
  const dw = vw * scale;
  const dh = vh * scale;
  const ox = (cw - dw) / 2;
  const oy = (ch - dh) / 2;
  return { scale, ox, oy, vw, vh, dw, dh };
}

function toCanvas(lm, fit, idx) {
  return {
    x: lm[idx].x * fit.vw * fit.scale + fit.ox,
    y: lm[idx].y * fit.vh * fit.scale + fit.oy,
  };
}

// ===== 人脸网格 =====
function drawFaceMesh(ctx, lm, fit) {
  // 1) 脸廓
  drawConnections(ctx, lm, FACE_OVAL, fit, COLOR.faceOval, 1.8);
  // 2) 左右眉
  drawConnections(ctx, lm, LEFT_EYEBROW, fit, COLOR.eyebrows, 1.5);
  drawConnections(ctx, lm, RIGHT_EYEBROW, fit, COLOR.eyebrows, 1.5);
  // 3) 左右眼
  drawConnections(ctx, lm, LEFT_EYE, fit, COLOR.eyes, 1.5, true);
  drawConnections(ctx, lm, RIGHT_EYE, fit, COLOR.eyes, 1.5, true);
  // 4) 鼻子
  drawConnections(ctx, lm, NOSE, fit, COLOR.nose, 1.2);
  // 5) 嘴唇（外圈 + 内圈）
  drawConnections(ctx, lm, LIPS_OUTER, fit, COLOR.lips, 1.5, true);
  drawConnections(ctx, lm, LIPS_INNER, fit, COLOR.lips, 1.2, true);
  // 6) 关键点点位（更亮）
  ctx.fillStyle = COLOR.facePoint;
  for (const idx of [1, 33, 263, 61, 291, 152]) {
    const p = toCanvas(lm, fit, idx);
    ctx.beginPath();
    ctx.arc(p.x, p.y, 2.5, 0, Math.PI * 2);
    ctx.fill();
  }
}

// ===== 手部骨架 =====
function drawHandSkeleton(ctx, lm, fit) {
  // 连线
  ctx.strokeStyle = COLOR.handBone;
  ctx.lineWidth = 2.5;
  for (const [a, b] of HAND_CONNECTIONS) {
    const p = toCanvas(lm, fit, a);
    const q = toCanvas(lm, fit, b);
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
    ctx.lineTo(q.x, q.y);
    ctx.stroke();
  }
  // 关键点
  for (let i = 0; i < lm.length; i++) {
    const p = toCanvas(lm, fit, i);
    ctx.fillStyle = i === 0 ? COLOR.handWrist : COLOR.handLand;
    ctx.beginPath();
    ctx.arc(p.x, p.y, i === 0 ? 5 : 4, 0, Math.PI * 2);
    ctx.fill();
  }
}

// ===== 人数检测框 =====
function drawPersonBBox(ctx, det, fit) {
  // COCO-SSD bbox 格式：[x, y, width, height]，基于视频原始分辨率
  const [bx, by, bw, bh] = det.bbox;
  const sx = bx * fit.scale + fit.ox;
  const sy = by * fit.scale + fit.oy;
  const sw = bw * fit.scale;
  const sh = bh * fit.scale;
  ctx.strokeStyle = COLOR.bbox;
  ctx.lineWidth = 2.5;
  ctx.strokeRect(sx, sy, sw, sh);
  // 标签
  const label = `person ${(det.score * 100).toFixed(0)}%`;
  drawTextBox(ctx, sx, sy - 22, label, COLOR.bbox);
}

function drawTextBox(ctx, x, y, text, accentColor) {
  ctx.font = '600 13px -apple-system, "PingFang SC", sans-serif';
  const padding = 6;
  const metrics = ctx.measureText(text);
  const w = metrics.width + padding * 2;
  const h = 20;
  ctx.fillStyle = COLOR.labelBg;
  ctx.fillRect(x, y, w, h);
  ctx.fillStyle = accentColor || COLOR.label;
  ctx.fillRect(x, y, 3, h); // 左侧色条
  ctx.fillStyle = COLOR.label;
  ctx.fillText(text, x + padding + 3, y + 14);
}

// ===== 标签（人脸/手部） =====
function drawLabel(ctx, lm, fit, text, kind) {
  // 取关键点 0（手腕/鼻尖附近）作为锚点
  const anchor = toCanvas(lm, fit, 0);
  const color = kind === 'hand' ? COLOR.handLand : COLOR.faceOval;
  drawTextBox(ctx, anchor.x + 8, anchor.y - 12, text, color);
}

// ===== 通用连线绘制 =====
function drawConnections(ctx, lm, indices, fit, color, lineWidth = 1.5, closeLoop = false) {
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.beginPath();
  for (let i = 0; i < indices.length; i++) {
    const p = toCanvas(lm, fit, indices[i]);
    if (i === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  }
  if (closeLoop) ctx.closePath();
  ctx.stroke();
}
