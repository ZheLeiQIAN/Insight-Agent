"""Insight Agent Web — Flask 后端 (完整功能)"""

import sys
import json
import threading
import logging
import os
import subprocess
import time
import uuid
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 统一日志（仅当独立运行时才初始化）
if not logging.getLogger().handlers:
    from logging_config import setup_logging
    setup_logging()
logger = logging.getLogger(__name__)

from flask import Flask, render_template, request, jsonify

app = Flask(__name__,
            template_folder=str(Path(__file__).parent / 'templates'),
            static_folder=str(Path(__file__).parent / 'static'))

_sessions = {}
_crawl_jobs = {}
_upload_folder = PROJECT_ROOT / 'output' / 'data'
_upload_folder.mkdir(parents=True, exist_ok=True)


def _is_valid_api_key(value: str) -> bool:
    return bool(value and not value.startswith('sk-your-key') and value != 'here')


def _get_api_key() -> str:
    api_key = os.environ.get('DEEPSEEK_API_KEY', '')
    env_file = PROJECT_ROOT / '.env'
    if not api_key and env_file.exists():
        for line in env_file.read_text(encoding='utf-8').splitlines():
            if line.strip().startswith('DEEPSEEK_API_KEY='):
                api_key = line.split('=', 1)[1].strip()
                break
    return api_key


# ==================== 页面 ====================
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/system/status')
def system_status():
    """给普通用户看的系统状态。"""
    data_files = []
    for ext in ['*.xlsx', '*.csv', '*.json']:
        data_files.extend(_upload_folder.rglob(ext))

    report_dir = PROJECT_ROOT / 'output' / 'reports'
    report_files = list(report_dir.glob('*.html')) if report_dir.exists() else []

    return jsonify({
        'api_key_configured': _is_valid_api_key(_get_api_key()),
        'data_file_count': len(data_files),
        'report_count': len(report_files),
        'data_dir': str(_upload_folder),
        'report_dir': str(report_dir),
    })


# ==================== 爬虫 ====================
@app.route('/api/crawlers')
def list_crawlers():
    from config import CRAWLER_SCRIPTS
    return jsonify([{'key': k, 'platform': v['platform'], 'name': v['name'], 'desc': v['description']} for k, v in CRAWLER_SCRIPTS.items()])


@app.route('/api/crawl', methods=['POST'])
def start_crawl():
    data = request.json
    key = data.get('crawler')
    params = data.get('params', {})

    from config import CRAWLER_SCRIPTS
    if key not in CRAWLER_SCRIPTS:
        return jsonify({'error': f'未知爬虫: {key}'}), 400

    job_id = datetime.now().strftime('%Y%m%d%H%M%S') + '_' + uuid.uuid4().hex[:6]
    _crawl_jobs[job_id] = {
        'id': job_id,
        'crawler': key,
        'platform': CRAWLER_SCRIPTS[key]['platform'],
        'status': 'queued',
        'logs': [],
        'file': None,
        'name': None,
        'rows': 0,
        'error': '',
        'cancel_requested': False,
    }

    thread = threading.Thread(target=_run_crawl_job, args=(job_id, key, params), daemon=True)
    _crawl_jobs[job_id]['thread'] = thread
    thread.start()

    return jsonify({'status': 'started', 'job_id': job_id})


def _append_job_log(job_id, line):
    job = _crawl_jobs.get(job_id)
    if not job:
        return
    logs = job.setdefault('logs', [])
    logs.append(line)
    if len(logs) > 200:
        del logs[:len(logs) - 200]


