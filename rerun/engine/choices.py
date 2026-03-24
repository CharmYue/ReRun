"""Choice system — input handling, consequence processing, BTC operations, stat triggers."""

from __future__ import annotations

from rerun.engine.events import GameEvent
from rerun.engine.state import PlayerState, get_btc_price

# ---------------------------------------------------------------------------
# Choice input validation
# ---------------------------------------------------------------------------


def get_valid_keys(event: GameEvent) -> list[str]:
    """Return the list of valid choice keys for an event."""
    return [c.key.upper() for c in event.choices]


def validate_choice(event: GameEvent, user_input: str) -> str | None:
    """Validate user input against event choices.

    Returns the normalized key (uppercase) if valid, None otherwise.
    """
    key = user_input.strip().upper()
    if key in get_valid_keys(event):
        return key
    return None


def get_choice(event: GameEvent, key: str):
    """Get the Choice object by key."""
    key = key.upper()
    for c in event.choices:
        if c.key.upper() == key:
            return c
    return None


# ---------------------------------------------------------------------------
# Consequence processing — the full pipeline
# ---------------------------------------------------------------------------


def process_choice(
    state: PlayerState,
    event: GameEvent,
    choice_key: str,
) -> tuple[PlayerState, dict]:
    """Process a player's choice and return (new_state, state_changes).

    Returns:
        new_state: The updated PlayerState after applying consequences.
        state_changes: Dict of {field: (old_value, new_value)} for display.
    """
    choice = get_choice(event, choice_key)
    if choice is None:
        return state, {}

    consequences = choice.consequences

    # Snapshot old values for change display
    old_values = {}
    for key in consequences:
        if hasattr(state, key):
            old_values[key] = getattr(state, key)

    # Apply consequences
    new_state = state.apply_consequences(consequences)

    # Track family help
    if event.category == "family" and consequences.get("times_helped_family", 0) > 0:
        pass  # already tracked in apply_consequences

    # Record the choice
    new_state = new_state.record_choice(
        year=event.year,
        event_title=event.title,
        choice_key=choice_key,
        choice_text=choice.text,
        consequences=consequences,
    )

    # Build state changes for display
    state_changes = {}
    for key in consequences:
        if hasattr(new_state, key):
            new_val = getattr(new_state, key)
            old_val = old_values.get(key, new_val)
            if old_val != new_val:
                state_changes[key] = (old_val, new_val)

    return new_state, state_changes


# ---------------------------------------------------------------------------
# BTC buy/sell operations
# ---------------------------------------------------------------------------


def buy_btc(state: PlayerState, amount_cny: float) -> PlayerState:
    """Buy BTC with CNY from savings.

    Args:
        state: Current player state.
        amount_cny: Amount in CNY to spend on BTC.

    Returns:
        New PlayerState with updated savings and btc_amount.
    """
    price = get_btc_price(state.year)
    if price <= 0 or amount_cny <= 0:
        return state
    amount_cny = min(amount_cny, state.savings)  # can't spend more than you have
    btc_bought = amount_cny / price
    return state.apply_consequences(
        {
            "savings": -amount_cny,
            "btc_amount": btc_bought,
        }
    )


def sell_btc(state: PlayerState, btc_count: float) -> PlayerState:
    """Sell BTC for CNY.

    Args:
        state: Current player state.
        btc_count: Number of BTC to sell.

    Returns:
        New PlayerState with updated savings and btc_amount.
    """
    price = get_btc_price(state.year)
    if price <= 0 or btc_count <= 0:
        return state
    btc_count = min(btc_count, state.btc_amount)  # can't sell more than you hold
    cny_received = btc_count * price
    return state.apply_consequences(
        {
            "savings": cny_received,
            "btc_amount": -btc_count,
        }
    )


def sell_all_btc(state: PlayerState) -> PlayerState:
    """Sell all BTC holdings."""
    return sell_btc(state, state.btc_amount)


# ---------------------------------------------------------------------------
# Hidden stat triggers — check if thresholds are hit
# ---------------------------------------------------------------------------


class StatTrigger:
    """Describes a triggered condition from hidden stats."""

    def __init__(self, stat: str, trigger_type: str, message: str) -> None:
        self.stat = stat
        self.trigger_type = trigger_type  # "warning" or "event"
        self.message = message


def check_stat_triggers(state: PlayerState) -> list[StatTrigger]:
    """Check hidden stat thresholds and return any triggers.

    These triggers inform the game engine to:
    - Show warnings to the player
    - Force-generate certain event types next year
    """
    triggers: list[StatTrigger] = []

    # Stress > 80 → health event risk
    if state.stress > 80:
        triggers.append(
            StatTrigger(
                stat="stress",
                trigger_type="warning",
                message="stress_warning",
            )
        )

    # Relationship < 20 → breakup / family conflict risk
    if state.relationship < 20:
        triggers.append(
            StatTrigger(
                stat="relationship",
                trigger_type="event",
                message="relationship_warning",
            )
        )

    # Social > 70 → beneficial connections
    if state.social > 70:
        triggers.append(
            StatTrigger(
                stat="social",
                trigger_type="event",
                message="social_opportunity",
            )
        )

    # Reputation > 80 → opportunities find you
    if state.reputation > 80:
        triggers.append(
            StatTrigger(
                stat="reputation",
                trigger_type="event",
                message="reputation_opportunity",
            )
        )

    return triggers


def get_forced_categories(triggers: list[StatTrigger]) -> list[str]:
    """Extract event categories that should be forced based on triggers."""
    forced = []
    for t in triggers:
        if t.trigger_type != "event":
            continue
        if t.stat == "relationship":
            forced.append("family")
        elif t.stat == "social":
            forced.append("social")
        elif t.stat == "reputation":
            forced.append("career")
    return forced
