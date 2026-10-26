"""Repeatable end-to-end run used for the demo video.

    python -m ladder.demo

Uses the scripted model, so it needs no AWS account and always produces the
same numbers. The pipeline, agents, tools and gates are the production ones.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .models import ScriptedModel
from .scripted import scripted_provider
from .tools import readability_metrics
from .workflow import Ladder, Run

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "demo" / "state.json"


def rule(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m")
    print("─" * 74)


def main() -> None:
    chapter = (ROOT / "data" / "chapter_water_cycle.txt").read_text(encoding="utf-8")
    profile = json.loads((ROOT / "data" / "class_profile.json").read_text(encoding="utf-8"))
    if STATE.exists():
        STATE.unlink()

    print("\033[1mLADDER\033[0m — evidence-bound practice sets for mixed-ability classrooms")
    rule("0. Input")
    src = readability_metrics(chapter)
    print(f"chapter      : water cycle, {src['words']} words, Flesch-Kincaid grade {src['fk_grade']}")
    print(f"class        : {profile['grade_name']}")
    print(f"reading range: grade {profile['reading_range'][0]}–{profile['reading_range'][1]}"
          f"   target {profile['target_grade']}   feedback language {profile['language']}")

    ladder = Ladder(ScriptedModel(scripted_provider), store_path=STATE)
    run = Run(chapter=chapter, profile=profile)

    rule("1. Plan — extract objectives, each tied to a verbatim sentence")
    for obj in ladder.plan(run):
        flag = "grounded" if obj["grounded"] else "NO QUOTE"
        print(f"  {obj['id']}  {obj['statement']}")
        print(f"      \033[2m[{flag}] {obj['evidence'][0][:84]}…\033[0m")

    rule("2. Write — one item per tier (recall / apply / transfer)")
    ladder.build(run)
    drafts = len(run.items) + len(run.rejected)
    print(f"  {drafts} drafts · {len(run.rejected)} rejected by the gate · "
          f"{len(run.rejected)} rewritten · {len(run.items)} in the final set")
    print(f"  (the writer never sees the teacher's answer key — only the chapter)")

    rule("3. Verify — deterministic quote gate before a teacher ever sees the item")
    for r in run.rejected:
        print(f"  \033[31mREJECTED\033[0m {r['objective_id']} {r['tier']}")
        print(f"    item    : {r['prompt']}")
        print(f"    quote   : \"{r['evidence']}\"")
        print(f"    reason  : {r['reason']}")
    print("  the writer was asked again with the rejection reason, and the slot is now:")
    fixed = [i for i in run.items if i["objective_id"] == "O3" and i["tier"] == "apply"][0]
    print(f"    \033[32mKEPT\033[0m    {fixed['prompt']}")
    print(f"    quote   : \"{fixed['evidence'][:70]}…\" → found verbatim in the chapter")

    rule("4. Practice — learner answers 15 items on one shared phone")
    answers = {
        i["index"]: i["answer"] for i in run.items
    }
    answers[1] = "The water goes into the air because the towel is hot."          # apply, O1: partial
    answers[4] = "Water from inside the bottle comes out through the glass."      # apply, O2: wrong
    answers[13] = "Rain adds new water to Earth every year."                      # apply, O5: wrong
    print(f"  submitted {len(answers)} answers · 3 of them carry a misconception")

    rule("5. Coach — grade, name the misconception, one next action")
    report = ladder.grade(run, learner_id="L-2481", answers=answers, language=profile["language"])
    correct = sum(1 for a in report["results"] if a["correct"])
    print(f"  score: {correct}/{len(report['results'])}")
    for a in report["results"]:
        if not a["correct"]:
            print(f"  ✗ {a['objective_id']}  misconception: {a['misconception']}")
    print(f"\n  diagnosis   : {report['diagnosis']}")
    print(f"  feedback    : {report['feedback']}")
    print(f"  next action : {report['next_action']}")

    rule("6. Mastery and next-due schedule (computed, not guessed)")
    for obj in run.objectives:
        m = report["mastery"].get(obj["id"], 0.0)
        s = report["schedule"].get(obj["id"], {})
        bar = "█" * round(m * 10) + "·" * (10 - round(m * 10))
        print(f"  {obj['id']} {bar} {m:.2f}   revisit in {s.get('interval_days', 0)}d  ease {s.get('ease', 2.5)}")

    rule("7. Adapt — one paragraph rewritten to the weakest readers' level")
    first_para = chapter.split("\n\n")[0]
    fitted = ladder.adapt(first_para, target_grade=3)
    print(f"  original : grade {readability_metrics(first_para)['fk_grade']}")
    print(f"  adapted  : grade {fitted['metrics']['fk_grade']}  (target {fitted['target_grade']}, "
          f"{len(fitted['attempts'])} attempts)")
    print(f"  text     : {fitted['text']}")

    rule("8. Run report")
    metrics = run.metrics()
    print(f"  objectives covered        {metrics['coverage_pct']}%  "
          f"({metrics['fully_laddered']}/{metrics['objectives']} with all three tiers)")
    print(f"  items grounded in source  {metrics['grounding_pct']}%")
    print(f"  items at class reading    {metrics['reading_level_fit_pct']}%  (target grade {metrics['target_grade']})")
    print(f"  items kept / rejected     {metrics['items_kept']} / {metrics['items_rejected']}")
    print("\n  stages:", " · ".join(f"{s.name} {s.seconds * 1000:.0f}ms" for s in run.stages))
    print("\n  state:", STATE.relative_to(ROOT))


if __name__ == "__main__":
    main()
