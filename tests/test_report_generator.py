"""报告生成器单元测试

不需要真实爬数据、不需要 LLM API；纯逻辑验证：
- 两种格式（.md / .html）都生成
- 五段式结构完整（执行摘要 / 数据说明 / 工具说明 / 分析结果 / 关键发现 / 启示与预测 / 附录）
- LLM 不可用时走降级版（用 llm_synthesize=False）
- 字段表正确填充，缺失率正确
- 数值字段四分位正确
- 转义安全（HTML/Markdown 不会破）
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main

# 让测试能从项目根 import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from report.generator import (
    generate_report,
    generate_html_from_markdown,
    _md_to_html,
    _simple_md_to_html,
)
from analysis.report_meta import build_data_meta, get_data_preview


# ---- 测试数据 ----

SAMPLE_DATA = [
    {"content": "这个产品非常好用", "score": 85, "author": "用户A", "date": "2026-05-30"},
    {"content": "体验很差，物流太慢", "score": 30, "author": "用户B", "date": "2026-05-31"},
    {"content": "还可以", "score": 60, "author": "用户C", "date": "2026-06-01"},
    {"content": "非常好", "score": 90, "author": "用户A", "date": "2026-06-01"},
    {"content": "不满意", "score": None, "author": "用户D", "date": "2026-06-02"},
    {"content": "挺不错 | 表格测试", "score": 75, "author": "用户E", "date": "2026-06-02"},
    {"content": "**粗体测试**", "score": 80, "author": "用户F", "date": "2026-06-02"},
]

SAMPLE_RESULTS = {
    "basic_stats": {
        "model": "基础统计",
        "record_count": 7,
        "fields": {
            "content": {"type": "text", "non_null": 7, "unique_count": 7, "avg_length": 8.5},
            "score": {
                "type": "numeric",
                "non_null": 6, "min": 30, "max": 90,
                "mean": 70.0, "median": 77.5, "p25": 60, "p75": 85,
            },
            "author": {"type": "text", "non_null": 7, "unique_count": 6},
        },
        "_raw_data": SAMPLE_DATA,           # 让 _extract_raw_data 拿得到
        "_data_fields": list(SAMPLE_DATA[0].keys()),
    },
    "sentiment": {
        "model": "情感分析",
        "total": 7,
        "positive": 4, "negative": 2, "neutral": 1,
        "positive_pct": 57.1, "negative_pct": 28.6, "neutral_pct": 14.3,
        "avg_score": 0.62,
    },
    "word_freq": {
        "model": "词频统计",
        "top_words": [("产品", 2), ("不错", 2), ("好", 2), ("体验", 1)],
        "keywords": [{"word": "产品", "weight": 0.8}, {"word": "体验", "weight": 0.5}],
    },
    "insight_mining": {
        "model": "观点挖掘",
        "insights": [
            {"type": "态度", "content": "整体偏正面", "evidence": "正面 57%", "significance": "高"},
            {"type": "问题", "content": "物流被诟病", "evidence": "差评关键词", "significance": "中"},
        ],
    },
}


class TestReportMeta(TestCase):
    """report_meta.py 的单元测试"""

    def test_build_data_meta_basic(self):
        meta = build_data_meta(SAMPLE_DATA, Path("test.csv"))
        self.assertEqual(meta["file_name"], "test.csv")
        self.assertEqual(meta["record_count"], 7)
        self.assertEqual(meta["field_count"], 4)

    def test_field_types_detected(self):
        meta = build_data_meta(SAMPLE_DATA)
        field_types = {f["name"]: f["type"] for f in meta["fields"]}
        self.assertEqual(field_types["content"], "text")
        self.assertEqual(field_types["score"], "numeric")
        self.assertEqual(field_types["author"], "text")

    def test_missing_rate(self):
        meta = build_data_meta(SAMPLE_DATA)
        score_field = next(f for f in meta["fields"] if f["name"] == "score")
        # 1/7 ≈ 0.143
        self.assertAlmostEqual(score_field["missing_rate"], 1/7, places=3)

    def test_numeric_quartiles(self):
        meta = build_data_meta(SAMPLE_DATA)
        score = next(f for f in meta["fields"] if f["name"] == "score")
        # score 非空值: [85, 30, 60, 90, 75, 80] (排除 None)
        self.assertEqual(score["min"], 30)
        self.assertEqual(score["max"], 90)
        self.assertEqual(score["mean"], 70.0)
        self.assertIn("p25", score)
        self.assertIn("p75", score)

    def test_text_top_values(self):
        meta = build_data_meta(SAMPLE_DATA)
        content = next(f for f in meta["fields"] if f["name"] == "content")
        # "非常好" 出现 1 次，不会有 top_values
        self.assertIn("top_values", content)

    def test_quality_issues_for_missing(self):
        # 造一个缺失率高的
        data = [{"x": None, "y": 1}] * 5 + [{"x": 1, "y": 1}]
        meta = build_data_meta(data)
        issues = " ".join(meta["quality_issues"])
        self.assertIn("缺失率", issues)

    def test_empty_data(self):
        meta = build_data_meta([])
        self.assertEqual(meta["record_count"], 0)
        self.assertIn("数据为空", meta["quality_issues"][0])

    def test_data_preview_truncates(self):
        data = [{"text": "x" * 100}] * 20
        preview = get_data_preview(data, n=5)
        self.assertEqual(len(preview), 5)
        # 截断到 50 + "..."
        self.assertTrue(preview[0]["text"].endswith("..."))


class TestGenerateReport(TestCase):
    """generate_report 的集成测试（不调 LLM）"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.data_file = self.tmp_path / "test.csv"
        self.data_file.write_text(
            "content,score,author,date\n" +
            "\n".join(f'"{r["content"]}",{r["score"]},{r["author"]},{r["date"]}' for r in SAMPLE_DATA),
            encoding="utf-8",
        )
        self.crawler_info = {
            "platform": "知乎",
            "name": "test",
            "crawl_method": "Playwright 浏览器自动化",
        }
        self.conversation = [
            {"role": "user", "content": "做情感分析"},
            {"role": "assistant", "content": "好的..."},
        ]

    def tearDown(self):
        self.tmp.cleanup()

    def test_returns_dict_with_three_paths(self):
        # 跑全流程；不调 LLM
        result = generate_report(
            self.crawler_info, SAMPLE_RESULTS, self.data_file, self.tmp_path,
            conversation=self.conversation,
            llm_synthesize=False,
        )
        self.assertIn("md", result)
        self.assertIn("html", result)
        self.assertIn("qa_json", result)
        for p in result.values():
            self.assertTrue(p.exists(), f"{p} should exist")

    def test_markdown_has_seven_sections(self):
        result = generate_report(
            self.crawler_info, SAMPLE_RESULTS, self.data_file, self.tmp_path,
            llm_synthesize=False,
        )
        md = result["md"].read_text(encoding="utf-8")
        for n, title in enumerate([
            "## 1. 执行摘要",
            "## 2. 数据说明",
            "## 3. 分析工具说明",
            "## 4. 分析结果",
            "## 5. 关键发现",
            "## 6. 启示与预测",
            "## 7. 附录：原始数据预览",
        ], 1):
            self.assertIn(title, md, f"section {n} missing")

    def test_html_has_seven_sections(self):
        result = generate_report(
            self.crawler_info, SAMPLE_RESULTS, self.data_file, self.tmp_path,
            llm_synthesize=False,
        )
        html_text = result["html"].read_text(encoding="utf-8")
        for sid in ["s1", "s2", "s3", "s4", "s5", "s6", "s7"]:
            self.assertIn(f'id="{sid}"', html_text, f"id={sid} missing")

    def test_markdown_toc_has_links(self):
        result = generate_report(
            self.crawler_info, SAMPLE_RESULTS, self.data_file, self.tmp_path,
            llm_synthesize=False,
        )
        md = result["md"].read_text(encoding="utf-8")
        self.assertIn("[1. 执行摘要](#1-执行摘要)", md)
        self.assertIn("[7. 附录：原始数据预览](#7-附录原始数据预览)", md)

    def test_html_contains_chart_js(self):
        result = generate_report(
            self.crawler_info, SAMPLE_RESULTS, self.data_file, self.tmp_path,
            llm_synthesize=False,
        )
        html_text = result["html"].read_text(encoding="utf-8")
        # script tag 引用 chart.js
        self.assertIn("chart.js", html_text.lower())
        # word_freq 关键词云 / sentiment bar 已经在 body 里
        self.assertIn("emotion-bar", html_text)

    def test_html_contains_toc_sticky(self):
        result = generate_report(
            self.crawler_info, SAMPLE_RESULTS, self.data_file, self.tmp_path,
            llm_synthesize=False,
        )
        html_text = result["html"].read_text(encoding="utf-8")
        self.assertIn('class="toc"', html_text)
        # sticky 样式
        self.assertIn("position: sticky", html_text)

    def test_html_has_print_styles(self):
        result = generate_report(
            self.crawler_info, SAMPLE_RESULTS, self.data_file, self.tmp_path,
            llm_synthesize=False,
        )
        html_text = result["html"].read_text(encoding="utf-8")
        self.assertIn("@media print", html_text)

    def test_field_table_appears(self):
        result = generate_report(
            self.crawler_info, SAMPLE_RESULTS, self.data_file, self.tmp_path,
            llm_synthesize=False,
        )
        md = result["md"].read_text(encoding="utf-8")
        self.assertIn("| 字段 | 类型 | 缺失率 |", md)
        self.assertIn("`content`", md)
        self.assertIn("`score`", md)

    def test_data_meta_auto_generated(self):
        result = generate_report(
            self.crawler_info, SAMPLE_RESULTS, self.data_file, self.tmp_path,
            llm_synthesize=False,
        )
        # qa.json 应包含 data_meta
        qa = json.loads(result["qa_json"].read_text(encoding="utf-8"))
        self.assertIn("data_meta", qa)
        self.assertEqual(qa["data_meta"]["record_count"], 7)
        self.assertEqual(qa["data_meta"]["field_count"], 4)

    def test_conversation_kept_in_qa_json(self):
        result = generate_report(
            self.crawler_info, SAMPLE_RESULTS, self.data_file, self.tmp_path,
            conversation=self.conversation,
            llm_synthesize=False,
        )
        qa = json.loads(result["qa_json"].read_text(encoding="utf-8"))
        self.assertIn("conversation", qa)
        self.assertEqual(len(qa["conversation"]), 2)

    def test_fallback_summary_used_when_no_llm(self):
        # llm_synthesize=False 时，三段 LLM 都用降级模板
        result = generate_report(
            self.crawler_info, SAMPLE_RESULTS, self.data_file, self.tmp_path,
            llm_synthesize=False,
        )
        md = result["md"].read_text(encoding="utf-8")
        # 降级摘要里至少有 "本次分析对象为"
        self.assertIn("本次分析对象为", md)
        # 降级关键发现会引用 sentiment 的数据
        self.assertIn("57.1", md)  # 正面率

    def test_safety_escape_for_pipe_in_value(self):
        # 含 | 的字段值应被转义成 \| 以不破坏 Markdown 表格
        data_with_pipes = [
            {"text": "a|b|c", "n": 1},
            {"text": "ok|not ok", "n": 2},
        ]
        with tempfile.TemporaryDirectory() as t:
            data_file = Path(t) / "x.csv"
            data_file.write_text("text,n\n\"a|b|c\",1\n", encoding="utf-8")
            results = {
                "basic_stats": {
                    "model": "基础统计",
                    "record_count": 2,
                    "fields": {"text": {"type": "text"}, "n": {"type": "numeric", "min": 1, "max": 2}},
                    "_raw_data": data_with_pipes,
                    "_data_fields": ["text", "n"],
                },
            }
            result = generate_report(
                {"platform": "test", "name": "x"},
                results, data_file, Path(t),
                llm_synthesize=False,
            )
            md = result["md"].read_text(encoding="utf-8")
            # 原始值里的 | 应被转义
            self.assertIn(r"\|", md)


