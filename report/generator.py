"""报告生成模块 — 五段式专业分析报告（Markdown + HTML 双格式）

报告结构：
  1. 执行摘要      (LLM 生成 / 模板降级)
  2. 数据说明      (字段表 + 质量提示，不依赖 LLM)
  3. 分析工具说明  (从 tools_registry 拉)
  4. 分析结果      (各工具的原始结果，含图表)
  5. 关键发现      (LLM 生成 / 模板降级)
  6. 启示与预测    (LLM 生成 / 模板降级)
  7. 附录：数据预览

向后兼容：旧 generate_report(crawler_info, results, data_file, output_dir) 仍可用，
返回 dict 包含 md / html / qa.json 三个路径。旧调用方拿到的 `report_path` 可用
`result["html"]` 替换。
"""

import html
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from config import REPORT_DIR

from report.llm_synth import (
    synthesize_summary,
    synthesize_findings,
    synthesize_implications,
)

logger = logging.getLogger(__name__)


# ================================================================
# 公共入口
# ================================================================

def generate_report(
    crawler_info: dict,
    analysis_results: Dict[str, Any],
    data_file: Path,
    output_dir: Path,
    *,
    conversation: List[Dict] = None,
    data_meta: Dict[str, Any] = None,
    llm_synthesize: bool = True,
    formats: tuple = ("md", "html", "qa_json"),
) -> Dict[str, Path]:
    """
    生成五段式分析报告，输出 .md / .html / .qa.json（可裁剪）

    Parameters
    ----------
    crawler_info    : {"platform": str, "name": str, ...} 数据来源描述
    analysis_results: {model_key: result_dict, ...} 各分析工具的输出
    data_file       : 原始数据文件路径
    output_dir      : 报告输出目录；为 None 时用 REPORT_DIR
    conversation    : AI 分析师对话历史（可选，存到 qa.json 里供后续 AI 问答用）
    data_meta       : 数据元信息（字段类型/缺失率等）；为 None 时自动从原始数据算
    llm_synthesize  : 是否调用 LLM 生成摘要/发现/启示
    formats         : 要生成的文件类型子集；默认全部。"md" / "html" / "qa_json" 任选

    Returns
    -------
    dict  例如 {"md": Path, "qa_json": Path}（取决于 formats）
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1) 归一化 context
    context = _build_context(
        crawler_info=crawler_info,
        analysis_results=analysis_results,
        data_file=data_file,
        conversation=conversation,
        data_meta=data_meta,
    )

    # 2) 先把降级模板放进去（即使 LLM 可用，也作为兜底）
    from report.llm_synth import (
        _fallback_summary, _fallback_findings, _fallback_implications,
    )
    context["executive_summary"] = _fallback_summary(context)
    context["key_findings"] = _fallback_findings(context)
    context["implications"] = _fallback_implications(context)

    # 3) LLM 增强段（覆盖降级版）
    if llm_synthesize:
        try:
            llm_summary = synthesize_summary(context)
            if llm_summary:
                context["executive_summary"] = llm_summary
        except Exception as e:
            logger.warning("执行摘要生成失败，使用降级模板: %s", e)
        try:
            llm_findings = synthesize_findings(context)
            if llm_findings:
                context["key_findings"] = llm_findings
        except Exception as e:
            logger.warning("关键发现生成失败，使用降级模板: %s", e)
        try:
            llm_impl = synthesize_implications(context)
            if llm_impl and (llm_impl.get("建议") or llm_impl.get("预测")):
                context["implications"] = llm_impl
        except Exception as e:
            logger.warning("启示预测生成失败，使用降级模板: %s", e)

    # 3) 拼装 + 写盘
    md = _build_markdown(context)
    html_doc = _build_html(context)

    # 写到指定目录（默认 REPORT_DIR）
    target_dir = Path(output_dir) if output_dir else REPORT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    out: Dict[str, Path] = {}
    if "md" in formats:
        out["md"] = target_dir / f"analysis_{timestamp}.md"
        out["md"].write_text(md, encoding="utf-8")
    if "html" in formats:
        out["html"] = target_dir / f"analysis_{timestamp}.html"
        out["html"].write_text(html_doc, encoding="utf-8")

    # 4) 写 qa.json（兼容旧行为 + 含 AI 对话）
    if "qa_json" in formats:
        qa_json_path = target_dir / f"analysis_{timestamp}.qa.json"
        qa_data = {
            "crawler": crawler_info,
            "analysis": analysis_results,
            "data_file": str(data_file),
            "data_meta": context["data_meta"],
            "generated_at": datetime.now().isoformat(),
        }
        if conversation:
            qa_data["conversation"] = conversation
        qa_json_path.write_text(
            json.dumps(qa_data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        out["qa_json"] = qa_json_path

    logger.info("报告已生成: %s", out)
    return out


# ================================================================
# PDF 导出（保留旧实现，不动）
# ================================================================

# ================================================================
# LLM 增强 HTML：从 .md 读，让 LLM 改写成更丰富的 HTML
# ================================================================

_PROMPT_MD_TO_HTML = """你是一位专业的数据可视化设计师与前端工程师。请把以下 Markdown 数据分析报告改写为一份完整的 HTML 文档。

## 设计要求
1. 完整保留原报告的所有数据、结论、文字（不要删改数据点）
2. 现代设计：Inter 字体 + Noto Sans SC 中文；柔和阴影 + 大圆角；渐变 / 玻璃拟态元素
3. 卡片化布局：关键发现用 3-4 列卡片网格；启示用绿色/蓝色左边框
4. 数字高亮：核心指标（百分比、绝对值）使用大字号彩色高亮
5. emoji 章节标题：每个 H2 前加一个合适的 emoji 图标
6. 图表：情感分布饼图、词频 Top 10 柱状图用 Chart.js 渲染（HTML 里直接内联 CDN）
7. 动效：滚动进入视口时淡入（IntersectionObserver）
8. 响应式：手机/平板/桌面都能看
9. 打印样式：@media print 隐藏 nav，章节避免被切断

## 结构要求
- 顶部 hero 区域：大标题 + 副标题 + 报告生成时间 + 数据文件信息
- 顶部 sticky 目录（点击跳转，带动画）
- 七段式：执行摘要 / 数据说明 / 分析工具说明 / 分析结果 / 关键发现 / 启示与预测 / 附录
- 底部 footer

## 输出要求
- 完整 <!DOCTYPE html> 文档：meta、title、内联 CSS、内联 JS
- 不需要任何额外说明文字，**直接输出 HTML 代码本身**
- 不要用 markdown 代码块围栏包住

以下是原 Markdown 报告：

