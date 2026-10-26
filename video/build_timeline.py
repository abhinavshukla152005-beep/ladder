"""Build the demo video timeline from a real pipeline run.

    python video/build_timeline.py

Runs `python -m ladder.demo`, keeps the ANSI colours, and assigns how long each
line stays on screen so the recording reads at a human pace.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANSI = re.compile(r"\x1b\[([0-9;]*)m")


def strip(line: str) -> tuple[str, set[str]]:
    codes: set[str] = set()

    def keep(m: re.Match) -> str:
        codes.update(m.group(1).split(";"))
        return ""

    return ANSI.sub(keep, line).rstrip(), codes


def classify(text: str, codes: set[str], first: bool) -> str:
    s = text.strip()
    if first:
        return "h1"
    if s.startswith("REJECTED") or "31" in codes:
        return "red"
    if s.startswith("KEPT") or "32" in codes:
        return "green"
    if s.startswith("─"):
        return "rule"
    if re.match(r"^\d\.\s", s):
        return "h2"
    if s.startswith(("chapter ", "class ", "reading range")):
        return "sub"
    if "2" in codes:
        return "dim"
    return "body"


def hold(cls: str, text: str) -> float:
    if cls == "h1":
        return 3.2
    if cls == "h2":
        return 1.6
    if cls == "rule":
        return 0.9
    if cls in ("red", "green"):
        return 2.2
    if cls == "dim":
        return 1.0
    if cls == "sub":
        return 1.3
    if not text.strip():
        return 0.2
    if "coverage" in text or "grounded in source" in text or "score:" in text:
        return 1.9
    return 0.62


def main() -> None:
    env = {**os.environ, "PYTHONPATH": "src", "PYTHONIOENCODING": "utf-8"}
    out = subprocess.run(
        [sys.executable, "-m", "ladder.demo"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout

    timeline = [{"cls": "cmd", "text": "$ python -m ladder.demo", "hold": 1.5}]
    for n, raw in enumerate(out.splitlines()):
        text, codes = strip(raw)
        cls = classify(text, codes, n == 0)
        timeline.append({"cls": cls, "text": text, "hold": hold(cls, text)})

    final = timeline[-1]
    final["hold"] = 3.0
    timeline += [
        {"cls": "h2", "text": "Ladder — MIT licensed · built with the Strands Agents SDK on Amazon Bedrock", "hold": 2.6},
        {"cls": "sub", "text": "", "hold": 0.0},
    ]

    dest = ROOT / "video" / "timeline.json"
    dest.write_text(json.dumps(timeline, indent=1, ensure_ascii=False), encoding="utf-8")
    total = sum(e["hold"] for e in timeline)
    print(f"{len(timeline)} lines · {total:.1f}s")


if __name__ == "__main__":
    main()
