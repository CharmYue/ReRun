"""Tests for the achievement system."""

from rerun.engine.achievements import (
    apply_achievements,
    check_achievements,
    get_achievement_display,
)
from rerun.engine.state import PlayerState


def _make_state(**overrides) -> PlayerState:
    """Create a PlayerState with overrides for testing."""
    return PlayerState(**overrides)


# ---------------------------------------------------------------------------
# get_achievement_display
# ---------------------------------------------------------------------------


def test_display_known_achievement():
    text = get_achievement_display("diamond_hands", lang="cn")
    assert "钻石手" in text
    assert "💎" in text


def test_display_unknown_achievement():
    assert get_achievement_display("nonexistent") == "nonexistent"


# ---------------------------------------------------------------------------
# Individual checker tests
# ---------------------------------------------------------------------------


def test_clown_lost_money():
    state = _make_state(savings=10_000, year=2025)
    unlocked = check_achievements(state, initial_savings=80_000)
    assert "clown" in unlocked


def test_clown_not_triggered_when_rich():
    state = _make_state(savings=200_000, year=2025)
    unlocked = check_achievements(state, initial_savings=80_000)
    assert "clown" not in unlocked


def test_landlord():
    state = _make_state(properties=3)
    unlocked = check_achievements(state, initial_savings=80_000)
    assert "landlord" in unlocked


def test_landlord_not_enough():
    state = _make_state(properties=2)
    unlocked = check_achievements(state, initial_savings=80_000)
    assert "landlord" not in unlocked


def test_tenbagger():
    state = _make_state(savings=800_000)
    unlocked = check_achievements(state, initial_savings=80_000)
    assert "tenbagger" in unlocked


def test_paper_hands():
    state = _make_state(times_sold_btc=3)
    unlocked = check_achievements(state, initial_savings=80_000)
    assert "paper_hands" in unlocked


def test_bottom_fisher():
    state = _make_state(
        choices_log=[
            {
                "year": 2018,
                "event_title": "buy btc",
                "choice_text": "buy",
                "consequences": {"btc_amount": 1},
            }
        ]
    )
    unlocked = check_achievements(state, initial_savings=80_000)
    assert "bottom_fisher" in unlocked


def test_life_winner():
    state = _make_state(savings=6_000_000, has_partner=True, relationship=80)
    unlocked = check_achievements(state, initial_savings=80_000)
    assert "life_winner" in unlocked


def test_life_winner_missing_partner():
    state = _make_state(savings=6_000_000, has_partner=False, relationship=80)
    unlocked = check_achievements(state, initial_savings=80_000)
    assert "life_winner" not in unlocked


def test_heartbreaker():
    state = _make_state(breakups=2)
    unlocked = check_achievements(state, initial_savings=80_000)
    assert "heartbreaker" in unlocked


def test_zen_master():
    state = _make_state(stress=30)
    unlocked = check_achievements(state, initial_savings=80_000)
    assert "zen_master" in unlocked


def test_regret():
    state = _make_state(savings=100_000, year=2025)
    unlocked = check_achievements(state, initial_savings=80_000)
    assert "regret" in unlocked


def test_filial_child():
    state = _make_state(times_helped_family=2)
    unlocked = check_achievements(state, initial_savings=80_000)
    assert "filial_child" in unlocked


def test_lone_wolf():
    state = _make_state(has_partner=False, social=20)
    unlocked = check_achievements(state, initial_savings=80_000)
    assert "lone_wolf" in unlocked


def test_exposed():
    state = _make_state(reputation=95)
    unlocked = check_achievements(state, initial_savings=80_000)
    assert "exposed" in unlocked


def test_storyteller():
    log = [
        {"year": 2015 + i, "event_title": f"event_{i}", "choice_text": "a", "consequences": {}}
        for i in range(8)
    ]
    state = _make_state(choices_log=log)
    unlocked = check_achievements(state, initial_savings=80_000)
    assert "storyteller" in unlocked


def test_diamond_hands():
    log = [
        {"year": 2018, "event_title": "crash", "choice_text": "hold", "consequences": {}},
    ]
    state = _make_state(btc_amount=1.0, max_btc_held=2.0, choices_log=log)
    unlocked = check_achievements(state, initial_savings=80_000)
    assert "diamond_hands" in unlocked


def test_diamond_hands_sold():
    log = [
        {
            "year": 2018,
            "event_title": "crash",
            "choice_text": "sell",
            "consequences": {"btc_amount": -1},
        },
    ]
    state = _make_state(btc_amount=0, max_btc_held=2.0, choices_log=log)
    unlocked = check_achievements(state, initial_savings=80_000)
    assert "diamond_hands" not in unlocked


# ---------------------------------------------------------------------------
# apply_achievements
# ---------------------------------------------------------------------------


def test_apply_achievements_unlocks():
    state = _make_state(properties=3)
    new_state, unlocked = apply_achievements(state, initial_savings=80_000)
    assert "landlord" in unlocked
    assert "landlord" in new_state.achievements


def test_apply_achievements_no_duplicate():
    state = _make_state(properties=3, achievements=["landlord"])
    new_state, unlocked = apply_achievements(state, initial_savings=80_000)
    assert "landlord" not in unlocked
    assert new_state.achievements.count("landlord") == 1


def test_apply_achievements_multiple():
    state = _make_state(properties=3, reputation=95, stress=30)
    new_state, unlocked = apply_achievements(state, initial_savings=80_000)
    assert "landlord" in unlocked
    assert "exposed" in unlocked
    assert "zen_master" in unlocked
