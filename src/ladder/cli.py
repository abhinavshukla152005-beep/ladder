"""Live CLI: the same pipeline against Amazon Bedrock.

    python -m ladder.cli plan   data/chapter_water_cycle.txt
    python -m ladder.cli build  data/chapter_water_cycle.txt
    python -m ladder.cli demo   data/chapter_water_cycle.txt --offline
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import ScriptedModel, bedrock_model
from .scripted import scripted_provider
from .workflow import Ladder, Run

ROOT = Path(__file__).resolve().parents[2]


def _model(offline: bool):
    return ScriptedModel(scripted_provider) if offline else bedrock_model()


def main() -> None:
    ap = argparse.ArgumentParser(prog="ladder")
    ap.add_argument("command", choices=["plan", "build", "demo"])
    ap.add_argument("chapter", nargs="?", default=str(ROOT / "data" / "chapter_water_cycle.txt"))
    ap.add_argument("--offline", action="store_true", help="run with the scripted model, no AWS calls")
    ap.add_argument("--language", default="Hindi")
    args = ap.parse_args()

    chapter = Path(args.chapter).read_text(encoding="utf-8")
    profile = json.loads((ROOT / "data" / "class_profile.json").read_text(encoding="utf-8"))
    run = Run(chapter=chapter, profile=profile)
    ladder = Ladder(_model(args.offline), store_path=ROOT / "demo" / "state.json")

    ladder.plan(run)
    if args.command == "plan":
        print(json.dumps(run.objectives, indent=2, ensure_ascii=False))
        return

    ladder.build(run)
    if args.command == "build":
        print(json.dumps([{k: i[k] for k in ("index", "objective_id", "tier", "prompt", "answer")} for i in run.items],
                         indent=2, ensure_ascii=False))
        print(json.dumps(run.metrics(), indent=2))
        return

    answers = {i["index"]: i["answer"] for i in run.items}
    answers[1] = "The water goes into the air because the towel is hot."
    report = ladder.grade(run, learner_id="L-2481", answers=answers, language=args.language)
    print(json.dumps({"metrics": run.metrics(), "mastery": report["mastery"], "feedback": report["feedback"]},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
