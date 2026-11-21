#!/usr/bin/env python3
"""
系统验证脚本

快速验证整个 Insight Agent 系统是否正常工作
"""

import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def validate_config():
    """验证配置"""
    try:
        from validator import ConfigValidator
        is_valid, errors = ConfigValidator.validate()
        return is_valid, errors
    except Exception as e:
        return False, [str(e)]


def validate_modules():
    """验证模块导入"""
    modules = [
        ("config", "配置模块"),
        ("ui", "UI 模块"),
        ("analysis.quantitative", "定量分析"),
        ("analysis.qualitative", "定性分析"),
        ("analysis.tools_registry", "工具注册表"),
        ("analysis.smart_analyzer", "智能分析器"),
        ("chat", "AI 对话"),
        ("report", "报告生成"),
        ("crawlers.runner", "爬虫运行器"),
        ("web.server", "Web 服务器"),
    ]

    results = []
    for module_name, description in modules:
        try:
            __import__(module_name)
            results.append((description, True, None))
        except ImportError as e:
            results.append((description, False, str(e)))
        except Exception as e:
            results.append((description, False, str(e)))

    return results


def validate_tools():
    """验证分析工具"""
    try:
        from analysis.tools_registry import get_available_tools
        tools = get_available_tools()
        return True, len(tools)
    except Exception as e:
        return False, str(e)


def validate_analysis():
    """验证分析功能"""
    try:
        from analysis.smart_analyzer import smart_analyze
        from pathlib import Path

        sample_data = [
            {"content": "测试文本", "score": "85"},
            {"content": "另一个测试", "score": "92"},
        ]

        result = smart_analyze(sample_data, Path("test.csv"), "情感分析")
        return result.success, result.tool_name
    except Exception as e:
        return False, str(e)


def validate_web():
    """验证 Web 服务器"""
    try:
        from web.server import start_server
        import threading
        import requests

        # 启动服务器
        server_thread = start_server(port=9533, open_browser=False, background=True)
        time.sleep(2)

        # 测试请求
        try:
            response = requests.get("http://localhost:9533/", timeout=5)
            return True, response.status_code
        except Exception as e:
            return False, str(e)
    except Exception as e:
        return False, str(e)


def main():
    """主验证流程"""
    console.print(Panel.fit(
        "[bold cyan]🔍 Insight Agent 系统验证[/]\n\n"
        "正在验证系统各个组件...",
        border_style="cyan"
    ))

    results = []

    # 1. 配置验证
    console.print("\n[bold]1️⃣ 配置验证[/]")
    config_ok, config_errors = validate_config()
    results.append(("配置", config_ok))
    if config_ok:
        console.print("   ✅ 配置验证通过")
    else:
        console.print(f"   ⚠️ 配置验证失败: {config_errors}")

    # 2. 模块验证
    console.print("\n[bold]2️⃣ 模块验证[/]")
    module_results = validate_modules()
    all_modules_ok = all(ok for _, ok, _ in module_results)
    results.append(("模块", all_modules_ok))

    for desc, ok, error in module_results:
        if ok:
            console.print(f"   ✅ {desc}")
        else:
            console.print(f"   ❌ {desc}: {error}")

    # 3. 工具验证
    console.print("\n[bold]3️⃣ 工具验证[/]")
    tools_ok, tools_info = validate_tools()
    results.append(("工具", tools_ok))
    if tools_ok:
        console.print(f"   ✅ 工具注册成功: {tools_info} 个工具")
    else:
        console.print(f"   ❌ 工具验证失败: {tools_info}")

    # 4. 分析验证
    console.print("\n[bold]4️⃣ 分析验证[/]")
    analysis_ok, analysis_info = validate_analysis()
    results.append(("分析", analysis_ok))
    if analysis_ok:
        console.print(f"   ✅ 分析功能正常: 使用 {analysis_info}")
    else:
        console.print(f"   ❌ 分析验证失败: {analysis_info}")

    # 5. Web 验证
    console.print("\n[bold]5️⃣ Web 验证[/]")
    web_ok, web_info = validate_web()
    results.append(("Web", web_ok))
    if web_ok:
        console.print(f"   ✅ Web 服务器正常: 状态码 {web_info}")
    else:
        console.print(f"   ❌ Web 验证失败: {web_info}")

    # 汇总结果
    console.print("\n" + "="*60)
    console.print("[bold]📊 验证结果汇总[/]")
    console.print("="*60)

    table = Table(show_header=True, header_style="bold")
    table.add_column("组件", style="cyan")
    table.add_column("状态", justify="center")
    table.add_column("说明")

    for name, ok in results:
        status = "✅ 通过" if ok else "❌ 失败"
        table.add_row(name, status, "")

    console.print(table)

    # 总结
    total = len(results)
    passed = sum(1 for _, ok in results if ok)

    console.print(f"\n[bold]总结: {passed}/{total} 组件验证通过[/]")

    if passed == total:
        console.print("\n[bold green]🎉 系统验证全部通过！[/]")
        console.print("\n💡 可以开始使用:")
        console.print("   python main.py          # CLI 模式")
        console.print("   python webui/webui_manager.py start  # Web UI")
        console.print("   python examples/full_workflow_demo.py  # 完整演示")
    else:
        console.print("\n[bold yellow]⚠️ 部分组件验证失败，请检查配置[/]")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
