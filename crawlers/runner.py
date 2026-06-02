"""爬虫模块 - 管理和运行爬虫脚本"""

import subprocess
import sys
import os
import re
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)


def _strip_ansi(text: str) -> str:
    """移除 ANSI 转义序列（颜色、光标控制等）"""
    return re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text).replace('\r', '')

from config import CRAWLER_SCRIPTS, CRAWLERS_DIR, DATA_DIR


def build_command(crawler_key: str, args: dict) -> Tuple[list, Path]:
    """构建爬虫运行命令"""
    info = CRAWLER_SCRIPTS[crawler_key]
    script_dir = CRAWLERS_DIR / crawler_key
    script_path = script_dir / info["script"]
    cmd = [sys.executable, str(script_path)]

    platform = info["platform"]

    if platform == "中国知网":
        cmd.extend(["search", args.get("keyword", ""), "-p", str(args.get("pages", 5))])
        if args.get("type"):
            cmd.extend(["-t", args["type"]])

    elif platform in ["知乎", "小红书"]:
        if args.get("url"):
            cmd.append(args["url"])
        if args.get("max"):
            cmd.extend(["--max", str(args["max"])])

    elif platform == "抖音":
        if args.get("url"):
            cmd.append(args["url"])
        if args.get("max"):
            cmd.extend(["--max", str(args["max"])])
        # 不再强制 --headless，由爬虫根据 session 状态智能决定
        # 首次运行会弹出浏览器让用户登录，之后自动 headless

    elif platform == "哔哩哔哩":
        bv_list = args.get("bv_list", [])
        if bv_list:
            cmd.extend(bv_list)

    elif platform in ["天猫", "京东"]:
        if args.get("url"):
            product_id = args["url"]
            # 京东提取纯数字ID
            if platform == "京东" and "jd.com" in str(product_id):
                import re
                m = re.search(r'(\d{8,})', str(product_id))
                if m:
                    product_id = m.group(1)
            cmd.append(str(product_id))
        if args.get("max"):
            cmd.extend(["--max", str(args["max"])])

    elif platform == "豆瓣":
        mode = args.get("mode", "book")
        if mode == "search" and args.get("keyword"):
            cmd.extend(["search", args["keyword"]])
        else:
            cmd.append(mode)

    elif platform == "通用网页":
        if args.get("url"):
            cmd.append(args["url"])
        if args.get("max"):
            cmd.extend(["--max", str(args["max"])])
        if args.get("mode"):
            cmd.extend(["--mode", str(args["mode"])])

    # 输出目录重定向到项目 data 目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_subdir = DATA_DIR / f"{crawler_key}_{timestamp}"
    output_subdir.mkdir(parents=True, exist_ok=True)

    return cmd, output_subdir


