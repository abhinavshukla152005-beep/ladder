"""Deterministic tools the agent graph relies on.

Every number a teacher sees in a Ladder report is computed here, in plain
Python, so it can be reproduced and audited. The language models only write
content -- they never get to grade their own arithmetic.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from strands import tool

VOWELS = "aeiouy"
_SENT_SPLIT = re.compile(r"[.!?]+")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _syllables(word: str) -> int:
    word = word.lower().strip("'-")
    if not word:
        return 0
    if len(word) <= 3:
        return 1
    groups = 0
    prev_vowel = False
    for ch in word:
        is_vowel = ch in VOWELS
        if is_vowel and not prev_vowel:
            groups += 1
        prev_vowel = is_vowel
    if word.endswith("e") and not word.endswith(("le", "ee")) and groups > 1:
        groups -= 1
    return max(1, groups)


def readability_metrics(text: str) -> dict:
    """Flesch-Kincaid grade plus the raw counts behind it."""
    sentences = [s for s in _SENT_SPLIT.split(text) if s.strip()]
    words = _WORD.findall(text)
    if not sentences or not words:
        return {
            "fk_grade": 0.0,
            "words": 0,
            "sentences": 0,
            "avg_sentence_words": 0.0,
            "pct_complex_words": 0.0,
            "syllables_per_word": 0.0,
        }
    syllables = sum(_syllables(w) for w in words)
    complex_words = sum(1 for w in words if _syllables(w) >= 3)
    avg_len = len(words) / len(sentences)
    fk = 0.39 * avg_len + 11.8 * (syllables / len(words)) - 15.59
    return {
        "fk_grade": round(fk, 2),
        "words": len(words),
        "sentences": len(sentences),
        "avg_sentence_words": round(avg_len, 2),
        "pct_complex_words": round(100 * complex_words / len(words), 1),
        "syllables_per_word": round(syllables / len(words), 2),
    }


def _normalise(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def evidence_span(quote: str, chapter: str) -> tuple[int, int] | None:
    """Locate a quote in the chapter after normalising case and whitespace."""
    q = _normalise(quote)
    if len(q) < 12:
        return None
    idx = _normalise(chapter).find(q)
    return None if idx < 0 else (idx, idx + len(q))


def coverage(objectives: list[dict], items: list[dict]) -> dict:
    """Which objectives have live items, and how many tiers each one reaches."""
    tiers = ("recall", "apply", "transfer")
    by_objective: dict[str, dict] = {}
    for obj in objectives:
        oid = obj["id"]
        mine = [i for i in items if i.get("objective_id") == oid and i.get("verified")]
        by_objective[oid] = {
            "items": len(mine),
            "tiers": sorted({i["tier"] for i in mine} & set(tiers)),
        }
    covered = [o for o, v in by_objective.items() if v["items"] > 0]
    full = [o for o, v in by_objective.items() if len(v["tiers"]) == len(tiers)]
    return {
        "objective_count": len(objectives),
        "covered": len(covered),
        "fully_laddered": len(full),
        "coverage_pct": round(100 * len(covered) / max(1, len(objectives)), 1),
        "detail": by_objective,
    }


def grounding_rate(items: list[dict]) -> dict:
    """Share of items whose evidence quote really appears in the chapter."""
    total = len(items)
    grounded = sum(1 for i in items if i.get("grounded"))
    return {"total": total, "grounded": grounded, "rate_pct": round(100 * grounded / max(1, total), 1)}


def sm2(quality: int, ease: float = 2.5, interval: int = 0, reps: int = 0) -> dict:
    """SuperMemo-2 scheduling for the next retrieval of one objective."""
    quality = max(0, min(5, int(quality)))
    if quality < 3:
        reps_out, interval_out = 0, 1
    else:
        reps_out = reps + 1
        interval_out = 1 if reps == 0 else 6 if reps == 1 else round(interval * ease)
    ease_out = max(1.3, ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    return {"ease": round(ease_out, 3), "interval_days": int(interval_out), "reps": reps_out}


@dataclass
class Store:
    """Learner state on disk. No names, no email -- an opaque id and skill counts."""

    path: Path
    data: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self.data.setdefault("learners", {})

    def learner(self, learner_id: str) -> dict:
        return self.data["learners"].setdefault(
            learner_id,
            {"mastery": {}, "history": [], "schedule": {}},
        )

    def record(self, learner_id: str, attempts: list[dict]) -> dict:
        rec = self.learner(learner_id)
        for a in attempts:
            oid = a["objective_id"]
            mastery = rec["mastery"].get(oid, 0.0)
            gained = 0.25 if a["correct"] else -0.1
            rec["mastery"][oid] = round(max(0.0, min(1.0, mastery + gained)), 3)
            rec["schedule"][oid] = sm2(
                quality=5 if a["correct"] else 2,
                ease=rec["schedule"].get(oid, {}).get("ease", 2.5),
                interval=rec["schedule"].get(oid, {}).get("interval_days", 0),
                reps=rec["schedule"].get(oid, {}).get("reps", 0),
            )
            rec["history"].append(a)
        self.save()
        return rec

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")


# --- tool wrappers handed to the agents -------------------------------------


@tool
def measure_readability(text: str) -> dict:
    """Measure the reading difficulty of a passage.

    Args:
        text: The passage to measure.

    Returns:
        Flesch-Kincaid grade level and the counts behind it.
    """
    return readability_metrics(text)


@tool
def check_evidence(quote: str, chapter: str) -> dict:
    """Check whether a quoted sentence really appears in the chapter.

    Args:
        quote: The sentence the item claims to be based on.
        chapter: The full source chapter text.

    Returns:
        Whether the quote was found, and its character span when it was.
    """
    span = evidence_span(quote, chapter)
    return {"found": span is not None, "span": span}
