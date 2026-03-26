"""V4 Event Map — flag-driven event graph replacing the old random pool system.

Each year defines fixed events (always happen) and conditional events (flag-driven).
Events set flags that drive future events, creating a coherent narrative chain.
"""

from __future__ import annotations

import random

from rerun.engine.events import Choice, GameEvent, filter_choices_for_state
from rerun.engine.state import PlayerState, get_btc_price, get_property_price

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_money(val: float) -> str:
    """Format money for event text."""
    if val == 0:
        return "¥0"
    a = abs(val)
    neg = val < 0
    if a < 10000:
        s = f"¥{a:,.0f}"
    elif a < 1_0000_0000:
        wan = a / 10000
        s = f"¥{wan:.1f}万" if wan != int(wan) else f"¥{int(wan)}万"
    else:
        yi = a / 1_0000_0000
        s = f"¥{yi:.1f}亿"
    return f"-{s}" if neg else s


def _partner_label(state: PlayerState) -> str:
    return state.flags.get("partner_name", "你的另一半")


def _dynamic_buy_amount(state: PlayerState, base_amount: float = 30000) -> float:
    """Calculate a dynamic BTC buy amount based on player savings.

    Returns an amount that scales with savings but stays reasonable.
    """
    savings = state.savings
    if savings <= 0:
        return 0
    if savings < 50000:
        return min(base_amount, savings * 0.5)
    if savings < 200000:
        return min(50000, savings * 0.3)
    if savings < 500000:
        return min(100000, savings * 0.3)
    if savings < 1000000:
        return min(200000, savings * 0.3)
    return min(500000, savings * 0.3)


# ---------------------------------------------------------------------------
# Event applicability check (spec §二)
# ---------------------------------------------------------------------------


def is_applicable(event: GameEvent, state: PlayerState) -> bool:
    """Check if an event is applicable given the current player state."""
    tid = event.template_id

    # BTC sell/crash events need BTC holdings
    btc_keywords = ["btc_surge", "btc_crash", "btc_sell", "btc_high", "nine_four",
                     "btc_milestone", "btc_regret_no"]
    if any(kw in tid for kw in btc_keywords):
        if "no_btc" in tid or "regret" in tid:
            pass  # these are specifically for non-holders
        elif state.btc_amount <= 0:
            return False

    # Employment-related events
    if "layoff" in tid and "庆幸" not in event.title:
        if not state.is_employed:
            return False

    # Partner events
    if "partner" in tid and "meet" not in tid:
        if not state.has_partner:
            return False

    return True


# ---------------------------------------------------------------------------
# 2015 Events (Tutorial Year)
# ---------------------------------------------------------------------------


def build_2015_events(state: PlayerState) -> list[GameEvent]:
    """Build the 3 fixed tutorial events for 2015."""
    btc_price = get_btc_price(2015)
    events: list[GameEvent] = []

    # --- Event 1/3: BTC Enlightenment (core fork point) ---
    savings = state.savings
    all_in_btc = savings / btc_price
    moderate_btc = 10000 / btc_price
    small_btc = 3000 / btc_price

    btc_event = GameEvent(
        year=2015, type="life", category="market",
        title="同事的神秘推荐",
        description=(
            "午饭时间，你的同事老王压低声音跟你说：\n\n"
            "「我最近在研究一个东西叫比特币，现在才 1800 块一个。\n"
            "  我已经买了 2 个试试水。你要不要也了解一下？」\n\n"
            "你作为重生者，当然知道这东西 2024 年会涨到 50 万。\n"
            "问题是——你现在手里的钱有限。"
        ),
        choices=[
            Choice(
                key="A",
                text=f"梭哈！把所有积蓄都买 BTC（约 {all_in_btc:.1f} 个）",
                hint="⚠️ 存款将清零。接下来几个月你得靠工资活。",
                consequences={"savings": -savings, "btc_amount": all_in_btc, "stress": 20},
                narrative="你把所有钱都买了 BTC。交易所里的数字让你心跳加速。\n从今天起，你的身家和 BTC 绑定在一起了。",
            ),
            Choice(
                key="B",
                text=f"拿 1 万块试试水（约 {moderate_btc:.1f} 个）",
                hint="💬 [系统] 稳妥的重生者。留了后手。",
                consequences={"savings": -10000, "btc_amount": moderate_btc, "stress": 5},
                narrative="你买了大约 5.5 个 BTC。剩下的钱留着生活。\n不多不少，进可攻退可守。",
            ),
            Choice(
                key="C",
                text=f"只买 3000 块的（约 {small_btc:.1f} 个）",
                hint="💬 [系统] 谨慎。但你是知道答案的人，这会不会太保守了？",
                consequences={"savings": -3000, "btc_amount": small_btc, "stress": 0},
                narrative="你买了大约 1.6 个 BTC。\n虽然不多，但至少上车了。",
            ),
            Choice(
                key="D",
                text="先不买，再观察观察",
                hint="💬 [系统] ……你穿越回来不买 BTC？系统怀疑你不是真的重生者。",
                consequences={"stress": -5},
                narrative="你决定再看看。老王觉得你没有投资眼光。\n你心想：我倒要看看不买 BTC 能不能活出不同的精彩。",
            ),
        ],
        template_id="2015_btc_enlightenment",
    )
    btc_event.choices = filter_choices_for_state(btc_event.choices, state)
    events.append(btc_event)

    # --- Event 2/3: Family Event (gender + 梭哈 variant) ---
    # We'll build this after BTC event is applied, so we use a builder that
    # checks the *post-BTC* state. Since we can't know the choice yet at build
    # time, we build the generic version. The chain system in apply_choice
    # will adjust family event dynamically via flags.
    gender = state.gender.value

    if gender == "male":
        # Check if player might be broke (梭哈 variant handled via flag in chains)
        family_event = GameEvent(
            year=2015, type="life", category="family",
            title="老妈的电话",
            description=(
                "周末，你妈打来电话：\n\n"
                "「儿子，妈给你说个事。你姨家的表妹今年高考，\n"
                "  考上了浙大，但学费生活费你姨凑不齐。\n"
                "  你工作了能不能帮衬一下？大概要 1 万 5。」\n\n"
                "你听出了妈妈话里的为难——她也不好意思开口。"
            ),
            choices=[
                Choice(
                    key="A", text="「没问题妈，我转给你。」",
                    hint="💬 [系统] 亲情投资。回报率算不清，但良心能安。",
                    consequences={"savings": -15000, "relationship": 15, "times_helped_family": 1},
                    narrative="你妈在电话那头沉默了几秒，然后说：「儿子，谢谢你。」\n你挂了电话，鼻子有点酸。",
                ),
                Choice(
                    key="B", text="「妈，我刚工作也不宽裕，先出 5000 吧。」",
                    hint="💬 [系统] 量力而行，不丢人。",
                    consequences={"savings": -5000, "relationship": 5},
                    narrative="你妈说：「行，多少是个心意。」\n你知道她理解你的难处。",
                ),
                Choice(
                    key="C", text="「让表妹申请助学贷款吧，现在政策挺好的。」",
                    hint="💬 [系统] 理性建议。但家庭群里可能会有些微妙。",
                    consequences={"relationship": -5},
                    narrative="你妈叹了口气：「也行吧。」\n挂电话后你有点心虚。但钱确实有更重要的用途。",
                ),
            ],
            template_id="2015_family_event_male",
        )
    else:
        family_event = GameEvent(
            year=2015, type="life", category="family",
            title="闺蜜的邀约",
            description=(
                "大学闺蜜小美约你周末逛街：\n\n"
                "「姐妹！我发现一个代购渠道特别赚钱，\n"
                "  韩国化妆品拿货价五折！我们一起做呗？\n"
                "  启动资金大概每人 1 万就够了。」\n\n"
                "你看了看她发来的截图，确实有利润空间。\n"
                "但你作为重生者知道：代购这行 2019 年后会被跨境电商干掉。"
            ),
            choices=[
                Choice(
                    key="A", text="「好呀！试试看。」",
                    hint="💬 [系统] 短期能赚点，但你知道这不是长期方向。",
                    consequences={"savings": -10000, "social": 10},
                    narrative="你和小美开始了代购生涯。周末变成了打包发货日。\n累是累，但多了一份收入，也多了和闺蜜的共同话题。",
                ),
                Choice(
                    key="B", text="「我再想想，最近手头有点紧。」",
                    hint="💬 [系统] 拒绝闺蜜不容易。但你的钱有更好的去处。",
                    consequences={"social": -5},
                    narrative="小美有点失望：「行吧，你再考虑考虑。」\n你们的关系没受太大影响，但你知道她有点不高兴。",
                ),
                Choice(
                    key="C", text="「代购不长久的，我们不如一起研究投资？」",
                    hint="💬 [系统] 带闺蜜上车？大胆。但万一 BTC 暴跌你们友谊还在吗？",
                    consequences={"social": 5},
                    narrative="小美瞪大了眼：「投资？你突然这么有想法了？」\n你神秘地笑了笑。",
                ),
            ],
            template_id="2015_family_event_female",
        )

    family_event.choices = filter_choices_for_state(family_event.choices, state)
    events.append(family_event)

    # --- Event 3/3: Year Review (no choice needed, press enter) ---
    review_desc = (
        "你站在出租屋的阳台上，看着城市的灯光。\n"
        "一年前你「醒来」的时候，只有一脑子未来记忆。\n\n"
        "提醒你一下接下来会发生什么：\n"
        "· 2016 年：房价要起飞了。\n"
        "· 2017 年：BTC 会到 13 万。\n"
        "· 2018 年：BTC 会暴跌 80%。\n\n"
        "你知道这些。但知道和做到之间，隔着 9 年的人生。"
    )
    events.append(GameEvent(
        year=2015, type="life", category="social",
        title="2015 年的最后一天",
        description=review_desc,
        choices=[Choice(
            key="A", text="准备好了。进入 2016 年。",
            hint="💬 [系统] 第一年结束。你的棋已经落下了第一手。",
            consequences={}, narrative="你深吸一口气，迎接新的一年。",
        )],
        template_id="2015_year_review",
    ))

    return events


