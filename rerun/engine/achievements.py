"""Achievement system — condition checking and unlocking."""

from __future__ import annotations

import json

from rerun.config import DATA_DIR
from rerun.engine.state import PlayerState

_achievements_cache: dict | None = None


def _load_achievements() -> dict:
    global _achievements_cache
    if _achievements_cache is None:
        path = DATA_DIR / "achievements.json"
        _achievements_cache = json.loads(path.read_text(encoding="utf-8"))
    return _achievements_cache


def get_achievement_display(ach_id: str, lang: str = "cn") -> str:
    """Return a formatted display string for an achievement like '💎 钻石手'."""
    data = _load_achievements()
    for category in data.values():
        for ach in category:
            if ach["id"] == ach_id:
                name = ach["name"] if lang == "cn" else ach.get("name_en", ach["name"])
                desc = (
                    ach["description"]
                    if lang == "cn"
                    else ach.get("description_en", ach["description"])
                )
                return f"{ach['emoji']} [{name}] — {desc}"
    return ach_id


# ---------------------------------------------------------------------------
# Condition checkers — each returns True if the achievement is earned
# ---------------------------------------------------------------------------


def _check_diamond_hands(state: PlayerState, initial_savings: float) -> bool:
    """Held through a 50%+ BTC crash without selling."""
    # Check if player held BTC through a crash year (2018 or 2022)
    if state.btc_amount <= 0:
        return False
    # Check choices_log for crash years — if they had BTC and didn't sell
    held_through_crash = False
    for entry in state.choices_log:
        year = entry.get("year", 0)
        cons = entry.get("consequences", {})
        if year in (2018, 2022) and cons.get("btc_amount", 0) < 0:
            return False  # sold during crash
        if year in (2018, 2022):
            held_through_crash = True
    return held_through_crash and state.max_btc_held > 0


def _check_clown(state: PlayerState, initial_savings: float) -> bool:
    """Knew the future and still lost money."""
    return state.net_worth < initial_savings


def _check_landlord(state: PlayerState, initial_savings: float) -> bool:
    return state.properties >= 2


def _check_tenbagger(state: PlayerState, initial_savings: float) -> bool:
    return state.net_worth >= initial_savings * 10


def _check_paper_hands(state: PlayerState, initial_savings: float) -> bool:
    return state.times_sold_btc >= 3


def _check_bottom_fisher(state: PlayerState, initial_savings: float) -> bool:
    """Bought BTC in a bottom year (2015, or crash years 2018/2022)."""
    for entry in state.choices_log:
        year = entry.get("year", 0)
        cons = entry.get("consequences", {})
        if year in (2015, 2018, 2022) and cons.get("btc_amount", 0) > 0:
            return True
    return False


def _check_life_winner(state: PlayerState, initial_savings: float) -> bool:
    return state.net_worth > 5_000_000 and state.has_partner and state.relationship > 70


def _check_heartbreaker(state: PlayerState, initial_savings: float) -> bool:
    return state.breakups >= 2


def _check_zen_master(state: PlayerState, initial_savings: float) -> bool:
    # Approximate: current stress < 50 (full history tracking would need state_history)
    return state.stress < 50


def _check_regret(state: PlayerState, initial_savings: float) -> bool:
    return state.net_worth < 450_000


def _check_filial_child(state: PlayerState, initial_savings: float) -> bool:
    return state.times_helped_family >= 2


def _check_lone_wolf(state: PlayerState, initial_savings: float) -> bool:
    return not state.has_partner and state.social < 30


def _check_prophet(state: PlayerState, initial_savings: float) -> bool:
    """Made optimal choices 5 times in a row — approximated by high net worth + low stress."""
    return state.net_worth > 10_000_000 and state.stress < 30


def _check_storyteller(state: PlayerState, initial_savings: float) -> bool:
    unique_events = {e.get("event_title", "") for e in state.choices_log}
    return len(unique_events) >= 8


def _check_phoenix(state: PlayerState, initial_savings: float) -> bool:
    # Approximation: negative savings at some point but ended rich
    return (
        state.savings < 0
        and state.net_worth > 1_000_000
        or (
            any(e.get("consequences", {}).get("savings", 0) < -100000 for e in state.choices_log)
            and state.net_worth > 1_000_000
        )
    )


def _check_exposed(state: PlayerState, initial_savings: float) -> bool:
    return state.reputation > 90


# Achievement timing: "realtime" = check during gameplay, "endgame" = check only at end
_REALTIME_CHECKERS: dict[str, callable] = {
    "diamond_hands": _check_diamond_hands,
    "landlord": _check_landlord,
    "tenbagger": _check_tenbagger,
    "bottom_fisher": _check_bottom_fisher,
    "life_winner": _check_life_winner,
    "filial_child": _check_filial_child,
    "storyteller": _check_storyteller,
}

_ENDGAME_CHECKERS: dict[str, callable] = {
    "clown": _check_clown,          # "小丑" — only meaningful at end
    "paper_hands": _check_paper_hands,
    "heartbreaker": _check_heartbreaker,
    "zen_master": _check_zen_master,  # "佛系" — needs full game history
    "regret": _check_regret,          # "意难平" — only meaningful at end
    "lone_wolf": _check_lone_wolf,
    "prophet": _check_prophet,
    "phoenix": _check_phoenix,
    "exposed": _check_exposed,
}

# Combined for any code that needs all
_ALL_CHECKERS: dict[str, callable] = {**_REALTIME_CHECKERS, **_ENDGAME_CHECKERS}


# Mutually exclusive achievements — if one is unlocked, the other cannot be
_MUTUALLY_EXCLUSIVE: dict[str, str] = {
    "diamond_hands": "paper_hands",
    "paper_hands": "diamond_hands",
}


def check_achievements(
    state: PlayerState, initial_savings: float, *, endgame: bool = False
) -> list[str]:
    """Check achievements and return list of newly unlocked IDs.

    Args:
        endgame: If True, check all achievements. If False, only realtime ones.
    """
    checkers = _ALL_CHECKERS if endgame else _REALTIME_CHECKERS
    newly_unlocked = []
    for ach_id, checker in checkers.items():
        if ach_id in state.achievements:
            continue
        # F6: Check mutual exclusion
        conflict = _MUTUALLY_EXCLUSIVE.get(ach_id)
        if conflict and conflict in state.achievements:
            continue
        try:
            if checker(state, initial_savings):
                newly_unlocked.append(ach_id)
        except Exception:
            pass  # don't let a buggy checker crash the game
    return newly_unlocked


def apply_achievements(
    state: PlayerState, initial_savings: float, *, endgame: bool = False
) -> tuple[PlayerState, list[str]]:
    """Check and unlock earned achievements. Returns (new_state, newly_unlocked).

    Args:
        endgame: If True, check all achievements (including endgame-only ones).
    """
    newly = check_achievements(state, initial_savings, endgame=endgame)
    new_state = state
    for ach_id in newly:
        new_state = new_state.unlock_achievement(ach_id)
    return new_state, newly
