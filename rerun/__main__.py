"""Entry point for `python -m rerun`."""

from __future__ import annotations

import argparse

from rerun.config import Language, get_settings


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="rerun",
        description="ReRun — A roguelike life simulator. Relive 2015-2025 with future knowledge.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Force offline mode (use fallback event pool, no LLM calls)",
    )
    parser.add_argument(
        "--lang",
        choices=["cn", "en"],
        default=None,
        help="Game language (default: from .env or cn)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="Record game session to files (text + JSON) in ./records/",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="Show version and exit",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    if args.version:
        from rerun import __version__

        print(f"ReRun v{__version__}")
        return

    # Build settings overrides from CLI args
    overrides: dict = {}
    if args.offline:
        overrides["openai_api_key"] = ""
    if args.lang:
        overrides["game_language"] = Language(args.lang)
    if args.debug:
        overrides["debug"] = True
    if args.record:
        overrides["record"] = True

    settings = get_settings(**overrides)

    if settings.debug:
        print(
            f"[DEBUG] Settings: offline={settings.is_offline}, lang={settings.game_language.value}"
        )

    # Launch the game
    from rerun.cli import run_game

    run_game(settings)


if __name__ == "__main__":
    main()