```markdown
{md_content}
```"""


def generate_html_from_markdown(
    md_path: Path,
    output_path: Path = None,
    *,
    llm_enhance: bool = True,
) -> Optional[Path]:
    """从 .md 文件生成 .html 报告。

    Parameters
    ----------
    md_path     : 已有 .md 报告路径
    output_path : .html 输出路径；默认同目录同名换后缀
    llm_enhance : 是否调用 LLM 改写（需要 LLM_API_KEY；失败则降级到简单 HTML 包装）

    Returns
    -------
    Path or None
    """
    md_path = Path(md_path)
    md_content = md_path.read_text(encoding="utf-8")
    if output_path is None:
        output_path = md_path.with_suffix(".html")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if llm_enhance:
        llm_html = _call_llm_for_html(md_content)
        if llm_html:
            output_path.write_text(llm_html, encoding="utf-8")
            logger.info("LLM 增强 HTML 已生成: %s (%d bytes)", output_path, output_path.stat().st_size)
            return output_path

    # 降级：用简单模板把 .md 渲染成 HTML
    fallback_html = _simple_md_to_html(md_content, title=md_path.stem)
    output_path.write_text(fallback_html, encoding="utf-8")
    logger.info("降级 HTML 已生成: %s (%d bytes)", output_path, output_path.stat().st_size)
    return output_path


def _call_llm_for_html(md_content: str) -> Optional[str]:
    """调 LLM 把 .md 改写成更丰富的 HTML。返回 None 表示不可用。"""
    try:
        from openai import OpenAI
        from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE
    except Exception as e:
        logger.debug("LLM 不可用: %s", e)
        return None

    if not LLM_API_KEY:
        logger.debug("LLM_API_KEY 为空，跳过")
        return None

    # .md 太长就截断（一般 < 30K 字符，留足 LLM 上下文）
    truncated = md_content[:25000]
    if len(md_content) > 25000:
        truncated += "\n\n... (内容过长已截断)"

    user_msg = _PROMPT_MD_TO_HTML.format(md_content=truncated)

    try:
        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是一位资深的数据可视化设计师 + 前端工程师，专长把 Markdown 数据报告改写成精美 HTML。"},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=min(LLM_MAX_TOKENS, 6000),
            temperature=0.4,  # 略低于默认，让设计更稳定
        )
        content = resp.choices[0].message.content
        if not content:
            return None
        html_doc = content.strip()
        # 去掉可能的 ```html 围栏
        if html_doc.startswith("```"):
            html_doc = re.sub(r"^```(?:html)?\s*\n?", "", html_doc)
            html_doc = re.sub(r"\n?```\s*$", "", html_doc)
        # 必须是完整 HTML
        if "<html" not in html_doc.lower() and "<!doctype" not in html_doc.lower():
            logger.warning("LLM 输出不像完整 HTML，降级")
            return None
        return html_doc
    except Exception as e:
        logger.warning("LLM HTML 生成失败: %s", e)
        return None


def _simple_md_to_html(md_content: str, title: str = "分析报告") -> str:
    """把 .md 简单包成 HTML（无 LLM 时的降级版）

    保留 .md 的七段式结构（## 1. ~ ## 7. 标题 → id="s1" ~ id="s7"），
    并加 sticky TOC、Chart.js CDN，与正式版 HTML 视觉一致。
    """
    inner = _md_to_html(md_content)

    # 从 .md 提取 7 段标题，在 inner 前面加 id 锚点
    # _md_to_html 把 ## N. 标题 (h2) 渲染成 <h4>N. 标题</h4>（+2 偏移）
    section_titles = []
    for m in re.finditer(r'^##\s+(\d+)\.\s+(.+)$', md_content, flags=re.MULTILINE):
        sid = f's{m.group(1)}'
        stitle = m.group(2).strip()
        section_titles.append((sid, stitle))
        # 在 _md_to_html 输出里找对应的 <h4>N. 标题</h4>，给它加 id
        escaped_title = html.escape(stitle)
        anchor = f'<h4 id="{sid}">'
        old = f'<h4>{m.group(1)}. {escaped_title}</h4>'
        if old in inner:
            inner = inner.replace(old, anchor + f'{m.group(1)}. {escaped_title}</h4>', 1)

    toc_items = "".join(
        f'<li><a href="#{sid}">{sid[1:]}. {html.escape(t)}</a></li>'
        for sid, t in section_titles
    )
    toc_html = f'''<nav class="toc" id="toc">
  <div class="toc-title">目录</div>
  <ol>{toc_items}</ol>
</nav>
''' if toc_items else ''

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)} — 数据分析报告</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
{_HTML_CSS}
</style>
</head>
<body>

<div class="header">
  <h1>{html.escape(title)}</h1>
  <p>数据分析报告（降级版 · 从 Markdown 渲染）</p>
</div>
{toc_html}
<div class="container">
{inner}
</div>
<div class="footer">
  <p>报告由 Insight Agent 自动生成 · Markdown 降级版 · Powered by DeepSeek</p>
</div>
</body>
</html>
"""


# ================================================================
# PDF 导出（保留旧实现，不动）
# ================================================================

def export_pdf(html_path: Path, pdf_path: Path = None) -> Optional[Path]:
    """将 HTML 报告导出为 PDF（weasyprint → playwright → 降级）"""
    if pdf_path is None:
        pdf_path = html_path.with_suffix('.pdf')

    html_content = html_path.read_text(encoding='utf-8')

    try:
        from weasyprint import HTML
        HTML(string=html_content, base_url=str(html_path.parent)).write_pdf(str(pdf_path))
        logger.info(f"PDF 导出成功 (weasyprint): {pdf_path}")
        return pdf_path
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"weasyprint 导出失败: {e}")

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(html_content, wait_until="networkidle")
            page.pdf(path=str(pdf_path), format="A4", margin={"top": "20mm", "bottom": "20mm"})
            browser.close()
        logger.info(f"PDF 导出成功 (playwright): {pdf_path}")
        return pdf_path
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"playwright 导出失败: {e}")

    logger.warning(
        "PDF 导出需要安装 weasyprint 或 playwright:\n"
        "  pip install weasyprint\n"
        "  或: pip install playwright && playwright install chromium"
    )
    return None


# ================================================================
# Context 归一化
# ================================================================

