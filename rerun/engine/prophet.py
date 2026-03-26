"""Prophet feedback system — rewards for making 'future-informed' decisions."""

from __future__ import annotations

import random

from rerun.engine.state import PlayerState

# ---------------------------------------------------------------------------
# Prophet reactions — shown when the player's foresight pays off
# ---------------------------------------------------------------------------

PROPHET_REACTIONS = [
    "💬 [系统] 当其他人还在犹豫的时候，你已经稳稳上车了。\n   重生者的从容，不过如此。",
    "💬 [系统] 你的同事们事后会说「运气好」。\n   只有你知道，这根本不是运气。",
    "💬 [系统] 恭喜，你又一次证明了：\n   知道答案的考试，就是这么轻松。\n   但别忘了，生活的考题不全在试卷上。",
    "💬 [系统] 朋友圈里有人转发「后悔没早点买」的文章。\n   你微微一笑，没有评论。\n   闷声发大财，重生者的基本素养。",
    "💬 [系统] 你又做对了一次。\n   这种「开卷考试」的感觉，永远不会腻。",
    "💬 [系统] 旁人觉得你有「投资天赋」。\n   你笑笑不说话。天赋？不，这叫作弊。",
]

# ---------------------------------------------------------------------------
# Prophet trigger conditions
# Each trigger: (year_to_check, condition_fn, reaction_context)
# Checked at the START of the specified year (so choices from prior year are visible)
# ---------------------------------------------------------------------------


def _bought_btc_early(state: PlayerState) -> bool:
    """Player bought BTC in 2015-2016."""
    return state.btc_amount > 0


def _sold_btc_before_crash(state: PlayerState) -> bool:
    """Player sold BTC before the 2018 crash (net worth high but low BTC)."""
    # Check if they sold most of their BTC by 2018
    return state.btc_amount < state.max_btc_held * 0.5 and state.times_sold_btc > 0


def _prepared_for_covid(state: PlayerState) -> bool:
    """Player stockpiled masks before COVID."""
    return bool(state.flags.get("stockpiled_masks"))


def _bet_on_ai_early(state: PlayerState) -> bool:
    """Player pivoted to AI before 2023."""
    return bool(state.flags.get("pivoted_to_ai_2018"))


def _has_high_net_worth(state: PlayerState) -> bool:
    """Player accumulated significant wealth."""
    return state.net_worth > 5_000_000


# Prophet triggers: (year, check_function, context_message)
PROPHET_TRIGGERS: list[tuple[int, callable, str]] = [
    (2016, _bought_btc_early, "你在BTC还是白菜价的时候入场了"),
    (2018, _sold_btc_before_crash, "你在高点逃顶了！BTC从13万跌到了2.5万"),
    (2020, _prepared_for_covid, "你居然提前囤了口罩！COVID来了，你早有准备"),
    (2023, _bet_on_ai_early, "你提前布局了AI！ChatGPT横空出世，你赢在了起跑线"),
]


def check_prophet_trigger(year: int, state: PlayerState) -> str | None:
    """Check if any prophet trigger fires for the current year.

    Returns a formatted prophet message or None.
    """
    for trigger_year, check_fn, context in PROPHET_TRIGGERS:
        if year == trigger_year and check_fn(state):
            reaction = random.choice(PROPHET_REACTIONS)
            return f"  [bold magenta]🔮 [先知时刻][/]\n  [magenta]{context}[/]\n\n  {reaction}"
    return None


# ---------------------------------------------------------------------------
# Milestone celebration system
# ---------------------------------------------------------------------------

# B9: Milestone descriptions now depend on player state (has_partner etc.)
# Each entry: (threshold, title, desc_with_partner, desc_without_partner)
MILESTONES = [
    (100_000, "十万俱乐部",
     "你比全国 70% 的同龄人有钱了",
     "你比全国 70% 的同龄人有钱了"),
    (500_000, "半百万",
     "首付够了...如果你想买房的话",
     "首付够了...如果你想买房的话"),
    (1_000_000, "百万富翁",
     "你是前 8% 了。但在上海，这也就刚够一套老破小",
     "你是前 8% 了。但在上海，这也就刚够一套老破小"),
    (5_000_000, "小目标的 1/200",
     "离王健林的小目标还差 199 个你",
     "离王健林的小目标还差 199 个你"),
    (10_000_000, "千万身家",
     "你和另一半可以在大部分城市实现财务自由了",
     "你可以在大部分城市实现财务自由了"),
    (100_000_000, "一个亿！",
     "🎉 你实现了王健林的小目标！这不是演习！",
     "🎉 你实现了王健林的小目标！这不是演习！"),
]


def check_milestone(
    state: PlayerState, reached_milestones: set[int]
) -> tuple[str | None, set[int]]:
    """Check if the player hit a new net worth milestone.

    Returns (formatted message or None, updated reached set).
    """
    nw = state.net_worth
    new_reached = set(reached_milestones)

    for threshold, title, desc_partner, desc_no_partner in MILESTONES:
        if threshold in reached_milestones:
            continue
        if nw >= threshold:
            new_reached.add(threshold)
            # B9: pick description based on relationship status
            description = desc_partner if state.has_partner else desc_no_partner
            msg = (
                f"\n  [bold yellow]{'━' * 40}[/]"
                f"\n  [bold yellow]🎉 里程碑：{title}！[/]"
                f"\n  [bold yellow]💎 净资产突破 ¥{threshold:,}[/]"
                f"\n  [dim]{description}[/]"
                f"\n  [bold yellow]{'━' * 40}[/]"
            )
            return msg, new_reached

    return None, new_reached
