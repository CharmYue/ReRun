"""Event chain system — flags-based follow-up events triggered by past choices.

V4: Expanded flag system per RERUN_WEALTH_LINE_EVENT_MAP.md
"""

from __future__ import annotations

from rerun.engine.events import Choice, GameEvent
from rerun.engine.state import PlayerState, get_btc_price


def set_flags_from_choice(state: PlayerState, event_id: str, choice_key: str) -> PlayerState:
    """Set flags based on an event choice, for triggering follow-up events later."""
    new_flags = dict(state.flags)

    # --- 2015 ---
    if event_id == "2015_btc_enlightenment":
        if choice_key == "A":
            new_flags["btc_choice_2015"] = "all_in"
            new_flags["bought_btc_2015"] = True
        elif choice_key == "B":
            new_flags["btc_choice_2015"] = "moderate"
            new_flags["bought_btc_2015"] = True
        elif choice_key == "C":
            new_flags["btc_choice_2015"] = "small"
            new_flags["bought_btc_2015"] = True
        elif choice_key == "D":
            new_flags["btc_choice_2015"] = "none"
            new_flags["skipped_btc_2015"] = True

    if event_id == "2015_family_event_male":
        if choice_key == "A":
            new_flags["helped_family_2015"] = True
            new_flags["helped_cousin_2015"] = True
        else:
            new_flags["helped_family_2015"] = False

    if event_id == "2015_family_event_female":
        if choice_key == "A":
            new_flags["joined_daigou_2015"] = True
        elif choice_key == "C":
            new_flags["invited_friend_invest"] = True

    # --- 2016 ---
    if event_id == "2016_house_fomo":
        if choice_key == "A":
            new_flags["bought_house_2016"] = True
        else:
            new_flags["bought_house_2016"] = False
            if choice_key == "B":
                new_flags["refused_house_2016"] = True
                new_flags["didnt_buy_house_2016"] = True

    if event_id == "2016_house_investment":
        if choice_key == "A" and state.savings >= 300000:
            new_flags["bought_house_2016"] = True

    if event_id == "2016_work_praise":
        if choice_key == "B":
            new_flags["got_promotion_2016"] = True

    if event_id == "2016_college_reunion":
        if choice_key in ("A", "B"):
            new_flags["reunion_attended"] = True

    if event_id == "2016_side_hustle":
        if choice_key == "A":
            new_flags["started_side_hustle"] = True

    if event_id == "2016_mom_saved_money":
        new_flags["mom_gave_money"] = True

    # --- 2017 ---
    if event_id == "2017_btc_surge":
        if choice_key == "A":
            new_flags["revealed_btc_2017"] = "low_key"
        elif choice_key == "B":
            new_flags["revealed_btc_2017"] = "hinted"
        elif choice_key == "C":
            new_flags["revealed_btc_2017"] = "full_reveal"
            new_flags["friends_know_btc"] = True
            new_flags["shared_btc_knowledge_2017"] = True

    if event_id == "2017_btc_regret_no":
        if choice_key == "A":
            new_flags["bought_btc_2017_late"] = True
            new_flags["bought_btc_2015"] = True  # now they have BTC

    if event_id == "2017_btc_milestone":
        if choice_key == "C":
            new_flags["took_profit_2017"] = True

    if event_id == "2017_nine_four":
        if choice_key == "A":
            new_flags["reaction_to_94"] = "hold"
        elif choice_key == "B":
            new_flags["reaction_to_94"] = "panic_sell"
        elif choice_key == "C":
            new_flags["reaction_to_94"] = "buy_more"

    # --- 2018 ---
    if event_id == "2018_layoff":
        if choice_key in ("A", "B"):
            new_flags["was_fired_2018"] = True
        if choice_key == "A":
            new_flags["chose_gap_year"] = True

    if event_id == "2018_ai_pivot":
        if choice_key == "A":
            new_flags["pivoted_to_ai_2018"] = True

    if event_id == "chain_friends_blame":
        new_flags["handled_friend_complaint"] = choice_key

    # --- 2019 ---
    if event_id == "2019_mask_stockpile":
        if choice_key in ("A", "B"):
            new_flags["stockpiled_masks"] = True
            new_flags["mask_amount"] = 50000 if choice_key == "A" else 10000

    if event_id == "2019_romance":
        if choice_key == "A":
            new_flags["met_partner_2019"] = True
            partner_name = "陈雨涵" if state.gender.value == "male" else "李浩然"
            new_flags["partner_name"] = partner_name
        elif choice_key == "B":
            new_flags["met_partner_2019_slow"] = True
            partner_name = "陈雨涵" if state.gender.value == "male" else "李浩然"
            new_flags["partner_name"] = partner_name

    # --- 2020 ---
    if event_id == "2020_312_crash":
        if choice_key == "A":
            new_flags["bottom_fished_2020"] = True
        elif choice_key == "C":
            new_flags["panic_sold_2020"] = True

    if event_id == "2020_romance_progress":
        if choice_key == "A":
            new_flags["living_together"] = True

    # --- 2021 ---
    if event_id == "2021_btc_peak":
        sell_map = {"A": "80pct", "B": "50pct", "C": "hold", "D": "all"}
        new_flags["sold_btc_2021"] = sell_map.get(choice_key, "hold")

    if event_id == "2021_marriage_pressure":
        if choice_key == "A":
            new_flags["married"] = True
        elif choice_key == "B":
            new_flags["refused_marriage_2021"] = True

    if event_id == "2021_romance_cohabit":
        if choice_key == "A":
            new_flags["living_together"] = True

    # Breakup events
    if event_id in ("chain_breakup_2022", "chain_breakup_2023"):
        if choice_key in ("A", "B"):
            cons = {}
            for c in []:
                pass
            # Check if this choice causes breakup by looking at choice consequences
            # Breakup happens on specific choices (B for 2022, B for 2023)
            if event_id == "chain_breakup_2022":
                new_flags["broke_up_2022"] = True
            elif event_id == "chain_breakup_2023" and choice_key == "B":
                new_flags["broke_up_2023"] = True

    # --- 2022 ---
    if event_id == "2022_chatgpt":
        if choice_key == "A":
            new_flags["ai_strategy_2022"] = "all_in"
        else:
            new_flags["ai_strategy_2022"] = "observe"

    # --- 2023 ---
    if event_id == "2023_ai_payoff":
        if choice_key == "B":
            new_flags["ai_startup_2023"] = True

    if new_flags != state.flags:
        return state.model_copy(update={"flags": new_flags})
    return state


