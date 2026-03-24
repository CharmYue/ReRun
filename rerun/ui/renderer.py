"""Rich renderer — panels, tables, state display, event rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

from rerun.engine.state import get_btc_price, get_property_price

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
    # Helpers
    # ------------------------------------------------------------------

    def _wait_for_continue(self) -> None:
        """Wait for user to press Enter to continue."""
        try:
            input("\n  [按回车继续...]")
        except (EOFError, KeyboardInterrupt):
            pass
        self.console.print("─" * 60)

    # ------------------------------------------------------------------
    # State panel (compact: no relationship/social/reputation)
    # ------------------------------------------------------------------

    def render_state_panel(self, state: PlayerState) -> None:
        """Render the current player state as a compact panel."""
        btc_price = get_btc_price(state.year)
        btc_val = state.btc_amount * btc_price
        job = state.job_title if state.is_employed else "无业"

        # Header bar
        header = f"  📅 {state.year} 年 | 💼 {job} | 💵 月薪 ¥{state.monthly_salary:,.0f}"

        # Asset lines
        lines = [header, SEPARATOR]

        # Row 1: savings + BTC
        row1 = f"  💰 存款: {_fmt_money(state.savings)}"
        if state.btc_amount > 0:
            row1 += f"    🪙 BTC ×{state.btc_amount:.2f}: {_fmt_money(btc_val)}"
        lines.append(row1)

        # Row 2: conditional assets
        extras = []
        if state.properties > 0:
            prop_val = state.properties * get_property_price(state.year)
            extras.append(f"🏠 房产: {state.properties}套 ({_fmt_money(prop_val)})")
        if state.stocks > 0:
            extras.append(f"📈 股票: {_fmt_money(state.stocks)}")
        if state.has_partner:
            extras.append("❤️ 伴侣: 有")
        if extras:
            lines.append("  " + "    ".join(extras))

        # Net worth
        lines.append(f"  💎 净资产: [bold]{_fmt_money(state.net_worth)}[/bold]")

        # Stress bar (visual)
        stress = state.stress
        filled = stress // 10
        empty = 10 - filled
        if stress >= 80:
            bar_color = "red"
        elif stress >= 50:
            bar_color = "yellow"
        else:
            bar_color = "green"
        bar = "■" * filled + "□" * empty
        lines.append(f"  😰 压力: [{bar_color}]{bar}[/] {stress}%    [dim]← 超80%触发坏事，满了=住院[/]")

        lines.append(SEPARATOR)

        self.console.print("\n".join(lines))

    # ------------------------------------------------------------------
    # Year start
    # ------------------------------------------------------------------

    def render_year_start(self, ys: YearStart, prev_state: PlayerState | None = None) -> None:
        """Render year start in two pages: macro context, then asset summary."""

        # ── 画面1: 年份转场 + 宏观大事件 ──
        self.console.print()
        self.console.print(f"[bold cyan]{SEPARATOR}[/]")
        self.console.print(f"[bold cyan]  📅 {ys.year} 年[/]")
        self.console.print(f"[bold cyan]{SEPARATOR}[/]")
        self.console.print()

        btc = ys.year_context.get("btc_price", {})
        if btc:
            self.console.print(
                f"  🪙 BTC 价格：¥{btc.get('start', 0):,} → ¥{btc.get('end', 0):,}"
                f"  (最低 ¥{btc.get('low', 0):,} / 最高 ¥{btc.get('high', 0):,})"
            )
            self.console.print()

        self._typewriter(f"  {ys.background}")

        self._wait_for_continue()

        # ── 画面2: 你的资产变化 ──
        self.console.print()

        # Show BTC value change if player holds BTC
        if ys.state.btc_amount > 0 and prev_state is not None:
            prev_btc_price = get_btc_price(prev_state.year)
            cur_btc_price = get_btc_price(ys.year)
            prev_btc_val = ys.state.btc_amount * prev_btc_price
            cur_btc_val = ys.state.btc_amount * cur_btc_price
            ratio = (cur_btc_price / prev_btc_price - 1) * 100 if prev_btc_price > 0 else 0
            sign = "+" if ratio >= 0 else ""
            color = "green" if ratio >= 0 else "red"
            self.console.print(
                f"  🪙 你的 BTC ×{ys.state.btc_amount:.2f}："
                f" {_fmt_money(prev_btc_val)} → {_fmt_money(cur_btc_val)}"
                f" [{color}]({sign}{ratio:.0f}%)[/]"
            )

        # Salary income
        if ys.state.is_employed:
            annual_salary = ys.state.annual_salary_income
            self.console.print(
                f"  💵 月薪到账：¥{ys.state.monthly_salary:,.0f} × 12 ="
                f" {_fmt_money(annual_salary)}"
            )
        else:
            self.console.print("  💵 收入：无业状态，无工资收入")

        # Detailed living costs breakdown
        costs = ys.state.calculate_annual_costs()
        total_cost = sum(costs.values())
        cost_parts = " + ".join(f"{k} {_fmt_money(v)}" for k, v in costs.items())
        self.console.print(f"  🏠 年度生活开支：-{_fmt_money(total_cost)}")
        self.console.print(f"      [dim]（{cost_parts}）[/dim]")

        # Net balance
        net_income = ys.state.annual_net_income
        net_color = "green" if net_income >= 0 else "red"
        net_sign = "+" if net_income >= 0 else ""
        self.console.print(
            f"  📊 年度结余：[{net_color}]{net_sign}{_fmt_money(abs(net_income))}"
            f"[/{net_color}]（不含投资收益）"
        )

        self.console.print()
        self.render_state_panel(ys.state)

        self._wait_for_continue()

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

    # Skill names and unlock descriptions
    SKILL_NAMES = {
        "investment_iq": ("🧠 投资认知", {
            2: "解锁：股票选项，显示基础涨跌",
            3: "解锁：基金定投 | 房产投资",
            4: "解锁：天使投资/创业投资",
            5: "解锁：「内幕消息」类事件",
        }),
        "career_level": ("💼 职业能力", {
            2: "可跳槽到更好公司，月薪 10-15K",
            3: "中层管理，月薪 20-30K",
            4: "高级岗位/合伙人，月薪 40-60K",
            5: "高管/创业者，收入不封顶",
        }),
        "network": ("🤝 人脉圈层", {
            2: "出现大学同学相关事件",
            3: "出现行业人脉事件（前辈提携）",
            4: "出现高净值人脉（投资人朋友）",
            5: "出现「贵人」事件",
        }),
        "emotional_iq": ("💕 情商", {
            2: "恋爱选项增加，不容易说错话",
            3: "能看穿对方真实想法（显示隐藏信息）",
            4: "社交事件中获得额外好处",
            5: "解锁「人格魅力」事件",
        }),
    }

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

        # Separate skill changes for special rendering
        skill_changes = {}
        normal_changes = {}
        for key, val in changes.items():
            if key in self.SKILL_NAMES:
                skill_changes[key] = val
            else:
                normal_changes[key] = val

        # Render normal changes
        for key, (old_val, new_val) in normal_changes.items():
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

        # Render skill upgrades with special popup format
        for key, (old_val, new_val) in skill_changes.items():
            if not isinstance(old_val, (int, float)):
                continue
            new_level = int(new_val)
            old_level = int(old_val)
            if new_level <= old_level:
                continue
            skill_name, unlock_map = self.SKILL_NAMES[key]
            unlock_text = unlock_map.get(new_level, "")
            self.console.print()
            self.console.print(f"  [bold green]📈 [能力提升！][/]")
            self.console.print(f"  {skill_name} Lv.{old_level} → Lv.{new_level}")
            if unlock_text:
                self.console.print(f"  [bold yellow]🔓 新解锁：{unlock_text}[/]")

    # ------------------------------------------------------------------
    # Year end
    # ------------------------------------------------------------------

    def render_year_end(self, year: int, state: PlayerState) -> None:
        """Render year-end summary line."""
        self.console.print(f"  [dim]── {year}年结束 ── 净资产: {_fmt_money(state.net_worth)} ──[/]")

    # ------------------------------------------------------------------
    # Bankruptcy (Game Over)
    # ------------------------------------------------------------------

    def render_bankruptcy(self, state: PlayerState) -> str:
        """Render the bankruptcy screen. Returns player choice: R/N/Q."""
        self.console.print()
        self.console.print(f"[bold red]{SEPARATOR}[/]")
        self.console.print("[bold red]  💸 你的存款跌破了零...[/]")
        self.console.print(f"[bold red]{SEPARATOR}[/]")
        self.console.print()

        self._typewriter("  你付不起下个月的房租了。")
        self._typewriter("  信用卡账单像催命符一样躺在手机里。")
        self.console.print()
        self._typewriter("  但你没有真的「死」。")
        self.console.print()
        self._typewriter("  你搬回了老家，在父母的小区附近")
        self._typewriter("  找了份月薪 4500 的工作。")
        self._typewriter("  你妈每天给你做饭，你爸假装不知道你破产了。")
        self.console.print()

        self.console.print(
            "  [cyan italic]💬 [系统] 重生者也会失败。[/]\n"
            "  [cyan italic]   但和上辈子不同的是——你知道未来还有机会。[/]\n"
            "  [cyan italic]   问题是，你还有勇气再赌一次吗？[/]"
        )
        self.console.print()

        self.console.print("  [bold yellow][R][/] 🔄 从这里继续（困难模式：低薪重新开始）")
        self.console.print("  [bold yellow][N][/] 🔄 ReRun：回到 2015 重新来过")
        self.console.print("  [bold yellow][Q][/] 退出游戏")
        self.console.print()

        while True:
            try:
                raw = input("  > ").strip().upper()
            except (EOFError, KeyboardInterrupt):
                return "Q"
            if raw in ("R", "N", "Q"):
                return raw
            self.console.print("  [red]请输入 R、N 或 Q[/]")

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