def rebuild_family_event_if_broke(event: GameEvent, state: PlayerState) -> GameEvent:
    """Rebuild the 2015 family event if the player went all-in and is now broke.

    Called just before rendering, after the BTC choice has been applied.
    """
    if event.template_id not in ("2015_family_event_male", "2015_family_event_female"):
        return event

    if state.savings >= 5000:
        # Not broke, use the original event with updated affordability
        return GameEvent(
            year=event.year, type=event.type, category=event.category,
            title=event.title, description=event.description,
            choices=filter_choices_for_state(event.choices, state),
            template_id=event.template_id,
        )

    # Player is broke (梭哈 variant)
    btc_price = get_btc_price(2015)
    gender = state.gender.value

    if gender == "male":
        return GameEvent(
            year=2015, type="life", category="family",
            title="老妈的电话",
            description=(
                "周末，你妈打来电话，说表妹需要学费。\n"
                f"你看了看银行卡余额：{_fmt_money(state.savings)}。\n"
                "你把所有钱都买了 BTC。\n"
                "这一刻你第一次感受到了梭哈的代价。"
            ),
            choices=[
                Choice(
                    key="A",
                    text="卖 1 个 BTC 凑钱帮表妹（你知道这 1 个 BTC 未来值 70 万…）",
                    hint="💬 [系统] 这是真正的牺牲。1 个 BTC 在 2025 年值 70 万。",
                    consequences={"btc_amount": -1, "savings": btc_price,
                                  "relationship": 15, "times_helped_family": 1},
                    narrative="你卖掉了 1 个 BTC，把钱转给了妈妈。\n你知道这个 BTC 未来值多少。但家人比币重要。",
                ),
                Choice(
                    key="B",
                    text="「妈，我最近手头真的紧，让表妹申请贷款吧」",
                    hint="💬 [系统] 你说的是实话。梭哈的代价。",
                    consequences={"relationship": -10, "stress": 10},
                    narrative="你妈沉默了很久。「行吧。」\n挂了电话，你盯着 BTC 钱包发呆。",
                ),
            ],
            template_id="2015_family_event_male",
        )
    else:
        # Female broke variant — simpler, same as original but with affordability filter
        return GameEvent(
            year=event.year, type=event.type, category=event.category,
            title=event.title, description=event.description,
            choices=filter_choices_for_state(event.choices, state),
            template_id=event.template_id,
        )


# ---------------------------------------------------------------------------
# 2016 Events (Accumulation Year)
# ---------------------------------------------------------------------------


def build_2016_events(state: PlayerState) -> list[GameEvent]:
    """Build 2016 events: 1 fixed (housing) + 1-2 from random pool."""
    events: list[GameEvent] = []
    btc_price = get_btc_price(2016)

    # --- Fixed: Housing Pressure (or investment property if already owns) ---
    savings = state.savings
    has_btc = state.btc_amount > 0

    # F4: Player already has a property (preset 3) — show investment variant instead
    if state.properties > 0:
        events.append(GameEvent(
            year=2016, type="life", category="family",
            title="要不要买第二套？",
            description=(
                "你已经有房了。朋友圈有人在讨论要不要买第二套投资房。\n"
                "你妈倒是不催了，但你看着房价节节攀升，有点心动。\n\n"
                f"你的存款：{_fmt_money(savings)}。"
            ),
            choices=[
                Choice(
                    key="A", text="买一套投资房",
                    hint="💬 [系统] 房价还在涨。但你知道 BTC 涨得更猛。钱只有一份。",
                    consequences={"savings": -300000, "properties": 1, "stress": 15,
                                  "mortgage_monthly": 5000.0},
                    narrative="你又买了一套。两套房在手，安全感拉满。\n但你的现金流更紧了。",
                ) if savings >= 300000 else Choice(
                    key="A", text="买不起第二套",
                    hint="💬 [系统] 首付不够。",
                    consequences={},
                    narrative="你看了看银行余额，算了。",
                ),
                Choice(
                    key="B", text="不买，把钱留给更好的投资",
                    hint="💬 [系统] 你已经有房了。别贪。",
                    consequences={"stress": -5},
                    narrative="你决定不追加房产。已经有一套了，够住就好。",
                ),
            ],
            template_id="2016_house_investment",
        ))
    else:
        # No property — show housing pressure event
        if state.savings < 5000:
            # 梭哈玩家 — broke variant
            housing_desc = (
                f"你妈每天打电话催买房。但你的存款只有 {_fmt_money(savings)}……\n"
            )
            if has_btc:
                housing_desc += f"当然你还有 {state.btc_amount:.1f} 个 BTC，但你不能说。\n\n"
            housing_desc += "「再不买就永远买不起了！」你妈的声音越来越焦虑。"
        elif not has_btc:
            housing_desc = (
                f"你妈催买房。你有 {_fmt_money(savings)} 存款，首付似乎够得着……\n\n"
                "「再不买就永远买不起了！」朋友圈里天天有人晒新房钥匙。"
            )
        else:
            housing_desc = (
                "房价彻底疯了。朋友圈里天天有人晒新房钥匙。\n"
                "你妈每天打电话催你买房。连出租车司机都在聊房子。\n\n"
                "「再不买就永远买不起了！」\n\n"
                f"你看了看银行卡余额：{_fmt_money(savings)}。"
            )

        housing_choices = []

        # Option A: Buy house (need 300k down payment)
        down_payment = 300000
        can_afford = savings >= down_payment
        can_afford_with_btc = (savings + state.btc_value) >= down_payment

        if can_afford:
            housing_choices.append(Choice(
                key="A", text="咬牙买一套，大家都在买",
                hint="💬 [系统] 你知道房价还会涨几年。但你也知道BTC涨得更多。钱，只有一份。",
                consequences={"savings": -down_payment, "properties": 1, "relationship": 15, "stress": 20,
                              "mortgage_monthly": 5000.0},
                narrative="你凑了首付，签了30年房贷。你妈终于不催了。\n但你心里在算：这30万如果买了BTC……算了，别想了。",
            ))
        elif can_afford_with_btc:
            btc_needed = (down_payment - savings) / btc_price if btc_price > 0 else 0
            housing_choices.append(Choice(
                key="A", text=f"买房（需卖 {btc_needed:.1f} 个 BTC 凑首付）",
                hint="⚠️ 存款不足，需要卖出部分 BTC 凑首付。",
                consequences={"savings": -down_payment, "properties": 1, "relationship": 15,
                              "stress": 25, "btc_amount": -btc_needed, "mortgage_monthly": 5000.0},
                narrative="你忍痛卖了一些 BTC，凑够了首付。签字的时候手在抖。\n你妈笑了，你的心在滴血。",
            ))

        housing_choices.append(Choice(
            key="B", text="坚定不买，把钱留给 BTC",
            hint="💬 [系统] 你是全小区唯一知道BTC明年要涨到13万的人。这个信息差值多少套房？",
            consequences={"relationship": -10, "stress": 15},
            narrative="你顶住了所有压力。你妈说你不听话，朋友说你傻。\n但你知道自己在做什么。",
        ))
        housing_choices.append(Choice(
            key="C", text="敷衍说「在看了」，继续拖",
            hint="💬 [系统] 拖延大法好。但每拖一天，你妈的焦虑就多一分。",
            consequences={"relationship": -5, "stress": 10},
            narrative="你又一次成功拖延了。但你知道这个话题还会回来。一遍又一遍。",
        ))

        events.append(GameEvent(
            year=2016, type="life", category="family",
            title="全民抢房焦虑",
            description=housing_desc,
            choices=filter_choices_for_state(housing_choices, state),
            template_id="2016_house_fomo",
        ))

    # --- Random pool: pick 1-2 events ---
    pool = _build_2016_random_pool(state)
    random.shuffle(pool)
    picked = 0
    for evt in pool:
        if is_applicable(evt, state):
            events.append(evt)
            picked += 1
            if picked >= 1:
                break

    return events


