"""The pipeline: plan -> write -> verify -> practice -> coach -> adapt.

Orchestration lives in Python on purpose. A teacher marking 60 notebooks needs
the same output for the same chapter every time, and a rejected item has to be
rejected by a deterministic check, not by the model's own opinion.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from . import agents
from .models import json_block
from .tools import Store, coverage, evidence_span, grounding_rate, readability_metrics, sm2

TIERS = ("recall", "apply", "transfer")


@dataclass
class Stage:
    name: str
    seconds: float
    detail: str = ""


@dataclass
class Run:
    chapter: str
    profile: dict
    objectives: list[dict] = field(default_factory=list)
    items: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    stages: list[Stage] = field(default_factory=list)

    def metrics(self) -> dict:
        cov = coverage(self.objectives, self.items)
        ground = grounding_rate(self.items)
        within = sum(
            1
            for i in self.items
            if i["readability"]["fk_grade"] <= self.profile["target_grade"] + 2
        )
        return {
            "objectives": cov["objective_count"],
            "items_kept": len(self.items),
            "items_rejected": len(self.rejected),
            "coverage_pct": cov["coverage_pct"],
            "fully_laddered": cov["fully_laddered"],
            "grounding_pct": ground["rate_pct"],
            "reading_level_fit_pct": round(100 * within / max(1, len(self.items)), 1),
            "target_grade": self.profile["target_grade"],
        }


class Ladder:
    def __init__(self, model, store_path: str | Path | None = None, max_rounds: int = 2) -> None:
        self.model = model
        self.store = Store(store_path or Path("ladder_state.json"))
        self.max_rounds = max_rounds
        self._planner = agents.planner(model)
        self._writer = agents.writer(model)
        self._verifier = agents.verifier(model)
        self._coach = agents.coach(model)
        self._adapter = agents.adapter(model)

    # --- stage 1 -----------------------------------------------------------
    def plan(self, run: Run) -> list[dict]:
        t0 = time.perf_counter()
        reply = str(
            self._planner(
                f"Class profile: {run.profile['grade_name']}, target reading grade "
                f"{run.profile['target_grade']}.\n\nCHAPTER:\n{run.chapter}"
            )
        )
        objectives = json_block(reply)["objectives"]
        for obj in objectives:
            quotes = obj.get("evidence") or []
            obj["evidence"] = [q for q in quotes if evidence_span(q, run.chapter)]
            obj["grounded"] = bool(obj["evidence"])
            obj["mastery"] = 0.0
        run.objectives = objectives
        run.stages.append(
            Stage("plan", time.perf_counter() - t0, f"{len(objectives)} objectives")
        )
        return objectives

    # --- stage 2 -----------------------------------------------------------
    def build(self, run: Run) -> list[dict]:
        t0 = time.perf_counter()
        brief = {
            "class_profile": run.profile,
            "objectives": [{"id": o["id"], "statement": o["statement"]} for o in run.objectives],
            "chapter": run.chapter,
        }
        reply = str(
            self._writer(
                "Write one item per tier for each objective.\n"
                f"INPUT:\n{_dumps(brief)}"
            )
        )
        items = self._normalise(json_block(reply)["items"])
        run.stages.append(Stage("write", time.perf_counter() - t0, f"{len(items)} drafts"))

        kept, rejected = self._verify(run, items)
        all_rejected = list(rejected)
        round_no = 1
        while rejected and round_no < self.max_rounds:
            round_no += 1
            t1 = time.perf_counter()
            fix_brief = {
                "rejections": [
                    {"objective_id": r["objective_id"], "tier": r["tier"], "reason": r["reason"]}
                    for r in rejected
                ],
                "objectives": [
                    {"id": o["id"], "statement": o["statement"]}
                    for o in run.objectives
                    if o["id"] in {r["objective_id"] for r in rejected}
                ],
                "chapter": run.chapter,
                "class_profile": run.profile,
            }
            reply = str(
                self._writer(
                    "Rewrite only the rejected slots. Obey the rejection reasons.\n"
                    f"INPUT:\n{_dumps(fix_brief)}"
                )
            )
            retry_items = self._normalise(json_block(reply)["items"])
            again_kept, again_rejected = self._verify(run, retry_items)
            kept.extend(again_kept)
            all_rejected.extend(again_rejected)
            rejected = again_rejected
            run.stages.append(
                Stage(f"rewrite-{round_no - 1}", time.perf_counter() - t1, f"{len(again_kept)} recovered")
            )

        for n, item in enumerate(kept):
            item["index"] = n
        run.items = kept
        run.rejected = all_rejected
        return kept

    def _normalise(self, raw: list[dict]) -> list[dict]:
        out = []
        for idx, item in enumerate(raw):
            item = dict(item)
            item.setdefault("objective_id", "O1")
            item.setdefault("tier", "recall")
            item["index"] = idx
            item["readability"] = readability_metrics(item.get("prompt", ""))
            out.append(item)
        return out

    def _verify(self, run: Run, items: list[dict]) -> tuple[list[dict], list[dict]]:
        t0 = time.perf_counter()
        spans = {i["index"]: evidence_span(i.get("evidence", ""), run.chapter) for i in items}
        payload = {
            "chapter": run.chapter,
            "items": [
                {
                    "index": i["index"],
                    "objective_id": i["objective_id"],
                    "tier": i["tier"],
                    "prompt": i["prompt"],
                    "answer": i.get("answer", ""),
                    "evidence": i.get("evidence", ""),
                    "quote_found_in_chapter": spans[i["index"]] is not None,
                }
                for i in items
            ],
        }
        reply = str(self._verifier(f"Gate this batch.\nINPUT:\n{_dumps(payload)}"))
        verdicts = {v["index"]: v for v in json_block(reply)["verdicts"]}

        kept, rejected = [], []
        for item in items:
            verdict = verdicts.get(item["index"], {"keep": False, "reason": "no verdict returned"})
            item["grounded"] = spans[item["index"]] is not None
            item["verified"] = bool(verdict.get("keep")) and item["grounded"]
            item["verdict_reason"] = verdict.get("reason", "")
            if item["verified"]:
                kept.append(item)
            else:
                reason = item["verdict_reason"] or "quoted sentence is not in the chapter"
                if not item["grounded"]:
                    reason = "quoted sentence is not in the chapter"
                rejected.append({**item, "reason": reason})

        run.stages.append(
            Stage("verify", time.perf_counter() - t0, f"{len(kept)} kept / {len(rejected)} rejected")
        )
        return kept, rejected

    # --- stage 3 -----------------------------------------------------------
    def grade(self, run: Run, learner_id: str, answers: dict[int, str], language: str = "English") -> dict:
        t0 = time.perf_counter()
        rec = self.store.learner(learner_id)
        payload = {
            "language": language,
            "mastery": rec["mastery"],
            "items": [
                {
                    "index": i["index"],
                    "objective_id": i["objective_id"],
                    "prompt": i["prompt"],
                    "answer": i.get("answer", ""),
                    "learner_answer": answers.get(i["index"], ""),
                    "misconception_probe": i.get("misconception", ""),
                }
                for i in run.items
            ],
        }
        result = json_block(str(self._coach(f"Grade and coach.\nINPUT:\n{_dumps(payload)}")))
        verdicts = {r["index"]: r for r in result["results"]}
        attempts = [
            {
                "objective_id": i["objective_id"],
                "correct": bool(verdicts.get(i["index"], {}).get("correct")),
                "misconception": verdicts.get(i["index"], {}).get("misconception"),
            }
            for i in run.items
        ]
        rec = self.store.record(learner_id, attempts)
        run.stages.append(
            Stage("coach", time.perf_counter() - t0, f"{sum(a['correct'] for a in attempts)}/{len(attempts)} correct")
        )
        return {
            "results": attempts,
            "mastery": rec["mastery"],
            "schedule": rec["schedule"],
            "diagnosis": result.get("diagnosis", ""),
            "feedback": result.get("feedback", ""),
            "next_action": result.get("next_action", ""),
            "language": result.get("language", language),
        }

    # --- stage 4 -----------------------------------------------------------
    def adapt(self, passage: str, target_grade: int, attempts: int = 3) -> dict:
        t0 = time.perf_counter()
        best = None
        history = []
        prompt = (
            f"Rewrite for grade {target_grade}. Measure with the readability tool.\n\nPASSAGE:\n{passage}"
        )
        for _ in range(attempts):
            reply = str(self._adapter(prompt)).strip()
            measured = readability_metrics(reply)
            history.append(measured["fk_grade"])
            if best is None or abs(measured["fk_grade"] - target_grade) < abs(best[1]["fk_grade"] - target_grade):
                best = (reply, measured)
            if abs(measured["fk_grade"] - target_grade) <= 1.0:
                break
            prompt = (
                f"Too hard or too easy: that version measured grade {measured['fk_grade']}. "
                f"Rewrite the same passage for exactly grade {target_grade}.\n\nPASSAGE:\n{passage}"
            )
        self.store.save()
        run_stage = Stage("adapt", time.perf_counter() - t0, f"fk {best[1]['fk_grade']} vs target {target_grade}")
        return {"text": best[0], "metrics": best[1], "target_grade": target_grade, "attempts": history, "stage": run_stage}

    def next_objectives(self, run: Run, learner_id: str) -> list[dict]:
        """Objectives due for retrieval first, then the ones with the least mastery."""
        rec = self.store.learner(learner_id)
        ranked = sorted(
            run.objectives,
            key=lambda o: (
                rec["schedule"].get(o["id"], {}).get("interval_days", 0),
                rec["mastery"].get(o["id"], 0.0),
            ),
        )
        return ranked


def _dumps(obj) -> str:
    import json

    return json.dumps(obj, indent=2, ensure_ascii=False)
