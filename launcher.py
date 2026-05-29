#!/usr/bin/env python3
"""Insight Agent 普通用户启动器。

目标：让用户双击启动脚本后，自动完成基础检查并打开 Web UI。
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
REQUIREMENTS = ROOT / "requirements.txt"
HOST = "127.0.0.1"
PORT = 9527
URL = f"http://{HOST}:{PORT}"
AUTO_INSTALL = os.environ.get("INSIGHT_AUTO_INSTALL", "1") != "0"


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


def banner() -> None:
    print()
    print("=" * 64)
    print("  Insight Agent 一键启动器")
    print("  双击即可打开本地 Web 工作台")
    print("=" * 64)
    print()


def pause(message: str = "按回车键退出...") -> None:
    try:
        input(f"\n{message}")
    except EOFError:
        pass


def ask_yes_no(question: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    try:
        answer = input(f"{question} ({suffix}): ").strip().lower()
    except EOFError:
        return default
    if not answer:
        return default
    return answer in {"y", "yes", "是", "好", "确认", "1"}


def run_command(cmd: list[str], title: str) -> bool:
    print(f"\n[步骤] {title}")
    print(" ".join(cmd))
    try:
        result = subprocess.run(cmd, cwd=str(ROOT))
        return result.returncode == 0
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        print(f"执行失败：{exc}")
        return False


def ensure_python() -> None:
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 9):
        print("当前 Python 版本过低。请安装 Python 3.9 或更高版本后再启动。")
        print(f"当前版本：{sys.version.split()[0]}")
        pause()
        sys.exit(1)
    print(f"Python 检查通过：{sys.version.split()[0]}")


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        return

    if ENV_EXAMPLE.exists():
        shutil.copy2(ENV_EXAMPLE, ENV_FILE)
    else:
        ENV_FILE.write_text(
            "\n".join(
                [
                    "DEEPSEEK_API_KEY=",
                    "DEEPSEEK_BASE_URL=https://api.deepseek.com",
                    "DEEPSEEK_MODEL=deepseek-chat",
                    "LOG_LEVEL=INFO",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    print("已创建 .env 配置文件。")


def read_env_value(key: str) -> str:
    if not ENV_FILE.exists():
        return ""
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def upsert_env_value(key: str, value: str) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    updated = False
    next_lines: list[str] = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            next_lines.append(f"{key}={value}")
            updated = True
        else:
            next_lines.append(line)
    if not updated:
        next_lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(next_lines) + "\n", encoding="utf-8")


def ensure_api_key() -> None:
    ensure_env_file()
    key = read_env_value("DEEPSEEK_API_KEY")
    if key and not key.startswith("sk-your-key"):
        print("DeepSeek API Key 已配置。")
        return

    print()
    print("提示：未配置 DeepSeek API Key。")
    print("没有 Key 也可以先打开界面、上传文件、做基础统计；AI 对话和定性分析需要 Key。")
    if ask_yes_no("现在要粘贴 DeepSeek API Key 吗", default=False):
        try:
            new_key = input("请粘贴 API Key：").strip()
        except EOFError:
            new_key = ""
        if new_key:
            upsert_env_value("DEEPSEEK_API_KEY", new_key)
            print("API Key 已保存到 .env。")
    elif key.startswith("sk-your-key"):
        upsert_env_value("DEEPSEEK_API_KEY", "")


def missing_packages() -> list[str]:
    missing: list[str] = []
    for import_name, package_name in REQUIRED_IMPORTS.items():
        if importlib.util.find_spec(import_name) is None:
            missing.append(package_name)
    return sorted(set(missing))


def ensure_dependencies() -> None:
    missing = missing_packages()
    if not missing:
        print("Python 依赖检查通过。")
        return

    print()
    print("检测到缺少依赖：")
    print(", ".join(missing))
    if not REQUIREMENTS.exists():
        print("未找到 requirements.txt，无法自动安装。")
        pause()
        sys.exit(1)

    if AUTO_INSTALL or ask_yes_no("是否自动安装项目依赖", default=True):
        if AUTO_INSTALL:
            print("正在自动安装缺少的依赖...")
        ok = run_command([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)], "安装依赖")
        if not ok:
            print("依赖安装失败。请检查网络，或手动运行：pip install -r requirements.txt")
            pause()
            sys.exit(1)
        print()
        print("依赖安装完成，正在重新启动启动器...")
        os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve())])
    else:
        print("已取消安装。")
        pause()
        sys.exit(1)


def ensure_playwright_browser() -> None:
    if importlib.util.find_spec("playwright") is None:
        return

    marker = ROOT / "output" / ".playwright_chromium_ready"
    if marker.exists():
        return

    print()
    print("爬虫和 PDF 导出通常需要 Playwright Chromium 浏览器。")
    if AUTO_INSTALL or ask_yes_no("是否现在安装 Chromium 浏览器组件", default=False):
        if AUTO_INSTALL:
            print("正在自动安装 Chromium 浏览器组件...")
        ok = run_command([sys.executable, "-m", "playwright", "install", "chromium"], "安装 Chromium")
        if ok:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(str(int(time.time())), encoding="utf-8")
        else:
            print("Chromium 安装失败。你仍然可以先使用上传文件和基础分析功能。")


def ensure_output_dirs() -> None:
    for path in [ROOT / "output", ROOT / "output" / "data", ROOT / "output" / "reports", ROOT / "output" / "sessions"]:
        path.mkdir(parents=True, exist_ok=True)


def start_web_ui() -> None:
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))

    print()
    print("正在启动 Insight Agent Web 工作台...")
    print(f"访问地址：{URL}")
    print("启动后请不要关闭这个窗口；关闭窗口会停止本地服务。")
    print()

    from web.server import start_server

    webbrowser.open(URL)
    start_server(host=HOST, port=PORT, open_browser=False, background=False)


def main() -> None:
    banner()
    try:
        ensure_python()
        ensure_output_dirs()
        ensure_dependencies()
        ensure_api_key()
        ensure_playwright_browser()
        start_web_ui()
    except KeyboardInterrupt:
        print("\n已停止启动。")
    except OSError as exc:
        if getattr(exc, "errno", None) == 48:
            print(f"\n端口 {PORT} 已被占用。请关闭已有的 Insight Agent 窗口后重试。")
        else:
            print(f"\n启动失败：{exc}")
        pause()
    except Exception as exc:
        print(f"\n启动失败：{exc}")
        print("可以把这个窗口里的错误信息发给维护者排查。")
        pause()


if __name__ == "__main__":
    main()
