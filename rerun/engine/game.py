"""Game engine — main loop, flow control, and state management."""

from __future__ import annotations

import time
from dataclasses import dataclass

from rerun.config import Settings
from rerun.engine.achievements import apply_achievements, get_achievement_display
from rerun.engine.choices import (
    check_stat_triggers,
    get_choice,
    get_forced_categories,
    process_choice,
)
from rerun.engine.events import (
    EventTracker,
    GameEvent,
    generate_fallback_event,
    get_year_background,
    get_year_context,
    select_events_from_pool,
)
from rerun.engine.state import (
    YEAR_END,
    Gender,
    PlayerState,
    create_player,
    get_btc_price,
)

# ---------------------------------------------------------------------------
# Game phases — data objects passed to the UI layer
# ---------------------------------------------------------------------------


@dataclass
class YearStart:
    """Data for rendering the year-start screen."""

    year: int
    state: PlayerState
    background: str
    btc_price: float
    year_context: dict


@dataclass
class EventPresentation:
    """Data for rendering an event + choices."""

    event: GameEvent
    stat_triggers: list  # StatTrigger objects


@dataclass
class ChoiceResult:
    """Data for rendering the aftermath of a choice."""

    event: GameEvent
    choice_key: str
    choice_text: str
    narrative: str
    hint: str
    state_changes: dict  # {field: (old, new)}
    new_state: PlayerState
    unlocked_achievements: list[str]


@dataclass
class YearEnd:
    """Data for rendering year-end summary."""

    year: int
    state: PlayerState


@dataclass
class GameEnding:
    """Data for rendering the final settlement screen."""

    state: PlayerState
    duration_seconds: float
    initial_savings: float
    baseline_net_worth: float  # what you'd have without rerun


# ---------------------------------------------------------------------------
# Game Engine
# ---------------------------------------------------------------------------

NO_RERUN_BASELINE = 450000.0  # 10 years of normal life