class TestMarkdownToHtml(TestCase):
    """_md_to_html 简单 Markdown→HTML 渲染器（用于降级版）"""

    def test_preserves_strong_tags(self):
        out = _md_to_html("这是一段 **粗体** 文字")
        self.assertIn("<strong>粗体</strong>", out)
        # 全文已被 escape，原文里的 ** 不应再出现
        self.assertNotIn("**", out)

    def test_preserves_code_tags(self):
        out = _md_to_html("字段 `score` 的均值是 70")
        self.assertIn("<code>score</code>", out)
        self.assertNotIn("`", out)

    def test_escapes_special_html_chars(self):
        out = _md_to_html("值 < 10 且 > 5")
        self.assertIn("&lt; 10", out)
        self.assertIn("&gt; 5", out)
        # 原始尖括号不能裸奔到 HTML 里
        self.assertNotIn("值 < 10", out)

    def test_heading_levels(self):
        md = "# 一级\n## 二级\n### 三级"
        out = _md_to_html(md)
        # h1 -> h3, h2 -> h4, h3 -> h5（在报告正文里的偏移）
        self.assertIn("<h3>一级</h3>", out)
        self.assertIn("<h4>二级</h4>", out)
        self.assertIn("<h5>三级</h5>", out)


class TestFormatsParam(TestCase):
    """formats 参数：只生成 .md / 只生成 .html / 完整三件套"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.data_file = self.tmp_path / "test.csv"
        self.data_file.write_text(
            "content,score\nok,80\nbad,30\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_md_only(self):
        """formats=("md",) 只生成 .md，不应有 .html"""
        result = generate_report(
            {"platform": "test", "name": "x"},
            SAMPLE_RESULTS, self.data_file, self.tmp_path,
            llm_synthesize=False,
            formats=("md",),
        )
        self.assertIn("md", result)
        self.assertNotIn("html", result)
        self.assertNotIn("qa_json", result)
        self.assertTrue(result["md"].exists())

    def test_html_only(self):
        """formats=("html",) 只生成 .html"""
        result = generate_report(
            {"platform": "test", "name": "x"},
            SAMPLE_RESULTS, self.data_file, self.tmp_path,
            llm_synthesize=False,
            formats=("html",),
        )
        self.assertIn("html", result)
        self.assertNotIn("md", result)
        self.assertNotIn("qa_json", result)
        self.assertTrue(result["html"].exists())

    def test_md_and_qa_json(self):
        """formats=("md", "qa_json") —— 主流程真实用法"""
        result = generate_report(
            {"platform": "test", "name": "x"},
            SAMPLE_RESULTS, self.data_file, self.tmp_path,
            llm_synthesize=False,
            formats=("md", "qa_json"),
        )
        self.assertIn("md", result)
        self.assertIn("qa_json", result)
        self.assertNotIn("html", result)
        self.assertTrue(result["md"].exists())
        self.assertTrue(result["qa_json"].exists())

    def test_output_dir_is_respected(self):
        """output_dir 真的写过去了 —— 不应落到 REPORT_DIR"""
        custom = self.tmp_path / "custom_subdir"
        custom.mkdir()
        result = generate_report(
            {"platform": "test", "name": "x"},
            SAMPLE_RESULTS, self.data_file, custom,
            llm_synthesize=False,
            formats=("md",),
        )
        self.assertTrue(str(result["md"]).startswith(str(custom)))
        # 不应在 REPORT_DIR 出现
        from config import REPORT_DIR
        report_dir_files = list(REPORT_DIR.glob("analysis_*.md"))
        # 至少确认我们的文件不在那
        self.assertNotIn(result["md"], report_dir_files)


class TestGenerateHtmlFromMarkdown(TestCase):
    """generate_html_from_markdown()：从 .md 读，调用 LLM 或降级生成 .html"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.md_path = self.tmp_path / "report.md"
        self.md_path.write_text(
            "# 测试报告\n\n## 1. 执行摘要\n\n**正例**有 `code`。\n\n值 < 10\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_fallback_html_when_llm_unavailable(self):
        """无 LLM 时，强制 llm_enhance=False 走降级"""
        out = generate_html_from_markdown(
            self.md_path, llm_enhance=False,
        )
        self.assertIsNotNone(out)
        self.assertTrue(out.exists())
        html_text = out.read_text(encoding="utf-8")
        # 完整 HTML 文档
        self.assertIn("<!DOCTYPE html>", html_text)
        self.assertIn("<html", html_text.lower())
        # 内容里至少应出现标题
        self.assertIn("测试报告", html_text)

    def test_output_path_default(self):
        """output_path 不传 → 与 md 同目录、换 .html 后缀"""
        out = generate_html_from_markdown(
            self.md_path, llm_enhance=False,
        )
        self.assertEqual(out.suffix, ".html")
        self.assertEqual(out.stem, self.md_path.stem)
        self.assertEqual(out.parent, self.md_path.parent)

    def test_output_path_custom(self):
        """output_path 自定义 → 写到指定位置"""
        custom = self.tmp_path / "sub" / "my.html"
        out = generate_html_from_markdown(
            self.md_path, custom, llm_enhance=False,
        )
        self.assertEqual(out, custom)
        self.assertTrue(out.exists())

    def test_simple_md_to_html_returns_valid_html(self):
        """_simple_md_to_html 输出是完整 HTML 文档"""
        md = "# Hi\n\n**bold** `code` < 5"
        html_doc = _simple_md_to_html(md, title="测试")
        self.assertIn("<!DOCTYPE html>", html_doc)
        self.assertIn("<title>测试", html_doc)
        self.assertIn("<strong>bold</strong>", html_doc)
        self.assertIn("<code>code</code>", html_doc)
        # < 5 应被 escape 成 &lt; 5
        self.assertIn("&lt; 5", html_doc)

    def test_simple_md_to_html_has_7_section_anchors(self):
        """降级版 HTML 应有 7 段式锚点 + sticky TOC + Chart.js"""
        md = """# 标题

## 1. 执行摘要

正文

## 2. 数据说明

字段

## 3. 分析工具说明

工具

## 4. 分析结果

结果

## 5. 关键发现

发现

## 6. 启示与预测

启示

## 7. 附录：原始数据预览

预览
"""
        html_doc = _simple_md_to_html(md, title="降级版")
        # 7 个 section id
        for i in range(1, 8):
            self.assertIn(f'id="s{i}"', html_doc, f"缺 s{i} 锚点")
        # sticky TOC
        self.assertIn('class="toc"', html_doc)
        self.assertIn("position: sticky", html_doc)
        # Chart.js CDN
        self.assertIn("chart.js", html_doc.lower())
        # TOC 里有 7 个链接
        toc_section = html_doc[html_doc.find('<nav class="toc"'):html_doc.find('</nav>')]
        link_count = toc_section.count('<a href="#s')
        self.assertEqual(link_count, 7)


class TestExportReportTriggers(TestCase):
    """main._is_export_report_request 关键词检测"""

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from main import _is_export_report_request
        self.match = _is_export_report_request

    def test_chinese_triggers(self):
        for text in [
            "导出报告",
            "帮我导出报告",
            "生成 markdown",
            "生成md",
            "出报告",
            "保存报告",
            "导出全部结果为一篇完整的 Markdown 报告",
            "给我报告",
            "写一份报告",
            "下载报告",
        ]:
            self.assertTrue(self.match(text), f"应匹配: {text!r}")

    def test_english_triggers(self):
        for text in ["report", "export the report", "markdown 报告", "md 报告"]:
            self.assertTrue(self.match(text), f"应匹配: {text!r}")

    def test_non_triggers(self):
        for text in [
            "打开报告文件夹",       # 问路径，不是导出
            "情感分析",             # 分析需求
            "exit",
            "你好",
            "总结一下",
        ]:
            self.assertFalse(self.match(text), f"不应匹配: {text!r}")

    def test_empty_string(self):
        self.assertFalse(self.match(""))
        self.assertFalse(self.match("   "))


if __name__ == "__main__":
    main()
