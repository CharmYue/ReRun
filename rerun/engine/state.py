"""Game state data models — the core of ReRun's state machine."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Gender(str, Enum):
    """Player gender — affects event text and some event availability."""

    MALE = "male"
    FEMALE = "female"

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

    # --- Identity ---
    gender: Gender = Gender.MALE

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

    # --- Skills (1-5, influence available options and events) ---
    investment_iq: int = 1   # 投资认知
    career_level: int = 1    # 职业能力
    network: int = 1         # 人脉圈层
    emotional_iq: int = 1    # 情商

    # --- Life status ---
    has_partner: bool = False
    has_child: bool = False
    is_employed: bool = True
    job_title: str = "普通上班族"
    monthly_salary: float = 8000.0
    monthly_expense: float = 5000.0
    mortgage_monthly: float = 0.0  # monthly mortgage payment (0 = no mortgage)

    # --- Event chain flags ---
    flags: dict = Field(default_factory=dict)

    # --- Records (for achievements & ending review) ---
    choices_log: list[dict] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    max_btc_held: float = 0.0
    times_sold_btc: int = 0
    times_helped_family: int = 0
    breakups: int = 0

    # --- Derived values ---

    @property
    def display_job_title(self) -> str:
        """Dynamic job title based on years working and career level."""
        if self.is_self_employed:
            return self.job_title
        if not self.is_employed:
            return "待业中"
        # If job_title was set explicitly by an event (e.g. "跳槽成功"), use it for 1 year
        # then revert to dynamic. Also keep preset titles for the first 2 years.
        years_working = self.year - YEAR_START
        if years_working == 0:
            return self.job_title  # keep preset title in first year
        # Preset 3 starts with career_level=1 but salary=15K — don't downgrade their title
        if self.career_level >= 4:
            return "资深从业者"
        if self.career_level >= 3 or self.monthly_salary >= 20000:
            return "业务骨干"
        if self.monthly_salary >= 12000:
            return "普通白领"
        if years_working <= 2:
            return "职场新人"
        return "普通白领"

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

    def calculate_annual_costs(self) -> dict[str, float]:
        """Calculate detailed annual living costs.

        Returns a dict of {label: amount} for display purposes.
        Costs scale with year to simulate inflation.
        """
        costs: dict[str, float] = {}
        year_offset = self.year - YEAR_START  # 0 in 2015, 10 in 2025

        # Base living expenses (food, transport, utilities, etc.)
        base_living = 36000 + year_offset * 3000  # ¥36K in 2015, +3K/year
        costs["日常开支"] = base_living

        # Housing: rent (no property) or mortgage (has property)
        if self.properties == 0:
            rent = 24000 + year_offset * 2400  # ¥2K/month in 2015, +200/month/year
            costs["房租"] = rent
        elif self.mortgage_monthly > 0:
            costs["房贷"] = self.mortgage_monthly * 12

        # Partner expenses
        if self.has_partner:
            costs["恋爱/家庭开支"] = 18000 + year_offset * 1200

        # Child expenses
        if self.has_child:
            costs["养娃开支"] = 50000 + year_offset * 5000

        return costs

    @property
    def annual_living_cost(self) -> float:
        """Total annual living costs (detailed calculation)."""
        return sum(self.calculate_annual_costs().values())

    @property
    def is_self_employed(self) -> bool:
        """Check if player is an entrepreneur or freelancer (has income but not traditionally employed)."""
        return self.job_title in ("AI 创业者", "自由职业者", "创业者")

    @property
    def has_income(self) -> bool:
        """Check if player has any income (employed, freelance, or entrepreneur)."""
        return self.is_employed or self.is_self_employed

    @property
    def annual_salary_income(self) -> float:
        """Annual salary income (0 if unemployed and not self-employed)."""
        if not self.has_income:
            return 0.0
        return self.monthly_salary * 12

    @property
    def annual_net_income(self) -> float:
        """Yearly income after all living costs."""
        return self.annual_salary_income - self.annual_living_cost

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
                # Clamp 1-5 skills
                if key in ("investment_iq", "career_level", "network", "emotional_iq"):
                    new_val = max(1, min(5, int(new_val)))
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

    def apply_salary_growth(self) -> tuple[PlayerState, float]:
        """Apply annual salary growth. Returns (new_state, raise_amount).

        Growth: 5-10% base + career bonus + industry boom/bust.
        """
        import random

        if not self.has_income:
            return self, 0.0

        base_rate = random.uniform(0.05, 0.10)
        # Career level bonus
        if self.career_level >= 3:
            base_rate += 0.05
        # Industry boom/bust by year
        boom = {2017: 0.05, 2020: -0.03, 2021: 0.08, 2023: 0.10}
        base_rate += boom.get(self.year, 0)
        base_rate = max(base_rate, 0)  # floor at 0

        old_salary = self.monthly_salary
        new_salary = int(old_salary * (1 + base_rate))
        raise_amount = new_salary - old_salary
        new_state = self.model_copy(update={"monthly_salary": float(new_salary)})
        return new_state, raise_amount

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
        "properties": 1,
        "mortgage_monthly": 5000.0,
    },
}


def create_player(preset: int, gender: Gender = Gender.MALE) -> PlayerState:
    """Create a PlayerState from a starting preset (1/2/3) and gender."""
    overrides = STARTING_PRESETS.get(preset, STARTING_PRESETS[2])
    return PlayerState(gender=gender, **overrides)
