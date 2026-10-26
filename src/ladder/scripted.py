"""A scripted model so the full pipeline can run with no AWS account and no network.

It is not a stub around the pipeline: every agent, tool, verification gate and
metric runs exactly as it does against Bedrock. Only the text generation is
fixed, which makes the demo repeatable and the tests deterministic.
"""

from __future__ import annotations

import json
import re

ROLE = re.compile(r"ROLE=([A-Z]+)")

PLAN = {
    "objectives": [
        {
            "id": "O1",
            "statement": "Explain evaporation as the Sun-driven change of liquid water into water vapour.",
            "evidence": [
                "The Sun heats the surface of oceans, rivers and lakes, and this heat turns liquid water into an invisible gas called water vapour."
            ],
        },
        {
            "id": "O2",
            "statement": "Distinguish condensation from evaporation and explain how clouds form.",
            "evidence": [
                "Cool air cannot hold as much water vapour as warm air, so some of the vapour changes back into tiny droplets."
            ],
        },
        {
            "id": "O3",
            "statement": "Describe precipitation and the three paths water takes after it reaches the ground.",
            "evidence": [
                "Rain that reaches the ground can do three things: it can run over the surface into streams and rivers, it can soak into the soil, or it can be taken up again by plants."
            ],
        },
        {
            "id": "O4",
            "statement": "Explain what groundwater is and why wells matter in rural areas.",
            "evidence": [
                "It fills the small spaces between grains of soil and rock, and it moves slowly downhill."
            ],
        },
        {
            "id": "O5",
            "statement": "Explain how drought and flood relate to a closed water cycle.",
            "evidence": [
                "A drought happens when a region gets much less rain than usual for a long time, so rivers shrink and groundwater is not refilled."
            ],
        },
    ]
}

ITEMS = {
    "items": [
        {
            "objective_id": "O1",
            "tier": "recall",
            "prompt": "Which process turns liquid water into an invisible gas, and what is that gas called?",
            "answer": "Evaporation turns liquid water into water vapour.",
            "evidence": "The Sun heats the surface of oceans, rivers and lakes, and this heat turns liquid water into an invisible gas called water vapour.",
            "misconception": "naming the gas as oxygen or steam",
        },
        {
            "objective_id": "O1",
            "tier": "apply",
            "prompt": "A wet towel dries faster on a sunny roof than in a shaded room. Use the chapter to explain why.",
            "answer": "The Sun heats the water, so evaporation turns it into water vapour faster.",
            "evidence": "This slow change from liquid to gas is called evaporation.",
            "misconception": "saying the water disappears instead of changing into vapour",
        },
        {
            "objective_id": "O1",
            "tier": "transfer",
            "prompt": "A farmer spreads wet grain in the sun. Predict what happens to the water in the grain and name the process.",
            "answer": "The water evaporates and joins the air as water vapour.",
            "evidence": "Plants also add water vapour to the air through their leaves in a process called transpiration.",
            "misconception": "thinking the grain creates new water",
        },
        {
            "objective_id": "O2",
            "tier": "recall",
            "prompt": "What is the change from a gas to a liquid called?",
            "answer": "Condensation.",
            "evidence": "This change from gas to liquid is called condensation.",
            "misconception": "swapping the names condensation and evaporation",
        },
        {
            "objective_id": "O2",
            "tier": "apply",
            "prompt": "A cold bottle of water gets drops on the outside on a warm day. Explain the drops with the chapter's idea about cool air.",
            "answer": "The bottle cools the air near it, so vapour in that air changes back into tiny droplets.",
            "evidence": "Cool air cannot hold as much water vapour as warm air, so some of the vapour changes back into tiny droplets.",
            "misconception": "believing the water leaks through the bottle",
        },
        {
            "objective_id": "O2",
            "tier": "transfer",
            "prompt": "Use the chapter to explain why clouds are common over cities and oceans.",
            "answer": "Dust and sea salt give the tiny droplets a surface to form on.",
            "evidence": "Dust and sea salt give the droplets a surface to form on, which is why clouds are common over cities and oceans.",
            "misconception": "saying clouds form because the sky is cold everywhere",
        },
        {
            "objective_id": "O3",
            "tier": "recall",
            "prompt": "What is any water that falls from clouds called?",
            "answer": "Precipitation.",
            "evidence": "Any water that falls from clouds is called precipitation.",
            "misconception": "calling all precipitation rain",
        },
        {
            "objective_id": "O3",
            "tier": "apply",
            "prompt": "Why does most of the rain in India fall in July and August?",
            "answer": "Because the monsoon winds bring moist air in from the sea.",
            "evidence": "Most rain in India falls in the months of July and August.",
            "misconception": "thinking all rain water flows to the sea",
        },
        {
            "objective_id": "O3",
            "tier": "transfer",
            "prompt": "A village gets very heavy rain in one afternoon and the ground is hard and dry. Which path will carry the most water, and why?",
            "answer": "Runoff, because too much rain arrives too quickly for soil and rivers to carry it away.",
            "evidence": "Floods happen when too much rain arrives too quickly for rivers and soil to carry it away.",
            "misconception": "assuming dry soil soaks up all the water",
        },
        {
            "objective_id": "O4",
            "tier": "recall",
            "prompt": "What is water called when it soaks into the ground and fills the spaces between soil and rock?",
            "answer": "Groundwater.",
            "evidence": "Water that soaks into the ground is called groundwater.",
            "misconception": "confusing groundwater with runoff",
        },
        {
            "objective_id": "O4",
            "tier": "apply",
            "prompt": "A well still has water months after the last rain. Use the chapter to explain why.",
            "answer": "Groundwater sits in the spaces between soil and rock and moves only slowly downhill.",
            "evidence": "It fills the small spaces between grains of soil and rock, and it moves slowly downhill.",
            "misconception": "thinking the well creates water",
        },
        {
            "objective_id": "O4",
            "tier": "transfer",
            "prompt": "Why is groundwater the only drinking water for many villages all year?",
            "answer": "Because wells reach groundwater, and it is there even when rain is not.",
            "evidence": "People dig wells to reach groundwater, and in many villages it is the only source of drinking water all year.",
            "misconception": "thinking rivers supply those villages all year",
        },
        {
            "objective_id": "O5",
            "tier": "recall",
            "prompt": "During a long drought, what happens to rivers and to groundwater?",
            "answer": "Rivers shrink and groundwater is not refilled.",
            "evidence": "A drought happens when a region gets much less rain than usual for a long time, so rivers shrink and groundwater is not refilled.",
            "misconception": "thinking groundwater grows during a drought",
        },
        {
            "objective_id": "O5",
            "tier": "apply",
            "prompt": "The chapter says the water cycle is a closed loop. What does that mean for the total water on Earth?",
            "answer": "The total stays almost the same; only where the water is changes.",
            "evidence": "Because the total amount of water on Earth stays almost the same, the cycle is a closed loop, but where the water is at any moment can change.",
            "misconception": "believing rain adds new water to Earth",
        },
        {
            "objective_id": "O5",
            "tier": "transfer",
            "prompt": "How does covering soil with concrete change what happens to rain water?",
            "answer": "Less water soaks in and more runs off the surface.",
            "evidence": "Cities cover soil with concrete, so less water soaks in and more runs off.",
            "misconception": "thinking concrete absorbs the water",
        },
    ]
}