def _build_2016_random_pool(state: PlayerState) -> list[GameEvent]:
    """Build the 2016 random event pool."""
    pool: list[GameEvent] = []
    btc_price = get_btc_price(2016)

    # a. Mom's money (warm event, high weight)
    amount = random.choice([5000, 8000, 10000])
    pool.append(GameEvent(
        year=2016, type="life", category="family",
        title="妈妈偷偷给你存了钱",
        description=(
            f"过年回家，你妈偷偷塞给你一个信封。\n\n"
            f"「这是妈这几年攒的，{amount} 块。你在外面不容易，别委屈自己。」\n\n"
            f"你打开一看，里面是一沓皱巴巴的钞票。你鼻子一酸。"
        ),
        choices=[
            Choice(key="A", text="收下，以后加倍还给她",
                   hint="💬 [系统] 妈妈的钱，每一分都是爱。",
                   consequences={"savings": amount, "relationship": 10, "stress": -15},
                   narrative="你收下了。心里默默发誓，以后一定让妈过上好日子。"),
            Choice(key="B", text="不要，「妈我不缺钱」",
                   hint="💬 [系统] 你确实不缺。但妈的心意比钱更重要。",
                   consequences={"relationship": 5, "stress": -10},
                   narrative="你硬是把钱塞了回去。你妈叹了口气：「这孩子，倔。」但她笑了。"),
        ],
        template_id="2016_mom_saved_money",
    ))

    # b. Work praise
    pool.append(GameEvent(
        year=2016, type="life", category="career",
        title="工作得到了认可",
        description=(
            "你负责的项目上线后效果很好。\n\n"
            "老板在周会上公开表扬了你：「表现非常出色，是团队的骨干。」\n\n"
            "同事们投来羡慕的目光。"
        ),
        choices=[
            Choice(key="A", text="谦虚一下，继续努力",
                   hint="💬 [系统] 低调做人，高调……买币。",
                   consequences={"reputation": 10, "stress": -5, "career_level": 1},
                   narrative="你笑着说了句「团队功劳」。心里想的是：打工嘛，维持住就行。"),
            Choice(key="B", text="趁热打铁，提出加薪要求",
                   hint="💬 [系统] 时机不错。谈钱不伤感情。",
                   consequences={"monthly_salary": 2000, "reputation": 5, "stress": 5},
                   narrative="你找老板聊了聊，月薪涨了 2000。蚊子再小也是肉。"),
        ],
        template_id="2016_work_praise",
    ))

    # c. College reunion
    pool.append(GameEvent(
        year=2016, type="life", category="social",
        title="大学同学聚会",
        description=(
            "大学同学组织了一场聚会。十几个人到了，\n"
            "大家聊工作、聊感情、聊房子。\n"
            "有人混得风生水起，有人还在迷茫。\n\n"
            "轮到你的时候，所有人看着你：「你最近在干嘛？」"
        ),
        choices=[
            Choice(key="A", text="低调，「就上班呗」",
                   hint="💬 [系统] 你的 BTC 账户够买下整桌人的年薪。但你选择低调。",
                   consequences={"social": 10, "stress": -5},
                   narrative="没人多问。这种从容，只有重生者才懂。"),
            Choice(key="B", text="暗示自己在做投资",
                   hint="💬 [系统] 虚荣心蠢蠢欲动。克制，克制。",
                   consequences={"social": 15, "reputation": 10, "stress": 10},
                   narrative="几个同学追问。你赶紧岔开话题。说得太多了。"),
            Choice(key="C", text="不去",
                   hint="💬 [系统] 社恐保护。",
                   consequences={"stress": -5},
                   narrative="你找了个借口没去。朋友圈看了看聚会照片，也就那样。"),
        ],
        template_id="2016_college_reunion",
    ))

    # d. Side hustle
    if state.stress < 70:
        pool.append(GameEvent(
            year=2016, type="life", category="career",
            title="发现一个副业机会",
            description=(
                "你发现可以用业余时间接私活/做自媒体，月入 3000-5000。\n\n"
                "「反正晚上也没事，不如赚点外快。」"
            ),
            choices=[
                Choice(key="A", text="试试看",
                       hint="💬 [系统] 额外收入不错，但别累垮了。",
                       consequences={"monthly_salary": 3000, "stress": 10},
                       narrative="你开始了副业。收入涨了，但下班后更累了。"),
                Choice(key="B", text="专注主业和投资",
                       hint="💬 [系统] 精力有限，投资才是大头。",
                       consequences={"stress": -5},
                       narrative="你决定把精力放在更重要的事情上。"),
            ],
            template_id="2016_side_hustle",
        ))

    return pool


# ---------------------------------------------------------------------------
# 2017 Events (Big Year)
# ---------------------------------------------------------------------------


