"""Event system — year-based event pools, fallback generation, and dedup."""

from __future__ import annotations

import json
import random
from typing import Literal

from pydantic import BaseModel

from rerun.config import DATA_DIR
from rerun.engine.state import PlayerState

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

EventCategory = Literal["family", "romance", "career", "social", "accident", "market"]
EventType = Literal["historical", "life"]

# Sentiment categories used in year-based event pools
EventSentiment = Literal["positive", "negative", "opportunity", "milestone"]


class Choice(BaseModel):
    """A single choice option within an event."""

    key: str  # A, B, C
    text: str
    hint: str  # narrator commentary
    consequences: dict  # {"savings": -50000, "stress": 20, ...}
    narrative: str  # post-choice story text


class GameEvent(BaseModel):
    """A game event — either historical or AI/fallback generated."""

    year: int
    type: EventType
    category: EventCategory
    title: str
    description: str
    choices: list[Choice]
    template_id: str = ""  # fallback template id, empty for AI-generated


# ---------------------------------------------------------------------------
# Historical data loader
# ---------------------------------------------------------------------------

_historical_cache: dict | None = None


def _load_historical_data() -> dict:
    global _historical_cache
    if _historical_cache is None:
        path = DATA_DIR / "historical_events.json"
        _historical_cache = json.loads(path.read_text(encoding="utf-8"))
    return _historical_cache


def get_year_context(year: int) -> dict:
    """Return the full historical data block for a given year."""
    data = _load_historical_data()
    return data.get(str(year), {})


def get_year_background(year: int) -> str:
    """Return the background narrative string for a year."""
    ctx = get_year_context(year)
    return ctx.get("background", "")


def get_historical_events(year: int) -> list[dict]:
    """Return the list of raw historical event dicts for a year."""
    ctx = get_year_context(year)
    return ctx.get("events", [])


# ---------------------------------------------------------------------------
# Year-based event pool system (v0.2)
# ---------------------------------------------------------------------------

_event_pool_cache: dict[int, dict] = {}


def _load_event_pool(year: int) -> dict | None:
    """Load the event pool for a specific year from data/events/YYYY.json."""
    if year in _event_pool_cache:
        return _event_pool_cache[year]
    path = DATA_DIR / "events" / f"{year}.json"
    if not path.exists():
        return None
    pool = json.loads(path.read_text(encoding="utf-8"))
    _event_pool_cache[year] = pool
    return pool


def is_event_applicable(tmpl: dict, state: PlayerState) -> bool:
    """Check if an event template is applicable to the current player state.

    Prevents showing BTC events to players without BTC, partner events to
    single players, etc.
    """
    event_id = tmpl.get("id", "")
    title = tmpl.get("title", "")
    desc = tmpl.get("description_template", "")
    combined = f"{event_id} {title} {desc}".lower()

    # BTC-related events need BTC holdings (sell/crash/割肉)
    btc_sell_keywords = ["卖btc", "卖出btc", "割肉", "btc暴跌要不要", "sell_btc", "btc_crash"]
    if any(kw in combined for kw in btc_sell_keywords) and state.btc_amount <= 0:
        return False

    # Property events need properties
    if ("卖房" in combined or "房贷" in combined) and state.properties <= 0:
        return False

    # Partner events need partner
    if any(kw in combined for kw in ["伴侣", "另一半", "女朋友", "男朋友", "partner_conflict"]):
        if "meet" not in combined and not state.has_partner:
            return False

    # Check requires field if present
    requires = tmpl.get("requires", {})
    for req_key, req_val in requires.items():
        parts = req_key.split(".")
        obj = state
        for part in parts:
            obj = getattr(obj, part, None)
            if obj is None:
                return False
        if isinstance(req_val, (int, float)) and obj < req_val:
            return False

    return True


def filter_choices_for_state(choices: list[Choice], state: PlayerState) -> list[Choice]:
    """Filter out choices the player cannot afford or doesn't qualify for.

    If a choice costs more than savings but player has BTC, add a warning.
    Always keep at least one choice.
    """
    available_liquid = state.savings + state.btc_value + state.stocks

    filtered = []
    for c in choices:
        # Check if savings consequence would make this unaffordable
        cost = 0.0
        for key, val in c.consequences.items():
            if key == "savings" and isinstance(val, (int, float)) and val < 0:
                cost = abs(val)

        if cost > 0 and cost > available_liquid:
            continue  # completely unaffordable, remove

        if cost > 0 and cost > state.savings and state.btc_value > 0:
            # Can afford but needs to sell BTC — add warning to text
            c = c.model_copy(
                update={"text": c.text + "\n      ⚠️ 存款不足，需要卖出部分 BTC"}
            )

        filtered.append(c)

    # Always keep at least one option
    if not filtered:
        fallback = Choice(
            key=choices[0].key if choices else "A",
            text="咬牙撑过去",
            hint="💬 [系统] 有时候，坚持就是最好的选择。",
            consequences={"stress": 15},
            narrative="你勒紧裤腰带，又熬过了一关。",
        )
        filtered.append(fallback)

    return filtered