def _build_context(
    crawler_info: dict,
    analysis_results: Dict[str, Any],
    data_file: Path,
    conversation: Optional[List[Dict]],
    data_meta: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """把入参归一化成统一 context dict，给 Markdown / HTML 拼装用"""

    # 自动算 data_meta（如果没传）
    if data_meta is None:
        try:
            from analysis.report_meta import build_data_meta
            # 从 analysis_results 找原始数据
            data = _extract_raw_data(analysis_results)
            data_meta = build_data_meta(data, data_file)
        except Exception as e:
            logger.warning("data_meta 自动生成失败: %s", e)
            data_meta = {
                "file_name": data_file.name,
                "record_count": 0,
                "field_count": 0,
                "fields": [],
                "quality_issues": ["元信息生成失败"],
            }

    # 加载工具元信息
    try:
        from analysis.tools_registry import ToolsRegistry, AnalysisCategory
        tool_objs = ToolsRegistry.get_all_tools()
        tools_meta = []
        for t in tool_objs:
            tools_meta.append({
                "name": t.name,
                "category": t.category.value,
                "description": t.description,
                "required_fields": t.required_fields or [],
            })
    except Exception as e:
        logger.warning("tools_meta 加载失败: %s", e)
        tools_meta = []

    platform = crawler_info.get("platform", "未知平台")
    name = crawler_info.get("name", data_file.stem)
    title = f"{platform} · {name}"

    return {
        "title": title,
        "platform": platform,
        "name": name,
        "crawler_info": crawler_info,
        "analysis_results": analysis_results,
        "data_meta": data_meta,
        "tools_meta": tools_meta,
        "conversation": conversation or [],
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_file": data_file,
        # LLM 段占位（generate_report 主流程会填充）
        "executive_summary": "",
        "key_findings": [],
        "implications": {"建议": [], "预测": []},
    }


def _extract_raw_data(results: Dict[str, Any]) -> list:
    """从 basic_stats 等结果里取原始 data（如果它附带了）"""
    bs = results.get("basic_stats", {})
    return bs.get("_raw_data", []) if isinstance(bs, dict) else []


# ================================================================
# Markdown 拼装
# ================================================================

def _build_markdown(ctx: Dict[str, Any]) -> str:
    parts = []
    parts.append(_md_header(ctx))
    parts.append(_md_toc())
    parts.append(_md_section_exec_summary(ctx))
    parts.append(_md_section_data_overview(ctx))
    parts.append(_md_section_tools(ctx))
    parts.append(_md_section_results(ctx))
    parts.append(_md_section_findings(ctx))
    parts.append(_md_section_implications(ctx))
    parts.append(_md_section_appendix(ctx))
    parts.append(_md_footer(ctx))
    return "\n\n".join(parts)


def _md_header(ctx: Dict[str, Any]) -> str:
    meta = ctx["data_meta"]
    n_models = len(ctx["analysis_results"])
    return f"""# {ctx['title']} — 数据分析报告

> 报告生成时间：{ctx['generated_at']}
> 数据文件：`{meta['file_name']}`
> 分析模型：{n_models} 个　|　数据规模：{meta['record_count']} 条 / {meta['field_count']} 字段
> 数据平台：{ctx['platform']}

---
"""


def _md_toc() -> str:
    return """## 目录

- [1. 执行摘要](#1-执行摘要)
- [2. 数据说明](#2-数据说明)
- [3. 分析工具说明](#3-分析工具说明)
- [4. 分析结果](#4-分析结果)
- [5. 关键发现](#5-关键发现)
- [6. 启示与预测](#6-启示与预测)
- [7. 附录：原始数据预览](#7-附录原始数据预览)
"""


def _md_section_exec_summary(ctx: Dict[str, Any]) -> str:
    summary = ctx.get("executive_summary", "").strip()
    if not summary:
        summary = "（执行摘要将由 LLM 生成；当前 LLM 不可用，请参考第 5 节关键发现与第 6 节启示与预测）"
    return f"""## 1. 执行摘要

{summary}
"""


def _md_section_data_overview(ctx: Dict[str, Any]) -> str:
    meta = ctx["data_meta"]
    info = ctx["crawler_info"]

    lines = ["## 2. 数据说明", ""]
    lines.append(f"- **数据平台**：{ctx['platform']}")
    lines.append(f"- **数据文件**：`{meta['file_name']}`")
    lines.append(f"- **采集方式**：{info.get('crawl_method', '浏览器自动化 (Playwright)')}")
    lines.append(f"- **记录规模**：{meta['record_count']} 条记录，{meta['field_count']} 个字段")

    # 字段表
    lines.append("")
    lines.append("### 字段概览")
    lines.append("")
    lines.append("| 字段 | 类型 | 缺失率 | 非空 | 唯一值 | 示例 |")
    lines.append("|------|------|--------|------|--------|------|")
    for f in meta["fields"]:
        ftype_zh = {"numeric": "数值", "text": "文本", "date": "日期", "other": "其他"}.get(f["type"], f["type"])
        miss_pct = f"{int(f['missing_rate']*100)}%"
        sample = f["sample"][:30].replace("|", "\\|")
        lines.append(f"| `{f['name']}` | {ftype_zh} | {miss_pct} | {f['non_null']} | {f['unique_count']} | {sample} |")

    # 数值字段统计
    numeric_fields = [f for f in meta["fields"] if f["type"] == "numeric"]
    if numeric_fields:
        lines.append("")
        lines.append("### 数值字段分布")
        lines.append("")
        for f in numeric_fields:
            lines.append(f"**`{f['name']}`** (n={f['non_null']})")
            lines.append(
                f"- 范围：min={f.get('min', '?')} / max={f.get('max', '?')}"
                f" / mean={f.get('mean', '?')} / median={f.get('median', '?')}"
            )
            if "p25" in f:
                lines.append(f"- 四分位：P25={f['p25']} / P75={f['p75']}")
            lines.append("")

    # 质量提示
    lines.append("### 数据质量提示")
    lines.append("")
    for issue in meta.get("quality_issues", []):
        lines.append(f"- {issue}")
    lines.append("")
    return "\n".join(lines)


def _md_section_tools(ctx: Dict[str, Any]) -> str:
    lines = ["## 3. 分析工具说明", ""]
    lines.append(f"本次分析调用了 **{len(ctx['analysis_results'])}** 个分析工具，覆盖以下类别：")
    lines.append("")

    used_keys = list(ctx["analysis_results"].keys())
    lines.append("| # | 工具 | 类别 | 适用字段 | 简要说明 |")
    lines.append("|---|------|------|----------|----------|")
    for i, key in enumerate(used_keys, 1):
        meta = next((t for t in ctx["tools_meta"] if t["name"] == key), None)
        if meta:
            cat_zh = _category_zh(meta["category"])
            req = "、".join(meta["required_fields"]) if meta["required_fields"] else "任意"
            lines.append(f"| {i} | `{meta['name']}` | {cat_zh} | {req} | {meta['description']} |")
        else:
            lines.append(f"| {i} | `{key}` | 未知 | - | 自定义分析 |")

    lines.append("")
    return "\n".join(lines)


def _md_section_results(ctx: Dict[str, Any]) -> str:
    lines = ["## 4. 分析结果", ""]
    for i, (key, result) in enumerate(ctx["analysis_results"].items(), 1):
        model_name = result.get("model", key) if isinstance(result, dict) else key
        lines.append(f"### 4.{i} {model_name}")
        lines.append("")
        lines.extend(_render_model_md(key, result))
        lines.append("")
    return "\n".join(lines)


def _render_model_md(key: str, result: Any) -> List[str]:
    if not isinstance(result, dict):
        return [f"```\n{result}\n```"]
    if "error" in result:
        return [f"⚠️ **错误**：{result['error']}"]

    if key == "basic_stats":
        return _md_basic_stats(result)
    elif key == "sentiment":
        return _md_sentiment(result)
    elif key == "word_freq":
        return _md_word_freq(result)
    elif key == "time_series":
        return _md_time_series(result)
    elif key == "theme_extraction":
        return _md_themes(result)
    elif key == "content_category":
        return _md_categories(result)
    elif key == "insight_mining":
        return _md_insights(result)
    elif key == "comment_clustering":
        return _md_clusters(result)
    elif key == "user_activity":
        return _md_user_activity(result)
    elif key == "interaction_network":
        return _md_network(result)

    # 默认：JSON 块
    return ["```json", json.dumps(result, ensure_ascii=False, indent=2, default=str)[:3000], "```"]


def _md_basic_stats(r: Dict) -> List[str]:
    lines = [f"- 总记录数：{r.get('record_count', 0)}", ""]
    for field, info in r.get("fields", {}).items():
        if info.get("type") == "numeric":
            lines.append(f"**{field}** (numeric):")
            lines.append(f"- min={info.get('min', '?')}, max={info.get('max', '?')}, mean={info.get('mean', '?')}, median={info.get('median', '?')}")
        elif info.get("type") == "text":
            lines.append(f"**{field}** (text): 非空 {info.get('non_null', 0)}，唯一 {info.get('unique_count', 0)}")
    return lines


def _md_sentiment(r: Dict) -> List[str]:
    total = r.get("total", 0)
    pos = r.get("positive", 0)
    neg = r.get("negative", 0)
    pos_pct = r.get("positive_pct", 0)
    neg_pct = r.get("negative_pct", 0)
    neu_pct = r.get("neutral_pct", 0)
    lines = [
        f"- 分析条数：{total}",
        f"- 平均情感分：{r.get('avg_score', 0)}",
        f"- 正面：{pos} 条 ({pos_pct}%)",
        f"- 中性：{r.get('neutral', 0)} 条 ({neu_pct}%)",
        f"- 负面：{neg} 条 ({neg_pct}%)",
        "",
        "**情感分布（ASCII 柱状图）**：",
        "",
        "```",
    ]
    bar_w = 40
    pos_w = int(bar_w * pos_pct / 100)
    neg_w = int(bar_w * neg_pct / 100)
    neu_w = bar_w - pos_w - neg_w
    lines.append(f"正面 {pos_pct:5.1f}% |{'█' * pos_w}{'░' * (bar_w - pos_w)}|")
    lines.append(f"中性 {neu_pct:5.1f}% |{'█' * neu_w}{'░' * (bar_w - neu_w)}|")
    lines.append(f"负面 {neg_pct:5.1f}% |{'█' * neg_w}{'░' * (bar_w - neg_w)}|")
    lines.append("```")
    return lines


def _md_word_freq(r: Dict) -> List[str]:
    lines = []
    if r.get("keywords"):
        lines.append("**TF-IDF 关键词**：")
        lines.append("")
        for item in r["keywords"][:15]:
            lines.append(f"- `{item['word']}` (权重 {item.get('weight', 0):.3f})")
        lines.append("")
    if r.get("top_words"):
        lines.append("**高频词汇 Top 30**：")
        lines.append("")
        lines.append("| 排名 | 词汇 | 频次 |")
        lines.append("|------|------|------|")
        for i, (w, c) in enumerate(r["top_words"][:30], 1):
            lines.append(f"| {i} | `{w}` | {c} |")
    return lines


def _md_time_series(r: Dict) -> List[str]:
    td = r.get("time_data", [])
    if not td:
        return ["（无时间序列数据）"]
    lines = [
        "| 日期 | 数量 |",
        "|------|------|",
    ]
    for d in td[-30:]:
        lines.append(f"| {d['date']} | {d['count']} |")
    return lines


def _md_themes(r: Dict) -> List[str]:
    lines = []
    for theme in r.get("themes", []):
        lines.append(f"#### 🏷️ {theme.get('name', '')}")
        if theme.get("description"):
            lines.append(f"{theme['description']}")
        if theme.get("sub_themes"):
            lines.append("")
            lines.append("子主题：" + " / ".join(f"`{st}`" for st in theme["sub_themes"]))
        if theme.get("example_quotes"):
            lines.append("")
            for q in theme["example_quotes"][:2]:
                lines.append(f"> {q}")
        lines.append("")
    return lines


def _md_categories(r: Dict) -> List[str]:
    lines = []
    if r.get("categories"):
        lines.append("**分类类别**：" + "、".join(f"`{c}`" for c in r["categories"]))
        lines.append("")
    if r.get("distribution"):
        lines.append("**分布**：")
        lines.append("")
        lines.append("| 类别 | 数量 |")
        lines.append("|------|------|")
        total = sum(r["distribution"].values()) or 1
        for k, v in r["distribution"].items():
            pct = v / total * 100
            lines.append(f"| {k} | {v} ({pct:.1f}%) |")
    return lines


def _md_insights(r: Dict) -> List[str]:
    lines = []
    for ins in r.get("insights", []):
        tag = ins.get("type", "")
        sig = ins.get("significance", "中")
        lines.append(f"- **[{tag} · 重要度:{sig}]** {ins.get('content', '')}")
        if ins.get("evidence"):
            lines.append(f"  - 证据：{ins['evidence']}")
    return lines


def _md_clusters(r: Dict) -> List[str]:
    lines = [
        f"- 总评论数：{r.get('total_comments', 0)}",
        f"- 已聚类：{r.get('clustered_comments', 0)}",
        f"- 聚类数：{len(r.get('clusters', []))}",
        "",
    ]
    for c in r.get("clusters", [])[:8]:
        lines.append(f"#### 聚类 #{c['id']}: {c.get('label', '')} ({c['size']}条)")
        if c.get("keywords"):
            lines.append("关键词：" + "、".join(f"`{kw}`" for kw in c["keywords"][:5]))
        lines.append("")
    return lines


def _md_user_activity(r: Dict) -> List[str]:
    lines = [
        f"- 用户数：{r.get('total_users', 0)}",
        f"- 总评论数：{r.get('total_comments', 0)}",
        "",
    ]
    if r.get("top_commenters"):
        lines.append("**最活跃用户 Top 10**：")
        lines.append("")
        lines.append("| 用户 | 评论数 | 平均长度 | 获赞 |")
        lines.append("|------|--------|---------|------|")
        for u in r["top_commenters"][:10]:
            lines.append(f"| {u['user']} | {u['comment_count']} | {u['avg_length']} | {u['likes_total']} |")
    return lines


def _md_network(r: Dict) -> List[str]:
    if r.get("note"):
        return [f"_{r['note']}_"]
    lines = [
        f"- 回复关系数：{r.get('total_edges', 0)}",
        f"- 总回复次数：{r.get('total_reply_count', 0)}",
        "",
    ]
    if r.get("top_edges"):
        lines.append("**最频繁回复关系 Top 10**：")
        lines.append("")
        lines.append("| 回复者 | 被回复者 | 次数 |")
        lines.append("|--------|---------|------|")
        for e in r["top_edges"][:10]:
            lines.append(f"| {e['from']} | {e['to']} | {e['count']} |")
    return lines


def _md_section_findings(ctx: Dict[str, Any]) -> str:
    findings = ctx.get("key_findings", [])
    lines = ["## 5. 关键发现", ""]
    if findings:
        for f in findings:
            lines.append(f"- {f}")
    else:
        lines.append("（关键发现将由 LLM 生成；当前 LLM 不可用，请参考各分析工具的原始结果）")
    lines.append("")
    return "\n".join(lines)


def _md_section_implications(ctx: Dict[str, Any]) -> str:
    impl = ctx.get("implications", {})
    lines = ["## 6. 启示与预测", ""]
    suggestions = impl.get("建议", [])
    predictions = impl.get("预测", [])
    if suggestions:
        lines.append("### 建议")
        lines.append("")
        for s in suggestions:
            lines.append(f"- {s}")
        lines.append("")
    if predictions:
        lines.append("### 预测")
        lines.append("")
        for p in predictions:
            lines.append(f"- {p}")
        lines.append("")
    if not suggestions and not predictions:
        lines.append("（启示与预测将由 LLM 生成；当前 LLM 不可用）")
    return "\n".join(lines)


def _md_section_appendix(ctx: Dict[str, Any]) -> str:
    lines = ["## 7. 附录：原始数据预览", ""]
    # 拿原始数据
    try:
        from analysis.report_meta import get_data_preview
        raw_data = _extract_raw_data(ctx["analysis_results"])
        if not raw_data:
            lines.append("（原始数据未在分析结果中保留，无法预览）")
            return "\n".join(lines)
        preview = get_data_preview(raw_data, n=20)
        if preview:
            cols = list(preview[0].keys())[:6]
            lines.append("| " + " | ".join(cols) + " |")
            lines.append("|" + "|".join("---" for _ in cols) + "|")
            for row in preview:
                cells = [str(row.get(c, ""))[:50].replace("|", "\\|") for c in cols]
                lines.append("| " + " | ".join(cells) + " |")
    except Exception as e:
        lines.append(f"（预览生成失败：{e}）")
    return "\n".join(lines)


def _md_footer(ctx: Dict[str, Any]) -> str:
    return f"""---

*报告由 Insight Agent 自动生成 · {ctx['generated_at']} · Powered by DeepSeek*"""


def _category_zh(cat: str) -> str:
    return {
        "quantitative": "定量",
        "qualitative": "定性",
        "text_analysis": "文本",
        "time_series": "时序",
        "visualization": "可视化",
        "advanced": "高级",
    }.get(cat, cat)


# ================================================================
# HTML 拼装
# ================================================================

def _build_html(ctx: Dict[str, Any]) -> str:
    """拼装完整的 HTML 报告"""
    body = "\n".join([
        _html_toc(ctx),
        _html_section_exec_summary(ctx),
        _html_section_data_overview(ctx),
        _html_section_tools(ctx),
        _html_section_results(ctx),
        _html_section_findings(ctx),
        _html_section_implications(ctx),
        _html_section_appendix(ctx),
    ])

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(ctx['title'])} — 数据分析报告</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
{_HTML_CSS}
</style>
</head>
<body>

