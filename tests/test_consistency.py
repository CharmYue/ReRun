"""Automated state consistency checks — runs three full game routes and validates rules.

Usage:
    python -m pytest tests/test_consistency.py -v
    python -m pytest tests/test_consistency.py -v -s  # with print output
"""

from __future__ import annotations

import io
import sys

# Force UTF-8 on Windows
if sys.platform == "win32" and isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

try:
    import pytest
except ImportError:
    pytest = None  # type: ignore[assignment]

from rerun.config import Settings
from rerun.engine.achievements import check_achievements
from rerun.engine.chains import set_flags_from_choice
from rerun.engine.choices import get_valid_keys, process_choice
from rerun.engine.event_map import build_year_events, is_applicable, rebuild_family_event_if_broke
from rerun.engine.events import filter_choices_for_state
from rerun.engine.game import GameEngine
from rerun.engine.state import (
    BTC_PRICE_BY_YEAR,
    YEAR_END,
    YEAR_START,
    Gender,
    PlayerState,
    create_player,
    get_btc_price,
)

# ---------------------------------------------------------------------------
# State consistency rules (checked after each year settlement)
# ---------------------------------------------------------------------------


def check_state_consistency(state: PlayerState, year: int, violations: list[str]) -> None:
    """Check all state invariants after year-end settlement."""

    # Rule 1: Unemployed (not entrepreneur/freelance) → annual income must be 0
    if not state.has_income:
        if state.annual_salary_income > 0:
            violations.append(f"[{year}] 待业中但年收入 > 0: {state.annual_salary_income}")

    # Rule 2: Entrepreneur/freelance → must have income
    if state.is_self_employed:
        if state.monthly_salary <= 0:
            violations.append(f"[{year}] 身份是{state.job_title}但月薪为0")

    # Rule 3: Has property + mortgage → costs should show 房贷 not 房租
    if state.properties > 0:
        costs = state.calculate_annual_costs()
        if "房租" in costs:
            violations.append(f"[{year}] 有房产但支出中出现房租")
        # If mortgage is set, 房贷 should appear
        if state.mortgage_monthly > 0 and "房贷" not in costs:
            violations.append(f"[{year}] 有房贷月供但支出中没有房贷")

    # Rule 4: No property → should not have mortgage
    if state.properties == 0 and state.mortgage_monthly > 0:
        violations.append(f"[{year}] 无房但有房贷月供: {state.mortgage_monthly}")

    # Rule 5: Annual balance = income - expense (verify calculation consistency)
    expected_balance = state.annual_salary_income - state.annual_living_cost
    actual_balance = state.annual_net_income
    if abs(expected_balance - actual_balance) > 0.01:
        violations.append(
            f"[{year}] 年结余计算不一致: expected={expected_balance}, actual={actual_balance}"
        )

    # Rule 6: Stress must not be negative
    if state.stress < 0:
        violations.append(f"[{year}] 压力值为负: {state.stress}")

    # Rule 7: BTC amount must not be negative
    if state.btc_amount < 0:
        violations.append(f"[{year}] BTC 数量为负: {state.btc_amount}")

    # Rule 8: Properties must not be negative
    if state.properties < 0:
        violations.append(f"[{year}] 房产数量为负: {state.properties}")

    # Rule 9: Skills must be 1-5
    for skill in ("investment_iq", "career_level", "network", "emotional_iq"):
        val = getattr(state, skill)
        if val < 1 or val > 5:
            violations.append(f"[{year}] 技能 {skill} 越界: {val}")

    # Rule 10: Hidden stats must be 0-100
    for stat in ("stress", "relationship", "social", "reputation"):
        val = getattr(state, stat)
        if val < 0 or val > 100:
            violations.append(f"[{year}] 隐藏属性 {stat} 越界: {val}")


def check_preset_3_init(state: PlayerState, violations: list[str]) -> None:
    """Rule 8 from spec: Preset 3 must start with property and mortgage."""
    if state.properties <= 0:
        violations.append("[2015] 选项3起步但 properties = 0")
    if state.mortgage_monthly <= 0:
        violations.append("[2015] 选项3起步但无房贷月供")


# ---------------------------------------------------------------------------
# Event applicability rules (checked before each event)
# ---------------------------------------------------------------------------


