"""Tests for rerun.engine.game — game engine flow."""

from rerun.config import get_settings
from rerun.engine.game import NO_RERUN_BASELINE, GameEngine


def _make_engine() -> GameEngine:
    settings = get_settings(openai_api_key="")  # offline
    return GameEngine(settings)


class TestGameInit:
    def test_init_player(self):
        engine = _make_engine()
        state = engine.init_player(2)
        assert state.year == 2015
        assert state.savings == 80000.0
        assert engine.initial_savings == 80000.0
        assert len(engine.state_history) == 1

    def test_init_player_preset_1(self):
        engine = _make_engine()
        state = engine.init_player(1)
        assert state.savings == 30000.0
        assert state.job_title == "应届毕业生"


class TestYearStart:
    def test_year_start_data(self):
        engine = _make_engine()
        engine.init_player(2)
        ys, salary_raise = engine.get_year_start()
        assert ys.year == 2015
        assert ys.btc_price == 1800
        assert ys.background != ""
        assert ys.state.savings == 80000.0
        assert salary_raise == 0.0  # no raise in first year


class TestEventGeneration:
    def test_generates_events(self):
        engine = _make_engine()
        engine.init_player(2)
        events = engine.get_events_for_year()
        assert len(events) >= 1
        assert events[0].year == 2015

    def test_boss_year_more_events(self):
        engine = _make_engine()
        engine.init_player(2)
        # Advance to 2018 (boss year)
        engine.state = engine.state.model_copy(update={"year": 2018})
        events = engine.get_events_for_year()
        assert len(events) >= 2  # boss years guarantee at least 2 events


class TestChoiceProcessing:
    def test_apply_choice(self):
        engine = _make_engine()
        engine.init_player(2)
        events = engine.get_events_for_year()
        assert len(events) >= 1

        event = events[0]
        choice_key = event.choices[0].key
        result = engine.apply_choice(event, choice_key)

        assert result.choice_key == choice_key
        assert result.new_state is engine.state
        assert len(engine.state_history) >= 2

    def test_choice_result_has_narrative(self):
        engine = _make_engine()
        engine.init_player(2)
        events = engine.get_events_for_year()
        event = events[0]
        result = engine.apply_choice(event, event.choices[0].key)
        assert result.narrative != ""


class TestYearSettlement:
    def test_settle_year(self):
        engine = _make_engine()
        engine.init_player(2)
        # salary=8000, expense=5000, annual_net = 36000
        year_end = engine.settle_year()
        assert year_end.year == 2015
        assert engine.state.year == 2016
        assert engine.state.savings == 80000 + 36000


class TestGameFlow:
    def test_full_run_offline(self):
        """Simulate a complete 10-year run in offline mode."""
        engine = _make_engine()
        engine.init_player(2)

        years_played = 0
        while not engine.is_game_over():
            # Year start
            ys, _ = engine.get_year_start()
            assert ys.year == engine.state.year

            # Events
            events = engine.get_events_for_year()
            for event in events:
                presentation = engine.present_event(event)
                assert presentation.event is event

                # Auto-pick first choice
                result = engine.apply_choice(event, event.choices[0].key)
                assert result.new_state is engine.state

            # Settle year
            engine.settle_year()
            years_played += 1

        assert years_played == 11  # 2015 through 2025
        assert engine.state.year == 2026

        # Ending
        ending = engine.get_ending()
        assert ending.initial_savings == 80000.0
        assert ending.baseline_net_worth == NO_RERUN_BASELINE
        assert ending.duration_seconds >= 0

    def test_reset(self):
        engine = _make_engine()
        engine.init_player(2)
        engine.settle_year()
        assert engine.state.year == 2016

        engine.reset()
        assert engine.state.year == 2015
        assert engine.state_history == []
        assert engine.initial_savings == 0.0


class TestGameOver:
    def test_not_over_at_start(self):
        engine = _make_engine()
        engine.init_player(2)
        assert not engine.is_game_over()

    def test_over_after_2025(self):
        engine = _make_engine()
        engine.init_player(2)
        engine.state = engine.state.model_copy(update={"year": 2026})
        assert engine.is_game_over()
