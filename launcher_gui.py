#!/usr/bin/env python3
"""Insight Agent 图形化启动器。

使用 Python 标准库 Tkinter 实现，不依赖项目第三方包。
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, Y, BooleanVar, StringVar, Tk, messagebox
from tkinter import ttk


ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
REQUIREMENTS = ROOT / "requirements.txt"
HOST = "127.0.0.1"
PORT = 9527
URL = f"http://{HOST}:{PORT}"

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


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        return
    if ENV_EXAMPLE.exists():
        shutil.copy2(ENV_EXAMPLE, ENV_FILE)
    else:
        ENV_FILE.write_text(
            "DEEPSEEK_API_KEY=\nDEEPSEEK_BASE_URL=https://api.deepseek.com\nDEEPSEEK_MODEL=deepseek-chat\n",
            encoding="utf-8",
        )


def read_env_value(key: str) -> str:
    if not ENV_FILE.exists():
        return ""
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


class LauncherApp:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title("Insight Agent")
        self.root.geometry("760x620")
        self.root.minsize(720, 560)
        self.root.configure(bg="#f5f5f7")

        self.api_key = StringVar(value=self._initial_api_key())
        self.use_api = BooleanVar(value=bool(self.api_key.get()))
        self.status = StringVar(value="准备就绪")
        self.server_proc: subprocess.Popen | None = None

        self._build_styles()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _initial_api_key(self) -> str:
        ensure_env_file()
        key = read_env_value("DEEPSEEK_API_KEY")
        if key.startswith("sk-your-key"):
            return ""
        return key

    def _build_styles(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Root.TFrame", background="#f5f5f7")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("Title.TLabel", background="#f5f5f7", foreground="#1d1d1f", font=("SF Pro Display", 30, "bold"))
        style.configure("Subtitle.TLabel", background="#f5f5f7", foreground="#6e6e73", font=("SF Pro Text", 13))
        style.configure("CardTitle.TLabel", background="#ffffff", foreground="#1d1d1f", font=("SF Pro Text", 15, "bold"))
        style.configure("Body.TLabel", background="#ffffff", foreground="#6e6e73", font=("SF Pro Text", 12))
        style.configure("Status.TLabel", background="#ffffff", foreground="#2563eb", font=("SF Pro Text", 12, "bold"))
        style.configure("Primary.TButton", font=("SF Pro Text", 13, "bold"), padding=(18, 10))
        style.configure("Secondary.TButton", font=("SF Pro Text", 12), padding=(14, 8))
        style.configure("TCheckbutton", background="#ffffff", foreground="#1d1d1f", font=("SF Pro Text", 12))

    def _build_ui(self) -> None:
        shell = ttk.Frame(self.root, style="Root.TFrame", padding=28)
        shell.pack(fill=BOTH, expand=True)

        ttk.Label(shell, text="Insight Agent", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            shell,
            text="本地 AI 数据分析工作台。自动完成依赖检查、可选 API 配置，并打开 Web 界面。",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(6, 24))

        card = ttk.Frame(shell, style="Card.TFrame", padding=24)
        card.pack(fill=X)

        ttk.Label(card, text="启动前设置", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            card,
            text="DeepSeek API Key 是可选项。未填写时仍可使用上传文件、基础统计和词频分析。",
            style="Body.TLabel",
        ).pack(anchor="w", pady=(6, 16))

        ttk.Checkbutton(card, text="启用 AI 对话和定性分析", variable=self.use_api).pack(anchor="w")
        api_row = ttk.Frame(card, style="Card.TFrame")
        api_row.pack(fill=X, pady=(12, 0))
        self.api_entry = ttk.Entry(api_row, textvariable=self.api_key, show="*", font=("SF Pro Text", 12))
        self.api_entry.pack(side=LEFT, fill=X, expand=True, ipady=7)
        ttk.Button(api_row, text="显示", style="Secondary.TButton", command=self._toggle_key).pack(side=RIGHT, padx=(10, 0))

        status_card = ttk.Frame(shell, style="Card.TFrame", padding=24)
        status_card.pack(fill=BOTH, expand=True, pady=(18, 0))
        ttk.Label(status_card, text="启动进度", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(status_card, textvariable=self.status, style="Status.TLabel").pack(anchor="w", pady=(6, 12))

        self.progress = ttk.Progressbar(status_card, mode="indeterminate")
        self.progress.pack(fill=X)

        log_frame = ttk.Frame(status_card, style="Card.TFrame")
        log_frame.pack(fill=BOTH, expand=True, pady=(14, 0))
        self.log_text = __import__("tkinter").Text(
            log_frame,
            height=10,
            bg="#111827",
            fg="#d1d5db",
            insertbackground="#d1d5db",
            relief="flat",
            font=("Menlo", 11),
            padx=14,
            pady=12,
        )
        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scroll.pack(side=RIGHT, fill=Y)
        self.log_text.configure(yscrollcommand=scroll.set)

        footer = ttk.Frame(shell, style="Root.TFrame")
        footer.pack(fill=X, pady=(18, 0))
        ttk.Button(footer, text="启动工作台", style="Primary.TButton", command=self.start).pack(side=RIGHT)
        ttk.Button(footer, text="打开使用指南", style="Secondary.TButton", command=self.open_guide).pack(side=RIGHT, padx=(0, 10))

    def _toggle_key(self) -> None:
        self.api_entry.configure(show="" if self.api_entry.cget("show") == "*" else "*")

    def log(self, message: str) -> None:
        def write() -> None:
            self.log_text.insert(END, message.rstrip() + "\n")
            self.log_text.see(END)
        self.root.after(0, write)

    def set_status(self, message: str) -> None:
        self.root.after(0, lambda: self.status.set(message))

    def run(self) -> None:
        self.root.mainloop()

    def start(self) -> None:
        self.progress.start(12)
        threading.Thread(target=self._start_worker, daemon=True).start()

    def _start_worker(self) -> None:
        try:
            self._prepare()
            self._start_server()
        except Exception as exc:
            self.set_status("启动失败")
            self.log(f"启动失败：{exc}")
            self.root.after(0, lambda: messagebox.showerror("启动失败", str(exc)))
        finally:
            self.root.after(0, self.progress.stop)

    def _prepare(self) -> None:
        self.set_status("检查 Python 环境")
        if sys.version_info < (3, 9):
            raise RuntimeError("请先安装 Python 3.9 或更高版本。")
        self.log(f"Python {sys.version.split()[0]} 检查通过")

        for path in [ROOT / "output", ROOT / "output" / "data", ROOT / "output" / "reports", ROOT / "output" / "sessions"]:
            path.mkdir(parents=True, exist_ok=True)

        if self.use_api.get() and self.api_key.get().strip():
            upsert_env_value("DEEPSEEK_API_KEY", self.api_key.get().strip())
            self.log("API Key 已保存")
        elif not self.use_api.get():
            upsert_env_value("DEEPSEEK_API_KEY", "")
            self.log("未启用 API Key，将使用基础功能")

        missing = missing_packages()
        if missing:
            self.set_status("安装项目依赖")
            self.log("缺少依赖：" + ", ".join(missing))
            self._run_command([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)])
        else:
            self.log("项目依赖检查通过")

        marker = ROOT / "output" / ".playwright_chromium_ready"
        if importlib.util.find_spec("playwright") is not None and not marker.exists():
            self.set_status("安装浏览器组件")
            self._run_command([sys.executable, "-m", "playwright", "install", "chromium"])
            marker.write_text(str(int(time.time())), encoding="utf-8")
        else:
            self.log("浏览器组件检查通过")

    def _run_command(self, cmd: list[str]) -> None:
        self.log("$ " + " ".join(cmd))
        proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        assert proc.stdout is not None
        for line in proc.stdout:
            if line.strip():
                self.log(line)
        code = proc.wait()
        if code != 0:
            raise RuntimeError(f"命令执行失败，退出码 {code}")

    def _start_server(self) -> None:
        self.set_status("启动 Web 工作台")
        if self.server_proc and self.server_proc.poll() is None:
            webbrowser.open(URL)
            return

        code = (
            "from web.server import start_server; "
            f"start_server(host='{HOST}', port={PORT}, open_browser=False, background=False)"
        )
        self.server_proc = subprocess.Popen([sys.executable, "-c", code], cwd=str(ROOT))
        time.sleep(1.2)
        webbrowser.open(URL)
        self.set_status("工作台已启动")
        self.log(f"工作台已打开：{URL}")

    def open_guide(self) -> None:
        guide = ROOT / "普通用户使用指南.md"
        webbrowser.open(guide.as_uri() if guide.exists() else URL)

    def _on_close(self) -> None:
        if self.server_proc and self.server_proc.poll() is None:
            if messagebox.askyesno("退出", "关闭启动器会停止本地 Web 工作台，确认退出吗？"):
                self.server_proc.terminate()
                self.root.destroy()
        else:
            self.root.destroy()


if __name__ == "__main__":
    LauncherApp().run()
