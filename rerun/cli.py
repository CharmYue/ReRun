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
    from rerun.engine.state import Gender
    from rerun.ui.renderer import GameRenderer
    from rerun.ui.screens import get_ending_narrator, get_year_end_narrator, render_opening

    renderer = GameRenderer(console, settings.typewriter_speed)
    engine = GameEngine(settings)
    lang = settings.game_language.value

    while True:
        # --- Opening (returns preset + gender) ---
        preset, gender_str = render_opening(renderer)
        gender = Gender.FEMALE if gender_str == "female" else Gender.MALE
        engine.init_player(preset, gender)

        # --- Year loop ---
        prev_state = None
        bankrupt_restart = False
        while not engine.is_game_over():
            # Year start (画面1 + 画面2, with press-enter paging)
            ys = engine.get_year_start()
            renderer.render_year_start(ys, prev_state=prev_state)

            # Prophet feedback — reward past foresight
            prophet_msg = engine.check_prophet()
            if prophet_msg:
                console.print(prophet_msg)
                console.print()

            # Milestone celebration
            milestone_msg = engine.check_milestone()
            if milestone_msg:
                console.print(milestone_msg)
                console.print()

            # Events (画面3: event + choices → 画面4: result)
            events = engine.get_events_for_year()
            for event in events:
                renderer.render_event(event)

                # Player choice
                valid = get_valid_keys(event)
                choice_key = renderer.prompt_choice(valid)

                # Process and display result (画面4)
                result = engine.apply_choice(event, choice_key)
                renderer.render_choice_result(result)

                # Check milestone after each choice (state may have changed)
                milestone_msg = engine.check_milestone()
                if milestone_msg:
                    console.print(milestone_msg)
                    console.print()

            # Year-end
            narrator_line = get_year_end_narrator(engine.state.year, lang)
            if narrator_line:
                console.print(f"  [cyan italic]{narrator_line}[/]")

            prev_state = engine.state
            year_end = engine.settle_year(year_events=events)
            renderer.render_year_end(year_end.year, year_end.state)

            # Bankruptcy check
            if engine.is_bankrupt():
                action = renderer.render_bankruptcy(engine.state)
                if action == "R":
                    engine.apply_bankruptcy_continue()
                    continue  # continue year loop with new low-income state
                elif action == "N":
                    bankrupt_restart = True
                    break  # break year loop → will restart via outer loop
                else:
                    console.print("\n  [dim]感谢游玩 ReRun。再见。[/]\n")
                    return  # exit entirely

        # Skip ending if restarting from bankruptcy
        if bankrupt_restart:
            engine.reset()
            continue

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