def build_2017_events(state: PlayerState) -> list[GameEvent]:
    """Build 2017 events: 3 fixed (surge → milestone → 94 crash)."""
    events: list[GameEvent] = []
    btc_price = get_btc_price(2017)
    has_btc = state.btc_amount > 0

    # --- Event 1: BTC Surge or Regret ---
    if has_btc:
        btc_val = state.btc_amount * btc_price
        events.append(GameEvent(
            year=2017, type="life", category="market",
            title="BTC 起飞了！",
            description=(
                "BTC 从年初的 7000 涨到了 13 万！\n\n"
                f"你的 {state.btc_amount:.2f} 个 BTC 现在值 {_fmt_money(btc_val)}。\n\n"
                "你的手机被各种消息轰炸：\n"
                "「你之前说的那个比特币，真的涨了？」\n"
                "「教教我怎么买！」\n\n"
                "你微微一笑，没有回复。"
            ),
            choices=[
                Choice(
                    key="A", text="低调，谁问都说「没买多少」",
                    hint="💬 [系统] 闷声发大财，重生者的基本素养。",
                    consequences={"stress": -10, "social": 5},
                    narrative="你在朋友圈看着大家讨论 BTC，一条评论都没发。\n真正赚钱的人从不声张。",
                ),
                Choice(
                    key="B", text="适当分享，「买了一点」",
                    hint="💬 [系统] 小心。暗示太多会被追问。",
                    consequences={"social": 15, "reputation": 10, "stress": 5},
                    narrative="几个朋友追问，你分享了一些「入门知识」。\n突然你成了朋友圈的「投资大神」。",
                ),
                Choice(
                    key="C", text="坦白：「不止买了，还买了不少。」",
                    hint="⚠️ 高风险。2018 年暴跌时这些人会回来找你。",
                    consequences={"social": 10, "reputation": 15, "stress": 15},
                    narrative="老王震惊地看着你。然后整个部门都知道了。\n你的微信开始不停弹消息：「带带我。」",
                ),
            ],
            template_id="2017_btc_surge",
        ))
    else:
        # No BTC → regret event
        events.append(GameEvent(
            year=2017, type="life", category="market",
            title="BTC 涨到 13 万了",
            description=(
                "BTC 涨到 13 万了。你去年没买。\n\n"
                "你算了一下，如果当初拿 3 万梭哈，现在值 ¥217 万。\n\n"
                "你盯着手机，沉默了很久。"
            ),
            choices=[
                Choice(
                    key="A", text="现在买，亡羊补牢",
                    hint="💬 [系统] 现在买还来得及。2021 年还有一轮。",
                    consequences={"savings": -30000, "btc_amount": 30000 / btc_price, "stress": 15},
                    narrative="你终于买了。虽然晚了，但总比没有强。",
                ),
                Choice(
                    key="B", text="算了，错过就错过了",
                    hint="💬 [系统] 有些重生者选择走不同的路。",
                    consequences={"stress": 10},
                    narrative="你关掉了行情软件。有些事，错过了就是错过了。",
                ),
            ],
            template_id="2017_btc_regret_no",
        ))

    # --- Event 2: Milestone check + sell option ---
    if has_btc and state.net_worth > 500000:
        nw = state.net_worth
        events.append(GameEvent(
            year=2017, type="life", category="market",
            title="你的资产突破了新高",
            description=(
                f"你算了算——净资产已经超过 {_fmt_money(nw)} 了。\n\n"
                "作为一个刚工作几年的年轻人，这个数字已经超越了绝大多数同龄人。\n"
                "你该怎么对待这笔财富？"
            ),
            choices=[
                Choice(
                    key="A", text="允许自己高兴一下（减压）",
                    hint="💬 [系统] 你值得。",
                    consequences={"stress": -15},
                    narrative="你独自打开了一罐啤酒。没有烟花，没有掌声。\n但你知道自己做到了。",
                ),
                Choice(
                    key="B", text="目标是 1 个亿（加压但加声望）",
                    hint="💬 [系统] 野心勃勃。重生一次不赚个亿，确实有点浪费。",
                    consequences={"stress": 5, "reputation": 5},
                    narrative="你关掉了计算器。这才哪到哪。你的目光投向了更远的地方。",
                ),
                Choice(
                    key="C", text="卖掉一部分落袋为安",
                    hint="💬 [系统] 2018 年会暴跌。现在卖一点是聪明的。",
                    consequences={"stress": -10, "_action": "sell_btc_50pct"},
                    narrative="你卖出了一半 BTC。纸面富贵变成了真金白银。\n拿着实实在在的钱，心安了不少。",
                ),
            ],
            template_id="2017_btc_milestone",
        ))

    # --- Event 3: 94 Ban Crash ---
    if state.btc_amount > 0:
        btc_val = state.btc_amount * btc_price
        events.append(GameEvent(
            year=2017, type="life", category="market",
            title="九四禁令：BTC 暴跌 40%",
            description=(
                "中国政府全面禁止 ICO，关闭境内交易所！\n\n"
                "BTC 一天内暴跌 40%。你的持仓市值蒸发了一大截。\n\n"
                "朋友圈一片哀嚎。有人割肉，有人跳楼。\n"
                "你的手在发抖，但你的脑子很清醒。\n\n"
                "你知道，年底会创新高。但此刻的恐惧是真实的。"
            ),
            choices=[
                Choice(
                    key="A", text="稳如泰山，一个币都不卖",
                    hint="💬 [系统] 你知道年底 BTC 会到 13 万。这只是洗盘。Hold 住。",
                    consequences={"stress": 20},
                    narrative="你把交易所 APP 删了一周。不看不想不纠结。\n一周后打开——涨回来了。你长舒一口气。",
                ),
                Choice(
                    key="B", text="恐慌卖出一部分",
                    hint="💬 [系统] 你明明知道会涨回来……但恐惧这东西不讲道理。",
                    consequences={"_action": "sell_btc_50pct", "stress": 25},
                    narrative="你在恐慌中卖出了一些。等到价格涨回来，你肠子都悔青了。",
                ),
                Choice(
                    key="C", text=f"趁暴跌加仓（投入 {_fmt_money(_dynamic_buy_amount(state, 20000))}）",
                    hint="💬 [系统] 别人恐惧我贪婪。巴菲特教的，还是开挂的？管它呢。",
                    consequences={"_action": f"buy_btc_{int(_dynamic_buy_amount(state, 20000))}", "stress": 15},
                    narrative="你在最恐慌的时候加仓了。两个月后，翻了倍。\n你默默给自己竖了个大拇指。",
                ),
            ],
            template_id="2017_nine_four",
        ))

    return events


# ---------------------------------------------------------------------------
# 2018 Events (Test Year)
# ---------------------------------------------------------------------------


def build_2018_events(state: PlayerState) -> list[GameEvent]:
    """Build 2018: layoff + AI pivot. Chain events (friend blame etc.) come from chains.py."""
    events: list[GameEvent] = []
    flags = state.flags

    # --- Event 1: Layoff (if employed, with foreshadowing from 2017) ---
    if state.is_employed:
        severance = state.monthly_salary * 4  # N+1 approx
        choices = [
            Choice(key="A", text=f"接受裁员，拿 N+1 赔偿（约 {_fmt_money(severance)}）",
                   hint="💬 [系统] 拿钱走人。有了这笔钱，你可以充电、休息、思考下一步。",
                   consequences={"savings": severance, "is_employed": False, "stress": 15},
                   narrative=f"HR 递过来一份协议。你签了字，拿了 {_fmt_money(severance)}。\n"
                             "走出大楼的那一刻，阳光很好。你觉得……好像也没那么糟。"),
        ]
        if state.career_level >= 2:
            choices.append(Choice(
                key="B", text="主动请辞，谈更好的赔偿条件",
                hint="💬 [系统] 你的能力在这里有目共睹。主动权在你手里。",
                consequences={"savings": severance * 1.5, "is_employed": False, "stress": 10,
                              "reputation": 5},
                narrative=f"你主动找了 HR 谈。最终拿到了 {_fmt_money(severance * 1.5)}。\n"
                          "前同事说你「走得漂亮」。"))
        choices.append(Choice(
            key="C", text="全力争取留下来",
            hint="💬 [系统] 你还想在这里继续。但未来两年可能更难。",
            consequences={"stress": 25, "career_level": 1},
            narrative="你熬过了这一轮。但公司的氛围变了，人人自危。"))

        events.append(GameEvent(
            year=2018, type="life", category="career",
            title="裁员风暴",
            description=(
                "果然来了。HR 通知你部门要裁 30%。\n"
                "你的直属上司私下跟你说名单还没定。\n\n"
                "你看了看自己的简历，又看了看银行卡余额。"
            ),
            choices=choices,
            template_id="2018_layoff",
        ))

    # --- Event 2: AI Pivot ---
    if flags.get("was_fired_2018") or not state.is_employed:
        ai_desc = "反正失业了，不如去学点新东西。\n有个 AI 方向的培训课程，口碑不错……"
    else:
        ai_desc = "有个猎头打来电话，AI 方向的岗位，年薪翻倍。但要跳槽。"

    events.append(GameEvent(
        year=2018, type="life", category="career",
        title="AI 的风口",
        description=ai_desc,
        choices=[
            Choice(key="A", text="投身 AI！这是未来",
                   hint="💬 [系统] 你知道 2022 年 ChatGPT 会改变世界。现在布局，4 年后收割。",
                   consequences={"savings": -15000, "stress": 10, "career_level": 1},
                   narrative="你报了课程，开始啃论文、刷 Kaggle。\n朋友说你疯了。你笑了笑。"),
            Choice(key="B", text="暂不转行，做好本职",
                   hint="💬 [系统] 稳妥路线。但 2023 年可能会后悔。",
                   consequences={"stress": -5},
                   narrative="你决定先把手头的事做好。AI？以后再说。"),
        ],
        template_id="2018_ai_pivot",
    ))

    return events


# ---------------------------------------------------------------------------
# 2019 Events (Breather Year)
# ---------------------------------------------------------------------------


