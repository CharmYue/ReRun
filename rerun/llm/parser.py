"""LLM output parser — JSON to Pydantic models with error handling."""

from __future__ import annotations

import json
import logging

from rerun.engine.events import Choice, GameEvent

logger = logging.getLogger(__name__)


def parse_event_response(raw: str, year: int) -> GameEvent | None:
    """Parse LLM JSON output into a GameEvent.

    Returns None if parsing fails.
    """
    try:
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            if text.startswith("json"):
                text = text[4:].strip()

        data = json.loads(text)

        # Validate required fields
        if "choices" not in data or not data["choices"]:
            logger.warning("LLM response missing choices")
            return None

        choices = []
        for c in data["choices"]:
            choices.append(
                Choice(
                    key=c.get("key", "A"),
                    text=c.get("text", ""),
                    hint=c.get("hint", ""),
                    consequences=c.get("consequences", {}),
                    narrative=c.get("narrative", ""),
                )
            )

        return GameEvent(
            year=data.get("year", year),
            type=data.get("type", "life"),
            category=data.get("category", "social"),
            title=data.get("title", "未知事件"),
            description=data.get("description", ""),
            choices=choices,
        )

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Failed to parse LLM event response: %s", e)
        return None


def parse_narrator_response(raw: str) -> str:
    """Parse narrator line from LLM response.

    Returns the raw text (narrator lines are plain text, not JSON).
    """
    text = raw.strip()
    if not text:
        return ""
    # Ensure it starts with the narrator prefix
    if not text.startswith("💬"):
        text = f"💬 [系统] {text}"
    return text
