# ReRun — Claude Code 项目规则

## 项目概述

ReRun 是一款 roguelike 人生模拟器（CLI，Python + Rich），玩家穿越回 2015 年重新经历 2015-2025 十年人生。

## 技术栈

- Python 3.11+, Pydantic, Rich
- 引擎在 `rerun/engine/`，UI 在 `rerun/ui/`，数据在 `rerun/data/`
- 入口: `python -m rerun`

## 状态一致性规则（每次改动后必须检查）

1. 任何改变 `is_employed` / `job_title` / `monthly_salary` 的代码，必须同时更新相关的收入计算和面板显示
2. 任何改变 `properties` / `mortgage_monthly` 的代码，必须同时更新年支出中的房租/房贷显示
3. 任何 BTC 买卖操作，必须用 `cost / price` 计算实际数量，不能硬编码
4. 加仓选项的金额必须根据玩家当前存款动态生成（使用 `_dynamic_buy_amount()`），不能固定 2-5 万
5. 创业/自由职业 ≠ 失业。这些状态必须有收入。使用 `state.has_income` 和 `state.is_self_employed` 判断
6. 蒙太奇文本必须基于 `choices_log` 中的实际选择生成，不能靠关键词猜。特别注意区分「被裁」和「创业」
7. 事件触发前必须调用 `is_applicable()` 检查状态（有房不出现买房焦虑、无业不出现裁员等）
8. 成就解锁前必须检查互斥（如 diamond_hands 和 paper_hands 不能同时解锁）
9. **每次提交代码前运行 `python tests/test_consistency.py` 确认零违规**

## 成就触发路径（每个成就必须有可达路径）

| 成就 | 条件 | 触发路径 |
|------|------|---------|
| 地主 | `properties >= 2` | 2016买房 + 2021求婚买房；或 preset3 + 2016投资房 |
| 纸手 | `times_sold_btc >= 3` | 九四恐慌卖 + 2020恐慌卖 + 2021卖出 |
| 渣男/渣女 | `breakups >= 2` | 2022分手(拒婚链) + 2024 rebound再分手 |
| 意难平 | `net_worth < 450000` | 不买BTC打工线自然达成 |
| 孝子 | `times_helped_family >= 2` | 2015帮表妹 + 2020口罩给家人 + 2022爸爸住院 (任选2) |
| 独狼 | `!has_partner && social < 30` | 拒绝所有社交和恋爱选项 |

- 添加新成就时必须同时验证有可达的游戏路径
- `breakups` 只能通过明确的分手事件增加，不能隐式触发

## 关键设计约束

- `PlayerState` 是不可变的（immutable by convention），所有修改通过 `apply_consequences()` 返回新 state
- Preset 3（有房贷）起步必须有 `properties=1` 和 `mortgage_monthly=5000`
- 隐藏属性（stress/relationship/social/reputation）范围 0-100
- 技能（investment_iq/career_level/network/emotional_iq）范围 1-5
- BTC 数量和房产数量不能为负

## 测试

- 一致性测试: `python tests/test_consistency.py`
  - 路线 A: 穷小子梭哈线 (preset=1, male)
  - 路线 B: 有房贷富裕线 (preset=3, female)
  - 路线 C: 不买BTC打工线 (preset=1, male)
- 所有路线必须零违规才能提交
