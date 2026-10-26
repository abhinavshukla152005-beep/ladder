from __future__ import annotations

import json
from pathlib import Path

from ladder.models import ScriptedModel
from ladder.scripted import scripted_provider
from ladder.workflow import Ladder, Run

ROOT = Path(__file__).resolve().parents[1]


def build_run(tmp_path) -> tuple[Ladder, Run]:
    chapter = (ROOT / "data" / "chapter_water_cycle.txt").read_text(encoding="utf-8")
    profile = json.loads((ROOT / "data" / "class_profile.json").read_text(encoding="utf-8"))
    ladder = Ladder(ScriptedModel(scripted_provider), store_path=tmp_path / "state.json")
    run = Run(chapter=chapter, profile=profile)
    ladder.plan(run)
    ladder.build(run)
    return ladder, run


def test_pipeline_rejects_ungrounded_item_and_recovers_it(tmp_path):
    _, run = build_run(tmp_path)
    assert len(run.rejected) == 1
    assert run.rejected[0]["objective_id"] == "O3"
    assert "not in the chapter" in run.rejected[0]["reason"]
    recovered = [i for i in run.items if i["objective_id"] == "O3" and i["tier"] == "apply"]
    assert len(recovered) == 1 and recovered[0]["grounded"]


def test_every_kept_item_is_grounded_and_every_objective_is_laddered(tmp_path):
    _, run = build_run(tmp_path)
    assert len(run.items) == 15
    assert all(i["grounded"] and i["verified"] for i in run.items)
    metrics = run.metrics()
    assert metrics["coverage_pct"] == 100.0
    assert metrics["fully_laddered"] == metrics["objectives"] == 5
    assert metrics["grounding_pct"] == 100.0
    assert [i["index"] for i in run.items] == list(range(15))


def test_grading_updates_mastery_and_schedule(tmp_path):
    ladder, run = build_run(tmp_path)
    answers = {i["index"]: i["answer"] for i in run.items}
    answers[1] = ""
    report = ladder.grade(run, learner_id="L-1", answers=answers, language="Hindi")
    assert report["results"][1]["correct"] is False
    assert report["results"][0]["correct"] is True
    assert report["mastery"]["O1"] < 1.0
    assert report["schedule"]["O1"]["interval_days"] >= 1
    assert "वाष्पीकरण" in report["feedback"]


def test_adapt_measures_against_target_grade(tmp_path):
    ladder, _ = build_run(tmp_path)
    first_para = (ROOT / "data" / "chapter_water_cycle.txt").read_text(encoding="utf-8").split("\n\n")[0]
    fitted = ladder.adapt(first_para, target_grade=3)
    assert fitted["metrics"]["fk_grade"] < 5.0
    assert fitted["attempts"]