def run_crawler(crawler_key: str, args: dict):
    """运行爬虫并返回输出目录，实时转发爬虫进度"""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    info = CRAWLER_SCRIPTS[crawler_key]

    console.print()
    console.print(Panel.fit(
        f"[bold cyan]Step 2: 运行爬虫[/]\n"
        f"平台: [bold]{info['platform']}[/]\n"
        f"脚本: [dim]{info['name']}[/]",
        border_style="cyan"
    ))

    cmd, output_dir = build_command(crawler_key, args)

    console.print(f"\n  [dim]执行命令:[/] {' '.join(cmd)}")
    console.print(f"  [dim]输出目录:[/] {output_dir}")
    console.print()

    # 设置环境变量让爬虫输出到指定目录
    env = os.environ.copy()

    # 对于使用 output/ 子目录的爬虫(zhihu, bilibili, douyin, xiaohongshu, tmall, jd)
    # 它们在自己的目录下创建 output/，我们运行后把文件移过来
    script_dir = CRAWLERS_DIR / crawler_key

    try:
        # 启动子进程，实时转发输出
        proc = subprocess.Popen(
            cmd,
            cwd=str(script_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        stdout_lines = []
        stderr_lines = []

        def _read_stdout():
            """实时读取并显示子进程 stdout"""
            for line in proc.stdout:
                clean = _strip_ansi(line.rstrip('\n'))
                if clean.strip():
                    # 只显示有意义的进度行，过滤掉空行和重复的装饰线
                    if len(clean.strip()) > 1:
                        console.print(f"  [dim]{clean}[/]")
                stdout_lines.append(clean)

        def _read_stderr():
            """读取子进程 stderr"""
            for line in proc.stderr:
                stderr_lines.append(line.rstrip('\n'))

        import threading
        t_out = threading.Thread(target=_read_stdout, daemon=True)
        t_err = threading.Thread(target=_read_stderr, daemon=True)
        t_out.start()
        t_err.start()

        console.print(f"  [cyan]⠋ 采集: {info['platform']}...[/]")

        try:
            proc.wait(timeout=600)
        except subprocess.TimeoutExpired:
            proc.kill()
            console.print("  [red]✗ 爬虫运行超时 (10分钟)[/]")
            _collect_output_files(script_dir, output_dir)
            return output_dir

        # 等待线程读完剩余输出
        t_out.join(timeout=3)
        t_err.join(timeout=3)

        if proc.returncode != 0:
            console.print(f"\n  [yellow]⚠ 爬虫返回非零退出码: {proc.returncode}[/]")
            if stderr_lines:
                err_text = '\n'.join(stderr_lines)
                console.print(f"  [red]错误: {err_text[:500]}[/]")

        # 尝试收集输出文件
        _collect_output_files(script_dir, output_dir)

        console.print(f"\n  [green]✓[/] 爬虫运行完成，数据保存在: [bold]{output_dir}[/]")
        return output_dir

    except subprocess.TimeoutExpired:
        console.print("  [red]✗ 爬虫运行超时 (10分钟)[/]")
        return output_dir
    except Exception as e:
        console.print(f"  [red]✗ 运行出错: {e}[/]")
        return output_dir


def _collect_output_files(script_dir: Path, output_dir: Path):
    """收集爬虫输出文件到统一目录"""
    import shutil

    # 检查常见的输出位置
    for sub in ["output", "data", "."]:
        search_dir = script_dir / sub
        if not search_dir.exists():
            continue

        for ext in ["*.xlsx", "*.csv", "*.json", "*.txt"]:
            for f in search_dir.glob(ext):
                if f.is_file() and not f.name.startswith("."):
                    dest = output_dir / f.name
                    if f != dest:
                        shutil.copy2(f, dest)


def get_latest_output_files(output_dir: Path) -> list:
    """获取输出目录中的文件列表"""
    files = []
    for ext in ["*.xlsx", "*.csv", "*.json"]:
        files.extend(output_dir.glob(ext))
    return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)


def login_crawler(crawler_key: str):
    """运行爬虫的登录模式（打开浏览器让用户手动登录，缓存 session）"""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    info = CRAWLER_SCRIPTS[crawler_key]

    console.print()
    console.print(Panel.fit(
        f"[bold cyan]🔑 登录模式[/]\n"
        f"平台: [bold]{info['platform']}[/]\n"
        f"请在弹出的浏览器窗口中完成登录",
        border_style="cyan"
    ))

    cmd, _ = build_command(crawler_key, {"url": ""})
    # 替换为登录模式命令
    script_dir = CRAWLERS_DIR / crawler_key
    script_path = script_dir / info["script"]
    cmd = [sys.executable, str(script_path), "--login-only"]

    console.print(f"  [dim]执行命令:[/] {' '.join(cmd)}\n")

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(script_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        def _read_output():
            for line in proc.stdout:
                clean = _strip_ansi(line.rstrip('\n'))
                if clean.strip():
                    console.print(f"  {clean}")

        import threading
        t = threading.Thread(target=_read_output, daemon=True)
        t.start()

        proc.wait(timeout=300)
        t.join(timeout=3)

        if proc.returncode == 0:
            console.print(f"\n  [green]✅ {info['platform']} 登录成功！session 已缓存[/]")
        else:
            console.print(f"\n  [yellow]⚠ 登录过程结束，返回码: {proc.returncode}[/]")

    except subprocess.TimeoutExpired:
        proc.kill()
        console.print("  [red]⏰ 登录超时 (5分钟)[/]")
    except Exception as e:
        console.print(f"  [red]❌ 登录出错: {e}[/]")
