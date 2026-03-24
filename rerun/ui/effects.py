"""Terminal effects — typewriter, number rolling, etc."""

from __future__ import annotations

import sys
import time

from rich.console import Console


def typewriter(console: Console, text: str, speed: float = 0.03) -> None:
    """Print text with typewriter effect, character by character."""
    if speed <= 0:
        console.print(text)
        return
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(speed)
    sys.stdout.write("\n")
    sys.stdout.flush()


def number_roll(
    console: Console,
    label: str,
    old_val: float,
    new_val: float,
    *,
    prefix: str = "¥",
    steps: int = 8,
    delay: float = 0.05,
) -> None:
    """Animate a number rolling from old to new value."""
    if delay <= 0 or steps <= 0:
        # No animation
        diff = new_val - old_val
        color = "green" if diff >= 0 else "red"
        sign = "+" if diff >= 0 else ""
        console.print(f"  {label}: {prefix}{new_val:,.0f} [{color}]({sign}{prefix}{diff:,.0f})[/]")
        return

    delta = new_val - old_val
    for i in range(1, steps + 1):
        current = old_val + delta * (i / steps)
        sys.stdout.write(f"\r  {label}: {prefix}{current:,.0f}  ")
        sys.stdout.flush()
        time.sleep(delay)

    # Final line with diff
    diff = new_val - old_val
    color = "green" if diff >= 0 else "red"
    sign = "+" if diff >= 0 else ""
    sys.stdout.write("\r")
    sys.stdout.flush()
    console.print(f"  {label}: {prefix}{new_val:,.0f} [{color}]({sign}{prefix}{diff:,.0f})[/]")


def pause(prompt: str = "按回车继续...") -> None:
    """Wait for user to press Enter."""
    input(f"\n  {prompt}")
