"""简易 API Key 鉴权（V0.6 阶段 E2）

设计:
- 从环境变量 INSIGHT_API_KEY 读取商家密钥（未设置则鉴权关闭）
- 客户端通过 X-API-Key Header 或 ?api_key= query 传密钥
- 公开端点（healthz/info）无需鉴权
- 鉴权失败返回 401

生产环境建议替换为 JWT/OAuth，本中间件仅作开发防护。
"""
import os
import logging
from functools import wraps
from typing import List, Optional

from flask import request, jsonify

logger = logging.getLogger(__name__)

API_KEY = os.environ.get("INSIGHT_API_KEY", "").strip()
AUTH_ENABLED = bool(API_KEY)

# 公开端点（无需鉴权）
PUBLIC_ENDPOINTS: List[str] = [
    "/api/healthz",
    "/api/info",
    "/api/rules",  # 规则是只读可展示
    "/socket.io/",
    "/static/",
]


def _extract_api_key() -> Optional[str]:
    """从 Header 或 query 提取 API key"""
    # 1) Header
    key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    if key:
        return key
    # 2) Query
    key = request.args.get("api_key")
    if key:
        return key
    return None


def is_public_path(path: str) -> bool:
    """路径是否公开"""
    for prefix in PUBLIC_ENDPOINTS:
        if path == prefix or path.startswith(prefix):
            return True
    return False


def require_api_key(fn):
    """API key 鉴权装饰器"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not AUTH_ENABLED:
            return fn(*args, **kwargs)
        if is_public_path(request.path):
            return fn(*args, **kwargs)
        provided = _extract_api_key()
        if not provided or provided != API_KEY:
            logger.warning("鉴权失败: %s %s (key=%s)", request.method, request.path, "yes" if provided else "no")
            return jsonify({
                "ok": False,
                "error": "Unauthorized",
                "message": "需要 X-API-Key 头或 ?api_key= 参数",
            }), 401
        return fn(*args, **kwargs)
    return wrapper


def install_auth(app):
    """在 Flask app 上安装全局鉴权"""
    if not AUTH_ENABLED:
        logger.info("API key 鉴权未启用（INSIGHT_API_KEY 未设置）")
        return
    logger.info("API key 鉴权已启用（公开端点: %s）", PUBLIC_ENDPOINTS)

    @app.before_request
    def _check_auth():
        # CORS preflight
        if request.method == "OPTIONS":
            return None
        if is_public_path(request.path):
            return None
        provided = _extract_api_key()
        if not provided or provided != API_KEY:
            return jsonify({
                "ok": False,
                "error": "Unauthorized",
                "message": "需要 X-API-Key 头或 ?api_key= 参数",
            }), 401

    return _check_auth
