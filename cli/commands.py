"""CLI 交互式命令 — 从 main.py 拆分

包含：自然语言爬虫、技能模板、定时任务、Web UI、登录管理、批量分析、物理世界
"""

import json
import logging
import os
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from config import (
    LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
    CRAWLER_SCRIPTS, REQUIRES_LOGIN, ANALYSIS_MODELS,
    PROJECT_ROOT,
)
from ui import select_crawler, get_crawler_args, select_existing_file, select_multiple_files, confirm_step
from crawlers.runner import run_crawler, get_latest_output_files, login_crawler

logger = logging.getLogger(__name__)
console = Console()


def check_and_login_if_needed(crawler_key: str):
    """爬虫运行前的登录检查"""
    if crawler_key not in REQUIRES_LOGIN:
        return

    from crawlers.common.login_helper import is_session_valid

    if is_session_valid(crawler_key):
        return

    console.print()
    console.print(f"  [yellow]⚠ {crawler_key} 尚未登录或 session 已过期[/]")
    console.print(f"  [dim]需要先在浏览器中手动登录，登录状态会缓存，之后无需重复登录[/]")

    from rich.prompt import Confirm
    if Confirm.ask(f"  是否现在登录 {crawler_key}？", default=True):
        login_crawler(crawler_key)


def login_setup():
    """登录设置：预登录各平台"""
    from crawlers.common.login_helper import print_session_status

    console.print()
    console.print(Panel.fit(
        "[bold cyan]🔑 登录设置[/]\n\n"
        "预登录各平台，缓存 session，之后爬取时无需重复登录\n"
        "[dim]首次使用或 session 过期时需要执行[/]",
        border_style="cyan"
    ))

    print_session_status()

    console.print("  [bold]可登录的平台:[/]")
    platforms = [
        ("douyin", "抖音"),
        ("zhihu", "知乎"),
        ("xiaohongshu", "小红书"),
        ("tmall", "天猫"),
        ("jd", "京东"),
    ]
    for i, (key, name) in enumerate(platforms, 1):
        console.print(f"    {i}. {name} ({key})")

    console.print(f"    0. 返回")

    try:
        choice = input("\n  选择平台 (输入数字): ").strip()
        if choice == "0" or not choice:
            return
        idx = int(choice) - 1
        if 0 <= idx < len(platforms):
            key, name = platforms[idx]
            login_crawler(key)
        else:
            console.print("  [red]无效选择[/]")
    except (ValueError, IndexError):
        console.print("  [red]无效输入[/]")