def check_chain_events(state: PlayerState) -> list[GameEvent]:
    """Check if any event chain follow-ups should fire this year."""
    events: list[GameEvent] = []
    year = state.year
    flags = state.flags

    # Chain: 2015 helped cousin → 2019 cousin graduates and thanks you
    if year == 2019 and flags.get("helped_cousin_2015"):
        events.append(GameEvent(
            year=year, type="life", category="family",
            title="表妹来感谢你了",
            description=(
                "表妹浙大毕业了，找到了一份不错的工作。\n"
                "她特地请你吃了一顿大餐。\n\n"
                "「哥/姐，当年多亏了你。我第一个月工资就想请你吃饭。」\n\n"
                "你看着她自信的样子，觉得那笔钱花得值。"
            ),
            choices=[Choice(
                key="A", text="很欣慰，继续鼓励她",
                hint="💬 [系统] 亲情的回报不能用金钱衡量。但这种温暖，比账户上的数字更让人踏实。",
                consequences={"relationship": 15, "stress": -10},
                narrative="表妹说以后有什么忙尽管开口。你笑了笑，觉得这一年有了个好的开头。",
            )],
            template_id="chain_cousin_thanks",
        ))

    # Chain: 2015 didn't help cousin → 2019 regret
    if year == 2019 and flags.get("helped_family_2015") is False:
        events.append(GameEvent(
            year=year, type="life", category="family",
            title="过年聚餐",
            description=(
                "过年聚餐时你听说表妹因为学费贷款压力很大，勉强毕业找了份普通工作。\n"
                "你妈在旁边叹了口气，没说什么。你知道她在想什么。"
            ),
            choices=[Choice(
                key="A", text="默默吃饭",
                hint="💬 [系统] 有些遗憾，只有自己知道。",
                consequences={"relationship": -5},
                narrative="饭桌上的气氛有些沉闷。你多喝了两杯。",
            )],
            template_id="chain_cousin_regret",
        ))

    # Chain: 2017 坦白了 → 2018 friends blame you
    if year == 2018 and flags.get("friends_know_btc"):
        events.append(GameEvent(
            year=year, type="life", category="social",
            title="朋友来找你算账了",
            description=(
                "BTC 从 13 万跌到了 2.5 万。\n\n"
                "去年听了你的话买 BTC 的朋友开始发消息了：\n"
                "「你不是说会涨吗？我亏了好几万！」\n"
                "「你是不是早就卖了？就坑我们？」\n\n"
                "你的微信群里炸了锅。"
            ),
            choices=[
                Choice(key="A", text="耐心解释：BTC 有周期，长期看好",
                       hint="💬 [系统] 讲道理在亏钱的人面前不太管用。但良心不能不过。",
                       consequences={"social": -10, "stress": 20},
                       narrative="你发了一大段分析。有几个人理解了，但更多人已读不回。"),
                Choice(key="B", text="道歉，适当补偿",
                       hint="💬 [系统] 不是你的错，但友情有时候需要你先低头。",
                       consequences={"savings": -5000, "social": 5, "stress": 15},
                       narrative="你请了几个损失最重的朋友吃饭。他们消了点气，但关系回不到从前了。"),
                Choice(key="C", text="不理，投资亏损是自己的责任",
                       hint="💬 [系统] 道理上没错。但社交上……你可能会失去几个朋友。",
                       consequences={"social": -20, "stress": 10},
                       narrative="你选择了沉默。从此你多了个外号：「币圈大忽悠」。"),
            ],
            template_id="chain_friends_blame",
        ))

    # Chain: 2017 没暴露 → 2018 先知爽感
    if year == 2018 and flags.get("bought_btc_2015") and not flags.get("friends_know_btc"):
        if state.btc_amount > 0:
            events.append(GameEvent(
                year=year, type="life", category="social",
                title="暗中观察",
                description=(
                    "BTC 从 13 万跌到了 2.5 万。朋友圈里哀嚎遍野。\n"
                    "有人 @你：「还好你没买那个比特币吧？」\n"
                    "你微微一笑：「是啊，幸好没买。」\n\n"
                    "你打开自己的钱包看了一眼——虽然缩水了，但你知道这只是暂时的。"
                ),
                choices=[Choice(
                    key="A", text="继续潜伏",
                    hint="💬 [系统] 闷声发大财。这是先知的自我修养。",
                    consequences={"stress": -10},
                    narrative="你安静地关掉手机。这种暗爽，只有重生者懂。",
                )],
                template_id="chain_secret_holder",
            ))

    # Chain: 2016 didn't buy house → 2018 mom nags
    if year == 2018 and flags.get("didnt_buy_house_2016"):
        events.append(GameEvent(
            year=year, type="life", category="family",
            title="你妈又开始念叨了",
            description=(
                "过年回家，饭桌上你妈又提起了房子的事：\n\n"
                "「2016 年让你买你不听，现在涨了多少了！\n"
                "  你看看隔壁小李，当时听他妈的话买了，现在涨了 50 万！」\n\n"
                "你爸在旁边假装看电视。"
            ),
            choices=[
                Choice(key="A", text="「妈，我有自己的计划。」",
                       hint="💬 [系统] 你的计划叫 BTC。但你不能说。",
                       consequences={"relationship": -5, "stress": 10},
                       narrative="你妈瞪了你一眼。饭桌上的气氛降到了冰点。你默默扒饭。"),
                Choice(key="B", text="笑笑不说话，夹菜吃饭",
                       hint="💬 [系统] 沉默是金。尤其当你知道自己比隔壁小李赚得多的时候。",
                       consequences={"stress": 5},
                       narrative="你妈叹了口气，话题终于过去了。你心想：等我资产过千万再说。"),
            ],
            template_id="chain_mom_nags_house",
        ))

    # Chain: 2021 refused marriage → 2022 breakup (if relationship is low)
    if year == 2022 and flags.get("refused_marriage_2021") and state.has_partner:
        if state.relationship < 40:
            partner_name = flags.get("partner_name", "TA")
            events.append(GameEvent(
                year=year, type="life", category="romance",
                title="感情走到了尽头",
                description=(
                    f"去年你拒绝了结婚的提议。{partner_name}嘴上说理解，但心里一直有个结。\n"
                    f"最近你们吵得越来越多。有一天{partner_name}终于说出了那句话：\n\n"
                    f"「我们分开吧。我等不了了。」"
                ),
                choices=[
                    Choice(key="A", text="「对不起，我做得不够好。」",
                           hint="💬 [系统] 有些东西，比 BTC 更难挽回。",
                           consequences={"has_partner": False, "breakups": 1,
                                         "relationship": -20, "stress": 25},
                           narrative=f"{partner_name}搬走了。你坐在空荡荡的房间里，\n"
                                     "第一次觉得钱包鼓鼓的也没什么用。"),
                    Choice(key="B", text="「也许这样对我们都好。」",
                           hint="💬 [系统] 理性到最后，连感情也用理性收尾。",
                           consequences={"has_partner": False, "breakups": 1,
                                         "stress": 15},
                           narrative=f"你们平静地分了手。{partner_name}临走时说：\n"
                                     "「你什么都好，就是心里装不下别人。」"),
                ],
                template_id="chain_breakup_2022",
            ))

    # Chain: low relationship + has partner → 2023 breakup
    if year == 2023 and state.has_partner and state.relationship < 25:
        if not flags.get("refused_marriage_2021"):  # avoid double breakup
            partner_name = flags.get("partner_name", "TA")
            events.append(GameEvent(
                year=year, type="life", category="romance",
                title="渐行渐远",
                description=(
                    f"你和{partner_name}之间的距离越来越远。\n"
                    "你忙着投资、忙着工作，忙着规划未来。\n"
                    f"但{partner_name}要的只是你的时间和关注。\n\n"
                    "「你心里到底有没有我？」"
                ),
                choices=[
                    Choice(key="A", text="「我会改的，给我一次机会。」",
                           hint="💬 [系统] 重生者能预测 BTC 走势，却看不懂身边人的心。",
                           consequences={"relationship": 15, "stress": 10},
                           narrative=f"你开始试着放下手机，陪{partner_name}吃饭散步。\n"
                                     "改变很难，但你在努力。"),
                    Choice(key="B", text="「也许你说得对，我不是好的伴侣。」",
                           hint="💬 [系统] 承认自己的问题，需要勇气。",
                           consequences={"has_partner": False, "breakups": 1,
                                         "stress": 20, "relationship": -15},
                           narrative=f"{partner_name}哭了。你也想哭，但你忍住了。\n"
                                     "分手那天你查了一下 BTC 价格。然后觉得自己真是个混蛋。"),
                ],
                template_id="chain_breakup_2023",
            ))

    # Chain: 2022 — Dad's health scare (family help opportunity for 孝子)
    if year == 2022:
        medical_cost = 30000
        events.append(GameEvent(
            year=year, type="life", category="family",
            title="爸爸住院了",
            description=(
                "你爸打篮球的时候摔了一跤，检查出半月板撕裂。\n"
                f"医生说要做手术，自费部分大约 {medical_cost // 10000} 万。\n\n"
                "你妈在电话那头声音发抖：「你爸说不治了，贴膏药就行。」"
            ),
            choices=[
                Choice(key="A", text=f"「妈，钱我出。必须治。」（花 {medical_cost // 10000} 万）",
                       hint="💬 [系统] 健康无价。你爸嘴上说不治，心里其实怕花你的钱。",
                       consequences={"savings": -medical_cost, "relationship": 15, "stress": 10,
                                     "times_helped_family": 1},
                       narrative="你爸做了手术，恢复得很好。出院那天他拍了拍你的肩膀，\n"
                                 "什么都没说。但你懂。"),
                Choice(key="B", text="「让爸先用医保，不够的我再补。」",
                       hint="💬 [系统] 量力而行。医保能报一部分。",
                       consequences={"savings": -10000, "relationship": 5, "stress": 5},
                       narrative="最后自费部分没那么多。你爸说：「还是年轻人懂得精打细算。」"),
                Choice(key="C", text="「爸，保守治疗也行，别做手术了。」",
                       hint="💬 [系统] ……你确定？",
                       consequences={"relationship": -15, "stress": 5},
                       narrative="你爸贴了膏药。走路一瘸一拐。你妈每次看到都叹气。"),
            ],
            template_id="chain_dad_hospital",
        ))

    # Chain: broke up → 2024 rebound romance (enables second breakup for 渣男/渣女)
    if year == 2024 and not state.has_partner and state.breakups >= 1:
        new_name = "林小诺" if state.gender.value == "male" else "张远"
        events.append(GameEvent(
            year=year, type="life", category="romance",
            title="意想不到的重逢",
            description=(
                f"一次行业聚会上你认识了{new_name}。\n"
                "TA 笑起来很好看，和你聊了一整晚关于 AI 和未来。\n\n"
                "你已经受过伤了。这次……要不要再试一次？"
            ),
            choices=[
                Choice(key="A", text="试试吧，人生最后一年了",
                       hint="💬 [系统] 伤疤没好全就上战场？还是说……这次不一样？",
                       consequences={"has_partner": True, "relationship": 30, "stress": -10},
                       narrative=f"你和{new_name}在一起了。\n这一次你告诉自己：要把心放进去。"),
                Choice(key="B", text="算了，一个人挺好的",
                       hint="💬 [系统] 独狼也有独狼的精彩。",
                       consequences={"stress": -5},
                       narrative="你礼貌地交换了微信，但再也没有打开过那个对话。"),
            ],
            template_id="chain_rebound_2024",
        ))

    # Chain: chose gap year after layoff → 2019 payoff
    if year == 2019 and flags.get("chose_gap_year"):
        events.append(GameEvent(
            year=year, type="life", category="career",
            title="充电期的收获",
            description=(
                "去年被裁后你选择了 gap year。\n"
                "这段时间你没闲着：读了 15 本书、学了 Python、\n"
                "考了一个含金量不错的证书，还认识了几个行业大佬。\n\n"
                "现在你准备好了。新的机会就在眼前。"
            ),
            choices=[
                Choice(key="A", text="带着新技能重新找工作",
                       hint="💬 [系统] 你现在的简历比被裁之前更好看了。",
                       consequences={"is_employed": True, "monthly_salary": 5000, "career_level": 1,
                                     "stress": -20, "job_title": "跳槽成功"},
                       narrative="你拿到了一个比之前更好的 offer。面试官说：「gap year 没有白费。」"),
                Choice(key="B", text="尝试自由职业",
                       hint="💬 [系统] 不上班的生活你已经习惯了。试试看？",
                       consequences={"monthly_salary": 3000, "stress": -10, "network": 1},
                       narrative="你开始接外包项目。收入不稳定，但自由的感觉无价。"),
            ],
            template_id="chain_gap_year_payoff",
        ))

    return events


# Layoff foreshadowing — non-interactive hint shown in 2017
LAYOFF_FORESHADOW_2017 = (
    "📰 你注意到公司最近频繁开全员会。\n"
    "   CEO 的邮件里出现了「聚焦核心业务」这个词。\n"
    "   茶水间的八卦变多了。\n"
    "   ⚠️ 公司动态：有隐忧"
)
