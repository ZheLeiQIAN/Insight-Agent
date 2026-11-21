# 分析工具系统指南

## 🎯 设计理念

**专业工具优先**：先用预定义的分析方法，没有时再调用大模型。

### 优势

1. **速度快**：专业工具执行效率高
2. **结果可靠**：经过验证的分析方法
3. **资源节省**：减少 LLM API 调用
4. **易于维护**：工具代码可复用

---

## 📝 报告输出

每次分析完成后，CLI 会自动在 `output/reports/` 下生成两份报告：

| 文件 | 用途 | 特点 |
|------|------|------|
| `analysis_<时间戳>.md` | Markdown 报告 | 可贴 IM、VSCode 预览、`pandoc` 转换 |
| `analysis_<时间戳>.html` | HTML 报告 | 含 chart.js 图表 + sticky 目录 + 打印样式（`Ctrl+P` 直接 PDF） |
| `analysis_<时间戳>.qa.json` | 原始数据 | AI 后续问答用 |

报告采用 **七段式专业结构**：

1. **执行摘要**（LLM 生成 / 降级模板）
2. **数据说明**（字段表 + 缺失率 + 质量提示）
3. **分析工具说明**（每个工具的类别、适用字段、说明）
4. **分析结果**（各工具的输出 + ASCII/HTML 图表）
5. **关键发现**（LLM 生成 3-5 条带情绪色块的发现）
6. **启示与预测**（LLM 生成的行动建议 + 带置信度的趋势预测）
7. **附录：原始数据预览**

> LLM 不可用时（无 `DEEPSEEK_API_KEY`），第 1/5/6 段会走降级模板，依然能生成完整报告。

## 📦 可用工具

### 定量分析 (QUANTITATIVE)

| 工具 | 描述 | 需要字段 |
|------|------|----------|
| `basic_stats` | 基础统计：计数、均值、中位数、最值、分布 | 任意 |

### 文本分析 (TEXT_ANALYSIS)

| 工具 | 描述 | 需要字段 |
|------|------|----------|
| `sentiment_analysis` | 情感分析：正面/中性/负面 | text |
| `word_frequency` | 词频统计：TF-IDF 关键词 | text |

### 时间序列 (TIME_SERIES)

| 工具 | 描述 | 需要字段 |
|------|------|----------|
| `time_series` | 时间序列：趋势和周期性 | date |

### 定性分析 (QUALITATIVE)

| 工具 | 描述 | 需要字段 |
|------|------|----------|
| `theme_extraction` | 主题提取：核心主题 | text |
| `content_category` | 内容分类：自动归类 | text |
| `insight_mining` | 观点挖掘：态度/问题/建议 | text |

---

## 🚀 使用方式

### 方式一：直接调用工具

```python
from analysis.tools_registry import execute_tool
from pathlib import Path

# 加载数据
data = [
    {"content": "这个产品非常好", "score": "85"},
    {"content": "体验很差", "score": "45"},
]

# 执行情感分析
result = execute_tool("sentiment_analysis", data, Path("data.csv"))
print(result)
```

### 方式二：智能分析（推荐）

```python
from analysis.smart_analyzer import smart_analyze
from pathlib import Path

data = [...]  # 你的数据

# 用户查询
result = smart_analyze(data, Path("data.csv"), "帮我做情感分析")

print(f"使用工具: {result.tool_name}")
print(f"来源: {result.source}")  # "builtin" 或 "llm"
print(f"结果: {result.result}")
```

### 方式三：获取推荐

```python
from analysis.tools_registry import recommend_tools, get_available_tools

data = [...]  # 你的数据

# 获取推荐工具
recommended = recommend_tools(data)
print(f"推荐工具: {recommended}")

# 获取所有工具
all_tools = get_available_tools()
for tool in all_tools:
    print(f"{tool['name']}: {tool['description']}")
```

---

## 🤖 AI 对话中的使用

在 AI 对话中，系统会自动：

1. **解析用户意图**
   ```
   用户: "帮我做情感分析"
   意图: sentiment_analysis
   ```

2. **匹配专业工具**
   ```
   检查: sentiment_analysis 工具存在
   检查: 数据包含 text 字段
   结果: 使用专业工具
   ```

3. **执行分析**
   ```python
   result = execute_tool("sentiment_analysis", data, data_file)
   ```

4. **返回结果**
   ```
   使用工具: sentiment_analysis
   来源: builtin (专业工具)
   结果: {...}
   ```

---

## 📊 工具优先级

系统按以下优先级选择工具：

1. **精确匹配**：用户查询直接匹配工具名
2. **关键词匹配**：查询包含工具关键词
3. **数据推荐**：根据数据特征推荐
4. **大模型兜底**：无匹配时调用 LLM