def natural_language_crawl(load_data_fn, run_ai_flow_fn):
    """自然语言描述需求，AI 自动选爬虫"""
    console.print()
    console.print(Panel.fit(
        "[bold cyan]💬 自然语言启动爬虫[/]\n"
        "用日常语言描述你想采集什么数据",
        border_style="cyan"
    ))

    if not LLM_API_KEY:
        console.print("  [red]未配置 DEEPSEEK_API_KEY，无法使用自然语言功能[/]")
        return

    desc = Prompt.ask("\n  [bold]描述需求[/]",
        default="爬知乎上关于人工智能的回答")

    from openai import OpenAI
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    platforms_desc = "\n".join(
        f"- {k}: {v['platform']} — {v['description']}"
        for k, v in CRAWLER_SCRIPTS.items()
    )

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{
                "role": "system",
                "content": f"""你是一个爬虫任务解析器。根据用户描述，选择最合适的爬虫平台并解析参数。
可用平台：
{platforms_desc}

输出 JSON 格式（不要其他文字、不要 markdown 代码块围栏）：
{{"platform_key": "zhihu", "params": {{"url": "https://..."}}, "reason": "选择理由"}}

字段说明：
- platform_key：上述可用平台中的一项；无法确定时填 null
- params：
  - url：需要打开的目标 URL（如问题页/视频/商品页），可从用户描述里直接拿到才填，没有就省略，不要编
- reason：一句话告诉用户为什么选这个平台

注意：
- "知乎"走 zhihu 平台，"小红书"走 xiaohongshu 平台，不要混
- 默认全部爬取，不加任何条数/上限参数"""
            }, {
                "role": "user",
                "content": desc
            }],
            max_tokens=300,
            temperature=0.1,
        )
    except Exception as e:
        # 捕获网络、鉴权、配额、限流、超时等所有 openai 异常
        console.print(f"  [red]✗ LLM 调用失败: {type(e).__name__}[/]")
        console.print(f"    [dim]{str(e)[:200]}[/]")
        console.print(f"    [dim]排查：检查 .env 中 DEEPSEEK_API_KEY / 网络 / 余额[/]")
        return

    raw = response.choices[0].message.content

    # 健壮 JSON 提取：尝试从 ```...``` 代码块中取，失败则全文本尝试，再失败则正则抓 {...}
    parsed = None
    try:
        # 优先剥掉 markdown 代码块围栏
        candidate = raw.strip()
        if "```" in candidate:
            parts = candidate.split("```")
            # 优先找形如 ```json ... ``` 的第二段；否则取第一个非空段
            for i, p in enumerate(parts):
                p = p.strip()
                if p.startswith("json"):
                    p = p[4:].strip()
                if p.startswith("{") and p.endswith("}"):
                    candidate = p
                    break
            else:
                candidate = parts[1].strip() if len(parts) > 1 else candidate
        else:
            candidate = candidate.strip()
        parsed = json.loads(candidate)
    except (json.JSONDecodeError, IndexError):
        # 兜底：正则抓第一个 {...} 块
        import re as _re
        m = _re.search(r"\{[\s\S]*\}", raw)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    if parsed is None:
        console.print(f"  [red]✗ 无法解析 AI 回复:[/]")
        console.print(f"    [dim]{raw[:200]}[/]")
        logger.error(f"JSON 解析失败，原始返回: {raw}")
        return

    platform = parsed.get("platform_key")
    if not platform or platform not in CRAWLER_SCRIPTS:
        reason_hint = parsed.get("reason", "")
        console.print(f"  [yellow]⚠ 无法确定爬虫平台（AI 返回: {platform}），建议手动选择[/]")
        if reason_hint:
            console.print(f"    [dim]AI 理由: {reason_hint}[/]")
        return

    info = CRAWLER_SCRIPTS[platform]
    params = parsed.get("params", {})
    reason = parsed.get("reason", "")

    console.print(f"\n  [green]✓[/] AI 分析: [bold]{info['name']}[/] ({info['platform']})")
    console.print(f"  [dim]原因: {reason}[/]")

    if not confirm_step("确认执行？"):
        return

    output_dir = run_crawler(platform, params)
    files = get_latest_output_files(output_dir)
    if not files:
        return

    data = load_data_fn(files[0])
    if data:
        run_ai_flow_fn(data, files[0])


def run_skill_template(load_data_fn, preview_fn, run_ai_flow_fn):
    """运行预设分析模板"""
    from skills import list_templates, get_template
    from rich.table import Table
    from concurrent.futures import ThreadPoolExecutor, as_completed

    console.print()
    console.print(Panel.fit("[bold cyan]📋 分析技能模板[/]", border_style="cyan"))

    templates = list_templates()
    t = Table(show_header=True, header_style="bold")
    t.add_column("#", width=4)
    t.add_column("模板", width=22)
    t.add_column("说明", width=45)
    for i, tmpl in enumerate(templates, 1):
        t.add_row(str(i), tmpl["name"], tmpl["desc"])
    console.print(t)
    console.print()

    try:
        choice = Prompt.ask("[bold]选择模板[/]", default="1")
        idx = int(choice) - 1
        if 0 <= idx < len(templates):
            tmpl = get_template(templates[idx]["id"])
        else:
            return
    except (ValueError, IndexError) as e:
        console.print(f"[red]无效选择: {e}[/]")
        return

    data_file = select_existing_file()
    if not data_file:
        return

    data = load_data_fn(data_file)
    if not data:
        return

    if not preview_fn(data, data_file):
        return

    console.print(f"\n  [cyan]执行: {tmpl['name']}...[/]")
    from cli._dispatch import run_single_quant, run_single_qual
    results = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {}
        for model in tmpl["models"]:
            if model in ANALYSIS_MODELS.get("quantitative", {}):
                futures[pool.submit(run_single_quant, data, model, data_file)] = model
            elif model in ANALYSIS_MODELS.get("qualitative", {}):
                futures[pool.submit(run_single_qual, data, model, data_file)] = model
        for f in as_completed(futures):
            try:
                results.update(f.result())
            except Exception as e:
                logger.warning(f"分析任务失败: {e}")
                continue

    from report import generate_report
    crawler_info = {"platform": "模板分析", "name": data_file.name}
    report = generate_report(crawler_info, results, data_file, data_file.parent)
    console.print(f"\n  [green]✓[/] 报告: {report['md']} (Markdown)\n              {report['html']} (HTML)")

    if confirm_step("进入AI对话？"):
        run_ai_flow_fn(data, data_file)