<div class="header">
  <h1>{html.escape(ctx['title'])}</h1>
  <p>数据分析报告 · {html.escape(ctx['generated_at'])}</p>
  <p class="meta">📁 {html.escape(ctx['data_meta']['file_name'])} · {ctx['data_meta']['record_count']} 条 / {ctx['data_meta']['field_count']} 字段 · {len(ctx['analysis_results'])} 个分析模型</p>
</div>

<nav class="toc" id="toc">
  <div class="toc-title">目录</div>
  <ol>
    <li><a href="#s1">执行摘要</a></li>
    <li><a href="#s2">数据说明</a></li>
    <li><a href="#s3">分析工具说明</a></li>
    <li><a href="#s4">分析结果</a></li>
    <li><a href="#s5">关键发现</a></li>
    <li><a href="#s6">启示与预测</a></li>
    <li><a href="#s7">附录：原始数据预览</a></li>
  </ol>
</nav>

<div class="container">
{body}
</div>

<div class="footer">
  <p>报告由 Insight Agent 自动生成 · Powered by DeepSeek · {html.escape(ctx['generated_at'])}</p>
</div>

</body>
</html>
"""


_HTML_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', 'Noto Sans SC', sans-serif; background: #f5f7fa; color: #2c3e50; line-height: 1.7; }
.header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); color: white; padding: 50px 20px 30px; text-align: center; }
.header h1 { font-size: 30px; margin-bottom: 12px; font-weight: 700; }
.header p { opacity: 0.85; font-size: 14px; }
.header .meta { opacity: 0.7; font-size: 12px; margin-top: 8px; }
.toc { position: sticky; top: 0; background: white; border-bottom: 1px solid #e8ecf1; padding: 12px 20px; z-index: 100; box-shadow: 0 1px 4px rgba(0,0,0,0.05); }
.toc-title { font-size: 12px; color: #888; margin-bottom: 6px; }
.toc ol { list-style: none; display: flex; flex-wrap: wrap; gap: 8px; }
.toc li a { color: #0f3460; text-decoration: none; padding: 4px 10px; border-radius: 12px; background: #f0f2f5; font-size: 13px; transition: all 0.2s; }
.toc li a:hover { background: #0f3460; color: white; }
.container { max-width: 1000px; margin: 0 auto; padding: 20px; }
.section { background: white; border-radius: 12px; padding: 28px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); scroll-margin-top: 80px; }
.section h2 { color: #1a1a2e; margin-bottom: 16px; font-size: 22px; border-bottom: 2px solid #e8ecf1; padding-bottom: 10px; }
.section h3 { color: #0f3460; margin: 20px 0 10px; font-size: 17px; }
.section h4 { color: #2c3e50; margin: 14px 0 6px; font-size: 15px; }
.overview-table { width: 100%; border-collapse: collapse; margin: 12px 0; }
.overview-table td, .overview-table th { padding: 10px 14px; border-bottom: 1px solid #eef0f3; text-align: left; }
.overview-table th { background: #f8f9fc; font-weight: 600; }
.overview-table td:first-child, .overview-table th:first-child { font-weight: 600; color: #555; width: 140px; }
.overview-table td.mono { font-family: 'JetBrains Mono', 'Menlo', monospace; font-size: 13px; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin: 16px 0; }
.stat-card { background: #f8f9fc; border-radius: 8px; padding: 16px; text-align: center; border: 1px solid #e8ecf1; }
.stat-card .value { font-size: 26px; font-weight: 700; color: #0f3460; }
.stat-card .label { font-size: 12px; color: #888; margin-top: 4px; }
.emotion-bar { display: flex; height: 30px; border-radius: 6px; overflow: hidden; margin: 16px 0; }
.emotion-bar .pos { background: #4CAF50; }
.emotion-bar .neu { background: #FF9800; }
.emotion-bar .neg { background: #f44336; }
.emotion-legend { display: flex; gap: 20px; margin-top: 8px; flex-wrap: wrap; }
.emotion-legend span { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.emotion-legend .dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
table.data-table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; }
table.data-table th { background: #f0f2f5; padding: 10px 12px; text-align: left; font-weight: 600; }
table.data-table td { padding: 8px 12px; border-bottom: 1px solid #eef0f3; }
.theme-card { background: #f8f9fc; border-left: 4px solid #0f3460; padding: 16px; margin: 12px 0; border-radius: 0 8px 8px 0; }
.theme-card .theme-name { font-size: 16px; font-weight: 600; color: #0f3460; margin-bottom: 6px; }
.theme-card .sub-themes { margin-top: 8px; }
.theme-card .sub-themes span { display: inline-block; background: #e3e8f0; padding: 2px 10px; border-radius: 12px; font-size: 12px; margin: 2px 4px; }
.insight-card { background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 14px 16px; margin: 10px 0; border-left: 4px solid #1565c0; }
.insight-card.risk { border-left-color: #c62828; }
.insight-card.suggest { border-left-color: #2e7d32; }
.insight-card.neutral { border-left-color: #e65100; }
.insight-card .tag { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; margin-right: 8px; }
.tag-attitude { background: #e3f2fd; color: #1565c0; }
.tag-problem { background: #fce4ec; color: #c62828; }
.tag-suggestion { background: #e8f5e9; color: #2e7d32; }
.tag-need { background: #fff3e0; color: #e65100; }
.finding-card { background: linear-gradient(90deg, #f8f9fc 0%, #ffffff 100%); border: 1px solid #e8ecf1; border-radius: 8px; padding: 14px 18px; margin: 10px 0; font-size: 14px; }
.implication-suggestion { background: #f1f8e9; border-left: 4px solid #2e7d32; padding: 12px 16px; margin: 8px 0; border-radius: 0 8px 8px 0; }
.implication-prediction { background: #e3f2fd; border-left: 4px solid #1565c0; padding: 12px 16px; margin: 8px 0; border-radius: 0 8px 8px 0; }
.implication-suggestion strong, .implication-prediction strong { color: #0f3460; }
.chart-container { width: 100%; max-width: 700px; margin: 20px auto; }
.chart-container canvas { max-height: 320px; }
.keyword-cloud { display: flex; flex-wrap: wrap; gap: 8px; padding: 16px; }
.keyword-tag { padding: 4px 14px; border-radius: 16px; font-size: 13px; }
.footer { text-align: center; padding: 30px 20px; color: #999; font-size: 12px; }
code { background: #f0f2f5; padding: 1px 6px; border-radius: 3px; font-family: 'JetBrains Mono', 'Menlo', monospace; font-size: 13px; }
pre { background: #1e1e2e; color: #f8f8f2; padding: 12px 16px; border-radius: 6px; overflow-x: auto; font-size: 12px; }
.quality-issue { background: #fff3e0; border-left: 4px solid #e65100; padding: 8px 14px; margin: 6px 0; border-radius: 0 6px 6px 0; font-size: 13px; }
.muted { color: #888; font-size: 12px; }
@media print {
  body { background: white; }
  .toc { position: static; box-shadow: none; }
  .section { box-shadow: none; border: 1px solid #e0e0e0; page-break-inside: avoid; }
  .header { background: #1a1a2e !important; -webkit-print-color-adjust: exact; }
  .insight-card, .implication-suggestion, .implication-prediction { page-break-inside: avoid; }
}
"""