def _check_milestone(check: str, state: PlayerState) -> bool:
    """Check if a milestone condition is met."""
    if check == "always":
        return True
    # Parse check strings like "net_worth_gt_1000000", "savings_gt_100000"
    parts = check.split("_")
    if len(parts) >= 3 and parts[-2] == "gt":
        field = "_".join(parts[:-2])
        threshold = float(parts[-1])
        if field == "net_worth":
            return state.net_worth > threshold
        if hasattr(state, field):
            return getattr(state, field) > threshold
    return False


def _build_event_from_pool_template(
    year: int, tmpl: dict, state: PlayerState, sentiment: str
) -> GameEvent:
    """Build a GameEvent from a pool template dict."""
    variables = tmpl.get("variables", {})

    # Fill description template
    desc = _fill_template(tmpl["description_template"], variables)

    # Build choices
    choices: list[Choice] = []
    for raw_choice in tmpl["choices"]:
        resolved_consequences = _resolve_cost_consequence(
            raw_choice["consequences"], variables, state
        )
        narrative = _fill_template(raw_choice["narrative"], variables)
        hint = _fill_template(raw_choice["hint"], variables)
        choices.append(
            Choice(
                key=raw_choice["key"],
                text=raw_choice["text"],
                hint=hint,
                consequences=resolved_consequences,
                narrative=narrative,
            )
        )

    # B3: Filter choices based on player state (affordability, etc.)
    choices = filter_choices_for_state(choices, state)

    # Map sentiment to a category for compatibility
    category_map: dict[str, EventCategory] = {
        "positive": "social",
        "negative": "accident",
        "opportunity": "market",
        "milestone": "career",
    }
    category = category_map.get(sentiment, "social")

    return GameEvent(
        year=year,
        type="life",
        category=category,
        title=tmpl["title"],
        description=desc,
        choices=choices,
        template_id=tmpl.get("id", ""),
    )


def _filter_by_gender(templates: list[dict], gender_value: str) -> list[dict]:
    """Filter event templates by gender compatibility."""
    return [
        t for t in templates
        if t.get("gender", "both") in ("both", gender_value)
    ]


def _build_2015_tutorial_events(pool: dict, state: PlayerState) -> list[GameEvent]:
    """Build the fixed 2015 tutorial events with dynamic BTC calculations."""
    from rerun.engine.state import get_btc_price

    btc_price = get_btc_price(2015)
    gender_val = state.gender.value if hasattr(state, "gender") else "male"
    events: list[GameEvent] = []

    for tmpl in pool.get("fixed_events", []):
        # Gender filter
        if tmpl.get("gender", "both") not in ("both", gender_val):
            continue

        # Build description
        desc = tmpl["description_template"]

        # Build choices with dynamic BTC amounts
        choices: list[Choice] = []
        for raw in tmpl["choices"]:
            cons = dict(raw["consequences"])

            # Special handling for BTC purchase event
            if tmpl["id"] == "2015_btc_enlightenment":
                if raw["key"] == "A":  # 梭哈
                    btc_bought = state.savings / btc_price
                    cons = {"savings": -state.savings, "btc_amount": btc_bought, "stress": 20}
                    text = f"梭哈！把所有积蓄都买 BTC（约 {btc_bought:.1f} 个）"
                elif raw["key"] == "B":  # 1万
                    btc_bought = 10000 / btc_price
                    cons = {"savings": -10000, "btc_amount": btc_bought, "stress": 5}
                    text = f"拿 1 万块试试水（约 {btc_bought:.1f} 个）"
                elif raw["key"] == "C":  # 3000
                    btc_bought = 3000 / btc_price
                    cons = {"savings": -3000, "btc_amount": btc_bought, "stress": 0}
                    text = f"只买 3000 块的（约 {btc_bought:.1f} 个）"
                else:
                    text = raw["text"]
            else:
                text = raw["text"]

            choices.append(Choice(
                key=raw["key"],
                text=text,
                hint=raw["hint"],
                consequences=cons,
                narrative=raw["narrative"],
            ))

        # Filter choices by affordability
        choices = filter_choices_for_state(choices, state)

        events.append(GameEvent(
            year=2015,
            type="life",
            category="market" if "btc" in tmpl["id"] else "family" if "family" in tmpl["id"] else "social",
            title=tmpl["title"],
            description=desc,
            choices=choices,
            template_id=tmpl["id"],
        ))

    return events


