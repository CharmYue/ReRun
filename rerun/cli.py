"""CLI main loop — game entry point."""

from __future__ import annotations

import io
import sys
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from rerun.config import Settings

# Force UTF-8 output on Windows to support emoji
if sys.platform == "win32" and isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

console = Console(force_terminal=True)


def run_game(settings: Settings) -> None:
    """Start the ReRun game loop."""
    from rerun.engine.choices import get_valid_keys
    from rerun.engine.game import GameEngine
    from rerun.ui.renderer import GameRenderer
    from rerun.ui.screens import get_ending_narrator, get_year_end_narrator, render_opening

    renderer = GameRenderer(console, settings.typewriter_speed)
    engine = GameEngine(settings)
    lang = settings.game_language.value

    while True:
        # --- Opening ---
        preset = render_opening(renderer)
        engine.init_player(preset)

        # --- Year loop ---
        while not engine.is_game_over():
            # Year start
            ys = engine.get_year_start()
            renderer.render_year_start(ys)

            # Events
            events = engine.get_events_for_year()
            for event in events:
                renderer.render_event(event)

                # Player choice
                valid = get_valid_keys(event)
                choice_key = renderer.prompt_choice(valid)

                # Process and display result
                result = engine.apply_choice(event, choice_key)
                renderer.render_choice_result(result)

            # Year-end
            narrator_line = get_year_end_narrator(engine.state.year, lang)
            if narrator_line:
                console.print(f"  [cyan italic]{narrator_line}[/]")

            year_end = engine.settle_year()
            renderer.render_year_end(year_end.year, year_end.state)

        # --- Ending ---
        ending = engine.get_ending()
        narrator_summary = get_ending_narrator(ending.state, lang)
        renderer.render_ending(ending, narrator_summary)

        # Post-ending menu
        action = renderer.render_ending_menu()
        if action == "R":
            engine.reset()
            continue
        else:
            console.print("\n  [dim]感谢游玩 ReRun。再见。[/]\n")
            break


def main() -> None:
    """Convenience entry for `rerun` console script."""
    from rerun.__main__ import main as _main

    _main()
