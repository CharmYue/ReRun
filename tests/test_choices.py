"""Tests for rerun.engine.choices — choice processing, BTC ops, stat triggers."""

from rerun.engine.choices import (
    StatTrigger,
    buy_btc,
    check_stat_triggers,
    get_choice,
    get_forced_categories,
    get_valid_keys,
    process_choice,
    sell_all_btc,
    sell_btc,
    validate_choice,
)
from rerun.engine.events import Choice, GameEvent
from rerun.engine.state import PlayerState, get_btc_price


def _make_event(year=2017) -> GameEvent:
    return GameEvent(
        year=year,
        type="life",
        category="family",
        title="Test Event",
        description="Something happened.",
        choices=[
            Choice(
                key="A",
                text="Help",
                hint="hint A",
                consequences={"savings": -50000, "relationship": 15},
                narrative="You helped.",
            ),
            Choice(
                key="B",
                text="Ignore",
                hint="hint B",
                consequences={"relationship": -20, "stress": 10},
                narrative="You ignored.",
            ),
        ],
    )


class TestInputValidation:
    def test_valid_keys(self):
        event = _make_event()
        assert get_valid_keys(event) == ["A", "B"]

    def test_validate_choice_valid(self):
        event = _make_event()
        assert validate_choice(event, "a") == "A"
        assert validate_choice(event, "B") == "B"
        assert validate_choice(event, " a ") == "A"

    def test_validate_choice_invalid(self):
        event = _make_event()
        assert validate_choice(event, "C") is None
        assert validate_choice(event, "") is None
        assert validate_choice(event, "xyz") is None

    def test_get_choice(self):
        event = _make_event()
        c = get_choice(event, "a")
        assert c is not None
        assert c.text == "Help"
        assert get_choice(event, "Z") is None


class TestProcessChoice:
    def test_applies_consequences(self):
        state = PlayerState(savings=80000, relationship=50)
        event = _make_event()
        new_state, changes = process_choice(state, event, "A")
        assert new_state.savings == 30000
        assert new_state.relationship == 65
        assert state.savings == 80000  # original unchanged

    def test_returns_state_changes(self):
        state = PlayerState(savings=80000, relationship=50)
        event = _make_event()
        _, changes = process_choice(state, event, "A")
        assert "savings" in changes
        assert changes["savings"] == (80000.0, 30000.0)
        assert "relationship" in changes
        assert changes["relationship"] == (50, 65)

    def test_records_choice_in_log(self):
        state = PlayerState()
        event = _make_event()
        new_state, _ = process_choice(state, event, "B")
        assert len(new_state.choices_log) == 1
        assert new_state.choices_log[0]["choice_key"] == "B"
        assert new_state.choices_log[0]["event_title"] == "Test Event"

    def test_invalid_key_returns_unchanged(self):
        state = PlayerState()
        event = _make_event()
        new_state, changes = process_choice(state, event, "Z")
        assert new_state == state
        assert changes == {}


class TestBTCOperations:
    def test_buy_btc(self):
        state = PlayerState(year=2015, savings=80000, btc_amount=0)
        # BTC price 2015 = 1800
        new_state = buy_btc(state, 18000)
        assert new_state.btc_amount == 10.0
        assert new_state.savings == 62000.0

    def test_buy_btc_cant_exceed_savings(self):
        state = PlayerState(year=2015, savings=10000, btc_amount=0)
        new_state = buy_btc(state, 50000)  # wants to spend 50k but only has 10k
        assert new_state.savings == 0.0
        expected_btc = 10000 / 1800
        assert abs(new_state.btc_amount - expected_btc) < 0.001

    def test_buy_btc_zero_amount(self):
        state = PlayerState(savings=80000)
        new_state = buy_btc(state, 0)
        assert new_state == state

    def test_sell_btc(self):
        state = PlayerState(year=2017, savings=0, btc_amount=10.0)
        # BTC price 2017 = 100,000
        new_state = sell_btc(state, 2.0)
        assert new_state.btc_amount == 8.0
        assert new_state.savings == 200000.0
        assert new_state.times_sold_btc == 1

    def test_sell_btc_cant_exceed_holdings(self):
        state = PlayerState(year=2017, savings=0, btc_amount=5.0)
        new_state = sell_btc(state, 10.0)
        assert new_state.btc_amount == 0.0
        assert new_state.savings == 500000.0

    def test_sell_all_btc(self):
        state = PlayerState(year=2021, savings=0, btc_amount=3.0)
        new_state = sell_all_btc(state)
        assert new_state.btc_amount == 0.0
        assert new_state.savings == 3.0 * get_btc_price(2021)

    def test_buy_then_sell_roundtrip(self):
        state = PlayerState(year=2015, savings=18000, btc_amount=0)
        state2 = buy_btc(state, 18000)
        assert state2.btc_amount == 10.0
        assert state2.savings == 0.0
        # Sell in same year — should get same money back
        state3 = sell_btc(state2, 10.0)
        assert state3.savings == 18000.0
        assert state3.btc_amount == 0.0


class TestStatTriggers:
    def test_stress_warning(self):
        state = PlayerState(stress=85)
        triggers = check_stat_triggers(state)
        assert any(t.stat == "stress" for t in triggers)

    def test_no_triggers_normal_state(self):
        state = PlayerState()  # defaults are all in safe range
        triggers = check_stat_triggers(state)
        assert triggers == []

    def test_relationship_crisis(self):
        state = PlayerState(relationship=15)
        triggers = check_stat_triggers(state)
        assert any(t.stat == "relationship" and t.trigger_type == "event" for t in triggers)

    def test_social_opportunity(self):
        state = PlayerState(social=75)
        triggers = check_stat_triggers(state)
        assert any(t.stat == "social" for t in triggers)

    def test_reputation_opportunity(self):
        state = PlayerState(reputation=85)
        triggers = check_stat_triggers(state)
        assert any(t.stat == "reputation" for t in triggers)

    def test_multiple_triggers(self):
        state = PlayerState(stress=90, relationship=10)
        triggers = check_stat_triggers(state)
        assert len(triggers) >= 2

    def test_get_forced_categories(self):
        triggers = [
            StatTrigger("relationship", "event", "relationship_warning"),
            StatTrigger("stress", "warning", "stress_warning"),
            StatTrigger("social", "event", "social_opportunity"),
        ]
        forced = get_forced_categories(triggers)
        assert "family" in forced
        assert "social" in forced
        assert len(forced) == 2  # stress is warning, not event
