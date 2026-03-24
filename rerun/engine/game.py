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
)
from rerun.engine.state import (
    YEAR_END,
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

    def init_player(self, preset: int) -> PlayerState:
        """Initialize player from a starting preset."""
        self.state = create_player(preset)
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
        """Generate all events for the current year."""
        year = self.state.year
        num_events = self.tracker.events_for_year(year)

        # Check stat triggers for forced categories
        triggers = check_stat_triggers(self.state)
        forced = get_forced_categories(triggers)

        events: list[GameEvent] = []
        for i in range(num_events):
            # First event: use forced category if available, otherwise normal
            exclude = self.tracker.exclude_categories
            if i == 0 and forced:
                # Try to generate from forced category
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

    def settle_year(self) -> YearEnd:
        """Settle the year-end: apply income/expense, advance year."""
        year_end = YearEnd(year=self.state.year, state=self.state)
        self.state = self.state.settle_year()
        self.state_history.append(self.state)
        return year_end

    def is_game_over(self) -> bool:
        """Check if the game has reached its final year."""
        return self.state.year > YEAR_END

    def get_ending(self) -> GameEnding:
        """Build the final settlement data."""
        duration = time.time() - self.start_time if self.start_time else 0.0
        return GameEnding(
            state=self.state,
            duration_seconds=duration,
            initial_savings=self.initial_savings,
            baseline_net_worth=NO_RERUN_BASELINE,
        )

    def reset(self) -> None:
        """Reset for a new run."""
        self.state = PlayerState()
        self.state_history = []
        self.tracker = EventTracker()
        self.start_time = 0.0
        self.initial_savings = 0.0