def _html_toc(ctx: Dict[str, Any]) -> str:
    """目录已经在 header 后 render 一份 sticky nav，这里是正文里的占位"""
    return ""


def _html_section_exec_summary(ctx: Dict[str, Any]) -> str:
    summary = ctx.get("executive_summary", "").strip()
    if not summary:
        summary = '<p class="muted">（执行摘要将由 LLM 生成；当前 LLM 不可用，请参考第 5 节关键发现）</p>'
    summary_html = _md_to_html(summary)
    return f"""
<div class="section" id="s1">
  <h2>1. 执行摘要</h2>
  {summary_html}
</div>
"""


def _html_section_data_overview(ctx: Dict[str, Any]) -> str:
    meta = ctx["data_meta"]
    info = ctx["crawler_info"]

    rows = []
    for f in meta["fields"]:
        ftype_zh = {"numeric": "数值", "text": "文本", "date": "日期", "other": "其他"}.get(f["type"], f["type"])
        sample = html.escape(f["sample"][:30])
        rows.append(
            f"<tr><td><code>{html.escape(f['name'])}</code></td>"
            f"<td>{ftype_zh}</td>"
            f"<td>{int(f['missing_rate']*100)}%</td>"
            f"<td>{f['non_null']}</td>"
            f"<td>{f['unique_count']}</td>"
            f"<td class='mono'>{sample}</td></tr>"
        )

    quality_html = "\n".join(
        f'<div class="quality-issue">⚠️ {html.escape(issue)}</div>'
        for issue in meta.get("quality_issues", [])
    )

    return f"""
<div class="section" id="s2">
  <h2>2. 数据说明</h2>
  <table class="overview-table">
    <tr><td>数据平台</td><td>{html.escape(ctx['platform'])}</td></tr>
    <tr><td>数据文件</td><td class="mono">{html.escape(meta['file_name'])}</td></tr>
    <tr><td>采集方式</td><td>{html.escape(info.get('crawl_method', '浏览器自动化 (Playwright)'))}</td></tr>
    <tr><td>记录规模</td><td>{meta['record_count']} 条 / {meta['field_count']} 字段</td></tr>
  </table>
  <h3>字段概览</h3>
  <table class="data-table">
    <tr><th>字段</th><th>类型</th><th>缺失率</th><th>非空</th><th>唯一值</th><th>示例</th></tr>
    {''.join(rows)}
  </table>
  <h3>数据质量提示</h3>
  {quality_html}
</div>
"""