def select_events_from_pool(
    year: int,
    state: PlayerState,
    used_ids: set[str],
    consecutive_negative_years: int = 0,
) -> list[GameEvent]:
    """Select events from the year-based event pool.

    Implements the 7:3 positive:negative ratio and prevents consecutive
    negative-only years. Filters by player gender. Returns a list of GameEvent objects.
    """
    pool = _load_event_pool(year)
    if pool is None:
        return []

    # 2015 tutorial year: fixed events, not random
    if pool.get("tutorial"):
        return _build_2015_tutorial_events(pool, state)

    gender_val = state.gender.value if hasattr(state, "gender") else "male"
    events: list[GameEvent] = []

    # 1. Check milestones (auto-trigger if conditions met)
    for tmpl in _filter_by_gender(pool.get("milestone", []), gender_val):
        check = tmpl.get("check", "always")
        tmpl_id = tmpl.get("id", "")
        if tmpl_id in used_ids:
            continue
        if _check_milestone(check, state):
            events.append(_build_event_from_pool_template(year, tmpl, state, "milestone"))
            break  # At most one milestone per year

    # 2. Always pick 1 positive event (filtered by unused + gender + state)
    positive_candidates = [
        t for t in _filter_by_gender(pool.get("positive", []), gender_val)
        if t.get("id", "") not in used_ids and is_event_applicable(t, state)
    ]
    if positive_candidates:
        weights = [t.get("weight", 1.0) for t in positive_candidates]
        chosen = random.choices(positive_candidates, weights=weights, k=1)[0]
        events.append(_build_event_from_pool_template(year, chosen, state, "positive"))

    # 3. Conditionally pick negative event (40% chance, blocked if 2+ consecutive negative years)
    if consecutive_negative_years < 2 and random.random() < 0.4:
        negative_candidates = [
            t for t in _filter_by_gender(pool.get("negative", []), gender_val)
            if t.get("id", "") not in used_ids and is_event_applicable(t, state)
        ]
        if negative_candidates:
            weights = [t.get("weight", 1.0) for t in negative_candidates]
            chosen = random.choices(negative_candidates, weights=weights, k=1)[0]
            events.append(_build_event_from_pool_template(year, chosen, state, "negative"))

    # 4. Conditionally pick opportunity event (30% chance)
    if random.random() < 0.3:
        opp_candidates = [
            t for t in _filter_by_gender(pool.get("opportunity", []), gender_val)
            if t.get("id", "") not in used_ids and is_event_applicable(t, state)
        ]
        if opp_candidates:
            weights = [t.get("weight", 1.0) for t in opp_candidates]
            chosen = random.choices(opp_candidates, weights=weights, k=1)[0]
            events.append(_build_event_from_pool_template(year, chosen, state, "opportunity"))

    # 5. Boss years get an extra event if we only have 1
    if is_boss_year(year) and len(events) < 2:
        all_candidates = []
        for sentiment in ("positive", "opportunity", "negative"):
            for t in _filter_by_gender(pool.get(sentiment, []), gender_val):
                tid = t.get("id", "")
                if tid not in used_ids and not any(
                    e.template_id == tid for e in events
                ):
                    all_candidates.append((sentiment, t))
        if all_candidates:
            sentiment, chosen = random.choice(all_candidates)
            events.append(_build_event_from_pool_template(year, chosen, state, sentiment))

    return events


# ---------------------------------------------------------------------------
# Fallback (offline) event generation — legacy system
# ---------------------------------------------------------------------------

_life_events_cache: dict | None = None


def _load_life_events() -> dict:
    global _life_events_cache
    if _life_events_cache is None:
        path = DATA_DIR / "life_events.json"
        _life_events_cache = json.loads(path.read_text(encoding="utf-8"))
    return _life_events_cache


def _fill_template(template: str, variables: dict) -> str:
    """Fill a template string with randomly chosen variables."""
    result = template
    for key, options in variables.items():
        if isinstance(options, list):
            chosen = random.choice(options)
            result = result.replace(f"{{{key}}}", str(chosen))
    return result


