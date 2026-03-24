"""Rich renderer — panels, tables, state display, event rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rerun.engine.state import get_btc_price

if TYPE_CHECKING:
    from rerun.engine.events import GameEvent
    from rerun.engine.game import ChoiceResult, GameEnding, YearStart
    from rerun.engine.state import PlayerState

SEPARATOR = "━" * 52


def _fmt_money(val: float) -> str:
    """Format money value with ¥ prefix."""
    if abs(val) >= 1_0000_0000:
        return f"¥{val / 1_0000_0000:,.2f}亿"
    if abs(val) >= 1_0000:
        return f"¥{val:,.0f}"
    return f"¥{val:,.0f}"


class GameRenderer:
    """Renders all game screens using rich."""

    def __init__(self, console: Console, typewriter_speed: float = 0.03) -> None:
        self.console = console
        self.speed = typewriter_speed

    def _typewriter(self, text: str) -> None:
        from rerun.ui.effects import typewriter

        typewriter(self.console, text, self.speed)

    # ------------------------------------------------------------------
    # State panel
    # ------------------------------------------------------------------

    def render_state_panel(self, state: PlayerState) -> None:
        """Render the current player state as a compact panel."""
        btc_price = get_btc_price(state.year)
        btc_val = state.btc_amount * btc_price

        grid = Table.grid(padding=(0, 2))
        grid.add_column(justify="left")
        grid.add_column(justify="left")
        grid.add_column(justify="left")
        grid.add_column(justify="left")

        grid.add_row(
            f"💰 存款: {_fmt_money(state.savings)}",
            f"🪙 BTC ×{state.btc_amount:.2f}: {_fmt_money(btc_val)}",
            f"🏠 房产: {state.properties}套",
            f"📈 股票: {_fmt_money(state.stocks)}",
        )
        grid.add_row(
            f"😰 压力: {state.stress}",
            f"💕 关系: {state.relationship}",
            f"🤝 社交: {state.social}",
            f"🌟 声望: {state.reputation}",
        )

        job = state.job_title if state.is_employed else "无业"
        partner = "有" if state.has_partner else "无"
        grid.add_row(
            f"💼 {job}",
            f"💵 月薪: ¥{state.monthly_salary:,.0f}",
            f"❤️ 伴侣: {partner}",
            f"💎 净资产: [bold]{_fmt_money(state.net_worth)}[/bold]",
        )

        self.console.print(Panel(grid, border_style="cyan", padding=(0, 1)))

    # ------------------------------------------------------------------
    # Year start
    # ------------------------------------------------------------------

    def render_year_start(self, ys: YearStart) -> None:
        """Render year header + state + background."""
        self.console.print()
        self.console.print(f"[bold cyan]{SEPARATOR}[/]")
        self.console.print(f"[bold cyan]  📅 {ys.year} 年[/]")
        self.console.print(f"[bold cyan]{SEPARATOR}[/]")

        self.render_state_panel(ys.state)

        btc = ys.year_context.get("btc_price", {})
        if btc:
            self.console.print(
                f"  🪙 BTC 价格：¥{btc.get('low', 0):,} ~ ¥{btc.get('high', 0):,}"
                f"  (年初 ¥{btc.get('start', 0):,} → 年末 ¥{btc.get('end', 0):,})"
            )

        self.console.print()
        self._typewriter(f"  {ys.background}")
        self.console.print()

    # ------------------------------------------------------------------
    # Event
    # ------------------------------------------------------------------

    def render_event(self, event: GameEvent) -> None:
        """Render an event: description + choice options."""
        self.console.print("  [bold]── 事件 ──────────────────────────────────[/]")
        self.console.print()
        self._typewriter(f"  {event.title}")
        self.console.print()

        for line in event.description.split("\n"):
            self._typewriter(f"  {line}")
        self.console.print()

        # Choices
        for choice in event.choices:
            self.console.print(f"  [bold yellow][{choice.key}][/] {choice.text}")
            self.console.print(f"      [dim italic]{choice.hint}[/]")
        self.console.print()

    def prompt_choice(self, valid_keys: list[str]) -> str:
        """Prompt the player to make a choice. Returns validated key."""
        while True:
            keys_str = "/".join(valid_keys)
            try:
                raw = input(f"  你的选择 [{keys_str}] > ").strip().upper()
            except (EOFError, KeyboardInterrupt):
                raw = valid_keys[0]  # default to first on interrupt
            if raw in valid_keys:
                return raw
            self.console.print(f"  [red]无效输入，请输入 {keys_str}[/]")

    # ------------------------------------------------------------------
    # Choice result
    # ------------------------------------------------------------------

    def render_choice_result(self, result: ChoiceResult) -> None:
        """Render the aftermath of a choice."""
        self.console.print()
        self._typewriter(f"  {result.narrative}")
        self.console.print()

        # State changes
        if result.state_changes:
            self._render_state_changes(result.state_changes)

        # Narrator hint
        if result.hint:
            self.console.print()
            self.console.print(f"  [cyan italic]{result.hint}[/]")

        # Achievements
        for ach_id in result.unlocked_achievements:
            self.console.print(f"\n  [bold yellow]🏆 成就解锁：{ach_id}[/]")

        self.console.print()

    def _render_state_changes(self, changes: dict) -> None:
        """Render state value changes with colors."""
        labels = {
            "savings": "💰 存款",
            "btc_amount": "🪙 BTC",
            "properties": "🏠 房产",
            "stocks": "📈 股票",
            "stress": "😰 压力",
            "relationship": "💕 关系",
            "social": "🤝 社交",
            "reputation": "🌟 声望",
            "monthly_salary": "💵 月薪",
            "monthly_expense": "💸 月支出",
            "has_partner": "❤️ 伴侣",
            "is_employed": "💼 工作",
            "job_title": "💼 职位",
        }

        for key, (old_val, new_val) in changes.items():
            label = labels.get(key, key)
            if isinstance(old_val, bool):
                old_s = "有" if old_val else "无"
                new_s = "有" if new_val else "无"
                self.console.print(f"  {label}: {old_s} → [bold]{new_s}[/]")
            elif isinstance(old_val, str):
                self.console.print(f"  {label}: {old_val} → [bold]{new_val}[/]")
            elif isinstance(old_val, (int, float)):
                diff = new_val - old_val
                color = "green" if diff >= 0 else "red"
                sign = "+" if diff >= 0 else ""
                if key in ("savings", "stocks", "monthly_salary", "monthly_expense"):
                    self.console.print(
                        f"  {label}: ¥{old_val:,.0f} → ¥{new_val:,.0f}"
                        f" [{color}]({sign}¥{diff:,.0f})[/]"
                    )
                elif key == "btc_amount":
                    self.console.print(
                        f"  {label}: {old_val:.2f} → {new_val:.2f} [{color}]({sign}{diff:.2f})[/]"
                    )
                else:
                    self.console.print(
                        f"  {label}: {old_val} → {new_val} [{color}]({sign}{diff:.0f})[/]"
                    )

    # ------------------------------------------------------------------
    # Year end
    # ------------------------------------------------------------------

    def render_year_end(self, year: int, state: PlayerState) -> None:
        """Render year-end summary line."""
        self.console.print(f"  [dim]── {year}年结束 ── 净资产: {_fmt_money(state.net_worth)} ──[/]")

    # ------------------------------------------------------------------
    # Ending
    # ------------------------------------------------------------------

    def render_ending(self, ending: GameEnding, narrator_summary: str | None = None) -> None:
        """Render the final settlement screen."""
        state = ending.state
        minutes = int(ending.duration_seconds / 60)

        self.console.print()
        self.console.print(f"[bold cyan]{SEPARATOR}[/]")
        self.console.print("[bold cyan]  🔄 ReRun — 结算报告[/]")
        self.console.print(f"[bold cyan]  📅 2015 → 2025 | 游戏时长: {minutes} 分钟[/]")
        self.console.print(f"[bold cyan]{SEPARATOR}[/]")
        self.console.print()

        # Net worth
        self.console.print(f"  [bold]💰 最终资产: {_fmt_money(state.net_worth)}[/]")
        self.console.print()

        # Asset breakdown table
        table = Table(title="资产构成", border_style="cyan", padding=(0, 1))
        table.add_column("类别", style="bold")
        table.add_column("数值", justify="right")

        btc_val = state.btc_amount * get_btc_price(state.year)
        from rerun.engine.state import get_property_price

        prop_val = state.properties * get_property_price(state.year)

        table.add_row("🪙 BTC", _fmt_money(btc_val))
        table.add_row("🏠 房产", _fmt_money(prop_val))
        table.add_row("💰 存款", _fmt_money(state.savings))
        table.add_row("📈 股票", _fmt_money(state.stocks))
        table.add_row("─" * 10, "─" * 12)
        table.add_row("[bold]💎 净资产[/]", f"[bold]{_fmt_money(state.net_worth)}[/]")
        self.console.print(table)
        self.console.print()

        # You vs baseline
        baseline = ending.baseline_net_worth
        multiplier = state.net_worth / baseline if baseline > 0 else 0
        bar_you = "█" * min(40, max(1, int(state.net_worth / baseline * 10)))
        bar_base = "██"
        self.console.print("  📊 你 vs 普通人（不穿越的基准线）")
        self.console.print(f"  你的资产:   {_fmt_money(state.net_worth)}  [green]{bar_you}[/]")
        self.console.print(f"  普通人资产: {_fmt_money(baseline)}  [dim]{bar_base}[/]")
        self.console.print(f"  倍数: [bold]{multiplier:.1f}x[/]")
        self.console.print()

        # Key choices review
        if state.choices_log:
            self.console.print("  [bold]── 关键抉择回顾 ──[/]")
            for entry in state.choices_log:
                self.console.print(
                    f"  {entry['year']}: {entry['event_title']} → {entry['choice_text']}"
                )
            self.console.print()

        # Achievements
        if state.achievements:
            self.console.print("  [bold]── 🏆 成就 ──[/]")
            for ach in state.achievements:
                self.console.print(f"  {ach}")
            self.console.print()

        # Narrator summary
        if narrator_summary:
            self.console.print("  [bold]── 💡 系统总评 ──[/]")
            self._typewriter(f"  {narrator_summary}")
            self.console.print()

        self.console.print(f"[bold cyan]{SEPARATOR}[/]")

    def render_ending_menu(self) -> str:
        """Show post-ending menu and get choice."""
        self.console.print()
        self.console.print("  [bold yellow][R][/] 🔄 再来一次")
        self.console.print("  [bold yellow][Q][/] 退出游戏")
        self.console.print()
        while True:
            try:
                raw = input("  > ").strip().upper()
            except (EOFError, KeyboardInterrupt):
                return "Q"
            if raw in ("R", "Q"):
                return raw
            self.console.print("  [red]请输入 R 或 Q[/]")
