"""Tests for rerun.engine.events — event system."""

from rerun.engine.events import (
    Choice,
    EventTracker,
    GameEvent,
    generate_fallback_event,
    get_historical_events,
    get_year_background,
    get_year_context,
    is_boss_year,
)
from rerun.engine.state import PlayerState


class TestHistoricalData:
    def test_year_context_has_btc_price(self):
        ctx = get_year_context(2017)
        assert "btc_price" in ctx
        assert ctx["btc_price"]["start"] == 7000

    def test_year_background_nonempty(self):
        bg = get_year_background(2020)
        assert "COVID" in bg or "疫情" in bg or "Boss" in bg

    def test_historical_events_exist(self):
        events = get_historical_events(2018)
        assert len(events) >= 2
        assert any("BTC" in e["title"] or "崩" in e["title"] for e in events)

    def test_all_years_have_data(self):
        for year in range(2015, 2026):
            ctx = get_year_context(year)
            assert ctx, f"No data for {year}"
            assert "btc_price" in ctx
            assert "background" in ctx

    def test_unknown_year_returns_empty(self):
        ctx = get_year_context(2000)
        assert ctx == {}


class TestGameEventModel:
    def test_create_event(self):
        event = GameEvent(
            year=2017,
            type="life",
            category="family",
            title="Test",
            description="Test desc",
            choices=[
                Choice(
                    key="A",
                    text="Do it",
                    hint="hint",
                    consequences={"savings": -10000},
                    narrative="You did it.",
                )
            ],
        )
        assert event.year == 2017
        assert len(event.choices) == 1
        assert event.choices[0].consequences["savings"] == -10000


class TestFallbackGeneration:
    def test_generates_event(self):
        state = PlayerState()
        event = generate_fallback_event(2016, state)
        assert event is not None
        assert event.year == 2016
        assert event.type == "life"
        assert len(event.choices) >= 2

    def test_excludes_categories(self):
        state = PlayerState()
        # Exclude all but accident
        event = generate_fallback_event(
            2016,
            state,
            exclude_categories=["family", "romance", "career", "social"],
        )
        assert event is not None
        assert event.category == "accident"

    def test_respects_used_templates(self):
        state = PlayerState()
        used = set()
        generated_categories = set()
        # Generate many events, track uniqueness
        for _ in range(10):
            event = generate_fallback_event(2017, state, used_templates=used)
            if event is None:
                break
            used.add(event.title)  # titles are unique per template
            generated_categories.add(event.category)
        # Should have generated from multiple categories
        assert len(generated_categories) >= 2

    def test_romance_filter_no_partner(self):
        state = PlayerState(has_partner=False)
        # partner_conflict and marriage_pressure should be excluded
        for _ in range(20):
            event = generate_fallback_event(
                2017,
                state,
                exclude_categories=["family", "career", "social", "accident"],
            )
            if event is not None:
                assert event.title != "伴侣对你的投资行为不满"
                assert event.title != "到了谈婚论嫁的阶段"

    def test_romance_filter_has_partner(self):
        state = PlayerState(has_partner=True)
        # meet_someone should be excluded when has_partner
        for _ in range(20):
            event = generate_fallback_event(
                2017,
                state,
                exclude_categories=["family", "career", "social", "accident"],
            )
            if event is not None:
                assert event.title != "遇到了一个不错的人"

    def test_returns_none_when_exhausted(self):
        state = PlayerState()
        # Use all templates
        all_templates = set()
        for _ in range(20):
            event = generate_fallback_event(2017, state, used_templates=all_templates)
            if event is None:
                break
            all_templates.add(event.template_id)
        # Eventually should return None
        event = generate_fallback_event(2017, state, used_templates=all_templates)
        assert event is None


class TestEventTracker:
    def test_exclude_recent(self):
        tracker = EventTracker()
        event = GameEvent(
            year=2016,
            type="life",
            category="family",
            title="t",
            description="d",
            choices=[Choice(key="A", text="x", hint="h", consequences={}, narrative="n")],
        )
        tracker.record(event, "parent_sick")
        assert "family" in tracker.exclude_categories
        assert "parent_sick" in tracker.used_templates

    def test_events_for_year(self):
        tracker = EventTracker()
        assert tracker.events_for_year(2015) == 1
        assert tracker.events_for_year(2018) == 2  # boss year
        assert tracker.events_for_year(2020) == 2  # boss year
        assert tracker.events_for_year(2022) == 2  # boss year
        assert tracker.events_for_year(2019) == 1


class TestBossYears:
    def test_boss_years(self):
        assert is_boss_year(2018)
        assert is_boss_year(2020)
        assert is_boss_year(2022)
        assert not is_boss_year(2017)
        assert not is_boss_year(2021)
