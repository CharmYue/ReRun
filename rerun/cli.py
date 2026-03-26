"""CLI main loop — game entry point."""

from __future__ import annotations

import io
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from rerun.config import Settings

# Force UTF-8 output on Windows to support emoji
if sys.platform == "win32" and isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def _save_records(engine, record_console: Console | None) -> None:
    """Save game session records to ./records/ directory."""
    records_dir = Path("records")
    records_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. Save structured JSON log
    json_path = records_dir / f"game_{timestamp}.json"
    log_data = {
        "timestamp": timestamp,
        "duration_seconds": round(
            (__import__("time").time() - engine.start_time) if engine.start_time else 0, 1
        ),
        "final_state": engine.state.model_dump(),
        "choices_log": engine.state.choices_log,
        "state_history": [s.model_dump() for s in engine.state_history],
    }
    json_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2. Save terminal text output (if recording was enabled)
    if record_console is not None:
        txt_path = records_dir / f"game_{timestamp}.txt"
        txt_path.write_text(record_console.export_text(), encoding="utf-8")
        print(f"\n  📄 文本记录已保存: {txt_path}")

    print(f"  📊 JSON 记录已保存: {json_path}")


def run_game(settings: Settings) -> None:
    """Start the ReRun game loop."""
    from rerun.engine.choices import get_valid_keys
    from rerun.engine.game import GameEngine
    from rerun.engine.state import Gender
    from rerun.ui.renderer import GameRenderer, _fmt_money
    from rerun.ui.screens import get_year_end_narrator, render_opening

    # Create console — enable recording if --record flag is set
    console = Console(force_terminal=True, record=settings.record)

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
                # V4: rebuild dynamic events based on current state (e.g. 梭哈 family variant)
                event = engine.prepare_event(event)
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

            # B4: Check hospitalization before year-end settlement
            hosp = engine.check_hospitalization()
            if hosp:
                console.print()
                console.print("  [bold red]⚠️ 你的压力已经到了极限！[/]")
                console.print("  你在办公室晕倒了。同事叫了 120。")
                console.print(f"  住院治疗花了 {_fmt_money(hosp['medical_cost'])}。")
                console.print(f"  出院后压力恢复到 {hosp['new_stress']}%。")
                console.print("  [dim]医生说：再这样下去，你的身体会垮掉。[/]")
                console.print()

            year_start_state = prev_state  # state at beginning of this year for comparison
            prev_state = engine.state
            year_end = engine.settle_year(year_events=events)
            renderer.render_year_end(year_end.year, year_end.state, prev_state=year_start_state)

            # Bankruptcy check — two tiers:
            # 1. Near-bankrupt (savings < 0 but has BTC/stocks) → survival event
            # 2. Truly bankrupt (savings < 0 and no assets) → game over
            if engine.is_near_bankrupt():
                # B5: pass can_move_home flag to renderer
                action = renderer.render_survival_event(
                    engine.state, can_move_home=engine.can_move_home()
                )
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
                    if settings.record:
                        _save_records(engine, console)
                    return

        # Skip ending if restarting from bankruptcy
        if bankrupt_restart:
            engine.reset()
            continue

        # --- Ending (cinematic montage) ---
        ending = engine.get_ending()
        action = renderer.render_ending(ending)
        if settings.record:
            _save_records(engine, console)
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