def manage_schedule():
    """管理定时任务"""
    from scheduler import Scheduler
    from rich.table import Table

    scheduler = Scheduler()
    console.print()
    console.print(Panel.fit("[bold cyan]📅 定时任务管理[/]", border_style="cyan"))

    jobs = scheduler.list_jobs()
    if jobs:
        t = Table(show_header=True, header_style="bold")
        t.add_column("ID", width=14)
        t.add_column("状态", width=6)
        t.add_column("平台", width=10)
        t.add_column("参数", width=30)
        t.add_column("间隔", width=6)
        t.add_column("上次", width=16)
        for j in jobs:
            t.add_row(j["id"], j["status"], j["platform"], j["params"][:28], j["interval"], j["last"])
        console.print(t)
    else:
        console.print("  [dim]暂无定时任务[/]")

    console.print()
    action = Prompt.ask("[bold]操作[/]", choices=["add", "remove", "run", "q"], default="add")
    if action == "q":
        return
    elif action == "add":
        sel = select_crawler()
        if not sel:
            return
        key, info = sel
        args = get_crawler_args(info)
        # 间隔输入：限 1~720 小时，非数字/越界给出友好提示而不是 stack trace
        interval_str = Prompt.ask("  间隔(小时)", default="24")
        try:
            interval = int(interval_str)
            if interval < 1 or interval > 720:
                console.print(f"  [red]✗ 间隔需在 1~720 小时之间（30 天内）[/]")
                return
        except ValueError:
            console.print(f"  [red]✗ 无效数字: '{interval_str}'[/]")
            return
        job_id = scheduler.add(key, args, interval)
        console.print(f"  [green]✓[/] 任务已创建: {job_id}")
    elif action == "remove":
        jid = Prompt.ask("  任务ID")
        try:
            ok = scheduler.remove(jid)
            if ok:
                console.print("  [green]✓[/] 已删除")
            else:
                console.print(f"  [red]✗ 任务 ID 不存在: {jid}[/]")
        except Exception as e:
            console.print(f"  [red]✗ 删除失败: {e}[/]")
    elif action == "run":
        results = scheduler.run_now()
        for r in results:
            console.print(f"  {r['status']} {r.get('report', '')}")


# ================================================================
# 统一服务管理器 — 6(WebUI) / 8(物理世界) / 9(城市热区) 共用
# ================================================================

_SERVICE_DIR = Path.home() / ".insight_agent"


def _service_start(name: str, cfg: dict) -> bool:
    """通用服务启动（单进程/双进程统一入口）"""
    log_dir = PROJECT_ROOT / "output" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # 1) 检查是否已在运行
    existing = _service_status(name, cfg, quiet=True)
    if existing:
        console.print(f"  [yellow]⚠ {cfg['name']} 已在运行 (PID: {', '.join(str(p) for p in existing)})[/]")
        return True

    # 2) 端口释放
    for port in cfg["ports"]:
        _force_free_port(port, f"{cfg['name']} · 端口 {port}")

    # 3) Node.js 检查（有前端的项目需要）
    if cfg.get("frontend_dir"):
        if not _check_node_available():
            console.print(f"  [red]✗ 未检测到 Node.js，请先安装: https://nodejs.org/[/]")
            console.print(f"    [dim]{cfg['name']} 需要 Node.js 18+。安装后重新启动。[/]")
            return False
        if not _ensure_npm_dependencies_generic(cfg["frontend_dir"], cfg["name"]):
            return False

    # 4) 启动所有子进程
    procs = []
    for key, cmd, cwd in cfg["start_cmds"]:
        log_path = log_dir / f"{name}_{key}.log"
        proc = _start_subprocess(cmd, cwd, log_path)
        procs.append((key, proc, log_path))

    # 5) 写 PID 文件
    pid_data = {key: proc.pid for key, proc, _ in procs}
    try:
        _SERVICE_DIR.mkdir(parents=True, exist_ok=True)
        cfg["pid_file"].write_text(json.dumps(pid_data))
    except Exception:
        pass

    # 6) 等待就绪
    all_ok = True
    for url_key, port_idx in [("frontend_url", 0), ("backend_url", 1)]:
        url = cfg.get(url_key)
        if not url:
            continue
        port = cfg["ports"][port_idx] if port_idx < len(cfg["ports"]) else None
        if not port:
            continue
        console.print(f"  [cyan]等待 {cfg['name']} {'前端' if url_key == 'frontend_url' else '后端'} ({url})...[/]")
        ok = False
        for _ in range(30):
            if _is_port_open("127.0.0.1", port):
                ok = True
                break
            procs_alive = all(p.poll() is None for _, p, _ in procs)
            if not procs_alive:
                break
            time.sleep(0.5)
        if ok:
            console.print(f"  [green]✓ 就绪[/]")
        else:
            console.print(f"  [yellow]⚠ 15 秒内未就绪（请查看日志: {log_dir}/{name}_*.log）[/]")
            all_ok = False

    # 7) 打开浏览器
    if cfg.get("frontend_url"):
        try:
            webbrowser.open(cfg["frontend_url"])
        except Exception:
            pass

    console.print(f"\n  [green]✅ {cfg['name']} 已启动[/]")
    if cfg.get("frontend_url"):
        console.print(f"    前端: [link={cfg['frontend_url']}]{cfg['frontend_url']}[/link]")
    if cfg.get("backend_url"):
        console.print(f"    后端: [link={cfg['backend_url']}]{cfg['backend_url']}[/link]")
    console.print(f"    日志: {log_dir}/{name}_*.log")
    console.print(f"    [dim]关闭: 回到主菜单再次选择该项即可管理[/]")
    return True


