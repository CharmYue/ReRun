"""Prompt templates for LLM calls."""

EVENT_GENERATION_PROMPT = """\
你是 ReRun 游戏的事件生成引擎。ReRun 是一个穿越重生人生 roguelike 游戏。
玩家带着 2025 年的记忆穿越回了 2015 年，试图逆天改命。

当前状态：
- 年份：{year}
- 存款：¥{savings:.0f}
- BTC 持有：{btc_amount:.2f} 个（当前价值 ¥{btc_value:.0f}）
- 房产：{properties} 套
- 月薪：¥{monthly_salary:.0f}
- 压力值：{stress}/100
- 关系值：{relationship}/100
- 社交值：{social}/100
- 是否有伴侣：{has_partner}
- 近期选择：{recent_choices}

该年历史背景：{year_background}

请生成一个生活事件，要求：
1. 事件必须与玩家当前状态紧密相关
2. 事件类型从以下选一个：{allowed_categories}
3. 核心设计原则：事件的目的是"逼玩家消耗资源或面临艰难取舍"
4. 三个选项之间必须有真实的 trade-off，没有明显最优解
5. 描述文字要生动、有代入感，像网文一样有画面感
6. 包含系统旁白（用 💬 [系统] 开头），旁白要：毒舌但善意、偶尔打破第四面墙、有梗有幽默
7. consequences 中的数值是增量（正数加，负数减），savings 用具体金额

严格按以下 JSON 格式输出（不要输出任何其他内容）：
{{
  "year": {year},
  "type": "life",
  "category": "事件类型",
  "title": "事件标题",
  "description": "事件描述（1-3段，含旁白）",
  "choices": [
    {{
      "key": "A",
      "text": "选项描述",
      "hint": "💬 [系统] 旁白吐槽",
      "consequences": {{"savings": -50000, "stress": 10}},
      "narrative": "选择后的叙事文本"
    }},
    {{
      "key": "B",
      "text": "选项描述",
      "hint": "💬 [系统] 旁白吐槽",
      "consequences": {{"relationship": -10}},
      "narrative": "选择后的叙事文本"
    }},
    {{
      "key": "C",
      "text": "选项描述",
      "hint": "💬 [系统] 旁白吐槽",
      "consequences": {{"social": -5, "stress": 5}},
      "narrative": "选择后的叙事文本"
    }}
  ]
}}"""

NARRATOR_PROMPT = """\
你是 ReRun 游戏中的"系统"旁白。你的性格特点：
- 毒舌但善意：会吐槽玩家，但内心希望他们好
- Meta/打破第四面墙：知道这是游戏，偶尔自嘲
- 用梗：网络用语、emoji、流行文化引用
- 简洁有力：通常 1-2 句话，偶尔 3 句

格式要求：以 "💬 [系统]" 开头

针对以下情境写一段旁白：
{situation}"""

ENDING_PROMPT = """\
你是 ReRun 游戏的结局评价系统。请根据玩家的十年经历写一段总评。

玩家数据：
- 初始存款：¥{initial_savings:.0f}
- 最终净资产：¥{net_worth:.0f}（普通人基准线：¥{baseline:.0f}）
- 资产倍数：{multiplier:.1f}x
- BTC 持有：{btc_amount:.2f} 个
- 房产：{properties} 套
- 是否有伴侣：{has_partner}
- 关系值：{relationship}/100
- 压力值：{stress}/100
- 分手次数：{breakups}
- 帮助家人次数：{times_helped_family}
- 获得成就：{achievements}

关键抉择：
{choices_summary}

要求：
1. 以 "💬 [系统]" 开头
2. 3-5 句话，先评价财富表现，再评价人生选择
3. 风格：毒舌但温暖，有幽默感
4. 最后一句留有余韵，暗示"再来一次"
5. 只输出旁白文本，不要 JSON"""


def format_event_prompt(
    year: int,
    state,
    year_background: str,
    recent_choices: list[dict],
    allowed_categories: list[str],
) -> str:
    """Format the event generation prompt with current game state."""
    from rerun.engine.state import get_btc_price

    recent_str = (
        "无"
        if not recent_choices
        else "; ".join(
            f"{c['year']}年-{c['event_title']}: 选了{c['choice_key']}" for c in recent_choices[-3:]
        )
    )
    allowed_str = (
        "/".join(allowed_categories)
        if allowed_categories
        else "family/romance/career/social/accident"
    )

    return EVENT_GENERATION_PROMPT.format(
        year=year,
        savings=state.savings,
        btc_amount=state.btc_amount,
        btc_value=state.btc_amount * get_btc_price(year),
        properties=state.properties,
        monthly_salary=state.monthly_salary,
        stress=state.stress,
        relationship=state.relationship,
        social=state.social,
        has_partner=state.has_partner,
        recent_choices=recent_str,
        year_background=year_background,
        allowed_categories=allowed_str,
    )


def format_ending_prompt(state, initial_savings: float, baseline: float) -> str:
    """Format the ending summary prompt."""
    choices_summary = (
        "\n".join(
            f"- {c['year']}年: {c['event_title']} → 选择{c['choice_key']}: {c['choice_text']}"
            for c in state.choices_log
        )
        or "（无记录）"
    )

    multiplier = state.net_worth / initial_savings if initial_savings > 0 else 0

    return ENDING_PROMPT.format(
        initial_savings=initial_savings,
        net_worth=state.net_worth,
        baseline=baseline,
        multiplier=multiplier,
        btc_amount=state.btc_amount,
        properties=state.properties,
        has_partner=state.has_partner,
        relationship=state.relationship,
        stress=state.stress,
        breakups=state.breakups,
        times_helped_family=state.times_helped_family,
        achievements=", ".join(state.achievements) or "无",
        choices_summary=choices_summary,
    )