def build_2019_events(state: PlayerState) -> list[GameEvent]:
    """Build 2019: mask stockpile + romance/side hustle."""
    events: list[GameEvent] = []
    flags = state.flags

    # --- Event 1: Mask Stockpile (core prophet event) ---
    events.append(GameEvent(
        year=2019, type="life", category="social",
        title="一条不起眼的新闻",
        description=(
            "你刷新闻看到武汉有个不明肺炎的小报道。\n"
            "大多数人划走了。但你的心跳加速了。\n"
            "你记得。你记得接下来会发生什么。\n\n"
            "朋友介绍的渠道 N95 口罩 2 元一只，起订 5000 个。"
        ),
        choices=[
            Choice(key="A", text="大量囤货，花 5 万",
                   hint="💬 [系统] 你是全世界最早准备的人之一。这不是投机，这是救命。",
                   consequences={"savings": -50000, "stress": 10},
                   narrative="你一口气订了 25000 只口罩。快递小哥问你开医院的吗。\n你没回答。"),
            Choice(key="B", text="买几千只以防万一，花 1 万",
                   hint="💬 [系统] 谨慎但有准备。比大多数人强多了。",
                   consequences={"savings": -10000, "stress": 5},
                   narrative="你买了 5000 只口罩，塞满了一个柜子。\n室友说你脑子有问题。"),
            Choice(key="C", text="算了，也许这个时间线不会有新冠",
                   hint="💬 [系统] ……你确定？你是重生者啊。",
                   consequences={"stress": -5},
                   narrative="你划走了那条新闻。也许有些事不会重演？"),
        ],
        template_id="2019_mask_stockpile",
    ))

    # --- Event 2: Romance or life event ---
    if not state.has_partner:
        partner_name = "陈雨涵" if state.gender.value == "male" else "李浩然"
        events.append(GameEvent(
            year=2019, type="life", category="romance",
            title="意料之外的相遇",
            description=(
                f"公司团建上你认识了{partner_name}。\n"
                "你们聊了一晚上，发现都喜欢看《三体》。\n"
                f"TA 加了你微信，头像是一只橘猫。"
            ),
            choices=[
                Choice(key="A", text="主动约周末看电影",
                       hint="💬 [系统] 重生者也需要爱情。不是所有事都跟钱有关。",
                       consequences={"has_partner": True, "relationship": 15, "stress": -10,
                                     "monthly_expense": 1500},
                       narrative=f"你们看了《流浪地球》。散场后{partner_name}说：\n"
                                 "「下次我请你。」你的心跳了一下。"),
                Choice(key="B", text="微信上慢慢聊",
                       hint="💬 [系统] 慢慢来也好。先了解再说。",
                       consequences={"social": 10, "stress": -5},
                       narrative=f"你和{partner_name}开始了每天的微信聊天。\n还没在一起，但好像已经习惯了TA的存在。"),
                Choice(key="C", text="算了，现在专心搞钱",
                       hint="💬 [系统] 重生者的优先级：财务自由 > 一切。但真的是这样吗？",
                       consequences={"stress": 5},
                       narrative="你礼貌地回了消息，但没有继续。\n有些缘分，错过了就是错过了。"),
            ],
            template_id="2019_romance",
        ))
    elif flags.get("started_side_hustle"):
        events.append(GameEvent(
            year=2019, type="life", category="career",
            title="副业有回报了",
            description="你的副业这一年做得不错，累计多赚了不少。\n甚至有人来问你要不要做大。",
            choices=[
                Choice(key="A", text="继续做，赚的都是额外收入",
                       hint="💬 [系统] 副业收入虽然不多，但积少成多。",
                       consequences={"savings": 30000, "stress": 5},
                       narrative="你继续经营副业。虽然累，但看着额外收入入账，值了。"),
                Choice(key="B", text="见好就收",
                       hint="💬 [系统] 该收手就收手。主业和投资才是大头。",
                       consequences={"stress": -10},
                       narrative="你逐渐减少了副业投入。把精力收回来。"),
            ],
            template_id="2019_side_hustle_payoff",
        ))

    return events


# ---------------------------------------------------------------------------
# 2020 Events (Drama Year)
# ---------------------------------------------------------------------------


def build_2020_events(state: PlayerState) -> list[GameEvent]:
    """Build 2020: COVID masks, 312 crash, romance progress."""
    events: list[GameEvent] = []
    flags = state.flags

    # --- Event 1: Mask Prophet or Regret ---
    if flags.get("stockpiled_masks"):
        events.append(GameEvent(
            year=2020, type="life", category="social",
            title="全小区的英雄",
            description=(
                "武汉封城了。你成了全小区唯一有口罩的人。\n"
                "邻居王大妈叫你「小神仙」。你给每户分了 20 只。\n\n"
                "有人问你怎么知道的。你笑了笑：「运气好。」"
            ),
            choices=[
                Choice(
                    key="A", text="大量分发，优先给家人和邻居",
                    hint="💬 [系统] 这是重生者最有意义的一次「先知」时刻。",
                    consequences={"reputation": 20, "social": 15, "stress": -15,
                                  "times_helped_family": 1},
                    narrative="你把大部分口罩分给了家人、邻居和朋友。\n"
                              "你妈骄傲地跟亲戚说：「我儿子/女儿真有远见。」",
                ),
            ],
            template_id="2020_mask_hero",
        ))
    else:
        events.append(GameEvent(
            year=2020, type="life", category="social",
            title="口罩断货了",
            description=(
                "武汉封城了。口罩全面断货。\n"
                "你在药店门口排了 3 个小时。最后花 50 块买了 5 只。\n\n"
                "你恨自己：你明明记得这件事会发生。为什么没准备？"
            ),
            choices=[Choice(
                key="A", text="自责归自责，先活下去",
                hint="💬 [系统] 知道未来不等于准备好了未来。重生者的教训。",
                consequences={"stress": 15},
                narrative="你戴着高价买来的口罩，窝在家里刷手机。\n朋友圈里全是求口罩的消息。你一条都不敢回。",
            )],
            template_id="2020_mask_regret",
        ))

    # --- Event 2: 312 Bottom Fishing ---
    btc_price_312 = 35000  # 312 crash price
    events.append(GameEvent(
        year=2020, type="life", category="market",
        title="312 暴跌：最后的低价",
        description=(
            "3 月 12 日。BTC 一天暴跌到 ¥35,000。\n"
            "你知道这是最后的低价。年底它会到 ¥190,000。\n"
            "但此刻你的手在发抖。"
        ),
        choices=[
            Choice(key="A", text=f"抄底！追加投资（投入 {_fmt_money(_dynamic_buy_amount(state, 30000))}）",
                   hint="💬 [系统] 这是教科书级别的抄底机会。你知道答案。",
                   consequences={"_action": f"buy_btc_{int(_dynamic_buy_amount(state, 30000))}", "stress": 15},
                   narrative="你在所有人恐惧的时候买入了。\n几个月后你会为今天的决定举杯。"),
            Choice(key="B", text="已有的不卖就好",
                   hint="💬 [系统] 不动也是一种智慧。至少你没恐慌。",
                   consequences={"stress": 5},
                   narrative="你紧握手机，告诉自己不看行情。明天会好的。"),
            Choice(key="C", text="在恐慌中忍不住卖了一些",
                   hint="💬 [系统] ……你是重生者啊！但恐惧不讲道理。",
                   consequences={"_action": "sell_btc_50pct", "stress": 25},
                   narrative="你在恐慌中卖出了一部分。等涨回来的时候，你不敢算亏了多少。"),
        ],
        template_id="2020_312_crash",
    ))

    # --- Event 3: Romance Progress or Remote Work ---
    if state.has_partner:
        partner = _partner_label(state)
        events.append(GameEvent(
            year=2020, type="life", category="romance",
            title="疫情中的感情",
            description=(
                f"疫情期间你和{partner}每天视频通话。\n"
                f"TA 说：「疫情结束后，我们要不要试试住在一起？」"
            ),
            choices=[
                Choice(key="A", text="「好啊」（开始同居）",
                       hint="💬 [系统] 同居意味着更多陪伴，也意味着更多磨合。",
                       consequences={"stress": -15, "relationship": 10, "monthly_expense": 1000},
                       narrative=f"你们搬到了一起。{partner}的橘猫也来了。\n"
                                 "你第一次觉得，这个出租屋有了家的味道。"),
                Choice(key="B", text="「再等等，我还没准备好」",
                       hint="💬 [系统] 你在想什么？是真的没准备好，还是不想让人发现你的 BTC？",
                       consequences={"relationship": -10, "stress": 5},
                       narrative=f"{partner}有点失望，但没说什么。\n你们的关系进入了一段微妙的时期。"),
            ],
            template_id="2020_romance_progress",
        ))
    else:
        events.append(GameEvent(
            year=2020, type="life", category="social",
            title="远程办公的日子",
            description=(
                "疫情让你开始远程办公。\n"
                "你发现……一个人也挺好的？\n"
                "每天穿着睡衣写代码，省了通勤时间，投资研究的时间多了。"
            ),
            choices=[
                Choice(key="A", text="享受独处",
                       hint="💬 [系统] 一个人的自由，有时候价值千金。",
                       consequences={"stress": -15},
                       narrative="你享受着独处的自由。效率比在办公室高了不少。"),
                Choice(key="B", text="太孤独了，注册了交友 APP",
                       hint="💬 [系统] 账户余额再高，也没人跟你说晚安。",
                       consequences={"social": 10, "stress": 5},
                       narrative="你注册了某款交友软件。划了半小时，觉得现代恋爱好累。"),
            ],
            template_id="2020_remote_work",
        ))

    return events


