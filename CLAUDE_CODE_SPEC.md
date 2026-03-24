# ReRun — Claude Code 开发规范
# 给 Claude Code 的项目上下文和开发指南

---

## 项目概述

ReRun 是一个**人生 roguelike 游戏**。玩家以"重生者"身份穿越回 2015 年，带着对未来 10 年的记忆（BTC 暴涨、COVID、AI 浪潮等），在真实历史事件中做出选择，试图逆天改命。

**产品形态：** CLI 先行（用 Python rich 库），后续补 Web 版
**核心体验：** 穿越重生 + roguelike 选择 + 真实历史 + AI 生成生活事件 + 有人格的吐槽旁白
**目标用户：** 泛人群（不只是开发者），以"好玩、能传播"为第一优先级
**参考调性：** 网文穿越爽文 + Slay the Spire 选择机制 + 抖音股神模拟视频的刺激感

完整游戏设计请参考 `ReRun_GDD_游戏设计文档.md`。本文档聚焦技术实现规范。

---

## 技术栈

```
语言: Python 3.12+
CLI UI: rich (终端富文本渲染、面板、表格、进度条、动画)
Web 框架: FastAPI（后续 Web 版）
LLM: OpenAI API (gpt-4o-mini)，通过抽象层调用，预留扩展
数据存储: 本地 JSON 文件（历史数据）+ SQLite（存档/排行榜，后续）
配置管理: pydantic-settings + .env
异步: asyncio + httpx（LLM 调用）
测试: pytest
包管理: uv 或 pip
容器化: Docker（后续）
```

---

## 项目结构

```
rerun-life/
├── README.md                    # 英文 README（主）
├── README_CN.md                 # 中文 README
├── LICENSE                      # MIT
├── pyproject.toml               # 项目配置
├── .env.example                 # 环境变量模板
├── .gitignore
│
├── rerun/
│   ├── __init__.py
│   ├── __main__.py              # python -m rerun 入口
│   ├── cli.py                   # CLI 主循环（rich UI）
│   ├── config.py                # 配置管理（pydantic-settings）
│   │
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── game.py              # 游戏主引擎（状态管理 + 流程控制）
│   │   ├── state.py             # 游戏状态数据模型
│   │   ├── events.py            # 事件系统（历史事件 + AI 生成事件）
│   │   ├── choices.py           # 选择系统（选项生成 + 后果计算）
│   │   └── achievements.py      # 成就系统
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py            # LLM 调用抽象层
│   │   ├── prompts.py           # 所有 prompt 模板
│   │   └── parser.py            # LLM 输出解析（JSON mode）
│   │
│   ├── data/
│   │   ├── historical_events.json   # 10 年历史大事件 + BTC 价格
│   │   ├── life_events.json         # 生活事件模板池
│   │   ├── achievements.json        # 成就定义
│   │   └── narrator_lines.json      # 旁白文案库（固定部分）
│   │
│   └── ui/
│       ├── __init__.py
│       ├── renderer.py          # rich 渲染器（面板、表格、动画）
│       ├── screens.py           # 各个画面（开场、事件、结算等）
│       └── effects.py           # 特效（数字跳动、打字机效果等）
│
├── tests/
│   ├── test_engine.py
│   ├── test_events.py
│   └── test_llm.py
│
└── examples/
    └── sample_run.md            # 一次完整 run 的示例输出
```

---

## 核心架构设计

### 1. 游戏状态 (state.py)

```python
from pydantic import BaseModel, Field

class PlayerState(BaseModel):
    """玩家当前状态"""
    year: int = 2015
    savings: float = 80000          # 💰 存款（元）
    btc_amount: float = 0           # 🪙 BTC 持有量
    properties: int = 0             # 🏠 房产数量
    stocks: float = 0               # 📈 股票市值
    
    # 隐性数值
    stress: int = 20                # 😰 压力值 0-100
    relationship: int = 50          # 💕 关系值 0-100
    social: int = 50                # 🤝 社交值 0-100
    reputation: int = 30            # 🌟 声望值 0-100
    
    # 状态标记
    has_partner: bool = False
    is_employed: bool = True
    job_title: str = "普通上班族"
    monthly_salary: float = 8000
    monthly_expense: float = 5000
    
    # 记录（用于成就判定和结算）
    choices_log: list[dict] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    max_btc_held: float = 0         # 历史最高持有量
    times_sold_btc: int = 0
    times_helped_family: int = 0
    breakups: int = 0
    
    @property
    def net_worth(self) -> float:
        """总资产"""
        btc_value = self.btc_amount * get_btc_price(self.year)
        property_value = self.properties * get_property_price(self.year)
        return self.savings + btc_value + property_value + self.stocks
```