def _html_section_tools(ctx: Dict[str, Any]) -> str:
    rows = []
    for i, key in enumerate(ctx["analysis_results"].keys(), 1):
        meta = next((t for t in ctx["tools_meta"] if t["name"] == key), None)
        if meta:
            cat_zh = _category_zh(meta["category"])
            req = "、".join(meta["required_fields"]) if meta["required_fields"] else "任意"
            rows.append(
                f"<tr><td>{i}</td><td><code>{html.escape(meta['name'])}</code></td>"
                f"<td>{cat_zh}</td><td>{html.escape(req)}</td>"
                f"<td>{html.escape(meta['description'])}</td></tr>"
            )
        else:
            rows.append(
                f"<tr><td>{i}</td><td><code>{html.escape(key)}</code></td>"
                f"<td>未知</td><td>-</td><td>自定义分析</td></tr>"
            )

    return f"""
<div class="section" id="s3">
  <h2>3. 分析工具说明</h2>
  <p>本次分析调用了 <strong>{len(ctx['analysis_results'])}</strong> 个分析工具。</p>
  <table class="data-table">
    <tr><th>#</th><th>工具</th><th>类别</th><th>适用字段</th><th>简要说明</th></tr>
    {''.join(rows)}
  </table>
</div>
"""


def _html_section_results(ctx: Dict[str, Any]) -> str:
    body = ['<div class="section" id="s4"><h2>4. 分析结果</h2>']
    for i, (key, result) in enumerate(ctx["analysis_results"].items(), 1):
        model_name = result.get("model", key) if isinstance(result, dict) else key
        body.append(f'<h3>4.{i} {html.escape(model_name)}</h3>')
        body.append(_render_model_html(key, result))
    body.append('</div>')
    return "\n".join(body)


def _render_model_html(key: str, result: Any) -> str:
    if not isinstance(result, dict):
        return f"<pre>{html.escape(str(result))}</pre>"
    if "error" in result:
        return f'<p style="color:#e65100;">⚠️ {html.escape(result["error"])}</p>'

    if key == "basic_stats":
        return _html_basic_stats(result)
    elif key == "sentiment":
        return _html_sentiment(result)
    elif key == "word_freq":
        return _html_word_freq(result)
    elif key == "time_series":
        return _html_time_series(result)
    elif key == "theme_extraction":
        return _html_themes(result)
    elif key == "content_category":
        return _html_categories(result)
    elif key == "insight_mining":
        return _html_insights(result)
    elif key == "comment_clustering":
        return _html_clusters(result)
    elif key == "user_activity":
        return _html_user_activity(result)
    elif key == "interaction_network":
        return _html_network(result)
    return f"<pre>{html.escape(json.dumps(result, ensure_ascii=False, indent=2, default=str)[:3000])}</pre>"


