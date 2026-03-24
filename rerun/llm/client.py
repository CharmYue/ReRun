"""LLM client abstraction layer — OpenAI with fallback support."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rerun.engine.events import GameEvent, generate_fallback_event
from rerun.engine.state import PlayerState
from rerun.llm.parser import parse_event_response, parse_narrator_response
from rerun.llm.prompts import (
    NARRATOR_PROMPT,
    format_ending_prompt,
    format_event_prompt,
)

if TYPE_CHECKING:
    from rerun.config import Settings

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM call abstraction.

    MVP: OpenAI gpt-4o-mini via the openai SDK.
    Future: Claude, DeepSeek, Ollama, etc.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = None

    def _get_client(self):
        """Lazy-init the OpenAI client."""
        if self._client is None:
            from openai import OpenAI

            kwargs = {"api_key": self.settings.openai_api_key}
            if self.settings.openai_base_url:
                kwargs["base_url"] = self.settings.openai_base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def _chat(self, prompt: str, *, json_mode: bool = False) -> str | None:
        """Make a synchronous chat completion call.

        Returns the response text, or None on failure.
        """
        if self.settings.is_offline:
            return None

        try:
            client = self._get_client()
            kwargs = {
                "model": self.settings.openai_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.settings.llm_temperature,
                "timeout": 15,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content

        except Exception:
            logger.exception("LLM call failed")
            return None

    def generate_event(
        self,
        year: int,
        state: PlayerState,
        year_background: str,
        recent_choices: list[dict],
        allowed_categories: list[str],
        used_templates: set[str] | None = None,
    ) -> GameEvent | None:
        """Generate a life event via LLM, with fallback to local pool.

        Returns a GameEvent, or None if both LLM and fallback fail.
        """
        # Try LLM first
        if not self.settings.is_offline:
            prompt = format_event_prompt(
                year,
                state,
                year_background,
                recent_choices,
                allowed_categories,
            )
            raw = self._chat(prompt, json_mode=True)
            if raw:
                event = parse_event_response(raw, year)
                if event:
                    return event
                logger.warning("LLM response failed to parse, falling back to local pool")

        # Fallback to local event pool
        exclude = (
            [
                c
                for c in ["family", "romance", "career", "social", "accident"]
                if c not in allowed_categories
            ]
            if allowed_categories
            else []
        )
        return generate_fallback_event(
            year,
            state,
            exclude_categories=exclude,
            used_templates=used_templates,
        )

    def generate_narrator_line(self, situation: str) -> str | None:
        """Generate a narrator quip for the given situation.

        Returns the narrator text, or None (caller should use fallback lines).
        """
        if self.settings.is_offline:
            return None

        prompt = NARRATOR_PROMPT.format(situation=situation)
        raw = self._chat(prompt)
        if raw:
            return parse_narrator_response(raw)
        return None

    def generate_ending_summary(
        self,
        state: PlayerState,
        initial_savings: float,
        baseline: float,
    ) -> str | None:
        """Generate the ending narrative summary.

        Returns the summary text, or None (caller should use fallback).
        """
        if self.settings.is_offline:
            return None

        prompt = format_ending_prompt(state, initial_savings, baseline)
        raw = self._chat(prompt)
        if raw:
            return parse_narrator_response(raw)
        return None