### 2. 事件系统 (events.py)

事件分为两类：

**确定性事件（历史事件）：** 从 `historical_events.json` 读取，每年固定触发。提供背景信息和市场数据。

**随机事件（AI 生成）：** 基于玩家当前状态，由 LLM 生成。每次 run 不同。

```python
class GameEvent(BaseModel):
    """游戏事件"""
    year: int
    type: Literal["historical", "life"]  # 历史事件 or 生活事件
    category: str  # family, romance, career, social, accident, market
    title: str                           # 事件标题
    description: str                     # 事件描述（1-3 段，含旁白）
    choices: list[Choice]                # 2-3 个选项
    
class Choice(BaseModel):
    """选项"""
    key: str          # A, B, C
    text: str         # 选项描述
    hint: str         # 系统提示（旁白吐槽 / 风险提示）
    consequences: dict # 数值变化 {"savings": -50000, "stress": +20, ...}
    narrative: str     # 选择后的叙事文本
```

**AI 生成事件的策略：**

```
输入给 LLM 的上下文：
- 当前年份 + 该年历史背景
- 玩家当前全部数值
- 玩家之前的选择历史（最近 3 个）
- 不要生成的事件类型（避免重复）

要求 LLM 输出：
- 严格 JSON 格式（使用 response_format: json_object）
- 事件必须与玩家当前状态相关
- 选择必须有明确的数值后果
- 旁白要有人格（毒舌、幽默、meta）
- 选择之间要有真实的取舍（没有明显最优解）
```

### 3. LLM 抽象层 (client.py)

```python
class LLMClient:
    """
    LLM 调用抽象层
    MVP: OpenAI gpt-4o-mini
    后续扩展: Claude, DeepSeek, Ollama 等
    """
    
    def __init__(self, provider: str = "openai", model: str = "gpt-4o-mini"):
        self.provider = provider
        self.model = model
    
    async def generate_event(self, context: EventContext) -> GameEvent:
        """根据上下文生成一个生活事件"""
        # 使用 JSON mode 确保输出格式
        pass
    
    async def generate_narrator_line(self, situation: str) -> str:
        """生成旁白吐槽"""
        pass
    
    async def generate_ending_summary(self, state: PlayerState) -> str:
        """生成结局总评"""
        pass
```

**关键原则：**
- 所有 LLM 调用都通过这一个类
- 使用 `response_format={"type": "json_object"}` 确保结构化输出
- 调用失败时有 fallback（从预设事件池随机选一个）
- 每次 run 大约需要 10-15 次 LLM 调用（每年 1-2 次），成本约 $0.02-0.05

### 4. CLI 渲染器 (renderer.py)

使用 `rich` 库实现终端 UI。

**核心渲染组件：**

```python
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.progress import Progress
import time

console = Console()

def render_year_header(year: int, state: PlayerState):
    """渲染年度头部：年份 + 数值面板"""
    # 用 rich Panel + Table 展示
    pass

def render_event(event: GameEvent):
    """渲染事件：描述 + 选项"""
    # 打字机效果逐字显示描述
    # 选项用 Panel 框起来
    pass

def render_consequence(choice: Choice, state_changes: dict):
    """渲染选择后果：数值变化 + 旁白"""
    # 数字跳动效果（从旧值到新值）
    pass

def render_ending(state: PlayerState, achievements: list):
    """渲染结算画面"""
    # 大面板 + 资产柱状图（用 rich bar chart）+ 成就列表
    pass

def typewriter(text: str, speed: float = 0.03):
    """打字机效果"""
    for char in text:
        console.print(char, end="", highlight=False)
        time.sleep(speed)
    console.print()
```

