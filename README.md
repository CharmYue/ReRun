# ReRun — Relive Your Life

> You wake up. Your phone says January 1, 2015.
> You remember everything — Bitcoin, COVID, ChatGPT.
> This time, you'll get it right... right?

**ReRun** is a roguelike life simulator played in the terminal. You travel back to 2015 with 10 years of future knowledge and make choices that shape your destiny through real historical events.

<!-- ![demo](docs/demo.gif) -->

## Features

- **10 years of real history** (2015-2025): Bitcoin booms & crashes, COVID, AI revolution
- **Meaningful choices** with real trade-offs — no obvious best option
- **16 achievements** across investment, life, and hidden categories
- **Rich terminal UI** with emoji, color panels, typewriter effects
- **AI-powered events** via OpenAI (optional) — or play fully offline
- **Snarky narrator** that breaks the fourth wall
- **Replayable** — different choices, different events, different endings

## Quick Start

```bash
pip install -e .
rerun
```

Or with Python directly:

```bash
python -m rerun
```

### Options

```
python -m rerun --offline    # No API key needed
python -m rerun --lang en    # English mode
python -m rerun --debug      # Debug output
```

### AI Mode (Optional)

Create a `.env` file for AI-generated events:

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

Without an API key, the game runs in offline mode with a curated event pool — fully playable and fun.

## How It Works

Each year (2015-2025), you'll see:
1. **Year briefing** — real historical context + your current stats
2. **Events** — life situations with 2-3 choices (career, family, romance, investment)
3. **Consequences** — stat changes, narrator commentary, maybe an achievement

Your stats include savings, BTC holdings, properties, stocks, stress, relationships, social standing, and reputation. Every choice shifts the balance.

At the end, you get a settlement report comparing your 10-year performance against a "normal life" baseline.

## Achievements

| Category | Examples |
|----------|---------|
| Investment | Diamond Hands, The Clown, Landlord, Tenbagger |
| Life | Life Winner, Heartbreaker, Zen Master, Lone Wolf |
| Hidden | Prophet, Storyteller, Phoenix, Exposed |

## Tech Stack

- Python 3.12+
- [Rich](https://github.com/Textualize/rich) for terminal UI
- [Pydantic](https://docs.pydantic.dev/) for data models
- OpenAI GPT-4o-mini for AI events (optional)

## Development

```bash
pip install -e ".[dev]"
pytest                    # Run tests
ruff check rerun/ tests/  # Lint
ruff format rerun/ tests/ # Format
```

## Disclaimer

The investment options in this game do not constitute real investment advice. BTC prices are based on historical data. Past performance does not predict future results.

## License

[MIT](LICENSE)
