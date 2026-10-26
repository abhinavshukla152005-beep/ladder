"""Amazon Bedrock AgentCore Runtime entrypoint.

Deployed with the AgentCore CLI (`agentcore configure` / `agentcore deploy`).
The container is stateless: the chapter, the class profile and the learner's
answers all arrive in the request payload, and the response carries the
practice set plus the run metrics.

    {"chapter": "...", "profile": {...}, "answers": {"0": "...", ...},
     "language": "Hindi", "mode": "build" | "grade"}
"""

from __future__ import annotations

import json

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from .models import bedrock_model
from .workflow import Ladder, Run

app = BedrockAgentCoreApp()

DEFAULT_PROFILE = {
    "grade_name": "Grade 6 science",
    "target_grade": 6,
    "reading_range": [3, 8],
    "language": "Hindi",
}


@app.entrypoint
def invoke(payload: dict) -> dict:
    chapter = payload.get("chapter", "")
    if not chapter.strip():
        return {"error": "payload.chapter is required"}
    profile = {**DEFAULT_PROFILE, **(payload.get("profile") or {})}

    run = Run(chapter=chapter, profile=profile)
    ladder = Ladder(bedrock_model(), store_path="/tmp/ladder_state.json")
    ladder.plan(run)
    ladder.build(run)

    response: dict = {
        "objectives": [
            {"id": o["id"], "statement": o["statement"], "evidence": o["evidence"]} for o in run.objectives
        ],
        "items": [
            {
                "objective_id": i["objective_id"],
                "tier": i["tier"],
                "prompt": i["prompt"],
                "answer": i["answer"],
                "evidence": i["evidence"],
                "readability_grade": i["readability"]["fk_grade"],
            }
            for i in run.items
        ],
        "rejected": [
            {"objective_id": r["objective_id"], "tier": r["tier"], "reason": r["reason"]} for r in run.rejected
        ],
        "metrics": run.metrics(),
    }

    if payload.get("answers"):
        answers = {int(k): v for k, v in payload["answers"].items()}
        report = ladder.grade(run, learner_id=payload.get("learner_id", "anonymous"),
                             answers=answers, language=payload.get("language", profile["language"]))
        response["coaching"] = {
            "results": report["results"],
            "diagnosis": report["diagnosis"],
            "feedback": report["feedback"],
            "next_action": report["next_action"],
            "mastery": report["mastery"],
            "schedule": report["schedule"],
        }

    return json.loads(json.dumps(response, ensure_ascii=False))


if __name__ == "__main__":
    app.run()
