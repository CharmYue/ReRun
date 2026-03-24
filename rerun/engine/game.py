"""Game engine — main loop, flow control, and state management."""

from __future__ import annotations

import time
from dataclasses import dataclass

from rerun.config import Settings
from rerun.engine.achievements import apply_achievements, get_achievement_display
from rerun.engine.chains import LAYOFF_FORESHADOW_2017, check_chain_events, set_flags_from_choice
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

    def get_year_start(self) -> tuple[YearStart, float]:
        """Build the year-start presentation data. Also applies salary growth.

        Returns (YearStart, salary_raise_amount).
        """
        # Apply annual salary growth (skip first year)
        raise_amount = 0.0
        if self.state.year > 2015:
            self.state, raise_amount = self.state.apply_salary_growth()

        year = self.state.year
        return YearStart(
            year=year,
            state=self.state,
            background=get_year_background(year),
            btc_price=get_btc_price(year),
            year_context=get_year_context(year),
        ), raise_amount

    def get_events_for_year(self) -> list[GameEvent]:
        """Generate events for the current year.

        Priority: chain events (flag-driven) → pool events → legacy fallback.
        """
        year = self.state.year
        events: list[GameEvent] = []

        # Step 5: Chain events first (flag-driven follow-ups)
        chain_events = check_chain_events(self.state)
        events.extend(chain_events)

        # Pool-based events
        pool_events = select_events_from_pool(
            year,
            self.state,
            used_ids=self.tracker.used_pool_ids,
            consecutive_negative_years=self.tracker.consecutive_negative_years,
        )

        if pool_events:
            events.extend(pool_events)
            return events

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

        # Set event chain flags
        new_state = set_flags_from_choice(new_state, event.template_id, choice_key)

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

    def is_near_bankrupt(self) -> bool:
        """Check if savings < 0 but player still has liquidatable assets."""
        return (
            self.state.savings < 0
            and (self.state.btc_value > 0 or self.state.stocks > 0)
        )

    def is_truly_bankrupt(self) -> bool:
        """Check if player is bankrupt with no way out."""
        return self.state.savings < 0 and self.state.net_worth <= 0

    def apply_survival_sell_btc(self) -> float:
        """Sell minimum BTC needed to cover negative savings. Returns BTC sold."""
        if self.state.btc_amount <= 0:
            return 0.0
        btc_price = get_btc_price(self.state.year)
        needed = abs(self.state.savings) + 5000  # cover deficit + small buffer
        btc_to_sell = min(self.state.btc_amount, needed / btc_price if btc_price > 0 else 0)
        cny_received = btc_to_sell * btc_price
        self.state = self.state.apply_consequences({
            "savings": cny_received,
            "btc_amount": -btc_to_sell,
        })
        return btc_to_sell

    def apply_survival_move_home(self) -> None:
        """Move back to parents' home — drastically reduce expenses."""
        self.state = self.state.model_copy(update={
            "savings": max(self.state.savings, 0) + 2000,  # parents help a bit
            "monthly_expense": 1500.0,
            "stress": min(100, self.state.stress + 20),
            "relationship": min(100, self.state.relationship + 10),
        })

    def apply_survival_borrow(self) -> bool:
        """Try to borrow money from friends. Requires network >= 3. Returns success."""
        if self.state.network < 3:
            return False
        borrow_amount = abs(self.state.savings) + 10000
        self.state = self.state.apply_consequences({
            "savings": borrow_amount,
            "social": -15,
            "stress": 15,
        })
        return True

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
        """Build the final settlement data. Also checks endgame achievements."""
        # Check endgame-only achievements now
        self.state, _ = apply_achievements(self.state, self.initial_savings, endgame=True)

        duration = time.time() - self.start_time if self.start_time else 0.0
        return GameEnding(
            state=self.state,
            duration_seconds=duration,
            initial_savings=self.initial_savings,
            baseline_net_worth=NO_RERUN_BASELINE,
        )

    def get_foreshadow(self) -> str | None:
        """Get any foreshadowing text for the current year."""
        if self.state.year == 2017 and self.state.is_employed:
            return LAYOFF_FORESHADOW_2017
        return None

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
