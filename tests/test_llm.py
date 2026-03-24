"""Tests for rerun.llm — prompts, parser, and client fallback."""

import json
import sys
import types

from rerun.config import get_settings
from rerun.engine.state import PlayerState
from rerun.llm.client import LLMClient
from rerun.llm.parser import parse_event_response, parse_narrator_response
from rerun.llm.prompts import format_ending_prompt, format_event_prompt


class TestPrompts:
    def test_event_prompt_format(self):
        state = PlayerState(savings=80000, btc_amount=10, year=2017)
        prompt = format_event_prompt(
            year=2017,
            state=state,
            year_background="BTC疯牛年",
            recent_choices=[],
            allowed_categories=["family", "career"],
        )
        assert "2017" in prompt
        assert "80000" in prompt  # savings
        assert "family/career" in prompt
        assert "BTC疯牛年" in prompt

    def test_event_prompt_with_recent_choices(self):
        state = PlayerState()
        choices = [
            {"year": 2015, "event_title": "买BTC", "choice_key": "A", "choice_text": "全买"},
        ]
        prompt = format_event_prompt(2016, state, "bg", choices, [])
        assert "2015年-买BTC: 选了A" in prompt

    def test_ending_prompt_format(self):
        state = PlayerState(
            year=2025,
            savings=1000000,
            btc_amount=5,
            properties=1,
            has_partner=True,
            relationship=70,
            stress=30,
            breakups=1,
            times_helped_family=2,
            achievements=["diamond_hands"],
            choices_log=[
                {"year": 2015, "event_title": "Test", "choice_key": "A", "choice_text": "Do it"},
            ],
        )
        prompt = format_ending_prompt(state, 80000, 450000)
        assert "diamond_hands" in prompt
        assert "2015年" in prompt


class TestParser:
    def test_parse_valid_json(self):
        data = {
            "year": 2017,
            "type": "life",
            "category": "family",
            "title": "Test Event",
            "description": "Something happened",
            "choices": [
                {
                    "key": "A",
                    "text": "Do it",
                    "hint": "hint",
                    "consequences": {"savings": -10000},
                    "narrative": "You did it.",
                }
            ],
        }
        event = parse_event_response(json.dumps(data), 2017)
        assert event is not None
        assert event.title == "Test Event"
        assert event.choices[0].consequences["savings"] == -10000

    def test_parse_with_markdown_fences(self):
        data = {
            "year": 2017,
            "type": "life",
            "category": "social",
            "title": "T",
            "description": "D",
            "choices": [
                {"key": "A", "text": "t", "hint": "h", "consequences": {}, "narrative": "n"}
            ],
        }
        raw = f"```json\n{json.dumps(data)}\n```"
        event = parse_event_response(raw, 2017)
        assert event is not None
        assert event.title == "T"

    def test_parse_invalid_json(self):
        event = parse_event_response("not json at all", 2017)
        assert event is None

    def test_parse_missing_choices(self):
        data = {
            "year": 2017,
            "type": "life",
            "category": "family",
            "title": "T",
            "description": "D",
            "choices": [],
        }
        event = parse_event_response(json.dumps(data), 2017)
        assert event is None

    def test_parse_narrator_plain(self):
        result = parse_narrator_response("💬 [系统] 你真行。")
        assert result.startswith("💬")

    def test_parse_narrator_adds_prefix(self):
        result = parse_narrator_response("你真行。")
        assert result.startswith("💬 [系统]")

    def test_parse_narrator_empty(self):
        result = parse_narrator_response("")
        assert result == ""


class TestClientOffline:
    def test_generate_event_fallback(self):
        settings = get_settings(openai_api_key="")
        client = LLMClient(settings)
        state = PlayerState()
        event = client.generate_event(
            year=2016,
            state=state,
            year_background="test",
            recent_choices=[],
            allowed_categories=["family", "romance", "career", "social", "accident"],
        )
        assert event is not None
        assert event.type == "life"

    def test_generate_narrator_offline_returns_none(self):
        settings = get_settings(openai_api_key="")
        client = LLMClient(settings)
        result = client.generate_narrator_line("test situation")
        assert result is None

    def test_generate_ending_offline_returns_none(self):
        settings = get_settings(openai_api_key="")
        client = LLMClient(settings)
        state = PlayerState()
        result = client.generate_ending_summary(state, 80000, 450000)
        assert result is None


class TestClientConfig:
    def test_uses_base_url_when_configured(self, monkeypatch):
        captured = {}

        class FakeOpenAI:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))

        settings = get_settings(
            openai_api_key="test-key",
            openai_base_url="https://example-resource.openai.azure.com/openai/v1/",
            openai_model="gpt-4o",
        )
        client = LLMClient(settings)

        client._get_client()

        assert captured["api_key"] == "test-key"
        assert captured["base_url"] == "https://example-resource.openai.azure.com/openai/v1/"

    def test_omits_base_url_when_not_configured(self, monkeypatch):
        captured = {}

        class FakeOpenAI:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))

        settings = get_settings(openai_api_key="test-key", openai_base_url="")
        client = LLMClient(settings)

        client._get_client()

        assert captured["api_key"] == "test-key"
        assert "base_url" not in captured