def _resolve_cost_consequence(consequences: dict, variables: dict, state: PlayerState) -> dict:
    """Resolve placeholder consequence values.

    In life_events.json, consequences with value -1 or 1 are placeholders
    meaning 'use the cost variable' or 'use the severance variable'.
    """
    resolved = {}
    cost_keys = {
        "cost",
        "amount",
        "investment",
        "bride_price",
        "wedding_cost",
        "severance",
        "tax_amount",
        "bonus",
        "prize",
        "gift",
    }
    # Find the resolved cost from variables
    cost_value = 0
    for k in cost_keys:
        if k in variables:
            opts = variables[k]
            cost_value = random.choice(opts) if isinstance(opts, list) else opts
            break

    for key, value in consequences.items():
        if key == "times_helped_family" and value == 1:
            resolved[key] = value
            continue
        if value == -1 and key == "savings":
            resolved[key] = -cost_value
        elif value == 1 and key == "savings":
            resolved[key] = cost_value
        elif value == 1 and key == "monthly_salary":
            # Promotion: set salary from variables
            salary_opts = variables.get("salary", [state.monthly_salary + 5000])
            resolved[key] = (
                random.choice(salary_opts) if isinstance(salary_opts, list) else salary_opts
            ) - state.monthly_salary  # delta
        elif value == 1 and key == "monthly_expense":
            # Use the first cost-like variable as expense delta
            expense_opts = variables.get("amount", variables.get("income", [2000]))
            resolved[key] = (
                random.choice(expense_opts) if isinstance(expense_opts, list) else expense_opts
            )
        elif isinstance(value, str) and value == "":
            # job_title placeholder: pick from variables
            title_opts = variables.get("position", ["新岗位"])
            resolved[key] = (
                random.choice(title_opts) if isinstance(title_opts, list) else title_opts
            )
        else:
            resolved[key] = value
    return resolved


def generate_fallback_event(
    year: int,
    state: PlayerState,
    exclude_categories: list[str] | None = None,
    used_templates: set[str] | None = None,
) -> GameEvent | None:
    """Generate an event from the legacy fallback pool.

    Returns None if no suitable template is available.
    """
    pool = _load_life_events()
    exclude = set(exclude_categories or [])
    used = used_templates or set()

    # Gather eligible templates
    candidates: list[tuple[str, dict]] = []
    for category, templates in pool.items():
        if category in exclude:
            continue
        for tmpl in templates:
            tid = tmpl["template"]
            if tid in used:
                continue
            # Filter: romance conflict only if has_partner
            if tid == "partner_conflict_btc" and not state.has_partner:
                continue
            if tid == "marriage_pressure" and not state.has_partner:
                continue
            # Filter: meet_someone only if no partner
            if tid == "meet_someone" and state.has_partner:
                continue
            candidates.append((category, tmpl))

    if not candidates:
        return None

    category, tmpl = random.choice(candidates)
    variables = tmpl.get("variables", {})

    # Build description
    desc = _fill_template(tmpl["description_template"], variables)

    # Build choices
    choices: list[Choice] = []
    for raw_choice in tmpl["choices"]:
        resolved_consequences = _resolve_cost_consequence(
            raw_choice["consequences"], variables, state
        )
        narrative = _fill_template(raw_choice["narrative"], variables)
        hint = _fill_template(raw_choice["hint"], variables)
        choices.append(
            Choice(
                key=raw_choice["key"],
                text=raw_choice["text"],
                hint=hint,
                consequences=resolved_consequences,
                narrative=narrative,
            )
        )

    return GameEvent(
        year=year,
        type="life",
        category=category,
        title=tmpl["title"],
        description=desc,
        choices=choices,
        template_id=tmpl["template"],
    )


# ---------------------------------------------------------------------------
# Event scheduling — how many events per year, which types
# ---------------------------------------------------------------------------

BOSS_YEARS = {2018, 2020, 2022}


def is_boss_year(year: int) -> bool:
    return year in BOSS_YEARS


class EventTracker:
    """Tracks event history within a single run for dedup and scheduling."""

    def __init__(self) -> None:
        self.recent_categories: list[str] = []
        self.used_templates: set[str] = set()
        self.used_pool_ids: set[str] = set()
        self.category_counts: dict[str, int] = {}
        self.consecutive_negative_years: int = 0
        self._year_had_negative: bool = False
        self._year_had_positive: bool = False

    def record(self, event: GameEvent, template_id: str | None = None) -> None:
        self.recent_categories.append(event.category)
        if template_id:
            self.used_templates.add(template_id)
        if event.template_id:
            self.used_pool_ids.add(event.template_id)
        self.category_counts[event.category] = self.category_counts.get(event.category, 0) + 1

    def record_year_sentiment(self, had_negative: bool, had_positive: bool) -> None:
        """Track consecutive negative years for ratio control."""
        if had_negative and not had_positive:
            self.consecutive_negative_years += 1
        else:
            self.consecutive_negative_years = 0

    @property
    def exclude_categories(self) -> list[str]:
        """Categories to exclude — the last 2 used categories."""
        return self.recent_categories[-2:] if self.recent_categories else []

    def events_for_year(self, year: int) -> int:
        """How many life events to generate for this year."""
        if is_boss_year(year):
            return 2
        return 1
