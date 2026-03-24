"""Event system — historical events loading, fallback event generation, and dedup."""

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
# Fallback (offline) event generation
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
    """Generate an event from the fallback pool.

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
        self.category_counts: dict[str, int] = {}

    def record(self, event: GameEvent, template_id: str | None = None) -> None:
        self.recent_categories.append(event.category)
        if template_id:
            self.used_templates.add(template_id)
        self.category_counts[event.category] = self.category_counts.get(event.category, 0) + 1

    @property
    def exclude_categories(self) -> list[str]:
        """Categories to exclude — the last 2 used categories."""
        return self.recent_categories[-2:] if self.recent_categories else []

    def events_for_year(self, year: int) -> int:
        """How many life events to generate for this year."""
        if is_boss_year(year):
            return 2
        return 1
