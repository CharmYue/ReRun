"""Game screens — opening, main loop, ending."""

from __future__ import annotations

import json
import random
from typing import TYPE_CHECKING

from rich.panel import Panel

from rerun.config import DATA_DIR

if TYPE_CHECKING:
    from rerun.ui.renderer import GameRenderer

OPENING_TEXT = """\
  你睁开眼。
  手机屏幕显示：2015 年 1 月 1 日。
  你愣了三秒，然后开始狂笑。

  你记得所有的事。比特币。新冠。ChatGPT。
  你记得未来十年每一个让你拍断大腿的瞬间。

  这一次，你要全部抓住。"""

DISCLAIMER = "⚠️ 本游戏中的投资选项不构成真实投资建议。BTC价格基于历史数据。"


def _load_narrator_lines() -> dict:
    path = DATA_DIR / "narrator_lines.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _get_narrator_line(situation: str, lang: str = "cn") -> str:
    lines = _load_narrator_lines()
    pool = lines.get(situation, {})
    if isinstance(pool, dict):
        pool = pool.get(lang, pool.get("cn", []))
    if pool:
        return random.choice(pool)
    return ""


def render_opening(renderer: GameRenderer) -> int:
    """Render the opening screen and return the chosen preset (1/2/3)."""
    console = renderer.console

    console.print()
    console.print(
        Panel(
            "[bold cyan]🔄 ReRun — 你的人生，再来一次[/]",
            border_style="cyan",
            padding=(0, 4),
        )
    )
    console.print()

    renderer._typewriter(OPENING_TEXT)
    console.print()

    # Narrator opening
    narrator = _get_narrator_line("opening")
    if narrator:
        console.print(f"  [cyan italic]{narrator}[/]")
        console.print()

    # Disclaimer
    console.print(f"  [dim]{DISCLAIMER}[/]")
    console.print()

    # Preset selection
    console.print("  先说说你自己吧：")
    console.print()
    console.print("  [bold yellow][1][/] ¥30,000  （刚毕业，穷但有时间）")
    console.print("  [bold yellow][2][/] ¥80,000  （工作几年，有点积蓄）")
    console.print("  [bold yellow][3][/] ¥200,000 （小有成就，但有房贷）")
    console.print()

    while True:
        try:
            raw = input("  你的起始存款 [1/2/3] > ").strip()
        except (EOFError, KeyboardInterrupt):
            raw = "2"
        if raw in ("1", "2", "3"):
            return int(raw)
        console.print("  [red]请输入 1、2 或 3[/]")


def get_year_end_narrator(year: int, lang: str = "cn") -> str:
    """Get a narrator line for year-end."""
    return _get_narrator_line("year_end", lang)


def get_ending_narrator(state, lang: str = "cn") -> str:
    """Get a fallback ending narrator line based on performance."""
    if state.net_worth > 5_000_000:
        return _get_narrator_line("ending_rich", lang)
    elif state.net_worth < 450_000:
        return _get_narrator_line("ending_poor", lang)
    else:
        return _get_narrator_line("ending_balanced", lang)
