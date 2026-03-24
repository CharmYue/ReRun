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
    from rerun.ui.renderer import GameRenderer, _fmt_money
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
            ys, salary_raise = engine.get_year_start()
            renderer.render_year_start(ys, prev_state=prev_state, salary_raise=salary_raise)

            # Foreshadowing (e.g., layoff hints in 2017)
            foreshadow = engine.get_foreshadow()
            if foreshadow:
                console.print(f"  [dim]{foreshadow}[/]")
                console.print()

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
            for idx, event in enumerate(events, 1):
                renderer.render_event(event, event_index=idx, total_events=len(events))

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

            year_start_state = prev_state  # state at beginning of this year for comparison
            prev_state = engine.state
            year_end = engine.settle_year(year_events=events)
            renderer.render_year_end(year_end.year, year_end.state, prev_state=year_start_state)

            # Bankruptcy check — two tiers:
            # 1. Near-bankrupt (savings < 0 but has BTC/stocks) → survival event
            # 2. Truly bankrupt (savings < 0 and no assets) → game over
            if engine.is_near_bankrupt():
                action = renderer.render_survival_event(engine.state)
                if action == "A":
                    btc_sold = engine.apply_survival_sell_btc()
                    console.print(f"\n  你忍痛卖掉了 {btc_sold:.2f} 个 BTC。存款回正了。")
                    console.print(f"  💰 存款：{_fmt_money(engine.state.savings)}")
                    console.print()
                elif action == "B":
                    engine.apply_survival_move_home()
                    console.print("\n  你搬回了父母家。生活成本大幅降低。")
                    console.print("  虽然有点丢脸，但至少活下来了。")
                    console.print()
                elif action == "C":
                    success = engine.apply_survival_borrow()
                    if success:
                        console.print("\n  朋友借了你一笔钱周转。记得还。")
                        console.print(f"  💰 存款：{_fmt_money(engine.state.savings)}")
                        console.print()
                    else:
                        console.print("\n  [red]借钱失败了。[/]")
            elif engine.is_truly_bankrupt():
                action = renderer.render_bankruptcy(engine.state)
                if action == "R":
                    engine.apply_bankruptcy_continue()
                    continue
                elif action == "N":
                    bankrupt_restart = True
                    break
                else:
                    console.print("\n  [dim]感谢游玩 ReRun。再见。[/]\n")
                    return

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