def _html_basic_stats(r: Dict) -> str:
    rows = [f"<tr><td>总记录数</td><td>{r.get('record_count', 0)}</td></tr>"]
    for field, info in r.get("fields", {}).items():
        if info.get("type") == "numeric":
            rows.append(
                f"<tr><td><code>{html.escape(field)}</code></td>"
                f"<td>min={info.get('min', '?')}, max={info.get('max', '?')}, "
                f"mean={info.get('mean', '?')}, median={info.get('median', '?')}</td></tr>"
            )
    return f'<table class="overview-table">{"".join(rows)}</table>'


def _html_sentiment(r: Dict) -> str:
    pos_pct = r.get("positive_pct", 0)
    neu_pct = r.get("neutral_pct", 0)
    neg_pct = r.get("negative_pct", 0)
    total = r.get("total", 0)
    return f"""
<div class="stats-grid">
  <div class="stat-card"><div class="value">{total}</div><div class="label">分析条数</div></div>
  <div class="stat-card"><div class="value">{r.get('avg_score', 0)}</div><div class="label">平均情感分</div></div>
  <div class="stat-card"><div class="value" style="color:#4CAF50;">{r.get('positive', 0)}</div><div class="label">正面</div></div>
  <div class="stat-card"><div class="value" style="color:#f44336;">{r.get('negative', 0)}</div><div class="label">负面</div></div>
</div>
<div class="emotion-bar">
  <div class="pos" style="width:{pos_pct}%"></div>
  <div class="neu" style="width:{neu_pct}%"></div>
  <div class="neg" style="width:{neg_pct}%"></div>
</div>
<div class="emotion-legend">
  <span><span class="dot" style="background:#4CAF50;"></span>正面 {pos_pct}%</span>
  <span><span class="dot" style="background:#FF9800;"></span>中性 {neu_pct}%</span>
  <span><span class="dot" style="background:#f44336;"></span>负面 {neg_pct}%</span>
</div>
"""


def _html_word_freq(r: Dict) -> str:
    parts = []
    if r.get("keywords"):
        tags = []
        for item in r["keywords"][:20]:
            size = min(20, max(10, int(item.get("weight", 1) * 15)))
            color = f"hsl({220 + (item.get('weight', 0.5) * 80):.0f}, 60%, 50%)"
            tags.append(
                f'<span class="keyword-tag" style="font-size:{size}px;background:{color};color:white;">'
                f'{html.escape(item["word"])}</span>'
            )
        parts.append(f'<h3>TF-IDF 关键词</h3><div class="keyword-cloud">{"".join(tags)}</div>')
    if r.get("top_words"):
        rows = "".join(
            f"<tr><td>{html.escape(w)}</td><td>{c}</td></tr>"
            for w, c in r["top_words"][:30]
        )
        parts.append(
            f'<h3>高频词汇 Top 30</h3>'
            f'<table class="data-table"><tr><th>词汇</th><th>频次</th></tr>{rows}</table>'
        )
    return "".join(parts)


def _html_time_series(r: Dict) -> str:
    td = r.get("time_data", [])
    if not td:
        return "<p class='muted'>（无时间序列数据）</p>"
    labels = json.dumps([d["date"] for d in td])
    values = json.dumps([d["count"] for d in td])
    rows = "".join(f"<tr><td>{d['date']}</td><td>{d['count']}</td></tr>" for d in td[-20:])
    return f"""
<div class="chart-container"><canvas id="timeChart_{abs(hash(str(td)))%10000}"></canvas></div>
<table class="data-table"><tr><th>日期</th><th>数量</th></tr>{rows}</table>
<script>
new Chart(document.querySelector('[id^="timeChart_"]'), {{
  type: 'line',
  data: {{
    labels: {labels},
    datasets: [{{
      label: '数据量',
      data: {values},
      borderColor: '#0f3460',
      backgroundColor: 'rgba(15, 52, 96, 0.1)',
      fill: true,
      tension: 0.3,
    }}]
  }},
  options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }} }}
}});
</script>
"""


def _html_themes(r: Dict) -> str:
    parts = []
    for theme in r.get("themes", []):
        sub_html = "".join(f"<span>{html.escape(st)}</span>" for st in theme.get("sub_themes", []))
        quotes_html = "".join(
            f'<p style="margin-top:6px;color:#888;font-size:12px;">📌 {html.escape(q)}</p>'
            for q in theme.get("example_quotes", [])[:2]
        )
        parts.append(f"""
<div class="theme-card">
  <div class="theme-name">{html.escape(theme.get('name', ''))}</div>
  <p>{html.escape(theme.get('description', ''))}</p>
  <div class="sub-themes">{sub_html}</div>
  {quotes_html}
</div>""")
    return "".join(parts)


def _html_categories(r: Dict) -> str:
    parts = []
    if r.get("categories"):
        items = "".join(f"<li>{html.escape(c)}</li>" for c in r["categories"])
        parts.append(f"<h3>分类类别</h3><ul>{items}</ul>")
    if r.get("distribution"):
        labels = json.dumps(list(r["distribution"].keys()))
        values = json.dumps(list(r["distribution"].values()))
        parts.append(f"""
<div class="chart-container"><canvas id="catChart_{abs(hash(str(r['distribution'])))%10000}"></canvas></div>
<script>
new Chart(document.querySelector('[id^="catChart_"]'), {{
  type: 'doughnut',
  data: {{
    labels: {labels},
    datasets: [{{
      data: {values},
      backgroundColor: ['#0f3460','#16213e','#1a1a2e','#e94560','#533483','#3498db','#2ecc71','#f39c12'],
    }}]
  }},
  options: {{ responsive: true }}
}});
</script>""")
    return "".join(parts)


def _html_insights(r: Dict) -> str:
    parts = []
    for ins in r.get("insights", []):
        t = ins.get("type", "")
        tag_class = {"态度": "tag-attitude", "问题": "tag-problem", "建议": "tag-suggestion", "需求": "tag-need"}.get(t, "tag-attitude")
        sig = ins.get("significance", "中")
        parts.append(f"""
<div class="insight-card">
  <span class="tag {tag_class}">{html.escape(t)}</span>
  <span class="muted">重要度: {html.escape(sig)}</span>
  <p style="margin-top:8px;">{html.escape(ins.get('content', ''))}</p>
  <p class="muted" style="margin-top:4px;">📌 {html.escape(ins.get('evidence', ''))}</p>
</div>""")
    return "".join(parts)