# ---------------------------------------------------------------------------
# 2021 Events (Peak Year)
# ---------------------------------------------------------------------------


def build_2021_events(state: PlayerState) -> list[GameEvent]:
    """Build 2021: BTC peak sell decision + romance/social."""
    events: list[GameEvent] = []
    flags = state.flags
    btc_price = get_btc_price(2021)  # 300000
    has_btc = state.btc_amount > 0

    # --- Event 1: BTC Peak — Ultimate Decision ---
    if has_btc:
        btc_val = state.btc_amount * btc_price
        events.append(GameEvent(
            year=2021, type="life", category="market",
            title="BTC 历史新高：终极抉择",
            description=(
                f"BTC 突破了 ¥300,000。你的持仓价值 {_fmt_money(btc_val)}。\n\n"
                "你知道——你非常清楚——2022 年它会暴跌到 ¥120,000。\n"
                "所有重生者的知识都在告诉你：现在卖。\n\n"
                "但你也知道 2024 年它会涨到 ¥500,000。\n\n"
                "问题是：你能在底部买回来吗？"
            ),
            choices=[
                Choice(key="A", text="卖掉 80%，只留底仓",
                       hint="💬 [系统] 保守安全。落袋为安永远不会错。",
                       consequences={"_action": "sell_btc_80pct", "stress": -20},
                       narrative="你在高位卖出了大部分。银行余额的数字让你恍惚。\n"
                                 "这是真的。你做到了。"),
                Choice(key="B", text="卖掉 50%，进退有据",
                       hint="💬 [系统] 一半落袋，一半留着。对冲两种未来。",
                       consequences={"_action": "sell_btc_50pct", "stress": -10},
                       narrative="你卖出了一半。不贪也不怯。\n这大概是重生者最理性的选择。"),
                Choice(key="C", text="一个都不卖，直接穿越熊市",
                       hint="💬 [系统] 钻石手极限版。2024 年会涨到 50 万。但 2022 年你扛得住吗？",
                       consequences={"stress": 20},
                       narrative="你选择了 HODL。接下来的一年，你需要钢铁般的意志。"),
                Choice(key="D", text="全卖！落袋为安！",
                       hint="💬 [系统] 激进但安心。问题是 2022 底你有勇气全买回来吗？",
                       consequences={"_action": "sell_btc_all", "stress": -25},
                       narrative="你清仓了。看着银行余额，你深吸一口气。\n这不是梦。这是你十年布局的回报。"),
            ],
            template_id="2021_btc_peak",
        ))
    else:
        events.append(GameEvent(
            year=2021, type="life", category="market",
            title="BTC 又创新高了",
            description=(
                "BTC 涨到了 30 万。你身边买了的人都在庆祝。\n"
                "你没有 BTC。但你有自己的人生。"
            ),
            choices=[
                Choice(key="A", text=f"现在买入（投入 {_fmt_money(_dynamic_buy_amount(state, 50000))}）",
                       hint="💬 [系统] 2022 会跌，但 2024 还会涨。",
                       consequences={"_action": f"buy_btc_{int(_dynamic_buy_amount(state, 50000))}", "stress": 15},
                       narrative="你终于买入了一些。虽然很贵了，但你知道还有空间。"),
                Choice(key="B", text="不买，我有自己的路",
                       hint="💬 [系统] 不是所有重生者都靠 BTC。",
                       consequences={"stress": 5},
                       narrative="你看了看自己的资产配置。不买就不买。条条大路通罗马。"),
            ],
            template_id="2021_btc_no_holder",
        ))

    # --- Event 2: Romance / Social ---
    if state.has_partner and flags.get("living_together"):
        partner = _partner_label(state)
        events.append(GameEvent(
            year=2021, type="life", category="romance",
            title="TA 开始暗示结婚了",
            description=(
                f"{partner}开始暗示结婚的事了。\n"
                f"TA 妈妈问你有没有房子。\n\n"
                "你看了看银行余额，又看了看房价。"
            ),
            choices=[
                Choice(key="A", text="买房 + 求婚",
                       hint="💬 [系统] 存款大减，但幸福感暴增。",
                       consequences={"savings": -500000, "properties": 1, "relationship": 20,
                                     "stress": 15, "mortgage_monthly": 8000.0, "has_child": False},
                       narrative=f"你买了房，在阳台上求了婚。{partner}哭了。\n"
                                 "你想：这大概是重生者最幸福的一天。"),
                Choice(key="B", text="「我们先攒攒钱」",
                       hint="💬 [系统] 拖延。但你知道 TA 等不了太久。",
                       consequences={"relationship": -15, "stress": 10},
                       narrative=f"{partner}没说什么，但那晚你们谁都没开口。\n"
                                 "你知道这个话题还会回来的。"),
            ],
            template_id="2021_marriage_pressure",
        ))
    elif state.has_partner:
        partner = _partner_label(state)
        events.append(GameEvent(
            year=2021, type="life", category="romance",
            title="感情升温",
            description=f"你和{partner}在一起快两年了。\n感觉越来越好。TA 提出想一起住。",
            choices=[
                Choice(key="A", text="同居吧",
                       hint="💬 [系统] 在一起的时间越多，越能确定这是对的人。",
                       consequences={"relationship": 10, "stress": -10, "monthly_expense": 1000},
                       narrative=f"你们搬到了一起。{partner}的猫也来了。\n你开始觉得人生不只有 K 线图。"),
                Choice(key="B", text="还不着急",
                       hint="💬 [系统] 保持距离也是一种相处方式。",
                       consequences={"relationship": -5},
                       narrative="你婉拒了。TA 说理解，但眼里有些失落。"),
            ],
            template_id="2021_romance_cohabit",
        ))
    else:
        # Social event for singles
        events.append(GameEvent(
            year=2021, type="life", category="social",
            title="朋友圈里的投资大神",
            description=(
                "你的朋友圈里多了很多「投资导师」。\n"
                "有人问你：「你好像一直在研究投资，能不能教教我？」"
            ),
            choices=[
                Choice(key="A", text="低调拒绝",
                       hint="💬 [系统] 教人投资是吃力不讨好的事。",
                       consequences={"stress": -5},
                       narrative="你礼貌地说了句「我也是小打小闹」。\n闷声发大财的日子继续。"),
                Choice(key="B", text="分享一些基础知识",
                       hint="💬 [系统] 适当分享不是坏事。但别说太多。",
                       consequences={"social": 10, "reputation": 10},
                       narrative="你写了篇长文科普投资基础。收获了不少感谢。\n但你没提自己的仓位。"),
            ],
            template_id="2021_social_guru",
        ))

    return events


# ---------------------------------------------------------------------------
# 2022 Events (Bear Market)
# ---------------------------------------------------------------------------


