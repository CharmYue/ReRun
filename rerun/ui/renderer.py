"""Rich renderer — panels, tables, state display, event rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

from rerun.engine.achievements import get_achievement_display
from rerun.engine.state import get_btc_price, get_property_price

if TYPE_CHECKING:
    from rerun.engine.events import GameEvent
    from rerun.engine.game import ChoiceResult, GameEnding, YearStart
    from rerun.engine.state import PlayerState

SEPARATOR = "━" * 52


def _fmt_money(val: float) -> str:
    """Format money value — 万/亿 units so users don't have to count zeros.

    Spec E1: <1万 show raw, 1万-1亿 show X.X万, >=1亿 show X.X亿.
    """
    if val == 0:
        return "¥0"
    neg = val < 0
    a = abs(val)
    if a < 10000:
        s = f"¥{a:,.0f}"
    elif a < 1_0000_0000:
        wan = a / 10000
        s = f"¥{wan:.1f}万" if wan != int(wan) else f"¥{int(wan)}万"
    else:
        yi = a / 1_0000_0000
        s = f"¥{yi:.1f}亿"
    return f"-{s}" if neg else s


class GameRenderer:
    """Renders all game screens using rich."""

    def __init__(self, console: Console, typewriter_speed: float = 0.03) -> None:
        self.console = console
        self.speed = typewriter_speed

    def _typewriter(self, text: str) -> None:
        # V4 spec §五: disable typewriter effect, use direct print instead
        self.console.print(text)

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
        job = state.display_job_title

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

    def render_year_start(
        self, ys: YearStart, prev_state: PlayerState | None = None, salary_raise: float = 0.0
    ) -> None:
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

        # Salary income + raise display (B5)
        if ys.state.has_income:
            annual_salary = ys.state.annual_salary_income
            if ys.state.is_self_employed:
                salary_line = f"  💵 年收入：{_fmt_money(annual_salary)}（{ys.state.job_title}）"
            else:
                salary_line = f"  💵 年收入：{_fmt_money(annual_salary)}（月薪 {_fmt_money(ys.state.monthly_salary)}）"
            if salary_raise > 0:
                salary_line += f"  [green]涨薪 +{_fmt_money(salary_raise)}/月[/]"
            self.console.print(salary_line)
        else:
            self.console.print("  💵 收入：无业状态，无工资收入")

        # Detailed living costs breakdown
        costs = ys.state.calculate_annual_costs()
        total_cost = sum(costs.values())
        cost_parts = " + ".join(f"{k} {_fmt_money(v)}" for k, v in costs.items())
        self.console.print(f"  🏠 年支出：{_fmt_money(total_cost)}")
        self.console.print(f"      [dim]（{cost_parts}）[/dim]")

        # B1 fix: Net balance = income - cost, negative shown in red with minus sign
        net_income = ys.state.annual_net_income
        if net_income > 0:
            self.console.print(f"  📊 年结余：[green]+{_fmt_money(net_income)}[/]")
        elif net_income < 0:
            self.console.print(f"  📊 年结余：[red]-{_fmt_money(abs(net_income))}[/]  ← [red]入不敷出[/]")
        else:
            self.console.print(f"  📊 年结余：[dim]¥0（刚好收支平衡）[/]")

        self.console.print()
        self.render_state_panel(ys.state)

        self._wait_for_continue()

    # ------------------------------------------------------------------
    # Event
    # ------------------------------------------------------------------

    def render_event(self, event: GameEvent, event_index: int = 0, total_events: int = 0) -> None:
        """Render an event: description + choice options."""
        # E2: show year in event header
        count_str = f" · 事件 {event_index}/{total_events}" if total_events > 0 else " · 事件"
        self.console.print(f"  [bold]── 📅 {event.year} 年{count_str} ──────────────────────[/]")
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
        """Prompt the player to make a choice. Accepts letters (A/B/C) or numbers (1/2/3)."""
        # Build mapping: both letter keys and numeric indices
        num_map: dict[str, str] = {}
        for i, key in enumerate(valid_keys):
            num_map[str(i + 1)] = key

        while True:
            keys_str = "/".join(valid_keys)
            try:
                raw = input(f"  你的选择 [{keys_str}] > ").strip().upper()
            except (EOFError, KeyboardInterrupt):
                raw = valid_keys[0]
            if raw in valid_keys:
                return raw
            if raw in num_map:
                return num_map[raw]
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

    # B6: Fields that should never be shown to the player
    _HIDDEN_FIELDS = {
        "flags", "choices_log", "achievements", "max_btc_held",
        "times_sold_btc", "times_helped_family", "breakups",
        "moved_home_count",
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
            # B6: hide internal variables from player
            if key in self._HIDDEN_FIELDS:
                continue
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

    def render_year_end(
        self, year: int, state: PlayerState, prev_state: PlayerState | None = None
    ) -> None:
        """Render year-end summary with key changes comparison."""
        self.console.print()
        self.console.print(f"  [bold]── 📊 {year} 年度总结 ──────────────────────[/]")
        self.console.print()

        if prev_state:
            # Savings change
            s_diff = state.savings - prev_state.savings
            s_color = "green" if s_diff >= 0 else "red"
            s_sign = "+" if s_diff >= 0 else ""
            self.console.print(
                f"  💰 存款    {_fmt_money(prev_state.savings)} → {_fmt_money(state.savings)}"
                f"    [{s_color}]{s_sign}{_fmt_money(s_diff)}[/]"
            )

            # BTC line (if any)
            if state.btc_amount > 0 or prev_state.btc_amount > 0:
                btc_val = state.btc_value
                self.console.print(
                    f"  🪙 BTC     {prev_state.btc_amount:.1f}个 → {state.btc_amount:.1f}个"
                    f"       💎 市值 {_fmt_money(btc_val)}"
                )

            # Salary change
            if state.monthly_salary != prev_state.monthly_salary:
                sal_diff = state.monthly_salary - prev_state.monthly_salary
                sal_color = "green" if sal_diff >= 0 else "red"
                self.console.print(
                    f"  💵 月薪    {_fmt_money(prev_state.monthly_salary)} → {_fmt_money(state.monthly_salary)}"
                    f"    [{sal_color}]涨薪 +{_fmt_money(sal_diff)}[/]"
                )

            # Stress
            self.console.print(f"  😰 压力    {prev_state.stress}% → {state.stress}%")

            # Net worth with change
            nw_diff = state.net_worth - prev_state.net_worth
            nw_color = "green" if nw_diff >= 0 else "red"
            nw_sign = "+" if nw_diff >= 0 else ""
            self.console.print()
            self.console.print(f"  💎 净资产: [bold]{_fmt_money(state.net_worth)}[/]")
            self.console.print(f"  📈 较去年: [{nw_color}]{nw_sign}{_fmt_money(nw_diff)}[/]")
        else:
            # First year: show breakdown so player can see BTC is included
            self.console.print(f"  💰 存款    {_fmt_money(state.savings)}")
            if state.btc_amount > 0:
                btc_val = state.btc_value
                self.console.print(
                    f"  🪙 BTC     {state.btc_amount:.1f}个"
                    f"       💎 市值 {_fmt_money(btc_val)}"
                )
            self.console.print()
            self.console.print(f"  💎 净资产: [bold]{_fmt_money(state.net_worth)}[/]")

        self.console.print()
        self.console.print(f"  [dim]── 按回车进入 {year + 1} 年 ──────────────────[/]")

        self._wait_for_continue()

    # ------------------------------------------------------------------
    # Bankruptcy (Game Over)
    # ------------------------------------------------------------------

    def render_survival_event(self, state: PlayerState, *, can_move_home: bool = True) -> str:
        """Render near-bankruptcy survival event. Returns choice: A/B/C."""
        self.console.print()
        self.console.print(f"[bold red]{SEPARATOR}[/]")
        self.console.print("[bold red]  ⚠️ 紧急状态：你快撑不住了[/]")
        self.console.print(f"[bold red]{SEPARATOR}[/]")
        self.console.print()

        self._typewriter("  你翻遍了所有口袋和账户。存款见底了。")

        btc_val = state.btc_value
        if state.btc_amount > 0:
            self.console.print(
                f"  但你的 BTC 钱包里还有 {state.btc_amount:.2f} 个 BTC，"
                f"当前价值约 {_fmt_money(btc_val)}。"
            )
        self.console.print()
        self._typewriter("  你必须做个决定：")
        self.console.print()

        options = []
        if state.btc_amount > 0:
            btc_price = get_btc_price(state.year)
            needed = abs(state.savings) + 5000
            btc_needed = min(state.btc_amount, needed / btc_price if btc_price > 0 else 0)
            self.console.print(
                f"  [bold yellow][A][/] 卖掉 {btc_needed:.2f} 个 BTC，够撑过这一年"
            )
            self.console.print(
                f"      [dim italic]💬 [系统] 断臂求生。你知道 BTC 以后还会涨。但命比币重要。[/]"
            )
            options.append("A")

        # B5: only allow moving home once
        if can_move_home:
            self.console.print(
                "  [bold yellow][B][/] 搬回父母家，靠省钱硬扛"
            )
            self.console.print(
                "      [dim italic]💬 [系统] 月支出降到 ¥1,500。自尊心受点伤，但钱包松了口气。[/]"
            )
            options.append("B")
        else:
            self.console.print(
                "  [dim][B] 搬回父母家 —— ⚠️ 你已经搬回去过一次了，不能再搬了[/]"
            )

        if state.network >= 3:
            self.console.print(
                f"  [bold yellow][C][/] 找朋友借 {_fmt_money(abs(state.savings) + 10000)} 周转"
            )
            self.console.print(
                "      [dim italic]💬 [系统] 你的人脉圈还够用。但欠人情的滋味不好受。[/]"
            )
            options.append("C")
        else:
            self.console.print(
                "  [dim][C] 找朋友借钱 —— ⚠️ 你的朋友圈……不太有能借钱的人（需要人脉 Lv.3）[/]"
            )

        self.console.print()
        self.console.print(
            "  [cyan italic]💬 [系统] 重生者也会穷到吃土。[/]\n"
            "  [cyan italic]   知道 BTC 能涨到 50 万，但今晚的外卖钱都没有。[/]\n"
            "  [cyan italic]   这种反差，只有你能体会。[/]"
        )
        self.console.print()

        while True:
            keys_str = "/".join(options)
            try:
                raw = input(f"  你的选择 [{keys_str}] > ").strip().upper()
            except (EOFError, KeyboardInterrupt):
                raw = options[0]
            if raw in options:
                return raw
            self.console.print(f"  [red]请输入 {keys_str}[/]")

    def render_bankruptcy(self, state: PlayerState) -> str:
        """Render the true bankruptcy screen (no assets left). Returns: R/N/Q."""
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

    # ------------------------------------------------------------------
    # Ending — cinematic montage (5 phases)
    # ------------------------------------------------------------------

    def render_ending(self, ending: GameEnding, narrator_summary: str | None = None) -> str:
        """Render the full cinematic ending. Returns menu choice: R/Q."""
        state = ending.state

        # Phase 1: Montage
        self._render_montage(state)

        # Phase 2: Final scores
        self._render_final_scores(ending)

        # Phase 3: Achievements
        self._render_achievements(state)

        # Phase 4: System commentary
        self._render_system_commentary(ending)

        # Phase 5: Parallel lives + menu
        return self._render_parallel_lives_and_menu(state)

    # --- Phase 1: Montage ---

    def _render_montage(self, state: PlayerState) -> None:
        """Generate and display cinematic montage from game history."""
        self.console.print()
        self.console.print(f"[bold cyan]{SEPARATOR}[/]")
        self.console.print("[bold cyan]  🔄 ReRun — 你的十年[/]")
        self.console.print(f"[bold cyan]{SEPARATOR}[/]")

        snippets = self._generate_montage_snippets(state)
        for snippet in snippets:
            self.console.print()
            for line in snippet.split("\n"):
                self._typewriter(f"  {line}")
            self._wait_for_continue()

    def _generate_montage_snippets(self, state: PlayerState) -> list[str]:
        """Pick the most important event per year and format as cinematic memories."""
        # Group choices by year
        by_year: dict[int, list[dict]] = {}
        for entry in state.choices_log:
            yr = entry.get("year", 0)
            by_year.setdefault(yr, []).append(entry)

        snippets: list[str] = []

        for year in range(2015, 2026):
            entries = by_year.get(year, [])
            snippet = self._format_year_snippet(year, entries, state)
            if snippet:
                snippets.append(snippet)

        # Ensure last snippet has ending feel
        if snippets:
            last = snippets[-1]
            if "2025" in last and not last.endswith("。"):
                last += "\n十年，就这样过完了。"
                snippets[-1] = last

        return snippets

    def _format_year_snippet(
        self, year: int, entries: list[dict], state: PlayerState
    ) -> str | None:
        """Format a single year's most important event as a montage snippet."""
        if not entries:
            # Generate context-based snippet for years without logged choices
            return self._generate_contextual_snippet(year, state)

        # Pick the most "dramatic" entry (highest abs consequence impact)
        best = max(entries, key=lambda e: self._drama_score(e))
        title = best.get("event_title", "")
        choice_text = best.get("choice_text", "")
        cons = best.get("consequences", {})

        # Try pattern-based formatting first
        snippet = self._match_montage_pattern(year, title, choice_text, cons, state)
        if snippet:
            return snippet

        # Fallback: generic format from event data
        return f"{year}年。{title}\n你选择了：{choice_text}"

    def _drama_score(self, entry: dict) -> float:
        """Score how dramatic/important a choice was."""
        cons = entry.get("consequences", {})
        score = 0.0
        score += abs(cons.get("savings", 0)) / 10000
        score += abs(cons.get("btc_amount", 0)) * 50
        score += abs(cons.get("stress", 0))
        score += abs(cons.get("properties", 0)) * 30
        score += abs(cons.get("relationship", 0)) * 2
        if cons.get("is_employed") is False:
            score += 40
        return score

    def _match_montage_pattern(
        self, year: int, title: str, choice_text: str, cons: dict, state: PlayerState
    ) -> str | None:
        """Match event to a cinematic montage template."""
        title_lower = title.lower()
        btc_price = get_btc_price(year)

        # BTC purchase
        if cons.get("btc_amount", 0) > 0:
            btc_bought = cons["btc_amount"]
            cost = abs(cons.get("savings", 0))
            return (
                f"{year}年。你花{_fmt_money(cost)}买了{btc_bought:.2f}个BTC。"
                f"当时1个才¥{btc_price:,.0f}。\n"
                f"没人觉得这是个好主意。除了你。"
            )

        # BTC sale
        if cons.get("btc_amount", 0) < 0:
            btc_sold = abs(cons["btc_amount"])
            gain = cons.get("savings", 0)
            return (
                f"{year}年。你卖了{btc_sold:.2f}个BTC，收回{_fmt_money(gain)}。\n"
                f"有人说你傻，有人说你聪明。你只是沉默。"
            )

        # Property purchase
        if cons.get("properties", 0) > 0:
            return (
                f"{year}年。你买了房。首付交出去的那一刻，\n"
                f"你觉得自己终于像个大人了。"
            )

        # Entrepreneurship (must check before layoff — both set is_employed=False)
        if cons.get("is_employed") is False and ("创业" in choice_text or "自己干" in choice_text):
            return (
                f"{year}年。你辞了职，开始创业。\n"
                f"从此，你的命运只属于自己。"
            )

        # Job loss / layoff
        if cons.get("is_employed") is False or "裁" in title or "失业" in title:
            return (
                f"{year}年。你被裁了。拿了N+1走出大楼。\n"
                f"阳光很好。你觉得……好像也没那么糟。"
            )

        # Job change / career
        if "跳槽" in title or "工作" in title or cons.get("monthly_salary", 0) > 0:
            salary = cons.get("monthly_salary", 0)
            if salary > 0:
                return (
                    f"{year}年。你换了工作。月薪涨了{_fmt_money(salary)}。\n"
                    f"你知道这个赛道的未来。"
                )

        # Family help
        if "家" in title or "妈" in title or "爸" in title or "亲" in title:
            family_cost = abs(cons.get("savings", 0)) if cons.get("savings", 0) < 0 else 0
            if family_cost > 0:
                return (
                    f"{year}年。家人需要{_fmt_money(family_cost)}。你没有犹豫。\n"
                    f"有些账，不是用钱算的。"
                )
            if cons.get("relationship", 0) > 0:
                return (
                    f"{year}年。过年回家。一大桌子人。\n"
                    f"你举起酒杯，觉得这一刻值得所有的辛苦。"
                )

        # Mask stockpile / COVID related
        if "口罩" in title or "疫情" in title or "新冠" in title:
            return (
                f"{year}年。你做了一件所有人都觉得疯狂的事。\n"
                f"后来证明，你是对的。"
            )

        # Romance
        if "恋" in title or "感情" in title or "对象" in title or cons.get("has_partner") is True:
            return (
                f"{year}年。你遇到了一个人。\n"
                f"在满脑子K线图的日子里，这是唯一让你心跳加速的事。"
            )

        # Breakup
        if "分手" in title or cons.get("has_partner") is False:
            return (
                f"{year}年。你失去了一个人。\n"
                f"你盯着屏幕上的数字，第一次觉得钱不能买到一切。"
            )

        # High stress events
        if cons.get("stress", 0) >= 20:
            return (
                f"{year}年。压力大到失眠。\n"
                f"你知道未来会好的。但身体不知道。"
            )

        return None

    def _generate_contextual_snippet(self, year: int, state: PlayerState) -> str | None:
        """Generate a snippet for years without specific logged choices."""
        # Only generate for key context years, skip mundane ones
        btc_price = get_btc_price(year)

        if year == 2017 and state.btc_amount > 0:
            val = state.btc_amount * btc_price
            return (
                f"{year}年。BTC涨到了¥{btc_price:,.0f}。你的持仓值{_fmt_money(val)}。\n"
                f"所有人都在问你买了没。你面不改色：「没有。」"
            )

        if year == 2020:
            return (
                f"{year}年。世界停转了。\n"
                f"你坐在家里，看着窗外空无一人的街道，\n"
                f"觉得重生者的记忆从来没有这么沉重过。"
            )

        if year == 2025:
            return (
                f"{year}年。最后一年了。\n"
                f"你站在阳台上，回想这十年走过的路。\n"
                f"十年，就这样过完了。"
            )

        return None

    # --- Phase 2: Final scores ---

    def _render_final_scores(self, ending: GameEnding) -> None:
        """Render the final asset summary."""
        state = ending.state
        self.console.print()
        self.console.print(f"[bold cyan]{SEPARATOR}[/]")
        self.console.print()
        self._typewriter("  十年结束了。")
        self.console.print()

        # Net worth headline
        self.console.print(f"  💎 最终净资产: [bold]{_fmt_money(state.net_worth)}[/]")
        multiplier = state.net_worth / ending.initial_savings if ending.initial_savings > 0 else 0
        self.console.print(
            f"  📈 起点 {_fmt_money(ending.initial_savings)}"
            f" → 终点 {_fmt_money(state.net_worth)}"
            f"（{multiplier:.1f}倍）"
        )
        self.console.print()

        # Comparison bar
        baseline = ending.baseline_net_worth
        bar_len_you = min(40, max(1, int(state.net_worth / max(baseline, 1) * 10)))
        bar_len_base = max(1, min(40, int(10)))  # baseline is the "10" reference
        bar_you = "█" * bar_len_you
        bar_base = "██"
        self.console.print("  ┌─────────────────────────────────────────┐")
        self.console.print(
            f"  │ 你的十年    [green]{bar_you}[/] {_fmt_money(state.net_worth)}"
        )
        self.console.print(
            f"  │ 普通人的十年 [dim]{bar_base}[/] {_fmt_money(baseline)}"
        )
        self.console.print("  └─────────────────────────────────────────┘")
        self.console.print()

        # Asset breakdown
        self.console.print("          资产构成")
        if state.savings != 0:
            self.console.print(f"  💰 存款   {_fmt_money(state.savings)}")
        if state.btc_amount > 0:
            btc_val = state.btc_amount * get_btc_price(state.year)
            self.console.print(f"  🪙 BTC    {state.btc_amount:.2f}个  {_fmt_money(btc_val)}")
        if state.properties > 0:
            prop_val = state.properties * get_property_price(state.year)
            self.console.print(f"  🏠 房产   {state.properties}套  {_fmt_money(prop_val)}")
        if state.stocks > 0:
            self.console.print(f"  📈 股票   {_fmt_money(state.stocks)}")
        self.console.print(f"  💎 总计   [bold]{_fmt_money(state.net_worth)}[/]")

        self._wait_for_continue()

    # --- Phase 3: Achievements ---

    def _render_achievements(self, state: PlayerState) -> None:
        """Render achievements: unlocked with full display, locked with just name."""
        from rerun.engine.achievements import _load_achievements

        all_achs = _load_achievements()
        # Flatten all achievement entries
        all_entries: list[dict] = []
        for category in all_achs.values():
            all_entries.extend(category)

        unlocked = set(state.achievements)
        unlocked_list = [a for a in all_entries if a["id"] in unlocked]
        locked_list = [a for a in all_entries if a["id"] not in unlocked and not a.get("hidden")]

        self.console.print()
        self.console.print(f"[bold cyan]{SEPARATOR}[/]")
        self.console.print()

        if unlocked_list:
            self.console.print(f"  🏆 你解锁了 {len(unlocked_list)} 个成就：")
            self.console.print()
            for ach in unlocked_list:
                self.console.print(
                    f"  {ach['emoji']} [{ach['name']}] — {ach['description']}"
                )
        else:
            self.console.print("  🏆 你没有解锁任何成就。下次加油！")

        if locked_list:
            self.console.print()
            locked_display = " ".join(f"🔒 [{a['name']}]" for a in locked_list)
            self.console.print(f"  [dim]未解锁：{locked_display}[/]")

        self._wait_for_continue()

    # --- Phase 4: System commentary ---

    def _render_system_commentary(self, ending: GameEnding) -> None:
        """Generate and display personalized system commentary."""
        state = ending.state
        self.console.print()
        self.console.print(f"[bold cyan]{SEPARATOR}[/]")
        self.console.print()
        self.console.print("  [bold]💬 [系统最终评价][/]")
        self.console.print()

        # Opening line
        mult = state.net_worth / ending.initial_savings if ending.initial_savings > 0 else 0
        self._typewriter(
            f"  你用十年把{_fmt_money(ending.initial_savings)}"
            f"变成了{_fmt_money(state.net_worth)}。"
        )
        self.console.print()

        # What player did right
        did_right: list[str] = []
        if state.btc_amount > 0 and state.btc_value > 100_000:
            did_right.append("在别人不懂的时候买了BTC")
        if "diamond_hands" in state.achievements:
            did_right.append("在所有人恐惧的时候拿住了")
        if "bottom_fisher" in state.achievements:
            did_right.append("在最恐慌的时候加仓")
        if state.properties > 0:
            did_right.append("买了房，有了自己的窝")
        if state.has_partner:
            did_right.append("找到了爱情")
        if "filial_child" in state.achievements:
            did_right.append("每次家人有难都帮了忙")
        if state.career_level >= 4:
            did_right.append("事业有成")
        if mult >= 10:
            did_right.append("资产翻了十倍以上")

        if did_right:
            self._typewriter("  你做对了很多事：" + "，\n  ".join(did_right) + "。")
            self.console.print()

        # What player missed
        missed: list[str] = []
        if state.properties == 0:
            missed.append("你没有买房")
        if not state.has_partner:
            missed.append("没有谈恋爱")
        if not state.is_employed and state.career_level < 3:
            missed.append("后来甚至没有工作")
        if state.stress >= 70:
            missed.append("压力大到快要崩溃")
        if state.btc_amount == 0 and state.flags.get("bought_btc_2015"):
            missed.append("曾经拥有BTC，但全卖了")
        if "clown" in state.achievements:
            missed.append("知道未来还亏了钱")
        if state.relationship < 30:
            missed.append("和家人的关系越来越远")

        if missed:
            self._typewriter("  但你也错过了一些东西：")
            self._typewriter("  " + "。".join(missed) + "。")
            self.console.print()

        # Closing reflection
        if state.net_worth > 3_000_000:
            self._typewriter("  作为重生者，你的财富线近乎完美。")
            self._typewriter("  但人生不只有财富线。")
        elif state.net_worth > ending.baseline_net_worth:
            self._typewriter("  你比不穿越的自己活得好了一些。")
            self._typewriter("  但「好一些」就够了吗？")
        else:
            self._typewriter("  你知道所有答案，却没拿到高分。")
            self._typewriter("  也许，人生的考试从来不是开卷就能满分。")

        self.console.print()
        self._typewriter("  如果再来一次——你会做出不同的选择吗？")

        self._wait_for_continue()

    # --- Phase 5: Parallel lives + menu ---

    def _render_parallel_lives_and_menu(self, state: PlayerState) -> str:
        """Render parallel lives easter eggs and final menu. Returns R/Q."""
        parallels = self._generate_parallel_lives(state)

        if parallels:
            self.console.print()
            self.console.print(f"[bold cyan]{SEPARATOR}[/]")
            self.console.print()
            self.console.print("  [bold]🔮 [你没有体验到的平行人生][/]")
            self.console.print()
            for p in parallels:
                self.console.print(f"  · {p}")
                self.console.print()

            self._typewriter("  💬 [系统] 每一个选择都通向一个不同的宇宙。")
            self._typewriter("     你只活了其中一个。")

            self._wait_for_continue()

        # Final menu
        self.console.print()
        self.console.print(f"[bold cyan]{SEPARATOR}[/]")
        self.console.print("  [bold yellow][R][/] 🔄 再来一次    [bold yellow][Q][/] 退出")
        self.console.print(f"[bold cyan]{SEPARATOR}[/]")
        self.console.print()

        while True:
            try:
                raw = input("  > ").strip().upper()
            except (EOFError, KeyboardInterrupt):
                return "Q"
            if raw in ("R", "Q"):
                return raw
            self.console.print("  [red]请输入 R 或 Q[/]")

    def _generate_parallel_lives(self, state: PlayerState) -> list[str]:
        """Generate parallel life hints based on choices the player DIDN'T make."""
        parallels: list[str] = []
        flags = state.flags

        # --- BTC-related ---
        if not flags.get("bought_btc_2015"):
            parallels.append(
                "如果你2015年买了BTC——\n"
                "  到2025年，哪怕只买1个，也值70万。\n"
                "  但你永远不会知道拿住有多难。"
            )
        elif flags.get("btc_choice_2015") == "all_in" and state.btc_amount > 0:
            parallels.append(
                "如果你当初只买了1万试试水——\n"
                "  你不会经历2016年吃土的日子\n"
                "  但你的最终资产也只有现在的三分之一"
            )
        elif flags.get("btc_choice_2015") in ("small", "moderate") and state.btc_amount > 0:
            parallels.append(
                "如果你2015年梭哈了——\n"
                "  前两年会很苦，但到2025年\n"
                "  你的BTC值" + _fmt_money(state.savings * 3) + "以上"
            )

        if flags.get("bought_btc_2015") and state.btc_amount > 0 and not flags.get("took_profit_2017"):
            parallels.append(
                "如果你2017年在高点卖了一半——\n"
                "  2018年暴跌时你会睡得安稳很多\n"
                "  但最终总资产会少一些"
            )
        elif flags.get("took_profit_2017"):
            parallels.append(
                "如果你2017年一个都没卖——\n"
                "  2018年暴跌时你会承受巨大的压力\n"
                "  但如果扛住了，最终回报会更高"
            )

        if flags.get("bought_btc_2015") and not flags.get("friends_know_btc"):
            parallels.append(
                "如果你2017年跟朋友坦白买了BTC——\n"
                "  2018年会有朋友因为跟着你买亏钱来找你算账\n"
                "  但2021年他们又会来感谢你"
            )
        elif flags.get("friends_know_btc"):
            parallels.append(
                "如果你一直保密——\n"
                "  你不会失去那些朋友\n"
                "  但「闷声发大财」的孤独，也是一种代价"
            )

        # --- Housing ---
        if not flags.get("bought_house_2016") and state.properties == 0:
            parallels.append(
                "如果你2016年买了房——\n"
                "  2024年它值150万，你妈逢人就夸你有远见\n"
                "  但你的BTC仓位会少很多"
            )
        elif flags.get("bought_house_2016"):
            parallels.append(
                "如果你没买房，把钱都留给了BTC——\n"
                "  你会多买好几个BTC\n"
                "  但你妈可能到现在还在催你"
            )

        # --- Family ---
        if not flags.get("helped_family_2015"):
            parallels.append(
                "如果你当年帮了表妹——\n"
                "  2019年她毕业后会请你吃顿大餐\n"
                "  那种温暖，比任何投资回报都真实"
            )

        # --- Career ---
        if not flags.get("pivoted_to_ai_2018"):
            parallels.append(
                "如果你2018年转行做了AI——\n"
                "  2023年ChatGPT爆发时，你是最抢手的人\n"
                "  年薪80万的offer随便挑"
            )
        elif flags.get("pivoted_to_ai_2018"):
            parallels.append(
                "如果你2018年没转AI——\n"
                "  2023年你会站在岸上看别人冲浪\n"
                "  「现在学还来得及吗？」——来得及，但不容易"
            )

        # --- Romance ---
        if not state.has_partner:
            parallels.append(
                "如果你谈了恋爱——\n"
                "  存款会少很多，但2025年的团圆饭上\n"
                "  不只有爸妈在等你"
            )
        elif state.has_partner and state.properties == 0:
            partner = flags.get("partner_name", "TA")
            parallels.append(
                f"如果你们买了房——\n"
                f"  每个月还贷的压力会让你失眠\n"
                f"  但那是你和{partner}的家"
            )

        # --- Masks ---
        if not flags.get("stockpiled_masks"):
            parallels.append(
                "如果你2019年囤了口罩——\n"
                "  2020年你会成为全小区的英雄\n"
                "  邻居叫你「小神仙」"
            )

        # Shuffle and pick 3 for variety
        import random
        random.shuffle(parallels)
        return parallels[:3]
