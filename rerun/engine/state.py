"""Game state data models — the core of ReRun's state machine."""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Historical price tables (real data, used for net_worth calculation)
# Will also be in historical_events.json — duplicated here as constants
# so state.py has zero file I/O dependencies.
# ---------------------------------------------------------------------------

BTC_PRICE_BY_YEAR: dict[int, float] = {
    2015: 1800,
    2016: 4500,
    2017: 100000,
    2018: 25000,
    2019: 50000,
    2020: 60000,
    2021: 300000,
    2022: 120000,
    2023: 200000,
    2024: 500000,
    2025: 700000,
}

# Average property price per unit (one "套", ~90sqm, tier-2 city baseline)
PROPERTY_PRICE_BY_YEAR: dict[int, float] = {
    2015: 900000,
    2016: 1100000,
    2017: 1400000,
    2018: 1500000,
    2019: 1500000,
    2020: 1600000,
    2021: 1800000,
    2022: 1700000,
    2023: 1600000,
    2024: 1500000,
    2025: 1500000,
}

YEAR_START = 2015
YEAR_END = 2025


def get_btc_price(year: int) -> float:
    return BTC_PRICE_BY_YEAR.get(year, 0.0)


def get_property_price(year: int) -> float:
    return PROPERTY_PRICE_BY_YEAR.get(year, 0.0)


# ---------------------------------------------------------------------------
# Player State
# ---------------------------------------------------------------------------


class PlayerState(BaseModel):
    """Complete snapshot of a player's state at a point in time.

    Immutable by convention — use `apply_consequences` to derive a new state.
    """

    # --- Timeline ---
    year: int = YEAR_START

    # --- Visible assets ---
    savings: float = 80000.0
    btc_amount: float = 0.0
    properties: int = 0
    stocks: float = 0.0

    # --- Hidden stats (influence event triggers) ---
    stress: int = 20
    relationship: int = 50
    social: int = 50
    reputation: int = 30

    # --- Life status ---
    has_partner: bool = False
    is_employed: bool = True
    job_title: str = "普通上班族"
    monthly_salary: float = 8000.0
    monthly_expense: float = 5000.0

    # --- Records (for achievements & ending review) ---
    choices_log: list[dict] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    max_btc_held: float = 0.0
    times_sold_btc: int = 0
    times_helped_family: int = 0
    breakups: int = 0

    # --- Derived values ---

    @property
    def net_worth(self) -> float:
        """Total net worth based on current year's market prices."""
        btc_value = self.btc_amount * get_btc_price(self.year)
        property_value = self.properties * get_property_price(self.year)
        return self.savings + btc_value + property_value + self.stocks

    @property
    def btc_value(self) -> float:
        return self.btc_amount * get_btc_price(self.year)

    @property
    def property_value(self) -> float:
        return self.properties * get_property_price(self.year)

    @property
    def annual_net_income(self) -> float:
        """Yearly income after expenses (12 months)."""
        if not self.is_employed:
            return -self.monthly_expense * 12
        return (self.monthly_salary - self.monthly_expense) * 12

    # --- State transitions ---

    def apply_consequences(self, consequences: dict) -> PlayerState:
        """Return a NEW PlayerState with consequences applied.

        `consequences` is a dict like {"savings": -50000, "stress": 20, ...}.
        Numeric fields are added (delta), bool/str fields are replaced.
        """
        updates: dict = {}
        for key, value in consequences.items():
            if not hasattr(self, key):
                continue
            current = getattr(self, key)
            # bool is subclass of int — check bool first to avoid treating True as 1
            if isinstance(current, bool) or isinstance(value, bool):
                updates[key] = value
                continue
            if isinstance(current, (int, float)) and isinstance(value, (int, float)):
                new_val = current + value
                # Clamp 0-100 stats
                if key in ("stress", "relationship", "social", "reputation"):
                    new_val = max(0, min(100, int(new_val)))
                # Savings can go negative (debt), but btc/properties can't
                if key in ("btc_amount", "properties", "stocks"):
                    new_val = max(0, new_val)
                updates[key] = new_val
            else:
                # Bool / str fields: direct replacement
                updates[key] = value

        new_state = self.model_copy(update=updates)

        # Track max BTC held
        if new_state.btc_amount > new_state.max_btc_held:
            new_state = new_state.model_copy(update={"max_btc_held": new_state.btc_amount})

        # Track BTC sell count
        if new_state.btc_amount < self.btc_amount:
            new_state = new_state.model_copy(
                update={"times_sold_btc": new_state.times_sold_btc + 1}
            )

        return new_state

    def record_choice(
        self, year: int, event_title: str, choice_key: str, choice_text: str, consequences: dict
    ) -> PlayerState:
        """Return a new state with the choice appended to choices_log."""
        entry = {
            "year": year,
            "event_title": event_title,
            "choice_key": choice_key,
            "choice_text": choice_text,
            "consequences": consequences,
        }
        new_log = [*self.choices_log, entry]
        return self.model_copy(update={"choices_log": new_log})

    def settle_year(self) -> PlayerState:
        """Apply annual salary/expense settlement and advance to next year."""
        new_savings = self.savings + self.annual_net_income
        return self.model_copy(
            update={
                "savings": new_savings,
                "year": self.year + 1,
            }
        )

    def unlock_achievement(self, achievement_id: str) -> PlayerState:
        """Unlock an achievement if not already unlocked. Returns new state."""
        if achievement_id in self.achievements:
            return self
        new_achievements = [*self.achievements, achievement_id]
        return self.model_copy(update={"achievements": new_achievements})


# ---------------------------------------------------------------------------
# Starting presets
# ---------------------------------------------------------------------------

STARTING_PRESETS: dict[int, dict] = {
    1: {
        "savings": 30000.0,
        "monthly_salary": 5000.0,
        "monthly_expense": 3500.0,
        "job_title": "应届毕业生",
    },
    2: {
        "savings": 80000.0,
        "monthly_salary": 8000.0,
        "monthly_expense": 5000.0,
        "job_title": "普通上班族",
    },
    3: {
        "savings": 200000.0,
        "monthly_salary": 15000.0,
        "monthly_expense": 10000.0,
        "job_title": "小有成就的白领",
        "has_partner": True,
        "relationship": 60,
    },
}


def create_player(preset: int) -> PlayerState:
    """Create a PlayerState from a starting preset (1/2/3)."""
    overrides = STARTING_PRESETS.get(preset, STARTING_PRESETS[2])
    return PlayerState(**overrides)