def _run_crawl_job(job_id, key, params):
    job = _crawl_jobs[job_id]
    try:
        from crawlers.runner import build_command, get_latest_output_files, _collect_output_files, _strip_ansi
        from main import load_data
        from config import CRAWLERS_DIR

        cmd, output_dir = build_command(key, params)
        script_dir = CRAWLERS_DIR / key
        job.update({
            'status': 'running',
            'output_dir': str(output_dir),
            'command': ' '.join(cmd),
            'started_at': datetime.now().isoformat(),
        })
        _append_job_log(job_id, f"开始采集：{job['platform']}")

        proc = subprocess.Popen(
            cmd,
            cwd=str(script_dir),
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        job['process'] = proc

        def read_stream(stream, is_error=False):
            for raw in stream:
                line = _strip_ansi(raw.rstrip('\n'))
                if line.strip():
                    _append_job_log(job_id, ("错误: " if is_error else "") + line)

        threading.Thread(target=read_stream, args=(proc.stdout, False), daemon=True).start()
        threading.Thread(target=read_stream, args=(proc.stderr, True), daemon=True).start()

        while proc.poll() is None:
            if job.get('cancel_requested'):
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                job['status'] = 'cancelled'
                job['finished_at'] = datetime.now().isoformat()
                _append_job_log(job_id, "任务已中止")
                return
            time.sleep(0.5)

        _collect_output_files(script_dir, output_dir)
        files = get_latest_output_files(output_dir)
        if files:
            raw = load_data(files[0])
            job.update({
                'status': 'done',
                'file': str(files[0]),
                'name': files[0].name,
                'rows': len(raw) if raw else 0,
                'finished_at': datetime.now().isoformat(),
            })
            _append_job_log(job_id, f"采集完成：{files[0].name}")
        elif proc.returncode == 0:
            job.update({'status': 'done', 'finished_at': datetime.now().isoformat()})
            _append_job_log(job_id, "采集完成，但没有找到输出文件")
        else:
            job.update({
                'status': 'failed',
                'error': f'爬虫退出码：{proc.returncode}',
                'finished_at': datetime.now().isoformat(),
            })
            _append_job_log(job_id, job['error'])
    except Exception as e:
        logger.error(f"爬虫任务失败: {e}", exc_info=True)
        job.update({'status': 'failed', 'error': str(e), 'finished_at': datetime.now().isoformat()})


@app.route('/api/crawl/status/<job_id>')
def crawl_status(job_id):
    job = _crawl_jobs.get(job_id)
    if not job:
        return jsonify({'error': '任务不存在'}), 404
    payload = {k: v for k, v in job.items() if k not in ('thread', 'process')}
    return jsonify(payload)


@app.route('/api/crawl/cancel/<job_id>', methods=['POST'])
def cancel_crawl(job_id):
    job = _crawl_jobs.get(job_id)
    if not job:
        return jsonify({'error': '任务不存在'}), 404
    if job.get('status') in ('done', 'failed', 'cancelled'):
        return jsonify({'status': job.get('status')})
    job['cancel_requested'] = True
    return jsonify({'status': 'cancelling'})


@app.route('/api/crawl-sync', methods=['POST'])
def start_crawl_sync():
    """保留同步采集接口，供旧调用方兼容。"""
    data = request.json
    key = data.get('crawler')
    params = data.get('params', {})

    from config import CRAWLER_SCRIPTS
    if key not in CRAWLER_SCRIPTS:
        return jsonify({'error': f'未知爬虫: {key}'}), 400

    try:
        from crawlers.runner import run_crawler, get_latest_output_files
        from main import load_data
        output_dir = run_crawler(key, params)
        files = get_latest_output_files(output_dir)
        if files:
            raw = load_data(files[0])
            if raw:
                return jsonify({'status': 'ok', 'file': str(files[0]), 'rows': len(raw), 'name': files[0].name})
        return jsonify({'status': 'ok', 'file': None, 'warning': '采集完成但无数据'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/nl-crawl', methods=['POST'])
def nl_crawl():
    desc = request.json.get('description', '')
    if not desc:
        return jsonify({'error': '请描述需求'}), 400

    from config import LLM_BASE_URL, LLM_MODEL, CRAWLER_SCRIPTS
    if not _is_valid_api_key(_get_api_key()):
        return jsonify({'error': 'DeepSeek API Key 未配置或仍是示例占位值，请在 .env 中填写真实 Key 后再使用自然语言采集。'}), 400

    from openai import OpenAI
    client = OpenAI(api_key=_get_api_key(), base_url=LLM_BASE_URL)

    platforms_desc = '\n'.join(f'- {k}: {v["platform"]} — {v["description"]}' for k, v in CRAWLER_SCRIPTS.items())
    try:
        r = client.chat.completions.create(model=LLM_MODEL, max_tokens=300, temperature=0.1,
            messages=[{'role': 'system', 'content': f'选爬虫。JSON:{{"platform_key":"...","params":{{"url":"...","max":50}},"reason":"..."}}\n{platforms_desc}'},
                      {'role': 'user', 'content': desc}])
    except Exception as e:
        logger.warning(f"自然语言采集 AI 解析失败: {e}")
        return jsonify({'error': f'AI 解析失败，请检查 API Key 或先使用手动选择平台。详情: {e}'}), 400
    raw_resp = r.choices[0].message.content.strip().split('```')[0].strip()
    parsed = json.loads(raw_resp)

    platform = parsed.get('platform_key')
    if not platform or platform not in CRAWLER_SCRIPTS:
        return jsonify({'error': f'无法识别平台: {platform}', 'raw': raw_resp}), 400

    params = parsed.get('params', {})
    reason = parsed.get('reason', '')

    job_id = datetime.now().strftime('%Y%m%d%H%M%S') + '_' + uuid.uuid4().hex[:6]
    _crawl_jobs[job_id] = {
        'id': job_id,
        'crawler': platform,
        'platform': CRAWLER_SCRIPTS[platform]['platform'],
        'reason': reason,
        'status': 'queued',
        'logs': [],
        'file': None,
        'name': None,
        'rows': 0,
        'error': '',
        'cancel_requested': False,
    }
    thread = threading.Thread(target=_run_crawl_job, args=(job_id, platform, params), daemon=True)
    _crawl_jobs[job_id]['thread'] = thread
    thread.start()
    return jsonify({
        'status': 'started',
        'job_id': job_id,
        'platform': CRAWLER_SCRIPTS[platform]['platform'],
        'reason': reason,
    })


# ==================== 模板 ====================
@app.route('/api/templates')
def list_templates():
    from skills import list_templates
    return jsonify(list_templates())


@app.route('/api/templates/run', methods=['POST'])
def run_template():
    data = request.json
    tid = data.get('template_id')
    file_path = data.get('file')

    from skills import get_template
    tmpl = get_template(tid)
    if not tmpl:
        return jsonify({'error': '未知模板'}), 400

    from main import load_data, _run_single_quant, _run_single_qual
    from config import ANALYSIS_MODELS
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from report.generator import generate_report

    fp = Path(file_path) if file_path else None
    if not fp or not fp.exists():
        return jsonify({'error': '文件不存在'}), 400

    raw = load_data(fp)
    if not raw:
        return jsonify({'error': '无法加载数据'}), 400

    results = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {}
        for model in tmpl['models']:
            if model in ANALYSIS_MODELS.get('quantitative', {}):
                futures[pool.submit(_run_single_quant, raw, model, fp)] = model
            elif model in ANALYSIS_MODELS.get('qualitative', {}):
                futures[pool.submit(_run_single_qual, raw, model, fp)] = model
        for f in as_completed(futures):
            try:
                results.update(f.result())
            except Exception as e:
                logger.error(f"分析模型执行失败: {e}")
                continue

    crawler_info = {'platform': '模板分析', 'name': fp.name}
    report_path = generate_report(crawler_info, results, fp, fp.parent)

    return jsonify({'status': 'ok', 'report': str(report_path), 'models_ran': len(results)})


# ==================== 定时任务 ====================
@app.route('/api/schedule', methods=['GET'])
def list_schedule():
    from scheduler import Scheduler
    s = Scheduler()
    return jsonify(s.list_jobs())


@app.route('/api/schedule', methods=['POST'])
def add_schedule():
    data = request.json
    from scheduler import Scheduler
    s = Scheduler()
    jid = s.add(data.get('crawler'), data.get('params', {}), data.get('interval_hours', 24))
    return jsonify({'id': jid})


@app.route('/api/schedule/<job_id>', methods=['DELETE'])
def remove_schedule(job_id):
    from scheduler import Scheduler
    s = Scheduler()
    s.remove(job_id)
    return jsonify({'status': 'ok'})


@app.route('/api/schedule/run', methods=['POST'])
def run_schedule_now():
    from scheduler import Scheduler
    s = Scheduler()
    results = s.run_now()
    return jsonify(results)


# ==================== 会话 + 对话 ====================
@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    result = []
    for sid, s in _sessions.items():
        result.append({
            'id': sid,
            'file': s.data_file.name if hasattr(s, 'data_file') else '?',
            'message_count': len(s.history) // 2 if hasattr(s, 'history') else 0,
            'messages': s.history if hasattr(s, 'history') else [],
        })
    return jsonify(result)


@app.route('/api/sessions', methods=['POST'])
def create_session():
    data = request.json or {}
    file_path = data.get('file')

    if not _is_valid_api_key(_get_api_key()):
        return jsonify({'error': 'AI 对话需要先配置 DeepSeek API Key。你仍然可以先在“分析报告”页面使用基础分析模板。'}), 400

    if file_path:
        fp = Path(file_path)
    else:
        files = list(_upload_folder.rglob('*.xlsx')) + list(_upload_folder.rglob('*.csv'))
        if not files:
            return jsonify({'error': '没有数据文件'}), 400
        fp = max(files, key=lambda f: f.stat().st_mtime)

    from main import load_data
    raw = load_data(fp)
    if not raw:
        return jsonify({'error': '无法加载数据'}), 400

    from chat.agent import AnalystSession
    from analysis.quantitative import auto_detect_fields

    sid = datetime.now().strftime('%Y%m%d%H%M%S')
    session = AnalystSession(raw, fp)
    session.created_at = datetime.now().isoformat()
    session.data_file = fp
    _sessions[sid] = session

    greeting = session.analyst.greet_and_analyze()
    session.history.append({'role': 'assistant', 'content': greeting})
    fields = auto_detect_fields(raw)

    return jsonify({
        'session_id': sid, 'file': fp.name,
        'rows': len(raw), 'columns': len(raw[0]) if raw else 0,
        'fields': fields, 'greeting': greeting,
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    sid = data.get('session_id', 'default')
    message = data.get('message', '')

    if sid not in _sessions:
        return jsonify({'error': '会话不存在'}), 404

    session = _sessions[sid]
    resp = session.process_message(message)
    if resp == '__EXIT__':
        del _sessions[sid]
        return jsonify({'response': '会话已结束', 'closed': True})
    return jsonify({'response': resp})


# ==================== 文件 ====================
@app.route('/api/upload', methods=['POST'])
def upload_file():
    f = request.files.get('file')
    if not f:
        return jsonify({'error': '没有文件'}), 400
    ext = Path(f.filename).suffix.lower()
    if ext not in ('.xlsx', '.csv', '.json'):
        return jsonify({'error': f'不支持: {ext}'}), 400
    dest = _upload_folder / f.filename
    f.save(str(dest))
    return jsonify({'path': str(dest), 'name': f.filename, 'size': dest.stat().st_size})


@app.route('/api/files', methods=['GET'])
def list_files():
    files = []
    for ext in ['*.xlsx', '*.csv', '*.json']:
        for fp in sorted(_upload_folder.rglob(ext), key=lambda f: f.stat().st_mtime, reverse=True)[:20]:
            files.append({
                'name': fp.name, 'path': str(fp),
                'size': fp.stat().st_size,
                'time': datetime.fromtimestamp(fp.stat().st_mtime).strftime('%m-%d %H:%M'),
            })
    return jsonify(files)


# ==================== 数据看板 ====================

@app.route('/api/dashboard/preview', methods=['POST'])
def data_preview():
    """预览数据文件（前 N 行）"""
    data = request.json or {}
    file_path = data.get('file')
    limit = data.get('limit', 20)

    if not file_path:
        return jsonify({'error': '缺少 file 参数'}), 400

    from main import load_data
    raw = load_data(Path(file_path))
    if not raw:
        return jsonify({'error': '数据加载失败'}), 400

    columns = list(raw[0].keys()) if raw else []
    return jsonify({
        'columns': columns,
        'rows': raw[:limit],
        'total': len(raw),
    })


@app.route('/api/dashboard/stats', methods=['POST'])
def data_stats():
    """获取数据文件的快速统计"""
    data = request.json or {}
    file_path = data.get('file')

    if not file_path:
        return jsonify({'error': '缺少 file 参数'}), 400

    from main import load_data
    from analysis.quantitative import auto_detect_fields, basic_stats

    raw = load_data(Path(file_path))
    if not raw:
        return jsonify({'error': '数据加载失败'}), 400

    fields = auto_detect_fields(raw)
    stats = basic_stats(raw, Path(file_path))

    return jsonify({
        'record_count': len(raw),
        'fields': fields,
        'stats': stats,
    })


@app.route('/api/dashboard/analyze', methods=['POST'])
def quick_analyze():
    """快速分析（选择工具执行）"""
    data = request.json or {}
    file_path = data.get('file')
    tool_name = data.get('tool', 'basic_stats')

    if not file_path:
        return jsonify({'error': '缺少 file 参数'}), 400

    from main import load_data
    from analysis.tools_registry import execute_tool

    raw = load_data(Path(file_path))
    if not raw:
        return jsonify({'error': '数据加载失败'}), 400

    result = execute_tool(tool_name, raw, Path(file_path))
    return jsonify(result)


@app.route('/api/dashboard/pipeline', methods=['POST'])
def run_pipeline():
    """运行流水线"""
    data = request.json or {}
    crawler = data.get('crawler')
    url = data.get('url', '')
    max_items = data.get('max', 200)
    models = data.get('models', ['basic_stats', 'sentiment', 'word_freq'])

    if not crawler:
        return jsonify({'error': '缺少 crawler 参数'}), 400

    try:
        from pipeline import quick_pipeline
        result = quick_pipeline(crawler, url, max_items, models)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/dashboard/clean', methods=['POST'])
def clean_data():
    """数据清洗"""
    data = request.json or {}
    file_path = data.get('file')

    if not file_path:
        return jsonify({'error': '缺少 file 参数'}), 400

    from main import load_data
    from analysis.data_cleaner import clean_data as do_clean

    raw = load_data(Path(file_path))
    if not raw:
        return jsonify({'error': '数据加载失败'}), 400

    result = do_clean(raw)
    return jsonify(result['stats'])


@app.route('/api/session/status', methods=['GET'])
def session_status():
    """获取所有平台的登录 session 状态"""
    from crawlers.common.login_helper import is_session_valid, _load_state
    platforms = ["douyin", "zhihu", "xiaohongshu", "tmall", "jd"]
    statuses = {}
    for p in platforms:
        state = _load_state(p)
        statuses[p] = {
            "valid": is_session_valid(p),
            "verified_at": state.get("verified_date", "从未验证"),
        }
    return jsonify(statuses)


def start_server(host='127.0.0.1', port=9527, open_browser=True, background=False):
    """
    启动 Web 服务器

    Args:
        host: 监听地址
        port: 监听端口
        open_browser: 是否自动打开浏览器
        background: 是否在后台运行
    """
    import webbrowser

    if open_browser:
        threading.Timer(1.5, lambda: webbrowser.open(f'http://{host}:{port}')).start()

    if background:
        # 后台运行模式
        server_thread = threading.Thread(
            target=lambda: app.run(host=host, port=port, debug=False, threaded=True),
            daemon=True,
            name="web-server"
        )
        server_thread.start()
        logger.info(f"Web 服务器已在后台启动: http://{host}:{port}")
        return server_thread
    else:
        # 前台运行模式（阻塞）
        print(f"\n🌐 Web UI 已启动: http://{host}:{port}")
        print("   按 Ctrl+C 停止服务器\n")
        try:
            app.run(host=host, port=port, debug=False, threaded=True)
        except KeyboardInterrupt:
            print("\n🛑 Web 服务器已停止")


if __name__ == '__main__':
    start_server()