REWRITE = {
    "items": [
        {
            "objective_id": "O3",
            "tier": "apply",
            "prompt": "After rain reaches the ground, name the three paths the water can take.",
            "answer": "It runs over the surface, it soaks into the soil, or plants take it up.",
            "evidence": "Rain that reaches the ground can do three things: it can run over the surface into streams and rivers, it can soak into the soil, or it can be taken up again by plants.",
            "misconception": "thinking all rain water flows to the sea",
        }
    ]
}

ADAPTED = (
    "The Sun makes water in the sea, in rivers and in lakes warm. "
    "The warm water turns into a gas. The gas is called water vapour. "
    "We call this evaporation. "
    "Plants also send water vapour into the air. We call this transpiration."
)

HINDI_FEEDBACK = (
    "आपने लगभग आधे सवाल ठीक किए। ध्यान दें: पानी बनता नहीं, वह रूप बदलता है। "
    "सूरज की गर्मी से पानी भाप बनकर उड़ जाता है, इसी को वाष्पीकरण कहते हैं।"
)


def _input_json(text: str) -> dict | None:
    i = text.find("INPUT:")
    if i < 0:
        return None
    raw = text[i + len("INPUT:") :].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 2}


def _grade_attempt(item: dict) -> bool:
    answer = _words(item.get("answer", ""))
    given = _words(item.get("learner_answer", ""))
    if not given:
        return False
    return len(answer & given) / max(1, len(answer)) >= 0.4


def scripted_provider(messages: list[dict], system_prompt: str) -> str:
    role = (ROLE.search(system_prompt) or [None, ""])[1]
    content = messages[-1].get("content", "") if messages else ""
    if isinstance(content, list):
        user = " ".join(str(c.get("text", "")) for c in content if isinstance(c, dict))
    else:
        user = str(content)

    if role == "PLANNER":
        return json.dumps(PLAN, ensure_ascii=False)
    if role == "WRITER":
        payload = _input_json(user) or {}
        return json.dumps(REWRITE if "rejections" in payload else ITEMS, ensure_ascii=False)
    if role == "VERIFIER":
        payload = _input_json(user) or {}
        verdicts = []
        for item in payload.get("items", []):
            found = bool(item.get("quote_found_in_chapter"))
            verdicts.append(
                {
                    "index": item["index"],
                    "keep": found,
                    "reason": ""
                    if found
                    else "the quoted sentence does not appear in the chapter, so the item is unsupported",
                }
            )
        return json.dumps({"verdicts": verdicts}, ensure_ascii=False)
    if role == "COACH":
        payload = _input_json(user) or {}
        items = payload.get("items", [])
        results = [
            {
                "index": i["index"],
                "correct": _grade_attempt(i),
                "misconception": None if _grade_attempt(i) else i.get("misconception_probe", "unclear"),
            }
            for i in items
        ]
        wrong = [i for i, r in zip(items, results) if not r["correct"]]
        lang = payload.get("language", "English")
        diagnosis = (
            "Retrieval is uneven: the missed items are all one step above recall, "
            "so the ideas are recognised but not yet usable."
            if wrong
            else "All items correct; move to the transfer tier for the weakest objective."
        )
        feedback = HINDI_FEEDBACK if lang.lower().startswith("hin") else (
            "You answered most of the set. Where it went wrong, the idea was recognised "
            "but not yet applied: read the evidence sentence again and say it in your own words."
        )
        return json.dumps(
            {
                "results": results,
                "diagnosis": diagnosis,
                "feedback": feedback,
                "next_action": "Practise the missed apply-tier item again tomorrow, then take the transfer item.",
                "language": lang,
            },
            ensure_ascii=False,
        )
    if role == "ADAPTER":
        return ADAPTED
    return "{}"