def _service_stop(name: str, cfg: dict):
    """通用服务停止：TERM → 2s → KILL"""
    pid_file = cfg["pid_file"]
    if not pid_file.exists():
        console.print(f"  [dim]{cfg['name']} 未在运行（无 PID 文件）[/]")
        return

    try:
        pid_data = json.loads(pid_file.read_text())
    except (json.JSONDecodeError, Exception):
        pid_data = {}

    console.print(f"  [cyan]正在停止 {cfg['name']}...[/]")
    for key, pid in pid_data.items():
        try:
            subprocess.run(["kill", "-TERM", str(pid)], check=False, timeout=2)
        except Exception:
            pass

    time.sleep(0.5)
    for _ in range(15):
        alive = False
        for _, pid in pid_data.items():
            try:
                subprocess.run(["kill", "-0", str(pid)], check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                alive = True
            except Exception:
                pass
        if not alive:
            break
        time.sleep(0.1)

    for _, pid in pid_data.items():
        try:
            subprocess.run(["kill", "-9", str(pid)], check=False, timeout=1)
        except Exception:
            pass

    pid_file.unlink(missing_ok=True)
    time.sleep(0.3)
    for port in cfg["ports"]:
        if not _is_port_open("127.0.0.1", port):
            console.print(f"  [green]✓ 端口 {port} 已释放[/]")
    console.print(f"  [green]✓ {cfg['name']} 已停止[/]")


def _service_status(name: str, cfg: dict, quiet=False) -> list:
    """通用服务状态检查。返回运行中的 PID 列表"""
    pid_file = cfg["pid_file"]
    pids = []
    if pid_file.exists():
        try:
            pid_data = json.loads(pid_file.read_text())
            pids = list(pid_data.values())
        except Exception:
            pids = []

    alive_pids = []
    for pid in pids:
        try:
            subprocess.run(["kill", "-0", str(pid)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            alive_pids.append(pid)
        except Exception:
            pass

    if quiet:
        return alive_pids

    if not alive_pids:
        if pid_file.exists():
            pid_file.unlink(missing_ok=True)
        console.print(f"  [dim]{cfg['name']}: 未运行[/]")
        return []

    console.print(f"  [green]{cfg['name']}: 运行中 (PID: {', '.join(str(p) for p in alive_pids)})[/]")
    for label, port in [("前端", cfg["ports"][0])]:
        ok = _is_port_open("127.0.0.1", port)
        url = cfg.get("frontend_url", f"http://127.0.0.1:{port}")
        console.print(f"    {'[green]✓[/]' if ok else '[red]✗[/]'} {url} {'可达' if ok else '不可达'}")
    if cfg.get("backend_url") and len(cfg["ports"]) > 1:
        port = cfg["ports"][1]
        ok = _is_port_open("127.0.0.1", port)
        console.print(f"    {'[green]✓[/]' if ok else '[red]✗[/]'} {cfg['backend_url']} {'可达' if ok else '不可达'}")
    return alive_pids


def _ensure_npm_dependencies_generic(target_dir: Path, label: str) -> bool:
    """通用 npm install"""
    if not target_dir.exists():
        console.print(f"  [red]✗ 目录不存在: {target_dir}[/]")
        return False
    node_modules = target_dir / "node_modules"
    if node_modules.exists():
        return True
    console.print(f"  [yellow]首次启动 {label}，正在安装前端依赖...[/]")
    try:
        result = subprocess.run(
            ["npm", "install", "--no-audit", "--no-fund"],
            cwd=str(target_dir),
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            console.print(f"  [red]✗ npm install 失败: {result.stderr[-500:]}[/]")
            return False
        console.print(f"  [green]✓ 前端依赖安装完成[/]")
        return True
    except subprocess.TimeoutExpired:
        console.print(f"  [red]✗ npm install 超时（>10 分钟）[/]")
        return False
    except FileNotFoundError:
        console.print(f"  [red]✗ 找不到 npm 命令，请先安装 Node.js[/]")
        return False


# 服务配置
_SERVICE_CONFIGS = {
    "web": {
        "name": "Web UI",
        "pid_file": _SERVICE_DIR / "web_server.pid",
        "ports": [9527],
        "frontend_url": "http://127.0.0.1:9527",
        "backend_url": None,
        "start_cmds": [
            ("server", [
                sys.executable, "-c",
                f"import sys, logging; sys.path.insert(0, '{PROJECT_ROOT}'); "
                f"from logging_config import setup_logging; setup_logging(); "
                f"from web.server import app; "
                f"app.run(host='127.0.0.1', port=9527, debug=False, threaded=True)"
            ], str(PROJECT_ROOT / "web")),
        ],
        "frontend_dir": None,
    },
    "physical": {
        "name": "物理世界",
        "pid_file": _SERVICE_DIR / "physical.pid",
        "ports": [9528, 9529],
        "frontend_url": "http://127.0.0.1:9528",
        "backend_url": "http://127.0.0.1:9529",
        "start_cmds": [
            ("backend", [
                sys.executable, str(PROJECT_ROOT / "web" / "physical_backend" / "app.py")
            ], str(PROJECT_ROOT / "web")),
            ("frontend", [
                "npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "9528"
            ], str(PROJECT_ROOT / "web" / "physical_world")),
        ],
        "frontend_dir": PROJECT_ROOT / "web" / "physical_world",
    },
    "cityheat": {
        "name": "城市热区图",
        "pid_file": _SERVICE_DIR / "cityheat.pid",
        "ports": [9530, 9531],
        "frontend_url": "http://127.0.0.1:9530",
        "backend_url": "http://127.0.0.1:9531",
        "start_cmds": [
            ("backend", [
                sys.executable, str(PROJECT_ROOT / "web" / "city_heatmap_backend" / "app.py")
            ], str(PROJECT_ROOT / "web")),
            ("frontend", [
                "npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "9530"
            ], str(PROJECT_ROOT / "web" / "city_heatmap")),
        ],
        "frontend_dir": PROJECT_ROOT / "web" / "city_heatmap",
    },
}


# ================================================================
# 统一服务管理 — 6/8/9 联动：后端全启，前端按需
# ================================================================

_ALL_SERVICE_KEYS = ["web", "physical", "cityheat"]


def _start_all_services(mode: str = "web"):
    """启动全部后端 + 仅对应前端。先杀后启，确保干净。
    mode: "web" | "physical" | "cityheat"
    """
    console.print()
    console.print(Panel.fit(
        "[bold cyan]🚀 启动 Insight Agent 服务[/]\n"
        f"[dim]后端全启 (9527/9529/9531) · 前端按需 ({mode})[/]",
        border_style="cyan",
    ))

    # 先全部停掉，确保干净重启
    for key in _ALL_SERVICE_KEYS:
        cfg = _SERVICE_CONFIGS[key]
        alive = _service_status(key, cfg, quiet=True)
        if alive:
            console.print(f"  [yellow]⚠ {cfg['name']} 已在运行，先停后启...[/]")
            _service_stop(key, cfg)
    # 额外确保端口全释放
    for port in [9527, 9528, 9529, 9530, 9531]:
        _force_free_port(port)
    console.print()

    # 启动全部后端
    for key in _ALL_SERVICE_KEYS:
        cfg = _SERVICE_CONFIGS[key]
        _service_start_backend_only(key, cfg)

    # 只启对应模式的前端
    if mode in _SERVICE_CONFIGS:
        cfg = _SERVICE_CONFIGS[mode]
        if cfg.get("frontend_dir"):  # 有独立前端的才单独启
            _service_start_frontend_only(mode, cfg)

    console.print()
    console.print("[green]✅ 全部服务已就绪[/]")
    console.print("  后端 (全启):   9527 · 9529 · 9531")
    console.print(f"  前端 (仅{mode}):  http://127.0.0.1:{_SERVICE_CONFIGS[mode]['ports'][0]}")
    console.print()

    # 自动打开浏览器
    url = _SERVICE_CONFIGS[mode].get("frontend_url") or f"http://127.0.0.1:{_SERVICE_CONFIGS[mode]['ports'][0]}"
    try:
        webbrowser.open(url)
        console.print(f"  [dim]🌐 已自动打开浏览器: {url}[/]")
    except Exception:
        pass


def _service_start_backend_only(name: str, cfg: dict):
    """只启动后端进程，跳过前端"""
    log_dir = PROJECT_ROOT / "output" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # 1) 释放后端端口
    backend_cmds = [(k, cmd, cwd) for k, cmd, cwd in cfg.get("start_cmds", []) if k == "server" or k == "backend"]
    for key, cmd, cwd in backend_cmds:
        # 根据 key 推断端口
        pass  # 端口释放统一在下面做

    for port in cfg["ports"]:
        _force_free_port(port, f"{cfg['name']} · 端口 {port}")

    # 2) Node.js 检查（仅前端需要，后端跳过）
    # 后端直接用 Python，不需要 Node

    # 3) 启动后端子进程
    procs = []
    for key, cmd, cwd in cfg.get("start_cmds", []):
        if key not in ("server", "backend"):
            continue  # 跳过前端进程
        log_path = log_dir / f"{name}_{key}.log"
        proc = _start_subprocess(cmd, cwd, log_path)
        procs.append((key, proc, log_path))
        console.print(f"  [dim]启动 {cfg['name']} {key} (PID {proc.pid})[/]")

    if not procs:
        return

    # 4) 写 PID 文件
    try:
        _SERVICE_DIR.mkdir(parents=True, exist_ok=True)
        pid_data = {key: proc.pid for key, proc, _ in procs}
        cfg["pid_file"].write_text(json.dumps(pid_data))
    except Exception:
        pass

    # 5) 等待后端就绪
    if cfg.get("backend_url"):
        port = cfg["ports"][-1] if cfg.get("backend_url") else cfg["ports"][0]
        console.print(f"  [cyan]等待 {cfg['name']} 后端 (端口 {port})...[/]")
        ok = False
        for _ in range(30):
            if _is_port_open("127.0.0.1", port):
                ok = True
                break
            procs_alive = all(p.poll() is None for _, p, _ in procs)
            if not procs_alive:
                break
            time.sleep(0.5)
        if ok:
            console.print(f"  [green]✓ {cfg['name']} 后端就绪[/]")
    else:
        # Web UI 只有一个进程
        port = cfg["ports"][0]
        console.print(f"  [cyan]等待 {cfg['name']} (端口 {port})...[/]")
        ok = False
        for _ in range(30):
            if _is_port_open("127.0.0.1", port):
                ok = True
                break
            procs_alive = all(p.poll() is None for _, p, _ in procs)
            if not procs_alive:
                break
            time.sleep(0.5)
        if ok:
            console.print(f"  [green]✓ {cfg['name']} 就绪[/]")
        else:
            console.print(f"  [yellow]⚠ {cfg['name']} 15s 内未就绪[/]")


def _service_start_frontend_only(name: str, cfg: dict):
    """只启动前端进程"""
    if not cfg.get("frontend_dir"):
        return  # Web UI 没有独立前端，跳过

    log_dir = PROJECT_ROOT / "output" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Node.js 检查
    if not _check_node_available():
        console.print(f"  [red]✗ 未检测到 Node.js，{cfg['name']} 前端无法启动[/]")
        return

    if not _ensure_npm_dependencies_generic(cfg["frontend_dir"], cfg["name"]):
        return

    # 确保前端端口释放
    frontend_port = cfg["ports"][0]
    _force_free_port(frontend_port, f"{cfg['name']} 前端 · 端口 {frontend_port}")

    # 读已有 PID 文件
    existing_pids = {}
    if cfg["pid_file"].exists():
        try:
            existing_pids = json.loads(cfg["pid_file"].read_text())
        except Exception:
            pass

    # 启动前端进程
    procs = []
    for key, cmd, cwd in cfg.get("start_cmds", []):
        if key != "frontend":
            continue
        log_path = log_dir / f"{name}_{key}.log"
        proc = _start_subprocess(cmd, cwd, log_path)
        procs.append((key, proc, log_path))
        console.print(f"  [dim]启动 {cfg['name']} {key} (PID {proc.pid})[/]")

    if not procs:
        return

    # 合并 PID
    for key, proc, _ in procs:
        existing_pids[key] = proc.pid
    try:
        _SERVICE_DIR.mkdir(parents=True, exist_ok=True)
        cfg["pid_file"].write_text(json.dumps(existing_pids))
    except Exception:
        pass

    # 等待前端就绪
    frontend_port = cfg["ports"][0]
    console.print(f"  [cyan]等待 {cfg['name']} 前端 (端口 {frontend_port})...[/]")
    ok = False
    for _ in range(30):
        if _is_port_open("127.0.0.1", frontend_port):
            ok = True
            break
        procs_alive = all(p.poll() is None for _, p, _ in procs)
        if not procs_alive:
            break
        time.sleep(0.5)
    if ok:
        console.print(f"  [green]✓ {cfg['name']} 前端就绪[/]")


def _stop_all_services():
    """停止全部三个服务"""
    console.print()
    console.print(Panel.fit(
        "[bold red]⏹ 停止全部 Insight Agent 服务[/]",
        border_style="red",
    ))

    for key in _ALL_SERVICE_KEYS:
        cfg = _SERVICE_CONFIGS[key]
        _service_stop(key, cfg)

    # 额外确保端口都释放
    for port in [9527, 9528, 9529, 9530, 9531]:
        _force_free_port(port)

    console.print()
    console.print("[green]✅ 全部服务已停止[/]")


def start_web_ui():
    """Web UI 服务管理 — 后端全启，仅开 Web UI 前端"""
    console.print()
    console.print(Panel.fit(
        "[bold cyan]🌐 Web UI — 网络数据洞察[/]\n"
        "[dim]后端全启 (9527/9529/9531) · 仅展示 Web UI 前端[/]",
        border_style="cyan",
    ))
    _service_manage_menu("web")


def start_physical_world_ui():
    """物理世界 — 后端全启，仅开物理世界前端"""
    console.print()
    console.print(Panel(
        "[bold cyan]👁 物理世界 — 摄像头·人流·行为[/]\n\n"
        "[dim]浏览器交互: MediaPipe Hands / FaceMesh + TensorFlow.js\n"
        "后端分析:  PaddleDetection (PP-Human / 商场定制 pipeline)\n"
        "智能体:    行为事件 → 意图预判 → 调 LLM 出商家建议\n\n"
        "后端全启 (9527/9529/9531) · 仅展示物理世界前端 (9528)[/]",
        title="👁 物理世界",
        border_style="cyan",
    ))
    _service_manage_menu("physical")


def start_city_heatmap_ui():
    """城市热区图 — 后端全启，仅开城市热区前端"""
    console.print()
    console.print(Panel(
        "[bold cyan]🔥 城市热区图 — 地图·粒子流·行为分析[/]\n\n"
        "[dim]地图引擎: 高德地图 JS API v2.0 (热力图 + 粒子流)\n"
        "分析引擎: 密度分析 / 流向分析 / 热区检测 / 异常预警\n"
        "智能体:   人群事件 → 行为分析 → LLM 建议\n\n"
        "后端全启 (9527/9529/9531) · 仅展示城市热区前端 (9530)[/]",
        title="🔥 城市热区图",
        border_style="cyan",
    ))
    _service_manage_menu("cityheat")


def _service_manage_menu(mode: str):
    """统一的服务管理子菜单"""
    all_running = True
    for key in _ALL_SERVICE_KEYS:
        cfg = _SERVICE_CONFIGS[key]
        alive = _service_status(key, cfg, quiet=True)
        if alive:
            console.print(f"  [green]● {cfg['name']}[/] 运行中 (PID {', '.join(str(p) for p in alive)})")
        else:
            console.print(f"  [dim]○ {cfg['name']}[/] 未运行")
            all_running = False
    console.print()

    default_action = "stop" if all_running else "start"
    action = Prompt.ask(
        "[bold]操作[/] [dim](start/stop/status/q=返回)[/]",
        choices=["start", "stop", "status", "q"],
        default=default_action,
    )
    if action == "q":
        return
    elif action == "start":
        _start_all_services(mode)
    elif action == "stop":
        _stop_all_services()
    elif action == "status":
        for key in _ALL_SERVICE_KEYS:
            cfg = _SERVICE_CONFIGS[key]
            _service_status(key, cfg)
    console.print()


def run_batch_analysis(files: List[Path], load_data_fn=None):
    """批量分析多个文件并生成对比报告"""
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from cli._dispatch import run_single_quant
    from ui import select_analysis_models
    from report import generate_report

    if load_data_fn is None:
        load_data_fn = load_data

    # 统一让用户选模型，单文件/批量化行为一致
    selected_models = select_analysis_models()
    if not selected_models:
        console.print("\n[yellow]未选择分析模型[/]")
        return

    all_reports = []
    console.print()
    console.print(Panel.fit(
        f"[bold magenta]批量分析: {len(files)} 个文件 · {len(selected_models)} 个模型[/]",
        border_style="magenta"
    ))

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as progress:
        task = progress.add_task("[cyan]分析中...", total=len(files))

        for f in files:
            progress.update(task, description=f"[cyan]分析: {f.name}[/]")
            data = load_data_fn(f)
            if not data:
                progress.advance(task)
                continue

            results = {}
            for model in selected_models:
                try:
                    r = run_single_quant(data, model, f)
                    results.update(r)
                except Exception as e:
                    logger.warning(f"分析模型 {model} 失败: {e}")
                    continue

            crawler_info = {"platform": "本地文件", "name": f.name}
            report = generate_report(crawler_info, results, f, f.parent)
            all_reports.append({"file": f.name, "path": report['html'], "results": results})
            progress.advance(task)

    console.print(f"\n  [green]✓[/] {len(all_reports)}/{len(files)} 个文件分析完成")
    for r in all_reports:
        record_count = r["results"].get("basic_stats", {}).get("record_count", "?")
        console.print(f"    📄 {r['file']} — {record_count} 条记录 → {r['path'].name}")

    console.print()
    if confirm_step(f"在浏览器中打开所有报告？"):
        import webbrowser
        for r in all_reports:
            webbrowser.open(f"file://{r['path']}")


def _is_port_open(host: str, port: int, timeout: float = 0.3) -> bool:
    """检查端口是否已被占用"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _get_port_pids(port: int) -> list:
    """获取监听指定端口的进程 PID 列表（macOS / Linux 通用，依赖 lsof）"""
    try:
        out = subprocess.check_output(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            stderr=subprocess.DEVNULL, text=True,
        )
        return [int(p) for p in out.split() if p.strip().isdigit()]
    except Exception:
        return []


def _get_process_cmdline(pid: int) -> str:
    """获取进程的完整命令行（macOS / Linux 通用）"""
    try:
        return subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "command="],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return ""


def _kill_orphan_insight_procs(port: int) -> int:
    """白名单清理：仅当端口占用者是 Insight Agent 自己遗留的孤儿进程时才 kill。
    返回被清理的进程数。
    """
    ALLOW_KEYWORDS = [
        ("physical_world", "vite"), ("physical_world", "npm"),
        ("physical_backend", "app.py"), ("physical_backend", "python"),
        ("city_heatmap", "vite"), ("city_heatmap", "npm"),
        ("city_heatmap_backend", "app.py"), ("city_heatmap_backend", "python"),
        ("app.py", "9529"), ("app.py", "9531"),
        ("web/server", "9527"), ("webui_manager", "start"),
    ]
    killed = 0
    for pid in _get_port_pids(port):
        cmd = _get_process_cmdline(pid)
        if not cmd:
            continue
        cmd_l = cmd.lower()
        for path_kw, launcher_kw in ALLOW_KEYWORDS:
            if path_kw in cmd_l and launcher_kw in cmd_l:
                try:
                    subprocess.run(["kill", "-9", str(pid)], check=False)
                    console.print(f"  [dim]清理孤儿 {path_kw} 进程 PID={pid} (port {port})[/]")
                    killed += 1
                except Exception:
                    pass
                break
    if killed > 0:
        time.sleep(0.6)
    return killed


def _force_free_port(port: int, label: str = "") -> bool:
    """强制释放端口 — 杀掉任何占用进程，不留情"""
    pids = _get_port_pids(port)
    if not pids:
        return True
    label_prefix = f"[{label}] " if label else ""
    for pid in pids:
        cmd = _get_process_cmdline(pid)
        console.print(f"  [yellow]⚠ {label_prefix}端口 {port} 被占用 (PID {pid}: {cmd[:60]})，正在杀掉...[/]")
        try:
            subprocess.run(["kill", "-9", str(pid)], check=False)
        except Exception:
            pass
    time.sleep(0.8)
    if _is_port_open("127.0.0.1", port):
        # 再试一次
        pids2 = _get_port_pids(port)
        for pid in pids2:
            try:
                subprocess.run(["kill", "-9", str(pid)], check=False)
            except Exception:
                pass
        time.sleep(0.5)
    if _is_port_open("127.0.0.1", port):
        console.print(f"  [red]✗ {label_prefix}端口 {port} 释放失败[/]")
        return False
    console.print(f"  [green]✓ {label_prefix}端口 {port} 已释放[/]")
    return True


def _check_node_available() -> bool:
    """检查 Node.js / npm 是否可用"""
    return subprocess.run(
        ["node", "-v"], capture_output=True, text=True
    ).returncode == 0


def _start_subprocess(cmd: list, cwd: str, log_path: Path, env: dict = None) -> subprocess.Popen:
    """后台启动子进程，日志重定向到 log_path"""
    log_f = open(log_path, "ab", buffering=0)
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        env={**os.environ, **(env or {})},
    )
    return proc
