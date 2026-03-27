"""Automated demo playthrough — generates asciicast v2 (.cast) file.

Works on Windows (PopenSpawn, no pty needed).

Usage:
    python scripts/record_demo.py          # → docs/demo.cast
    python scripts/record_demo.py --play   # Terminal echo only, no file

    # Convert to GIF:
    agg docs/demo.cast docs/demo.gif --cols 100 --rows 30
    # Upload:
    asciinema upload docs/demo.cast
"""

from __future__ import annotations

import io
import json
import re
import sys
import time
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")

from pexpect.popen_spawn import PopenSpawn

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROJECT = Path(__file__).resolve().parent.parent
PYTHON = str(PROJECT / ".venv" / "Scripts" / "python.exe")
if not Path(PYTHON).exists():
    PYTHON = sys.executable
CAST_PATH = PROJECT / "docs" / "demo.cast"
COLS, ROWS = 100, 30

FAST = 0.3
CHOICE = 1.5
HOLD_END = 3.0

# ---------------------------------------------------------------------------
# Strip Rich ANSI escape sequences for reliable matching
# ---------------------------------------------------------------------------
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\].*?\x07")


def _strip(text: str) -> str:
    return _ANSI_RE.sub("", text)


# ---------------------------------------------------------------------------
# Scripted choices: (keyword_in_context, desired_choice, delay)
# ---------------------------------------------------------------------------
SCRIPT: list[tuple[str, str, float]] = [
    # 2015
    ("同事的神秘推荐",      "A", CHOICE),
    ("老妈的电话",          "A", CHOICE),
    ("2015 年的最后一天",   "A", FAST),
    # 2016
    ("全民抢房",            "B", CHOICE),
    # 2017
    ("BTC 起飞",            "A", CHOICE),
    ("资产突破",            "B", CHOICE),
    ("九四禁令",            "A", CHOICE),
    # 2018
    ("裁员风暴",            "A", CHOICE),
    # 2019
    ("不起眼的新闻",        "A", CHOICE),
    # 2020
    ("全小区",              "A", FAST),
    ("312",                 "A", CHOICE),
    # 2021
    ("历史新高",            "B", CHOICE),
    # General fallbacks (order matters — checked last)
    ("口罩",                "A", CHOICE),
]


def _match_script(context: str) -> tuple[str, float] | None:
    plain = _strip(context)
    for kw, val, delay in SCRIPT:
        if kw in plain:
            return val, delay
    return None


def _parse_valid_keys(text: str) -> list[str]:
    """Extract valid keys from '你的选择 [A/B/C] >'."""
    plain = _strip(text)
    m = re.search(r"你的选择 \[([A-Z/]+)\]", plain)
    if m:
        return m.group(1).split("/")
    # Survival event or other prompt
    m = re.search(r"\[([A-Z/]+)\]\s*>", plain)
    if m:
        return m.group(1).split("/")
    return ["A"]


# ---------------------------------------------------------------------------
# Asciicast v2 recorder
# ---------------------------------------------------------------------------
class CastWriter:
    def __init__(self):
        self.rows: list[str] = []
        self.t0 = time.monotonic()
        header = {
            "version": 2,
            "width": COLS,
            "height": ROWS,
            "timestamp": int(time.time()),
            "title": "ReRun — 穿越回2015逆天改命",
            "env": {"SHELL": "/bin/bash", "TERM": "xterm-256color"},
        }
        self.rows.append(json.dumps(header, ensure_ascii=False))

    def event(self, etype: str, data: str):
        ts = round(time.monotonic() - self.t0, 4)
        self.rows.append(json.dumps([ts, etype, data], ensure_ascii=False))

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(self.rows) + "\n", encoding="utf-8")
        print(f"\n✅  Saved: {path}  ({len(self.rows) - 1} events)")


# ---------------------------------------------------------------------------
# Main playthrough
# ---------------------------------------------------------------------------
def run(*, save_cast: bool = True):
    cmd = f'"{PYTHON}" -m rerun --offline'
    child = PopenSpawn(cmd, encoding="utf-8", timeout=60, cwd=str(PROJECT))

    cast = CastWriter() if save_cast else None

    def read_until_prompt(timeout: float = 30.0) -> str:
        """Read output until we detect an input prompt (ends with '> ' or '...]')."""
        buf = ""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                # Expect common prompt endings
                idx = child.expect_exact(
                    ["> ", "...]", "──\r\n"],
                    timeout=max(0.5, deadline - time.monotonic()),
                )
                chunk = (child.before or "") + (child.after or "")
                buf += chunk
                if cast:
                    cast.event("o", chunk)
                sys.stdout.write(chunk)
                sys.stdout.flush()

                plain = _strip(buf)
                # Detected a choice prompt
                if "> " in (child.after or ""):
                    return buf
                # Detected a "press enter" prompt
                if "...]" in (child.after or ""):
                    return buf
                # Just a separator line — keep reading
                continue
            except Exception:
                break
        return buf

    def send(text: str, delay: float = FAST):
        time.sleep(delay)
        if cast:
            cast.event("i", text + "\r\n")
        child.sendline(text)

    # ---- Opening ----
    out = read_until_prompt(15)  # Gender prompt
    send("1", CHOICE)

    out = read_until_prompt(10)  # Preset prompt
    send("1", CHOICE)

    # ---- Game loop ----
    context = ""
    for _ in range(300):  # Safety limit
        out = read_until_prompt(20)
        if not out:
            break

        plain = _strip(out)
        context += plain

        # "Press enter" prompt
        if "按回车" in plain or "...]" in (child.after or ""):
            send("", FAST)
            context = ""
            continue

        # Choice prompt (你的选择 [...] > )
        if "你的选择" in plain and "> " in (child.after or ""):
            scripted = _match_script(context)
            valid_keys = _parse_valid_keys(out)

            if scripted:
                choice, delay = scripted
                # Ensure our scripted choice is actually valid
                if choice not in valid_keys:
                    choice = valid_keys[0]
            else:
                choice = valid_keys[0]
                delay = CHOICE

            send(choice, delay)
            context = ""
            continue

        # Survival/bankruptcy prompt
        if ("紧急状态" in plain or "存款跌破" in plain) and "> " in (child.after or ""):
            valid_keys = _parse_valid_keys(out)
            # Prefer B (move home) to preserve BTC
            choice = "B" if "B" in valid_keys else valid_keys[0]
            send(choice, CHOICE)
            context = ""
            continue

        # Final ending menu
        if "再来一次" in plain or ("退出" in plain and "> " in (child.after or "")):
            time.sleep(HOLD_END)
            send("Q", 0.5)
            break

        # Unmatched prompt — send enter
        if "> " in (child.after or ""):
            send("", FAST)
            context = ""

    # Drain remaining output
    time.sleep(1)
    try:
        child.expect_exact(["§NEVER§"], timeout=2)
    except Exception:
        rest = child.before or ""
        if rest:
            if cast:
                cast.event("o", rest)
            sys.stdout.write(rest)
            sys.stdout.flush()

    try:
        child.kill(9)
    except Exception:
        pass

    if cast:
        cast.save(CAST_PATH)
        print(f"   agg {CAST_PATH} docs/demo.gif --cols {COLS} --rows {ROWS}")


if __name__ == "__main__":
    run(save_cast="--play" not in sys.argv)
