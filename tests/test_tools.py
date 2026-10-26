from __future__ import annotations

from ladder.tools import coverage, evidence_span, readability_metrics, sm2

CHAPTER = (
    "The Sun heats the surface of oceans, rivers and lakes, and this heat turns "
    "liquid water into an invisible gas called water vapour."
)


def test_readability_orders_hard_and_easy_text():
    easy = "The sun is hot. The pot is hot. The water gets hot."
    hard = (
        "Notwithstanding the thermodynamic implications of insolation, "
        "evapotranspirational processes precipitate consequential hydrological redistribution."
    )
    assert readability_metrics(easy)["fk_grade"] < readability_metrics(hard)["fk_grade"]
    assert readability_metrics("")["words"] == 0


def test_evidence_span_ignores_case_and_whitespace():
    quote = "the SUN heats the surface of oceans,\n rivers and lakes"
    assert evidence_span(quote, CHAPTER) is not None
    assert evidence_span("Most rain in India falls in July and August.", CHAPTER) is None
    assert evidence_span("too short", CHAPTER) is None


def test_coverage_counts_only_verified_items():
    objectives = [{"id": "O1"}, {"id": "O2"}]
    items = [
        {"objective_id": "O1", "tier": "recall", "verified": True},
        {"objective_id": "O1", "tier": "apply", "verified": True},
        {"objective_id": "O1", "tier": "transfer", "verified": False},
        {"objective_id": "O2", "tier": "recall", "verified": False},
    ]
    result = coverage(objectives, items)
    assert result["covered"] == 1
    assert result["coverage_pct"] == 50.0
    assert result["detail"]["O1"]["tiers"] == ["apply", "recall"]


def test_sm2_resets_on_failure_and_grows_on_success():
    first = sm2(quality=5)
    assert first == {"ease": 2.6, "interval_days": 1, "reps": 1}
    second = sm2(quality=5, ease=first["ease"], interval=first["interval_days"], reps=first["reps"])
    assert second["interval_days"] == 6
    lapsed = sm2(quality=1, ease=second["ease"], interval=second["interval_days"], reps=second["reps"])
    assert lapsed["reps"] == 0 and lapsed["interval_days"] == 1 and lapsed["ease"] >= 1.3