def check_event_applicability(event, state: PlayerState, year: int, violations: list[str]) -> None:
    """Check event is appropriate for current state."""
    tid = event.template_id

    # Rule: Layoff event + not employed → should not trigger
    if "layoff" in tid and "survivor" not in tid and "safe" not in tid:
        if not state.is_employed and not state.is_self_employed:
            violations.append(f"[{year}] 无业但触发裁员事件: {tid}")

    # Rule: Buy house event for someone who already has house (old buy event)
    if tid == "2016_house_fomo" and state.properties > 0:
        violations.append(f"[{year}] 已有房产但出现买房焦虑事件: {tid}")

    # Rule: BTC sell events need BTC
    btc_sell_keywords = ["btc_sell", "btc_peak", "btc_crash", "btc_milestone", "nine_four"]
    if any(kw in tid for kw in btc_sell_keywords):
        if "no" not in tid and "regret" not in tid and "winner" not in tid:
            if state.btc_amount <= 0:
                violations.append(f"[{year}] 无 BTC 但触发 BTC 事件: {tid}")

    # Rule: Partner events need partner (except meeting events)
    if "partner" in tid and "meet" not in tid and "romance" not in tid:
        if not state.has_partner:
            violations.append(f"[{year}] 无伴侣但触发伴侣事件: {tid}")


# ---------------------------------------------------------------------------
# Achievement consistency rules
# ---------------------------------------------------------------------------


def check_achievement_consistency(state: PlayerState, violations: list[str]) -> None:
    """Check achievement logic is self-consistent."""
    achieved = state.achievements

    # Rule: diamond_hands and paper_hands are mutually exclusive
    if "diamond_hands" in achieved and "paper_hands" in achieved:
        violations.append("钻石手和纸手同时解锁，逻辑矛盾")


# ---------------------------------------------------------------------------
# Job title tracking rules
# ---------------------------------------------------------------------------


class JobTitleTracker:
    """Track job title changes across years to detect invalid regressions."""

    def __init__(self):
        self._prev_job_title: str | None = None
        self._prev_salary: float = 0.0

    def check(self, state: PlayerState, year: int, violations: list[str]) -> None:
        """Check job title and salary transitions."""
        # Rule 6: job_title should not regress from entrepreneur to 待业中 without reason
        if self._prev_job_title:
            if self._prev_job_title in ("AI 创业者", "创业者") and state.job_title == "待业中":
                if state.is_employed:  # still employed but title regressed?
                    violations.append(
                        f"[{year}] 职业标签从'{self._prev_job_title}'回退为'待业中'"
                    )

        self._prev_job_title = state.display_job_title
        self._prev_salary = state.monthly_salary


# ---------------------------------------------------------------------------
# Simulated game runner
# ---------------------------------------------------------------------------


def run_simulated_game(
    preset: int,
    gender: str,
    choices: dict[int, list[str]],
    violations: list[str],
    label: str,
) -> PlayerState:
    """Run a full simulated game with predetermined choices.

    Args:
        preset: Starting preset (1/2/3)
        gender: "male" or "female"
        choices: {year: [choice_key_1, choice_key_2, ...]}
        violations: List to append violations to
        label: Route label for error messages

    Returns:
        Final PlayerState
    """
    gender_enum = Gender.FEMALE if gender == "female" else Gender.MALE
    state = create_player(preset, gender_enum)
    initial_savings = state.savings
    job_tracker = JobTitleTracker()

    # Preset 3 init check
    if preset == 3:
        check_preset_3_init(state, violations)

    for year in range(YEAR_START, YEAR_END + 1):
        # Apply salary growth (skip first year)
        if year > YEAR_START:
            state, _ = state.apply_salary_growth()

        year_choices = choices.get(year, [])
        choice_idx = 0

        # Build events for this year
        events = build_year_events(year, state)
        if events is None:
            events = []

        for event in events:
            # Rebuild dynamic events
            event = rebuild_family_event_if_broke(event, state)

            # Check event applicability
            check_event_applicability(event, state, year, violations)

            # Filter choices for state
            event_choices = filter_choices_for_state(event.choices, state)
            valid_keys = [c.key.upper() for c in event_choices]

            # Get predetermined choice or default to first valid
            if choice_idx < len(year_choices):
                chosen = year_choices[choice_idx].upper()
                # If the predetermined choice is not valid, fall back to first valid
                if chosen not in valid_keys:
                    chosen = valid_keys[0] if valid_keys else "A"
            else:
                chosen = valid_keys[0] if valid_keys else "A"
            choice_idx += 1

            # Process the choice
            new_state, state_changes = process_choice(state, event, chosen)

            # Set flags
            new_state = set_flags_from_choice(new_state, event.template_id, chosen)

            state = new_state

        # Track job title changes
        job_tracker.check(state, year, violations)

        # Year-end state consistency check (before settlement)
        check_state_consistency(state, year, violations)

        # Settle year
        state = state.settle_year()

    # Reset year to YEAR_END for final checks (settle_year advances to 2026)
    if state.year > YEAR_END:
        state = state.model_copy(update={"year": YEAR_END})

    # Endgame achievement check
    from rerun.engine.achievements import apply_achievements
    state, _ = apply_achievements(state, initial_savings, endgame=True)
    check_achievement_consistency(state, violations)

    return state


