"""Event chain system — flags-based follow-up events triggered by past choices."""

from __future__ import annotations

from rerun.engine.events import Choice, GameEvent
from rerun.engine.state import PlayerState


def set_flags_from_choice(state: PlayerState, event_id: str, choice_key: str) -> PlayerState:
    """Set flags based on an event choice, for triggering follow-up events later."""
    new_flags = dict(state.flags)

    if event_id == "2015_btc_enlightenment" and choice_key in ("A", "B", "C"):
        new_flags["bought_btc_2015"] = True
    if event_id == "2015_btc_enlightenment" and choice_key == "D":
        new_flags["skipped_btc_2015"] = True

    if event_id == "2015_family_event_male" and choice_key == "A":
        new_flags["helped_cousin_2015"] = True
    if event_id == "2015_family_event_female" and choice_key == "A":
        new_flags["joined_daigou_2015"] = True

    if event_id in ("2017_btc_moon",) and choice_key == "B":
        new_flags["shared_btc_knowledge_2017"] = True

    if "layoff" in event_id and choice_key == "B":
        new_flags["chose_gap_year"] = True

    if event_id == "2016_house_fomo" and choice_key == "B":
        new_flags["didnt_buy_house_2016"] = True

    if new_flags != state.flags:
        return state.model_copy(update={"flags": new_flags})
    return state


def check_chain_events(state: PlayerState) -> list[GameEvent]:
    """Check if any event chain follow-ups should fire this year."""
    events: list[GameEvent] = []
    year = state.year
    flags = state.flags

    # Chain 1: 2015 helped cousin → 2019 cousin graduates and thanks you
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
                consequences={"relationship": 10, "stress": -15},
                narrative="表妹说以后有什么忙尽管开口。你笑了笑，觉得这一年有了个好的开头。",
            )],
            template_id="chain_cousin_thanks",
        ))

    # Chain 2: 2015 bought BTC → 2017 colleague asks if you bought early
    if year == 2017 and flags.get("bought_btc_2015") and state.btc_amount > 0:
        events.append(GameEvent(
            year=year, type="life", category="social",
            title="老王又来了",
            description=(
                "BTC 涨到 10 万了。当初推荐你买的同事老王找到你：\n\n"
                "「兄弟，你当初买了没？看这涨幅……你不会真的买了吧？」\n\n"
                "他盯着你的表情，试图从你脸上读出答案。"
            ),
            choices=[
                Choice(
                    key="A", text="「买了一点点，运气好。」",
                    hint="💬 [系统] 低调是保护色。暴露太多不是好事。",
                    consequences={"social": 5, "stress": 5},
                    narrative="老王「啧」了一声：「你小子可以啊。」他没再追问，但眼神变了。",
                ),
                Choice(
                    key="B", text="「没买，当时觉得不靠谱。」",
                    hint="💬 [系统] 撒谎。但这是最安全的答案。",
                    consequences={"stress": -5},
                    narrative="老王叹了口气：「可惜了。」你面不改色，心里偷偷松了口气。",
                ),
                Choice(
                    key="C", text="坦白：「不止买了，还买了不少。」",
                    hint="💬 [系统] ⚠️ 高风险。2018 年暴跌时这些人会回来找你。",
                    consequences={"social": 10, "reputation": 15, "stress": 15},
                    narrative="老王震惊地看着你。然后整个部门都知道了。\n你的微信开始不停弹消息：「带带我。」",
                ),
            ],
            template_id="chain_lw_asks_btc",
        ))

    # Chain 3: 2016 didn't buy house → 2018 mom nags every holiday
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
                Choice(
                    key="A", text="「妈，我有自己的计划。」",
                    hint="💬 [系统] 你的计划叫 BTC。但你不能说。",
                    consequences={"relationship": -5, "stress": 10},
                    narrative="你妈瞪了你一眼。饭桌上的气氛降到了冰点。你默默扒饭。",
                ),
                Choice(
                    key="B", text="笑笑不说话，夹菜吃饭",
                    hint="💬 [系统] 沉默是金。尤其当你知道自己比隔壁小李赚得多的时候。",
                    consequences={"stress": 5},
                    narrative="你妈叹了口气，话题终于过去了。你心想：等我资产过千万再说。",
                ),
            ],
            template_id="chain_mom_nags_house",
        ))

    # Chain 4: 2017 shared BTC knowledge → 2018 friends blame you for crash losses
    if year == 2018 and flags.get("shared_btc_knowledge_2017"):
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
                Choice(
                    key="A", text="耐心解释：BTC 有周期，长期看好",
                    hint="💬 [系统] 讲道理在亏钱的人面前不太管用。但良心不能不过。",
                    consequences={"social": -10, "stress": 20},
                    narrative="你发了一大段分析。有几个人理解了，但更多人已读不回。\n有个朋友直接把你删了。",
                ),
                Choice(
                    key="B", text="道歉，适当补偿",
                    hint="💬 [系统] 不是你的错，但友情有时候需要你先低头。",
                    consequences={"savings": -5000, "social": 5, "stress": 15},
                    narrative="你请了几个损失最重的朋友吃饭，掏了5000块。\n他们消了点气，但关系回不到从前了。",
                ),
                Choice(
                    key="C", text="不理，投资亏损是自己的责任",
                    hint="💬 [系统] 道理上没错。但社交上……你可能会失去几个朋友。",
                    consequences={"social": -20, "stress": 10},
                    narrative="你选择了沉默。骂你的人骂完了也就散了。\n但从此你多了个外号：「币圈大忽悠」。",
                ),
            ],
            template_id="chain_friends_blame",
        ))

    # Chain 5: chose gap year after layoff → 2019 payoff
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
                Choice(
                    key="A", text="带着新技能重新找工作",
                    hint="💬 [系统] 你现在的简历比被裁之前更好看了。",
                    consequences={"is_employed": True, "monthly_salary": 5000, "career_level": 1,
                                  "stress": -20, "job_title": "跳槽成功"},
                    narrative="你拿到了一个比之前更好的 offer。面试官说：「gap year 没有白费。」",
                ),
                Choice(
                    key="B", text="尝试自由职业",
                    hint="💬 [系统] 不上班的生活你已经习惯了。试试看？",
                    consequences={"monthly_salary": 3000, "stress": -10, "network": 1},
                    narrative="你开始接外包项目。收入不稳定，但自由的感觉无价。",
                ),
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
