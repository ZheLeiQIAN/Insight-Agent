#!/usr/bin/env python3
"""Browser-based graphical launcher for Insight Agent.

This launcher uses only Python's standard library. It opens a local setup page,
lets the user optionally save a DeepSeek API key, installs missing pieces, and
starts the main Flask workbench.
"""

from __future__ import annotations

import importlib.util
import errno
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
REQUIREMENTS = ROOT / "requirements.txt"
SETUP_PORT = 9530
APP_PORT = 9527
SETUP_URL = f"http://127.0.0.1:{SETUP_PORT}"
APP_URL = f"http://127.0.0.1:{APP_PORT}"

REQUIRED_IMPORTS = {
    "flask": "flask",
    "rich": "rich",
    "openai": "openai",
    "pandas": "pandas",
    "playwright": "playwright",
    "bs4": "beautifulsoup4",
    "jieba": "jieba",
    "snownlp": "snownlp",
    "prompt_toolkit": "prompt_toolkit",
    "openpyxl": "openpyxl",
}

STATE = {
    "running": False,
    "status": "准备就绪",
    "logs": [],
    "app_started": False,
    "error": "",
}
STATE_LOCK = threading.Lock()
APP_PROCESS: subprocess.Popen | None = None


def log(message: str) -> None:
    with STATE_LOCK:
        STATE["logs"].append(message.rstrip())
        STATE["logs"] = STATE["logs"][-240:]


def set_status(message: str) -> None:
    with STATE_LOCK:
        STATE["status"] = message


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        return
    if ENV_EXAMPLE.exists():
        shutil.copy2(ENV_EXAMPLE, ENV_FILE)
    else:
        ENV_FILE.write_text(
            "DEEPSEEK_API_KEY=\nDEEPSEEK_BASE_URL=https://api.deepseek.com\nDEEPSEEK_MODEL=deepseek-chat\nLOG_LEVEL=INFO\n",
            encoding="utf-8",
        )


def read_env_value(key: str) -> str:
    ensure_env_file()
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def upsert_env_value(key: str, value: str) -> None:
    ensure_env_file()
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    next_lines = []
    updated = False
    for line in lines:
        if line.strip().startswith(f"{key}="):
            next_lines.append(f"{key}={value}")
            updated = True
        else:
            next_lines.append(line)
    if not updated:
        next_lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(next_lines) + "\n", encoding="utf-8")


def missing_packages() -> list[str]:
    missing = []
    for import_name, package_name in REQUIRED_IMPORTS.items():
        if importlib.util.find_spec(import_name) is None:
            missing.append(package_name)
    return sorted(set(missing))


def run_command(cmd: list[str]) -> None:
    log("$ " + " ".join(cmd))
    proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert proc.stdout is not None
    for line in proc.stdout:
        if line.strip():
            log(line)
    code = proc.wait()
    if code != 0:
        raise RuntimeError(f"命令执行失败，退出码 {code}")