**视觉风格要求：**
- 使用 emoji 增强可读性（💰🪙🏠😰💕🤝🌟⚡📱💬）
- 面板使用 `rich.panel.Panel` 带边框
- 数值变化用颜色标记：涨 = 绿色、跌 = 红色
- 旁白文本用特殊样式（dim italic 或 特定颜色）
- 年份切换时有明显的视觉分隔（━━━ 分隔线）
- 关键数字（资产、BTC 价格）要醒目（bold + 颜色）

---

## Prompt 设计规范

### 事件生成 Prompt

```
你是 ReRun 游戏的事件生成引擎。ReRun 是一个穿越重生人生 roguelike 游戏。
玩家带着 2025 年的记忆穿越回了 2015 年，试图逆天改命。

当前状态：
- 年份：{year}
- 存款：¥{savings}
- BTC 持有：{btc_amount} 个（当前价值 ¥{btc_value}）
- 房产：{properties} 套
- 月薪：¥{monthly_salary}
- 压力值：{stress}/100
- 关系值：{relationship}/100
- 是否有伴侣：{has_partner}
- 近期选择：{recent_choices}

该年历史背景：{year_context}

请生成一个生活事件，要求：
1. 事件必须与玩家当前状态紧密相关
2. 事件类型从以下选一个：family/romance/career/social/accident
3. 不要生成 {exclude_types} 类型（最近已出现过）
4. 核心设计原则：事件的目的是"逼玩家消耗资源或面临艰难取舍"
5. 三个选项之间必须有真实的 trade-off，没有明显最优解
6. 描述文字要生动、有代入感，像网文一样有画面感
7. 包含系统旁白（用 💬 [系统] 开头），旁白要：毒舌但善意、偶尔打破第四面墙、有梗有幽默

严格按以下 JSON 格式输出（不要输出任何其他内容）：
{event_json_schema}
```

### 旁白生成 Prompt

```
你是 ReRun 游戏中的"系统"旁白。你的性格特点：
- 毒舌但善意：会吐槽玩家，但内心希望他们好
- Meta/打破第四面墙：知道这是游戏，偶尔自嘲
- 用梗：网络用语、emoji、流行文化引用
- 简洁有力：通常 1-2 句话，偶尔 3 句

格式要求：以 "💬 [系统]" 开头

针对以下情境写一段旁白：
{situation}
```

---

## 数据文件格式

### historical_events.json

```json
{
  "2015": {
    "btc_price": {
      "start": 1800,
      "end": 2900,
      "high": 3200,
      "low": 1200
    },
    "property_price_per_sqm": {
      "beijing": 35000,
      "shanghai": 32000,
      "shenzhen": 30000,
      "hangzhou": 18000,
      "average_tier2": 10000
    },
    "events": [
      {
        "month": 6,
        "title": "A 股股灾",
        "description": "上证指数从 5178 点暴跌至 2850 点",
        "impact": "股市投资者巨亏，但与 BTC 无关"
      }
    ],
    "background": "BTC 在底部徘徊，大多数人还不知道它是什么。A 股经历了疯牛和股灾。房价开始蠢蠢欲动。"
  },
  "2016": {
    "...": "..."
  }
}
```

### life_events.json（AI 生成的 fallback 事件池）

```json
{
  "family": [
    {
      "template": "parent_sick",
      "title": "父/母生病",
      "description_template": "你{parent}查出了{illness}，需要{cost}治疗费...",
      "variables": {
        "parent": ["爸", "妈"],
        "illness": ["甲状腺结节", "腰椎间盘突出", "心脏支架"],
        "cost": [80000, 120000, 200000]
      }
    }
  ],
  "romance": ["..."],
  "career": ["..."],
  "social": ["..."],
  "accident": ["..."]
}
```

---

## 开发阶段规划

### Phase 1: CLI MVP（本周目标）