def build_2022_events(state: PlayerState) -> list[GameEvent]:
    """Build 2022: BTC crash reaction, ChatGPT, layoff wave."""
    events: list[GameEvent] = []
    flags = state.flags
    has_btc = state.btc_amount > 0

    # --- Event 1: BTC Crash Reaction (flag-driven) ---
    sold_2021 = flags.get("sold_btc_2021")
    if sold_2021 and sold_2021 in ("80pct", "all"):
        events.append(GameEvent(
            year=2022, type="life", category="market",
            title="你是对的",
            description=(
                "BTC 从 30 万跌到了 12 万。FTX 交易所爆雷。\n"
                "你看了看自己的银行余额——去年在高点卖出的决定，英明无比。\n\n"
                "💬 [系统] 这大概是重生者最有优越感的时刻之一。"
            ),
            choices=[Choice(
                key="A", text=f"在底部买回来一些（投入 {_fmt_money(_dynamic_buy_amount(state, 50000))}）",
                hint="💬 [系统] 你知道 2024 年会涨到 50 万。现在是时候了。",
                consequences={"_action": f"buy_btc_{int(_dynamic_buy_amount(state, 50000))}", "stress": -10},
                narrative="你在所有人恐惧的时候重新买入了。\n历史再次证明：你知道答案。",
            ), Choice(
                key="B", text="看戏就好，不急",
                hint="💬 [系统] 稳坐钓鱼台。",
                consequences={"stress": -15},
                narrative="你泡了杯茶，刷着别人的哀嚎。内心平静如水。",
            )],
            template_id="2022_btc_crash_winner",
        ))
    elif has_btc:
        btc_val = state.btc_amount * get_btc_price(2022)
        events.append(GameEvent(
            year=2022, type="life", category="market",
            title="BTC 暴跌 + FTX 爆雷",
            description=(
                "BTC 从 30 万暴跌到 12 万。FTX 交易所爆雷。\n"
                f"你的持仓缩水到 {_fmt_money(btc_val)}。\n\n"
                "但你紧握手机，心里默念：2024 年会到 50 万。撑住。"
            ),
            choices=[
                Choice(key="A", text="坚定持有，信仰不灭",
                       hint="💬 [系统] 你经历过 2018。这一次你更从容。",
                       consequences={"stress": 10},
                       narrative="你把行情软件删了。不看不想。你知道未来。"),
                Choice(key="B", text=f"趁低价加仓（投入 {_fmt_money(_dynamic_buy_amount(state, 30000))}）",
                       hint="💬 [系统] 别人恐惧你贪婪。第几次了？",
                       consequences={"_action": f"buy_btc_{int(_dynamic_buy_amount(state, 30000))}", "stress": 15},
                       narrative="你在底部又加了仓。如果这是最后一次抄底，让它成为最漂亮的一次。"),
            ],
            template_id="2022_btc_crash_holder",
        ))

    # --- Event 2: ChatGPT ---
    if flags.get("pivoted_to_ai_2018"):
        chatgpt_desc = "你等这一天等了 4 年。ChatGPT 一出你就知道风口来了。\n你的技能现在是市场上最抢手的。"
    else:
        chatgpt_desc = "ChatGPT 发布了。所有人都在说 AI 要改变世界。\n你开始认真思考自己的位置。"

    events.append(GameEvent(
        year=2022, type="life", category="career",
        title="ChatGPT 横空出世",
        description=chatgpt_desc,
        choices=[
            Choice(key="A", text="全力投入 AI 赛道",
                   hint="💬 [系统] 无论之前有没有布局，现在 all in AI 都不晚。",
                   consequences={"career_level": 1, "stress": 10, "reputation": 5},
                   narrative="你开始没日没夜地学习和实践。\n你知道这波浪潮会比移动互联网更大。"),
            Choice(key="B", text="观望一下，先看看再说",
                   hint="💬 [系统] 谨慎。但窗口期不会太长。",
                   consequences={"stress": -5},
                   narrative="你注册了 ChatGPT，玩了一会儿。\n「确实厉害。」但你还没想好怎么切入。"),
        ],
        template_id="2022_chatgpt",
    ))

    # --- Event 3: Layoff Wave (skip if already fired 2018) ---
    if flags.get("was_fired_2018"):
        events.append(GameEvent(
            year=2022, type="life", category="career",
            title="昔日同事纷纷「毕业」",
            description=(
                "你看着昔日同事纷纷「毕业」，庆幸自己 4 年前就上了岸。\n"
                "甚至有人来问你：「你当年被裁后怎么转型的？」"
            ),
            choices=[Choice(
                key="A", text="分享经验",
                hint="💬 [系统] 当年的低谷成了今天的谈资。人生就是这样。",
                consequences={"reputation": 10, "social": 10, "stress": -10},
                narrative="你请了几个前同事吃饭，分享了你的转型经历。\n「塞翁失马」他们说。你笑了。",
            )],
            template_id="2022_layoff_survivor",
        ))
    elif state.is_employed:
        if flags.get("pivoted_to_ai_2018") or flags.get("ai_strategy_2022") == "all_in":
            events.append(GameEvent(
                year=2022, type="life", category="career",
                title="裁员潮中的安全岛",
                description="大厂裁员潮汹涌。但 AI 岗位是唯一在扩招的方向。\n你的工位稳如泰山。",
                choices=[Choice(
                    key="A", text="继续深耕",
                    hint="💬 [系统] 你是暴风眼中最安全的人。",
                    consequences={"stress": -10, "career_level": 1},
                    narrative="同事们人心惶惶，你却在收到新的 offer。\n时代红利，你接住了。",
                )],
                template_id="2022_layoff_safe",
            ))

    return events


# ---------------------------------------------------------------------------
# 2023 Events (Seed Year)
# ---------------------------------------------------------------------------


def build_2023_events(state: PlayerState) -> list[GameEvent]:
    """Build 2023: AI payoff + BTC last window."""
    events: list[GameEvent] = []
    flags = state.flags

    # --- Event 1: AI Payoff ---
    if flags.get("pivoted_to_ai_2018") or flags.get("ai_strategy_2022") == "all_in":
        events.append(GameEvent(
            year=2023, type="life", category="career",
            title="AI 布局兑现",
            description=(
                "你的 AI 技能现在是市场上最抢手的。猎头电话每周 3 个。\n"
                "一家大厂开出了年薪 80 万的 offer。"
            ),
            choices=[
                Choice(key="A", text="接！翻倍涨薪！",
                       hint="💬 [系统] 你等这一刻等了 5 年。",
                       consequences={"monthly_salary": 30000, "stress": 10, "career_level": 1,
                                     "reputation": 10, "job_title": "AI 技术专家"},
                       narrative="你跳槽了。新公司的工牌上写着你的名字和一个很长的 title。\n"
                                 "5 年前的布局，今天开花结果了。"),
                Choice(key="B", text="拒。我要自己干。",
                       hint="💬 [系统] AI 创业的窗口正在打开。你有技术、有钱、有时机。",
                       consequences={"savings": -100000, "stress": 20, "reputation": 15,
                                     "is_employed": False, "job_title": "AI 创业者"},
                       narrative="你辞了职，注册了公司。\n你知道这波 AI 创业潮里，你的起点比 99% 的人都高。"),
            ],
            template_id="2023_ai_payoff",
        ))
    else:
        events.append(GameEvent(
            year=2023, type="life", category="career",
            title="AI 浪潮来了",
            description=(
                "AI 浪潮席卷一切。但你感觉自己站在岸上看别人冲浪。\n"
                "不过现在开始学还来得及。"
            ),
            choices=[
                Choice(key="A", text="现在开始学 AI",
                       hint="💬 [系统] 来得及。但不容易。",
                       consequences={"savings": -10000, "stress": 10, "career_level": 1},
                       narrative="你报了课程，开始恶补。晚了 5 年，但好过再晚 5 年。"),
                Choice(key="B", text="做好本职工作就行",
                       hint="💬 [系统] 不是所有人都要追风口。",
                       consequences={"stress": -5},
                       narrative="你继续做好自己的事。AI 浪潮跟你没关系。\n至少你是这么告诉自己的。"),
            ],
            template_id="2023_ai_late",
        ))

    # --- Event 2: BTC Last Window ---
    btc_price = get_btc_price(2023)  # 200000
    events.append(GameEvent(
        year=2023, type="life", category="market",
        title="BTC 最后的上车机会",
        description=(
            f"BTC 从 12 万缓慢回到了 {_fmt_money(btc_price)}。\n"
            "你知道明年会到 50 万。这是最后的低价了。"
        ),
        choices=[
            Choice(key="A", text=f"加仓（投入 {_fmt_money(_dynamic_buy_amount(state, 50000))}）",
                   hint="💬 [系统] 最后一次机会。你比任何人都确定。",
                   consequences={"_action": f"buy_btc_{int(_dynamic_buy_amount(state, 50000))}", "stress": 10},
                   narrative="你在别人还在犹豫的时候果断出手了。\n最后一次。然后等待 2024 年的收获。"),
            Choice(key="B", text="够了，已经很多了",
                   hint="💬 [系统] 知足常乐。你已经有足够的筹码了。",
                   consequences={"stress": -5},
                   narrative="你决定不再追加。该有的都有了。"),
        ],
        template_id="2023_btc_last_window",
    ))

    return events


