"""CLI 启动辅助 — 共享给 main.py、cli/commands.py、launcher_web.py、launcher_gui.py"""
import time
import urllib.error
import urllib.request
from typing import Optional


def wait_for_health(base_url: str, timeout: float = 15.0) -> bool:
    """轮询 /api/healthz 直到 200 或超时。

    用于所有"启动 Flask 服务后再开浏览器"的位置，避免浏览器抢在端口起来前打开看到连接失败。
    """
    health_url = base_url.rstrip("/") + "/api/healthz"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=1.5) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.4)
    return False


def ping_api(base_url: str, timeout: float = 1.5) -> bool:
    """单次 ping，初始化阶段用（带超时，不阻塞主流程）"""
    health_url = base_url.rstrip("/") + "/api/healthz"
    try:
        with urllib.request.urlopen(health_url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False