# ---------------------------------------------------------------------------
# Test routes
# ---------------------------------------------------------------------------


ROUTE_A_CHOICES = {
    # 路线 A：穷小子梭哈线
    # 选项1(3万) → 梭哈BTC → 帮表妹(卖1个BTC) → 进入2016
    2015: ["A", "A", "A"],
    # 不买房, 低调
    2016: ["B", "A"],
    # 低调, 高兴, 稳住不卖
    2017: ["A", "A", "A"],
    # 接受裁员, 投身AI
    2018: ["A", "A"],
    # 大量囤口罩, 主动约
    2019: ["A", "A"],
    # 口罩英雄, 抄底, 同居
    2020: ["A", "A", "A"],
    # 不卖BTC, 同居/暗示结婚
    2021: ["C", "A"],
    # 坚定持有, 全力AI, 分享经验
    2022: ["A", "A", "A"],
    # 创业, 加仓
    2023: ["B", "A"],
    # 感慨, 做有意义的事
    2024: ["A", "A"],
    # 团圆
    2025: ["A"],
}

ROUTE_B_CHOICES = {
    # 路线 B：有房贷富裕线
    # 选项3(20万有房贷) → 1万试水 → 不帮 → 进入2016
    2015: ["B", "B", "A"],
    # 不买投资房(已有房), 低调
    2016: ["B", "A"],
    # 低调, 卖一部分, 稳住
    2017: ["A", "C", "A"],
    # 留下, 投身AI
    2018: ["C", "A"],
    # 少量囤口罩, 主动约
    2019: ["B", "A"],
    # 口罩英雄, 抄底, 同居
    2020: ["A", "A", "A"],
    # 卖50%, 求婚
    2021: ["B", "A"],
    # 买回来, 全力AI
    2022: ["A", "A"],
    # 接offer, 不加仓
    2023: ["A", "B"],
    # 感慨, 做有意义的事
    2024: ["A", "C"],
    # 团圆
    2025: ["A"],
}

ROUTE_C_CHOICES = {
    # 路线 C：不买BTC打工线
    # 选项1(3万) → 不买BTC → 帮表妹 → 进入2016
    2015: ["D", "A", "A"],
    # 买房(if affordable, else B), 低调
    2016: ["A", "A"],
    # 后悔买入, ...
    2017: ["A", "A"],
    # 留下, 不转AI
    2018: ["C", "B"],
    # 少量囤口罩, 主动约
    2019: ["B", "A"],
    # 口罩英雄, 不抄底, 同居
    2020: ["A", "B", "A"],
    # 不买BTC, 暗示结婚
    2021: ["B", "A"],
    # 观望, 全力AI
    2022: ["B", "A"],
    # 现在学AI, 不加仓
    2023: ["A", "B"],
    # 感慨
    2024: ["A", "A"],
    # 团圆
    2025: ["A"],
}


def test_route_a_consistency():
    """Route A: 穷小子梭哈线 — preset 1, male."""
    violations: list[str] = []
    state = run_simulated_game(
        preset=1, gender="male",
        choices=ROUTE_A_CHOICES,
        violations=violations,
        label="路线A-梭哈",
    )
    if violations:
        msg = f"路线A 发现 {len(violations)} 个问题:\n" + "\n".join(f"  · {v}" for v in violations)
        if pytest:
            pytest.fail(msg)
        else:
            raise AssertionError(msg)