def start_worker(api_key: str, use_api: bool) -> None:
    global APP_PROCESS
    with STATE_LOCK:
        if STATE["running"]:
            return
        STATE["running"] = True
        STATE["error"] = ""

    try:
        set_status("检查环境")
        log(f"Python {sys.version.split()[0]} 检查通过")
        if sys.version_info < (3, 9):
            raise RuntimeError("请安装 Python 3.9 或更高版本")

        for path in [ROOT / "output", ROOT / "output" / "data", ROOT / "output" / "reports", ROOT / "output" / "sessions"]:
            path.mkdir(parents=True, exist_ok=True)

        if use_api and api_key.strip():
            upsert_env_value("DEEPSEEK_API_KEY", api_key.strip())
            log("DeepSeek API Key 已保存")
        elif not use_api:
            upsert_env_value("DEEPSEEK_API_KEY", "")
            log("未启用 API Key，将使用基础分析功能")

        missing = missing_packages()
        if missing:
            set_status("安装项目依赖")
            log("检测到缺少依赖：" + ", ".join(missing))
            run_command([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)])
        else:
            log("项目依赖检查通过")

        marker = ROOT / "output" / ".playwright_chromium_ready"
        if not marker.exists():
            set_status("安装浏览器组件")
            run_command([sys.executable, "-m", "playwright", "install", "chromium"])
            marker.write_text(str(int(time.time())), encoding="utf-8")
        else:
            log("浏览器组件检查通过")

        set_status("启动工作台")
        if APP_PROCESS is None or APP_PROCESS.poll() is not None:
            code = (
                "from web.server import start_server; "
                f"start_server(host='127.0.0.1', port={APP_PORT}, open_browser=False, background=False)"
            )
            APP_PROCESS = subprocess.Popen([sys.executable, "-c", code], cwd=str(ROOT))
            time.sleep(1.2)
        webbrowser.open(APP_URL)
        with STATE_LOCK:
            STATE["app_started"] = True
        set_status("工作台已启动")
        log(f"工作台已打开：{APP_URL}")
    except Exception as exc:
        with STATE_LOCK:
            STATE["error"] = str(exc)
        set_status("启动失败")
        log(f"启动失败：{exc}")
    finally:
        with STATE_LOCK:
            STATE["running"] = False


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Insight Agent 启动器</title>
  <style>
    :root { color-scheme: light; --blue:#0071e3; --text:#1d1d1f; --muted:#6e6e73; --bg:#f5f5f7; --line:#e5e5ea; }
    * { box-sizing: border-box; }
    body {
      margin:0; min-height:100vh; font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",sans-serif;
      color:var(--text); background:
        radial-gradient(circle at 20% 0%, rgba(0,113,227,.16), transparent 32%),
        radial-gradient(circle at 80% 0%, rgba(94,92,230,.14), transparent 30%),
        var(--bg);
    }
    .wrap { max-width: 1080px; margin: 0 auto; padding: 56px 24px; }
    .hero { display:grid; grid-template-columns: 1.05fr .95fr; gap: 28px; align-items: stretch; }
    .intro, .panel {
      border: 1px solid rgba(0,0,0,.08); border-radius: 30px; background: rgba(255,255,255,.82);
      backdrop-filter: blur(24px); box-shadow: 0 30px 90px rgba(0,0,0,.10);
    }
    .intro { padding: 46px; min-height: 560px; display:flex; flex-direction:column; justify-content:space-between; overflow:hidden; position:relative; }
    .intro:after { content:""; position:absolute; width:420px; height:420px; right:-170px; bottom:-160px; border-radius:50%; background:linear-gradient(135deg,#0071e3,#5e5ce6); opacity:.16; }
    .kicker { color:var(--blue); font-weight:800; font-size:13px; margin-bottom:18px; }
    h1 { font-size: 56px; line-height: 1.04; letter-spacing: 0; margin:0 0 18px; }
    .lead { color:var(--muted); font-size:19px; line-height:1.55; max-width: 560px; }
    .steps { display:grid; grid-template-columns: repeat(3,1fr); gap:12px; position:relative; z-index:1; }
    .step { background:#f5f5f7; border:1px solid var(--line); border-radius:18px; padding:16px; }
    .step b { display:block; font-size:14px; margin-bottom:6px; }
    .step span { color:var(--muted); font-size:12px; line-height:1.45; }
    .panel { padding: 30px; }
    .panel h2 { margin: 0 0 8px; font-size: 26px; }
    .panel p { color:var(--muted); margin:0 0 22px; line-height:1.55; }
    label { display:block; color:#424245; font-size:13px; font-weight:700; margin-bottom:8px; }
    input[type=password], input[type=text] { width:100%; height:48px; border:1px solid var(--line); border-radius:14px; padding:0 14px; font-size:14px; outline:none; background:#fff; }
    input:focus { border-color:var(--blue); box-shadow:0 0 0 4px rgba(0,113,227,.12); }
    .check { display:flex; align-items:center; gap:10px; margin:18px 0; color:#424245; font-size:14px; }
    .actions { display:flex; gap:12px; margin-top:18px; }
    button, a.button { border:0; border-radius:999px; height:46px; padding:0 20px; font-weight:800; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; justify-content:center; }
    .primary { background:var(--blue); color:#fff; box-shadow:0 14px 34px rgba(0,113,227,.24); }
    .secondary { background:#eef2f7; color:#1d1d1f; }
    button:disabled { opacity:.55; cursor:not-allowed; }
    .status { margin-top:22px; padding:16px; border-radius:18px; background:#f5f5f7; border:1px solid var(--line); }
    .status strong { color:var(--blue); }
    .log { margin-top:14px; height:210px; overflow:auto; border-radius:18px; background:#111827; color:#d1d5db; padding:14px; font:12px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace; white-space:pre-wrap; }
    .bar { height:8px; background:#e5e5ea; border-radius:999px; overflow:hidden; margin-top:12px; }
    .bar i { display:block; height:100%; width:36%; background:linear-gradient(90deg,#0071e3,#5e5ce6); border-radius:999px; animation: move 1.1s infinite alternate ease-in-out; }
    @keyframes move { from { transform:translateX(-20%); } to { transform:translateX(210%); } }
    @media (max-width: 860px) { .hero { grid-template-columns:1fr; } h1 { font-size:42px; } .intro { min-height: auto; } .steps { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <div class="intro">
        <div>
          <div class="kicker">Insight Agent Launcher</div>
          <h1>打开你的本地 AI 数据工作台。</h1>
          <p class="lead">选择是否启用 API Key，然后一键完成环境检查、依赖安装和 Web 工作台启动。第一次会稍慢，之后基本就是直接打开。</p>
        </div>
        <div class="steps">
          <div class="step"><b>1. 设置</b><span>可选填写 DeepSeek API Key。</span></div>
          <div class="step"><b>2. 检查</b><span>自动补齐 Python 依赖和浏览器组件。</span></div>
          <div class="step"><b>3. 使用</b><span>自动打开 WebUI，上传或采集数据。</span></div>
        </div>
      </div>
      <div class="panel">
        <h2>启动设置</h2>
        <p>不填 Key 也能先使用基础分析。AI 对话、主题提取、观点挖掘需要真实 DeepSeek API Key。</p>
        <div class="check"><input id="useApi" type="checkbox" checked><span>启用 AI 功能</span></div>
        <label for="apiKey">DeepSeek API Key</label>
        <input id="apiKey" type="password" placeholder="sk-..." value="__API_KEY__">
        <div class="actions">
          <button id="start" class="primary">启动工作台</button>
          <button id="toggle" class="secondary">显示 Key</button>
          <a id="openApp" class="button secondary" href="http://127.0.0.1:9527" target="_blank">打开 WebUI</a>
        </div>
        <div class="status">
          <div>状态：<strong id="status">准备就绪</strong></div>
          <div id="progress" class="bar" style="display:none"><i></i></div>
          <div id="log" class="log"></div>
        </div>
      </div>
    </section>
  </main>
  <script>
    const apiKey = document.getElementById('apiKey');
    const useApi = document.getElementById('useApi');
    const start = document.getElementById('start');
    const toggle = document.getElementById('toggle');
    const logBox = document.getElementById('log');
    const statusEl = document.getElementById('status');
    const progress = document.getElementById('progress');
    toggle.onclick = () => { apiKey.type = apiKey.type === 'password' ? 'text' : 'password'; toggle.textContent = apiKey.type === 'password' ? '显示 Key' : '隐藏 Key'; };
    async function poll() {
      const r = await fetch('/state'); const s = await r.json();
      statusEl.textContent = s.status;
      logBox.textContent = (s.logs || []).join('\n');
      logBox.scrollTop = logBox.scrollHeight;
      progress.style.display = s.running ? 'block' : 'none';
      start.disabled = !!s.running;
      if (s.app_started) document.getElementById('openApp').style.background = '#dbeafe';
    }
    setInterval(poll, 1200); poll();
    start.onclick = async () => {
      await fetch('/start', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ use_api: useApi.checked, api_key: apiKey.value }) });
      poll();
    };
  </script>
</body>
</html>"""


class ReusableHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/state":
            with STATE_LOCK:
                payload = dict(STATE)
            self._json(payload)
            return
        key = read_env_value("DEEPSEEK_API_KEY")
        if key.startswith("sk-your-key"):
            key = ""
        body = HTML.replace("__API_KEY__", key).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/start":
            self._json({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        threading.Thread(target=start_worker, args=(data.get("api_key", ""), bool(data.get("use_api"))), daemon=True).start()
        self._json({"ok": True})

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    ensure_env_file()
    try:
        server = ReusableHTTPServer(("127.0.0.1", SETUP_PORT), Handler)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            webbrowser.open(SETUP_URL)
            return
        raise
    webbrowser.open(SETUP_URL)
    print(f"Insight Agent 启动页：{SETUP_URL}")
    server.serve_forever()


if __name__ == "__main__":
    main()
