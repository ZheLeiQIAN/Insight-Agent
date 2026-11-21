"""城市热区图 — LLM Agent 桥接

连接 DeepSeek API，将人群行为事件转化为智能建议。
"""

import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def _get_llm_config():
    """获取 LLM 配置"""
    from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
    return {
        'api_key': LLM_API_KEY,
        'base_url': LLM_BASE_URL,
        'model': LLM_MODEL,
    }


# 建议模板（LLM 不可用时的降级方案）
# V4: 餐饮 / 火锅店运营上下文
_FALLBACK_ADVICES = [
    {
        'priority': 'high',
        'title': '建议启动高峰分流预案',
        'description': '滨江道商圈火锅客流持续上升，等位超25分钟，建议：① 增加1-2个临时等位区 ② 备菜/锅底提前1.5h启动 ③ 拼桌优先大桌。',
    },
    {
        'priority': 'medium',
        'title': '食材消耗动态调度',
        'description': '监测到毛肚/黄喉/鸭血消耗增长，建议后厨按1.3倍备货，午市/晚市交接班前补满。',
    },
    {
        'priority': 'medium',
        'title': '商圈差异化竞争',
        'description': '意式风情区火锅供给偏低，建议联合"一人食火锅"或"火锅+精酿"模式抢占新客群。',
    },
    {
        'priority': 'low',
        'title': '外卖产品线拓展',
        'description': '火锅外卖渗透率仅5%，建议开发"火锅冒菜化"单人份套餐（38-58元客单），承接写字楼午市。',
    },
]


# V4: 系统提示词 — 城市餐饮 / 火锅店运营专家
_RESTAURANT_SYSTEM_PROMPT = """你是 Insight Agent 城市餐饮运营专家，专精火锅/烧烤/川菜/粤菜/日料/西餐/小吃/酒吧等业态的城市分布与门店运营。

请基于实时监测数据，给出可执行的运营/投资建议，覆盖以下维度：
- 菜系格局：火锅/烧烤/川菜/粤菜/日料/西餐/小吃/酒吧 占比、增速、季节性
- 商圈分析：商圈饱和度、客单、上座率、翻台率、等位、午晚市结构
- 选址投资：菜系×商圈矩阵的空白点、一人食/外卖/夜宵 等新兴机会
- 时段运营：午餐 11-13 / 下午茶 14-17 / 晚餐 17-20 / 夜宵 21-01 各时段最佳调度
- 食客流向：居住区/办公区/大学城/交通枢纽 食客构成与迁徙规律

回答要简洁、结构化、可执行，必要时给出数字范围与具体动作（不要空话）。"""


def analyze_events_with_llm(events: List[Dict]) -> List[Dict]:
    """使用 LLM 分析事件列表，生成智能建议（V4: 餐饮上下文）"""
    if not events:
        return []

    config = _get_llm_config()
    if not config['api_key'] or OpenAI is None:
        return _FALLBACK_ADVICES[:2]

    try:
        client = OpenAI(
            api_key=config['api_key'],
            base_url=config['base_url'],
        )

        # 构建事件描述
        event_descriptions = '\n'.join([
            f"- [{e.get('severity', '?')}] {e.get('description', '未知事件')}"
            for e in events[:10]
        ])

        prompt = f"""当前城市餐饮实时事件（火锅/烧烤/川菜/粤菜/日料/西餐/小吃等多业态）：

{event_descriptions}

请给出2-3条具体、可执行的运营/投资建议。每条建议包含：priority(high/medium/low)、title、description。
以 JSON 数组格式返回，每条格式: {{"priority": "...", "title": "...", "description": "..."}}
只返回 JSON，不要其他内容。"""

        response = client.chat.completions.create(
            model=config['model'],
            messages=[
                {"role": "system", "content": _RESTAURANT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=500,
        )

        content = response.choices[0].message.content.strip()
        # 尝试解析 JSON
        import json
        if content.startswith('```'):
            content = content.split('\n', 1)[1].rsplit('\n', 1)[0]
        advices = json.loads(content)
        return advices if isinstance(advices, list) else [advices]

    except Exception as e:
        logger.warning(f"LLM 调用失败，使用降级建议: {e}")
        return _FALLBACK_ADVICES[:2]


def generate_report(snapshot: Dict) -> str:
    """使用 LLM 生成阶段性分析报告（V4: 餐饮四段式）"""
    config = _get_llm_config()
    if not config['api_key'] or OpenAI is None:
        return _generate_fallback_report(snapshot)

    try:
        client = OpenAI(
            api_key=config['api_key'],
            base_url=config['base_url'],
        )

        prompt = f"""根据以下城市餐饮（火锅/烧烤/川菜/粤菜/日料/西餐/小吃等多业态）实时监测数据，生成结构化阶段报告：

- 实时客流: {snapshot.get('total_people', 0)} 人
- 人群密度: {snapshot.get('density', 0)} 人/km²
- 热区数量: {snapshot.get('hotspot_count', 0)} 个
- 异常事件: {snapshot.get('anomaly_count', 0)} 件

输出固定 4 段：客流概况 / 商圈热度 / 菜系竞争 / 投资参考。每段 80-150 字，给出可执行建议。"""

        response = client.chat.completions.create(
            model=config['model'],
            messages=[
                {"role": "system", "content": _RESTAURANT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=700,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.warning(f"LLM 报告生成失败: {e}")
        return _generate_fallback_report(snapshot)


def _generate_fallback_report(snapshot: Dict) -> str:
    """降级报告（无 LLM 时使用，V4: 餐饮四段式）"""
    total = snapshot.get('total_people', 0)
    density = snapshot.get('density', 0)
    hotspots = snapshot.get('hotspot_count', 0)
    anomalies = snapshot.get('anomaly_count', 0)

    risk_level = '低'
    if density > 300:
        risk_level = '高'
    elif density > 200:
        risk_level = '中'

    return f"""## 城市餐饮热度分析报告（火锅/烧烤/川菜/粤菜等）

### 一、客流概况
实时客流 {total} 人，密度 {density} 人/km²，热区 {hotspots} 个，异常事件 {anomalies} 件。整体处于{'偏高' if density > 200 else '正常'}水平。

### 二、商圈热度
核心商圈密度{'持续走高，需关注翻台' if density > 200 else '保持平稳'}。建议：① 等位引导（线上排号+小食赠送）② 午市套餐提效率 ③ 晚市 17:30 提前开台分流。

### 三、菜系竞争
火锅仍占主导，烧烤进入旺季（夏季+18%）。建议关注：① 火锅"一人食/小份"差异化 ② 烧烤夜市档口延长至 23:30 ③ 轻食沙拉承接白领午市 ④ 深夜酒吧/小酒馆匹配 22:00 后客流。

### 四、投资参考
1) 核心商圈火锅密度趋于饱和，建议差异化定位（一人食/火锅+精酿）
2) 城西/中北镇/张家窝等新兴板块餐饮空白明显，是新店首选
3) 夏季户外餐饮（露台/夜市/大排档）即将迎来旺季
4) 外卖渠道可考虑"火锅冒菜化"/"烧烤单人份"轻量化产品线

整体风险等级：**{risk_level}**。{'加强监测与疏导准备' if risk_level != '低' else '保持常规巡检即可'}。"""