def test_route_b_consistency():
    """Route B: 有房贷富裕线 — preset 3, female."""
    violations: list[str] = []
    state = run_simulated_game(
        preset=3, gender="female",
        choices=ROUTE_B_CHOICES,
        violations=violations,
        label="路线B-有房贷",
    )
    if violations:
        msg = f"路线B 发现 {len(violations)} 个问题:\n" + "\n".join(f"  · {v}" for v in violations)
        if pytest:
            pytest.fail(msg)
        else:
            raise AssertionError(msg)


def test_route_c_consistency():
    """Route C: 不买BTC打工线 — preset 1, male."""
    violations: list[str] = []
    state = run_simulated_game(
        preset=1, gender="male",
        choices=ROUTE_C_CHOICES,
        violations=violations,
        label="路线C-不买BTC",
    )
    if violations:
        msg = f"路线C 发现 {len(violations)} 个问题:\n" + "\n".join(f"  · {v}" for v in violations)
        if pytest:
            pytest.fail(msg)
        else:
            raise AssertionError(msg)


def test_preset_3_has_property():
    """Verify preset 3 starts with property and mortgage (F1)."""
    state = create_player(3, Gender.MALE)
    assert state.properties >= 1, "Preset 3 should start with a property"
    assert state.mortgage_monthly > 0, "Preset 3 should have mortgage payments"
    # Costs should show 房贷, not 房租
    costs = state.calculate_annual_costs()
    assert "房贷" in costs, "Preset 3 should show 房贷 in costs"
    assert "房租" not in costs, "Preset 3 should NOT show 房租 in costs"


def test_entrepreneur_has_income():
    """Verify entrepreneurs/freelancers count as having income (F2)."""
    state = PlayerState(
        is_employed=False,
        job_title="AI 创业者",
        monthly_salary=15000,
    )
    assert state.is_self_employed, "AI 创业者 should be self-employed"
    assert state.has_income, "AI 创业者 should have income"
    assert state.annual_salary_income > 0, "AI 创业者 annual income should be > 0"
    assert state.display_job_title == "AI 创业者", "Should show 创业者 not 待业中"


def test_achievement_mutual_exclusion():
    """Verify diamond_hands and paper_hands cannot both unlock (F6)."""
    # Player with diamond_hands already
    state = PlayerState(achievements=["diamond_hands"])
    newly = check_achievements(state, 30000, endgame=True)
    assert "paper_hands" not in newly, "paper_hands should not unlock when diamond_hands exists"


def test_no_buy_house_event_for_owner():
    """Verify players with property don't get 买房焦虑 (F4)."""
    state = create_player(3, Gender.FEMALE)  # preset 3 has property
    events = build_year_events(2016, state)
    assert events is not None
    for event in events:
        assert event.template_id != "2016_house_fomo", \
            "Player with property should not get 买房焦虑 event"


# Run as standalone script
if __name__ == "__main__":
    print("=" * 60)
    print("ReRun v0.5 — 状态一致性自动检查")
    print("=" * 60)

    all_violations: list[str] = []

    routes = [
        ("路线A-梭哈", 1, "male", ROUTE_A_CHOICES),
        ("路线B-有房贷", 3, "female", ROUTE_B_CHOICES),
        ("路线C-不买BTC", 1, "male", ROUTE_C_CHOICES),
    ]

    for label, preset, gender, choices in routes:
        violations: list[str] = []
        print(f"\n▶ {label} (preset={preset}, gender={gender})")
        try:
            state = run_simulated_game(
                preset=preset, gender=gender,
                choices=choices, violations=violations, label=label,
            )
            if violations:
                print(f"  ❌ {len(violations)} 个问题:")
                for v in violations:
                    print(f"    · {v}")
            else:
                print(f"  ✅ 通过! 最终净资产: ¥{state.net_worth:,.0f}")
        except Exception as e:
            violations.append(f"[CRASH] {label}: {e}")
            print(f"  💥 崩溃: {e}")
            import traceback
            traceback.print_exc()
        all_violations.extend(violations)

    print("\n" + "=" * 60)
    if all_violations:
        print(f"❌ 总计 {len(all_violations)} 个问题")
    else:
        print("✅ 所有规则检查通过！")
    print("=" * 60)