def _html_clusters(r: Dict) -> str:
    parts = [f"""
<div class="stats-grid">
  <div class="stat-card"><div class="value">{r.get('total_comments', 0)}</div><div class="label">总评论数</div></div>
  <div class="stat-card"><div class="value">{r.get('clustered_comments', 0)}</div><div class="label">已聚类</div></div>
  <div class="stat-card"><div class="value">{r.get('noise_comments', 0)}</div><div class="label">独立评论</div></div>
  <div class="stat-card"><div class="value">{len(r.get('clusters', []))}</div><div class="label">聚类数</div></div>
</div>"""]
    for c in r.get("clusters", [])[:10]:
        keywords = " / ".join(html.escape(kw) for kw in c.get("keywords", [])[:5])
        examples = "".join(f'<p class="muted" style="margin-top:4px;">💬 {html.escape(ex)}</p>' for ex in c.get("examples", []))
        parts.append(f"""
<div class="theme-card">
  <div class="theme-name">聚类 #{c['id']}: {html.escape(c.get('label', ''))} ({c['size']}条)</div>
  <div class="sub-themes">{''.join(f'<span>{html.escape(kw)}</span>' for kw in c.get('keywords', []))}</div>
  {examples}
</div>""")
    return "".join(parts)


def _html_user_activity(r: Dict) -> str:
    parts = [f"""
<div class="stats-grid">
  <div class="stat-card"><div class="value">{r.get('total_users', 0)}</div><div class="label">用户数</div></div>
  <div class="stat-card"><div class="value">{r.get('total_comments', 0)}</div><div class="label">总评论数</div></div>
</div>"""]
    dist = r.get("activity_distribution", {})
    if dist:
        labels = json.dumps(list(dist.keys()))
        values = json.dumps(list(dist.values()))
        parts.append(f"""
<div class="chart-container"><canvas id="activityChart_{abs(hash(str(dist)))%10000}"></canvas></div>
<script>
new Chart(document.querySelector('[id^="activityChart_"]'), {{
  type: 'pie',
  data: {{
    labels: {labels},
    datasets: [{{ data: {values}, backgroundColor: ['#4CAF50','#FF9800','#2196F3','#f44336'] }}]
  }},
  options: {{ responsive: true, plugins: {{ title: {{ display: true, text: '用户活跃度分布' }} }} }}
}});
</script>""")
    if r.get("top_commenters"):
        rows = "".join(
            f"<tr><td>{html.escape(u['user'])}</td><td>{u['comment_count']}</td><td>{u['avg_length']}</td><td>{u['likes_total']}</td></tr>"
            for u in r["top_commenters"][:10]
        )
        parts.append(
            f'<h3>🏆 最活跃用户</h3>'
            f'<table class="data-table"><tr><th>用户</th><th>评论数</th><th>平均长度</th><th>获赞</th></tr>{rows}</table>'
        )
    return "".join(parts)


def _html_network(r: Dict) -> str:
    if r.get("note"):
        return f'<p class="muted">{html.escape(r["note"])}</p>'
    parts = [f"""
<div class="stats-grid">
  <div class="stat-card"><div class="value">{r.get('total_edges', 0)}</div><div class="label">回复关系数</div></div>
  <div class="stat-card"><div class="value">{r.get('total_reply_count', 0)}</div><div class="label">总回复次数</div></div>
</div>"""]
    if r.get("top_edges"):
        rows = "".join(
            f"<tr><td>{html.escape(e['from'])}</td><td>{html.escape(e['to'])}</td><td>{e['count']}</td></tr>"
            for e in r["top_edges"][:10]
        )
        parts.append(
            f'<h3>🔗 最频繁回复关系 Top 10</h3>'
            f'<table class="data-table"><tr><th>回复者</th><th>被回复者</th><th>次数</th></tr>{rows}</table>'
        )
    return "".join(parts)


def _html_section_findings(ctx: Dict[str, Any]) -> str:
    findings = ctx.get("key_findings", [])
    if not findings:
        body = '<p class="muted">（关键发现将由 LLM 生成；当前 LLM 不可用）</p>'
    else:
        body = "".join(f'<div class="finding-card">{html.escape(f)}</div>' for f in findings)
    return f"""
<div class="section" id="s5">
  <h2>5. 关键发现</h2>
  {body}
</div>
"""


def _html_section_implications(ctx: Dict[str, Any]) -> str:
    impl = ctx.get("implications", {})
    suggestions = impl.get("建议", [])
    predictions = impl.get("预测", [])
    s_html = "".join(f'<div class="implication-suggestion">💡 <strong>建议</strong>　{html.escape(s)}</div>' for s in suggestions)
    p_html = "".join(f'<div class="implication-prediction">🔮 <strong>预测</strong>　{html.escape(p)}</div>' for p in predictions)
    if not s_html and not p_html:
        s_html = '<p class="muted">（启示与预测将由 LLM 生成；当前 LLM 不可用）</p>'
    return f"""
<div class="section" id="s6">
  <h2>6. 启示与预测</h2>
  <h3>建议</h3>
  {s_html}
  <h3>预测</h3>
  {p_html}
</div>
"""


def _html_section_appendix(ctx: Dict[str, Any]) -> str:
    try:
        from analysis.report_meta import get_data_preview
        raw_data = _extract_raw_data(ctx["analysis_results"])
        if not raw_data:
            body = '<p class="muted">（原始数据未在分析结果中保留，无法预览）</p>'
        else:
            preview = get_data_preview(raw_data, n=20)
            if not preview:
                body = '<p class="muted">（无预览数据）</p>'
            else:
                cols = list(preview[0].keys())[:6]
                header = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
                rows = "".join(
                    "<tr>" + "".join(f"<td>{html.escape(str(row.get(c, ''))[:50])}</td>" for c in cols) + "</tr>"
                    for row in preview
                )
                body = f'<table class="data-table"><tr>{header}</tr>{rows}</table>'
    except Exception as e:
        body = f'<p class="muted">（预览生成失败：{html.escape(str(e))}）</p>'

    return f"""
<div class="section" id="s7">
  <h2>7. 附录：原始数据预览</h2>
  {body}
</div>
"""


def _md_to_html(md_text: str) -> str:
    """把 Markdown 文本转简单 HTML（仅本项目需要的子集）

    关键：用占位符保护 <strong> / <code> 标签不被 html.escape 转义。
    """
    lines = md_text.split("\n")
    html_parts = []
    in_para = False

    for line in lines:
        raw_line = line.rstrip()
        if not raw_line.strip():
            if in_para:
                html_parts.append("</p>")
                in_para = False
            continue
        # 标题（最优先）
        m = re.match(r'^(#{1,6})\s+(.+)$', raw_line)
        if m:
            if in_para:
                html_parts.append("</p>")
                in_para = False
            level = len(m.group(1))
            html_parts.append(f"<h{level+2}>{html.escape(m.group(2))}</h{level+2}>")
            continue
        # 占位符保护 <strong>/<code>
        line = raw_line
        line = re.sub(r'\*\*(.+?)\*\*', lambda m: '\x00S\x00' + m.group(1) + '\x00/S\x00', line)
        line = re.sub(r'`([^`]+)`', lambda m: '\x00C\x00' + m.group(1) + '\x00/C\x00', line)
        line = html.escape(line)
        line = line.replace('\x00S\x00', '<strong>').replace('\x00/S\x00', '</strong>')
        line = line.replace('\x00C\x00', '<code>').replace('\x00/C\x00', '</code>')

        if not in_para:
            html_parts.append("<p>")
            in_para = True
        else:
            html_parts.append("<br>")
        html_parts.append(line)

    if in_para:
        html_parts.append("</p>")
    return "\n".join(html_parts)