**Day 1-2: 骨架 + 数据**
- [ ] 项目初始化（pyproject.toml, .env, .gitignore）
- [ ] `state.py` — 完整的游戏状态模型
- [ ] `historical_events.json` — 10 年历史数据（BTC 价格、大事件）
- [ ] `config.py` — 配置管理
- [ ] `client.py` — LLM 抽象层（OpenAI）
- [ ] 基础测试

**Day 3-4: 引擎核心**
- [ ] `events.py` — 事件系统（历史事件加载 + AI 事件生成）
- [ ] `choices.py` — 选择系统（后果计算）
- [ ] `game.py` — 游戏主循环（年度推进）
- [ ] `prompts.py` — prompt 模板
- [ ] `parser.py` — LLM 输出解析
- [ ] 端到端测试：能跑通一个完整 10 年 run

**Day 5: CLI UI**
- [ ] `renderer.py` — rich 渲染（面板、表格、颜色）
- [ ] `screens.py` — 开场、事件、结算画面
- [ ] `effects.py` — 打字机效果、数字跳动
- [ ] `cli.py` — CLI 主循环

**Day 6: 打磨**
- [ ] `achievements.py` — 成就系统
- [ ] 优化 prompt（让旁白更有趣、事件更刺激）
- [ ] 跑 5+ 次完整 run，修 bug、调平衡
- [ ] 离线模式（fallback 事件池，无 API 也能玩）

**Day 7: 发布**
- [ ] README.md（英文）+ README_CN.md（中文）
- [ ] 录制终端 GIF（asciinema 或 terminalizer）
- [ ] 发布 v0.1.0
- [ ] 传播（小红书 / Twitter / HN / 即刻）

### Phase 2: Web 版（下周）
- FastAPI 后端 + SSE 流式推送
- HTML/CSS/JS 前端（时间线推进动画、数字跳动）
- 分享卡片生成

### Phase 3: 社区化（后续）
- 排行榜
- 更多场景（不只是财富线）
- 多语言
- 自定义起点

---

## 代码风格与约定

### Python 风格
- 使用 type hints（严格）
- Pydantic models 用于所有数据结构
- async/await 用于 LLM 调用
- 函数和变量使用 snake_case
- 类使用 PascalCase
- 常量使用 UPPER_CASE
- docstring 使用 Google 风格

### 命名约定
- 游戏引擎相关: `game_`, `event_`, `choice_`, `state_`
- LLM 相关: `llm_`, `prompt_`, `parse_`
- UI 相关: `render_`, `screen_`, `effect_`

### 关键设计原则
1. **LLM 调用与游戏逻辑分离**：数值计算由规则引擎处理（确定性），LLM 只负责生成文案和事件叙事
2. **Fallback everywhere**：任何 LLM 调用失败都有本地 fallback（预设事件池）
3. **状态不可变**：每次状态变更都生成新的 PlayerState，保留历史方便回溯
4. **渲染与逻辑分离**：engine/ 不依赖 ui/，方便后续 Web 版复用引擎

### Git 约定
- commit message 格式: `type: description`
- type: feat, fix, refactor, docs, style, test, chore
- 分支: main（稳定）, dev（开发）
- PR 自己 merge 就行（个人项目）

---

## 注意事项

### LLM 调用优化
- gpt-4o-mini 足够用，不需要 gpt-4o
- 使用 JSON mode（`response_format={"type": "json_object"}`）
- temperature 设为 0.9（需要创意和随机性）
- 每次 run 约 10-15 次调用，控制在 $0.05 以内
- 事件生成和旁白可以合并在一次调用里（减少 API 次数）

### 平衡性
- BTC 价格使用真实历史数据，不要随意调整
- 生活事件的"消耗"要合理：不要每年都让家人生病
- 确保不同选择路径都能到达有意义的结局
- "不穿越的基准线"设为：10 年后存款约 ¥300,000-500,000（普通上班族）

### 敏感内容边界
- 不涉及政治内容
- 家庭事件保持温暖基调（即使是冲突也有人情味）
- 感情选项不涉及不道德内容
- 投资选项不构成真实投资建议（加 disclaimer）
- 旁白吐槽保持善意，不刻薄不冒犯