# ---------------------------------------------------------------------------
# 2024 Events (Harvest Year)
# ---------------------------------------------------------------------------


def build_2024_events(state: PlayerState) -> list[GameEvent]:
    """Build 2024: all choices bear fruit + life decision."""
    events: list[GameEvent] = []
    flags = state.flags

    # --- Event 1: Choices Review (flag-driven) ---
    review_lines = []
    if flags.get("bought_house_2016"):
        prop_val = get_property_price(2024) * state.properties
        review_lines.append(f"你 2016 年买的房子现在值 {_fmt_money(prop_val)} 了。你妈逢人就说你有远见。")
    if flags.get("pivoted_to_ai_2018"):
        review_lines.append("你在 AI 行业已经做了 6 年了。简历上写的每一个项目现在都是金字招牌。")
    if flags.get("took_profit_2017"):
        review_lines.append("2017 年你在高点卖了一部分 BTC。那笔钱让你安然度过了 2018 年的寒冬。")
    if flags.get("panic_sold_2020"):
        review_lines.append("你偶尔还是会想起 2020 年 312 那天恐慌卖出的那些 BTC……\n算了不想了。算了。")
    if flags.get("stockpiled_masks"):
        review_lines.append("2019 年囤口罩的事，到现在邻居还在提。你成了小区传说。")
    if flags.get("helped_cousin_2015"):
        review_lines.append("表妹现在在大厂做得很好。她说当年的学费是她人生的转折点。")
    if not review_lines:
        review_lines.append("回顾这十年，每一个选择都把你推到了今天的位置。")

    events.append(GameEvent(
        year=2024, type="life", category="social",
        title="十年选择，终见分晓",
        description="\n".join(review_lines),
        choices=[Choice(
            key="A", text="感慨一下，继续前行",
            hint="💬 [系统] 种什么因，得什么果。这就是你的十年。",
            consequences={"stress": -10},
            narrative="你坐在窗前，翻看手机相册里这些年的照片。\n每一张都是一个选择的印记。",
        )],
        template_id="2024_choices_review",
    ))

    # --- Event 2: Life Decision (net worth driven) ---
    nw = state.net_worth
    if nw > 10_000_000:
        events.append(GameEvent(
            year=2024, type="life", category="social",
            title="财务自由之后",
            description=(
                f"你的净资产超过了 {_fmt_money(nw)}。你财务自由了。\n"
                "接下来怎么办？"
            ),
            choices=[
                Choice(key="A", text="提前退休，环游世界",
                       hint="💬 [系统] 你赚够了。是时候享受了。",
                       consequences={"is_employed": False, "stress": -30, "savings": -200000},
                       narrative="你递了辞职信。订了飞往冰岛的机票。\n人生第一次，你觉得完全自由了。"),
                Choice(key="B", text="继续搞钱，目标 1 个亿",
                       hint="💬 [系统] 贪婪还是野心？你分不清了。",
                       consequences={"stress": 10, "reputation": 5},
                       narrative="你定了新目标。有些人天生停不下来。"),
                Choice(key="C", text="做点有意义的事",
                       hint="💬 [系统] 钱够了。但人生的意义呢？",
                       consequences={"savings": -300000, "reputation": 20, "stress": -10,
                                     "relationship": 10},
                       narrative="你拿出一部分钱成立了一个小基金，帮助年轻人创业。\n你想：如果当年有人帮我一把……"),
            ],
            template_id="2024_life_choice_rich",
        ))
    elif nw > 1_000_000:
        events.append(GameEvent(
            year=2024, type="life", category="social",
            title="不上不下",
            description=(
                f"你的净资产 {_fmt_money(nw)}。比大多数人好，但还不算自由。\n"
                "最后一年了。"
            ),
            choices=[
                Choice(key="A", text="满足了，知足常乐",
                       hint="💬 [系统] 知足者富。",
                       consequences={"stress": -15},
                       narrative="你决定不再焦虑。有些东西比钱更重要。"),
                Choice(key="B", text=f"最后再搏一把（投入 {_fmt_money(_dynamic_buy_amount(state, 50000))}）",
                       hint="💬 [系统] 孤注一掷的勇气……还是不甘心？",
                       consequences={"_action": f"buy_btc_{int(_dynamic_buy_amount(state, 50000))}", "stress": 15},
                       narrative="你把最后一笔大钱投了进去。All or nothing。"),
            ],
            template_id="2024_life_choice_mid",
        ))
    else:
        events.append(GameEvent(
            year=2024, type="life", category="social",
            title="十年了",
            description=(
                "十年了。你没有暴富，但你还活着。\n"
                f"净资产 {_fmt_money(nw)}。"
            ),
            choices=[
                Choice(key="A", text="虽然没大赚，但学到了很多",
                       hint="💬 [系统] 人生不只有一种衡量方式。",
                       consequences={"stress": -10},
                       narrative="你笑了笑。钱不是唯一的尺度。\n至少你比上辈子活得清醒。"),
                Choice(key="B", text="有点遗憾。如果重来……等等，这不就是重来吗？",
                       hint="💬 [系统] 重生者的终极悖论：你已经重来过了，还想再来一次吗？",
                       consequences={"stress": 5},
                       narrative="你苦笑。知道答案和做对题目，终究是两回事。"),
            ],
            template_id="2024_life_choice_low",
        ))

    return events


# ---------------------------------------------------------------------------
# 2025 Events (Final Year)
# ---------------------------------------------------------------------------


def build_2025_events(state: PlayerState) -> list[GameEvent]:
    """Build 2025: reunion dinner (emotional climax)."""
    events: list[GameEvent] = []
    flags = state.flags

    # --- Reunion Dinner ---
    has_helped = (flags.get("helped_family_2015") or
                  state.times_helped_family >= 1)
    high_relationship = state.relationship >= 60

    if high_relationship and has_helped:
        dinner_desc = (
            "除夕。你妈做了一桌子你爱吃的菜。\n"
            "她说：「这些年你给家里的那些钱，妈一分没花，都给你存着呢。」\n"
            "你红了眼眶。"
        )
    elif state.has_partner:
        partner = _partner_label(state)
        dinner_desc = (
            f"除夕。{partner}第一次来你家过年。\n"
            f"你妈拉着 TA 的手说个不停。你爸默默给 TA 倒了杯茶。\n"
            "你看着这一幕，觉得这才是真正的「资产」。"
        )
    elif not high_relationship:
        dinner_desc = (
            "除夕。回家过年，气氛有点沉默。\n"
            "你给爸妈转了一笔钱。你妈收了，没说什么。\n"
            "你知道钱买不回那些错过的陪伴。"
        )
    else:
        dinner_desc = (
            "除夕。你一个人在城市的出租屋里。\n"
            "妈妈打来视频电话：「儿子/女儿，吃饭了没？」\n"
            "你说吃了。其实你在吃外卖。\n"
            "挂了电话，你看着窗外的烟花，想起了这十年。"
        )

    events.append(GameEvent(
        year=2025, type="life", category="family",
        title="团圆饭",
        description=dinner_desc,
        choices=[Choice(
            key="A", text="举杯",
            hint="💬 [系统] 十年了。不管赚了多少钱，能和重要的人在一起，就是最好的结局。",
            consequences={"stress": -20, "relationship": 10},
            narrative="你举起杯子。\n不管这十年过得怎么样——\n谢谢你，重生者。",
        )],
        template_id="2025_reunion_dinner",
    ))

    return events


# ---------------------------------------------------------------------------
# Master dispatcher
# ---------------------------------------------------------------------------


def build_year_events(year: int, state: PlayerState) -> list[GameEvent] | None:
    """Build events for a year using the event map.

    Returns None if this year isn't handled by the event map (falls back to old system).
    """
    builders = {
        2015: build_2015_events,
        2016: build_2016_events,
        2017: build_2017_events,
        2018: build_2018_events,
        2019: build_2019_events,
        2020: build_2020_events,
        2021: build_2021_events,
        2022: build_2022_events,
        2023: build_2023_events,
        2024: build_2024_events,
        2025: build_2025_events,
    }
    builder = builders.get(year)
    if builder is None:
        return None
    return builder(state)