class GameEngine:
    """Core game engine — manages state, events, and flow.

    The engine is UI-agnostic. It yields phase objects that the UI layer
    renders. Input is collected via callback functions.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.state: PlayerState = PlayerState()
        self.state_history: list[PlayerState] = []
        self.tracker = EventTracker()
        self.start_time: float = 0.0
        self.initial_savings: float = 0.0
        self.reached_milestones: set[int] = set()

    def init_player(self, preset: int, gender: Gender = Gender.MALE) -> PlayerState:
        """Initialize player from a starting preset and gender."""
        self.state = create_player(preset, gender)
        self.initial_savings = self.state.savings
        self.state_history = [self.state]
        self.start_time = time.time()
        return self.state

    def get_year_start(self) -> YearStart:
        """Build the year-start presentation data."""
        year = self.state.year
        return YearStart(
            year=year,
            state=self.state,
            background=get_year_background(year),
            btc_price=get_btc_price(year),
            year_context=get_year_context(year),
        )

    def get_events_for_year(self) -> list[GameEvent]:
        """Generate events for the current year.

        Uses the year-based event pool system first (v0.2).
        Falls back to the legacy category-based system if no pool exists.
        """
        year = self.state.year

        # Try new pool-based system first
        pool_events = select_events_from_pool(
            year,
            self.state,
            used_ids=self.tracker.used_pool_ids,
            consecutive_negative_years=self.tracker.consecutive_negative_years,
        )

        if pool_events:
            return pool_events

        # Fallback to legacy system
        num_events = self.tracker.events_for_year(year)
        triggers = check_stat_triggers(self.state)
        forced = get_forced_categories(triggers)

        events: list[GameEvent] = []
        for i in range(num_events):
            exclude = self.tracker.exclude_categories
            if i == 0 and forced:
                event = generate_fallback_event(
                    year,
                    self.state,
                    exclude_categories=[c for c in exclude if c not in forced],
                    used_templates=self.tracker.used_templates,
                )
            else:
                event = generate_fallback_event(
                    year,
                    self.state,
                    exclude_categories=exclude,
                    used_templates=self.tracker.used_templates,
                )

            if event is not None:
                events.append(event)

        return events

    def present_event(self, event: GameEvent) -> EventPresentation:
        """Build the event presentation data."""
        triggers = check_stat_triggers(self.state)
        return EventPresentation(event=event, stat_triggers=triggers)

    def apply_choice(self, event: GameEvent, choice_key: str) -> ChoiceResult:
        """Process a choice and return the result for rendering."""
        choice = get_choice(event, choice_key)
        new_state, state_changes = process_choice(self.state, event, choice_key)

        # Track event in dedup tracker
        self.tracker.record(event, event.template_id or None)

        # Check achievements
        new_state, unlocked = apply_achievements(new_state, self.initial_savings)
        unlocked_display = [get_achievement_display(a) for a in unlocked]

        # Update engine state
        self.state = new_state
        self.state_history.append(self.state)

        return ChoiceResult(
            event=event,
            choice_key=choice_key,
            choice_text=choice.text if choice else "",
            narrative=choice.narrative if choice else "",
            hint=choice.hint if choice else "",
            state_changes=state_changes,
            new_state=new_state,
            unlocked_achievements=unlocked_display,
        )

    def settle_year(self, year_events: list[GameEvent] | None = None) -> YearEnd:
        """Settle the year-end: apply income/expense, advance year."""
        # Track year sentiment for consecutive negative year control
        if year_events:
            has_neg = any(e.template_id.startswith(f"{self.state.year}_") and
                         any(kw in e.template_id for kw in ("crash", "fomo", "ban", "scam",
                              "rent", "burnout", "layoff", "sick", "lost", "hack", "tax",
                              "anxiety", "fear", "pressure", "conflict"))
                         for e in year_events)
            has_pos = any(e.template_id.startswith(f"{self.state.year}_") and
                         any(kw in e.template_id for kw in ("bonus", "friend", "lottery",
                              "moon", "reunion", "wedding", "praise", "surprise", "mom",
                              "cooking", "halving", "btc", "happy", "warm", "celebrate"))
                         for e in year_events)
            self.tracker.record_year_sentiment(has_neg, has_pos)

        year_end = YearEnd(year=self.state.year, state=self.state)
        self.state = self.state.settle_year()
        self.state_history.append(self.state)
        return year_end

    def is_game_over(self) -> bool:
        """Check if the game has reached its final year."""
        return self.state.year > YEAR_END

    def is_bankrupt(self) -> bool:
        """Check if the player is bankrupt (net worth below zero)."""
        return self.state.savings < 0 and self.state.net_worth < 0

    def apply_bankruptcy_continue(self) -> None:
        """Reset to a low-income state for 'continue from bankruptcy' mode."""
        self.state = self.state.model_copy(update={
            "savings": 10000.0,
            "monthly_salary": 4500.0,
            "is_employed": True,
            "job_title": "小城打工人",
            "stress": 60,
        })

    def get_ending(self) -> GameEnding:
        """Build the final settlement data."""
        duration = time.time() - self.start_time if self.start_time else 0.0
        return GameEnding(
            state=self.state,
            duration_seconds=duration,
            initial_savings=self.initial_savings,
            baseline_net_worth=NO_RERUN_BASELINE,
        )

    def check_prophet(self) -> str | None:
        """Check if a prophet feedback should fire this year."""
        from rerun.engine.prophet import check_prophet_trigger
        return check_prophet_trigger(self.state.year, self.state)

    def check_milestone(self) -> str | None:
        """Check if a milestone celebration should fire."""
        from rerun.engine.prophet import check_milestone
        msg, self.reached_milestones = check_milestone(self.state, self.reached_milestones)
        return msg

    def reset(self) -> None:
        """Reset for a new run."""
        self.state = PlayerState()
        self.state_history = []
        self.tracker = EventTracker()
        self.start_time = 0.0
        self.initial_savings = 0.0
        self.reached_milestones = set()