### 示例

```
用户查询: "情感分析"
→ 精确匹配: sentiment_analysis ✅

用户查询: "分析用户态度"
→ 关键词匹配: "态度" → sentiment_analysis ✅

用户查询: "看看数据有什么规律"
→ 无匹配 → 调用大模型
```

---

## 🔧 扩展工具

### 添加新工具

1. **创建分析函数**

```python
# analysis/custom_analysis.py
def my_custom_analysis(data, data_file):
    """自定义分析"""
    # 分析逻辑
    return {"result": "..."}
```

2. **注册工具**

```python
# analysis/tools_registry.py
from analysis.custom_analysis import my_custom_analysis

ToolsRegistry.register(AnalysisTool(
    name="my_custom_analysis",
    category=AnalysisCategory.QUANTITATIVE,
    description="自定义分析：...",
    function=my_custom_analysis,
    required_fields=["text"],
    output_type="custom",
    priority=5,
    examples=["自定义分析", "特殊需求"]
))
```

3. **测试工具**

```python
from analysis.tools_registry import execute_tool
result = execute_tool("my_custom_analysis", data, data_file)
print(result)
```

---

## 💡 最佳实践

### 1. 工具选择策略

```python
# ✅ 推荐：使用智能分析
result = smart_analyze(data, data_file, "情感分析")

# ⚠️ 可用：直接调用工具
result = execute_tool("sentiment_analysis", data, data_file)

# ❌ 不推荐：直接写代码（除非必要）
from analysis.quantitative import sentiment_analysis
result = sentiment_analysis(data, data_file)
```

### 2. 错误处理

```python
result = smart_analyze(data, data_file, "情感分析")

if result.success:
    print(f"分析成功: {result.result}")
else:
    print(f"分析失败: {result.result.get('error')}")
    # 考虑使用大模型兜底
```

### 3. 性能优化

```python
# 批量分析时，复用分析器实例
from analysis.smart_analyzer import SmartAnalyzer

analyzer = SmartAnalyzer(data, data_file)

# 多次分析
result1 = analyzer.analyze("情感分析")
result2 = analyzer.analyze("词频统计")
```

---

## 📈 性能对比

| 指标 | 专业工具 | 大模型 |
|------|----------|--------|
| 速度 | ⚡ 快 (0.1-1秒) | 🐌 慢 (2-10秒) |
| 成本 | 💰 低 | 💰💰💰 高 |
| 准确性 | ✅ 高 | ✅ 高 |
| 灵活性 | ⚠️ 固定 | ✅ 灵活 |
| 适用场景 | 常见分析 | 复杂/特殊需求 |

---

## 🎯 使用场景

### 场景 1：标准分析

```
用户: "帮我做情感分析"
系统: 使用 sentiment_analysis 工具
结果: 正面 60%，中性 25%，负面 15%
耗时: 0.5秒
```

### 场景 2：复杂分析

```
用户: "分析用户评论中的潜在需求"
系统: 无匹配工具，调用大模型
结果: 需求列表 + 分析说明
耗时: 5秒
```

### 场景 3：组合分析

```
用户: "全面分析一下数据"
系统: 
  1. basic_stats (基础统计)
  2. sentiment_analysis (情感分析)
  3. word_frequency (词频统计)
结果: 综合报告
耗时: 2秒
```

---

## 🔍 调试技巧

### 查看工具列表

```python
from analysis.tools_registry import get_available_tools
import json

tools = get_available_tools()
print(json.dumps(tools, indent=2, ensure_ascii=False))
```

### 查看推荐结果

```python
from analysis.tools_registry import recommend_tools

data = [...]  # 你的数据
recommended = recommend_tools(data)
print(f"推荐工具: {recommended}")
```

### 测试工具执行

```python
from analysis.tools_registry import execute_tool
from pathlib import Path

data = [{"content": "测试文本"}]
result = execute_tool("sentiment_analysis", data, Path("test.csv"))
print(result)
```

---

## 📚 相关文档

- [README.md](../README.md) - 项目概述
- [CLI_GUIDE.md](CLI_GUIDE.md) - CLI 使用指南
- [WEB_UI_GUIDE.md](WEB_UI_GUIDE.md) - Web UI 指南

---

## 🎉 总结

**专业工具优先**策略的优势：

✅ **高效**：常见分析秒级完成  
✅ **可靠**：经过验证的方法  
✅ **经济**：减少 API 调用  
✅ **易维护**：工具代码可复用  

**立即开始**：
```python
from analysis.smart_analyzer import smart_analyze
result = smart_analyze(data, data_file, "你的分析需求")
```

---

**文档版本**: v1.0  
**最后更新**: 2024-01-27
