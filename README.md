# Ladder

**Evidence-bound practice sets for mixed-ability classrooms.**

Built with the [Strands Agents SDK](https://strandsagents.com) on Amazon Bedrock for the
AWS Builder Center hackathon *Strands SDK: Workshop to Ship* (October 2026), Education focus area.

[72-second demo](https://youtu.be/aoFbngpUhP8) · [Project write-up](https://builder.aws.com/content/3LIzyXgNwd06SXd5hM85uHcqxrY/one-chapter-fifteen-verified-practice-items-one-phone)

---

## The problem

A teacher with 48 learners and one phone per group cannot write four versions of the same
practice set, grade them, and work out who misunderstood what. Textbooks are written for one
reading level — usually the middle — so the strongest learners are bored and the weakest are
locked out. AI can generate practice questions in seconds, but in a classroom an item that
"looks right" is worse than no item at all: if the question is unsupported by the chapter, the
teacher has to catch the error in front of the class, and a learner who is already behind
learns something false.

Ladder is built around that constraint: **no practice item reaches a learner until a
deterministic check proves it is supported by a sentence that actually exists in the chapter.**

## What it does

Given a chapter and a class profile, Ladder:

1. **Plans** — extracts 4–6 learning objectives, each tied to a verbatim sentence of the chapter.
2. **Writes** — one item per tier for every objective: recall, apply, transfer.
3. **Verifies** — rejects any item whose quoted evidence is not found in the chapter verbatim,
   or that the reviewer agent flags as unsupported, ambiguous or answer-leaking. Rejected slots
   go back to the writer once with the rejection reason.
4. **Coaches** — grades a class's responses, names the misconception behind each wrong answer,
   and writes feedback in the learner's language.
5. **Schedules** — updates a mastery estimate and an SM-2 retrieval schedule per objective.
6. **Adapts** — rewrites a paragraph for the weakest readers and *measures* the result until it
   is within one grade level of the target.

Every number a teacher sees (coverage, grounding rate, reading grade, mastery, next-due date)
is computed in plain Python. The models write content; they never grade their own arithmetic.

## Architecture

```
                    ┌──────────────┐
 chapter + profile ─►  planners    │  5 objectives, each with a verbatim quote
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │  writer      │  15 items: recall / apply / transfer
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐      deterministic quote search
                    │  verifier    │ ◄─── (evidence_span) + model review
                    └──────┬───────┘
              rejected ────┴───► writer (once, with the rejection reason)
                           ▼ kept
                    ┌──────────────┐
 learner answers ──►│  coach       │  grade · misconception · feedback (Hindi/English)
                    └──────┬───────┘
                           ▼
              mastery + SM-2 schedule  ──► next session's objective order

                    ┌──────────────┐
 long paragraph ───►│  adapter     │  rewrite → measure Flesch-Kincaid → retry ≤3×
                    └──────────────┘
```

Six specialised agents, orchestrated by a small deterministic supervisor in `workflow.py`.
Orchestration lives in code because a teacher marking 60 notebooks needs the same output for
the same chapter twice, and a rejected item must be rejected by a check, not by an opinion.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

python -m ladder.demo                    # full pipeline, scripted model, no AWS account needed
pytest -q                                # 8 tests

# live, against Amazon Bedrock
export AWS_REGION=us-east-1
export LADDER_MODEL_ID=us.amazon.nova-lite-v1:0
python -m ladder.cli plan  data/chapter_water_cycle.txt
python -m ladder.cli build data/chapter_water_cycle.txt
```

A real run on `data/chapter_water_cycle.txt` (grade 7.3 chapter, grade 6 class):

| Metric | Value |
|---|---|
| Objectives grounded in a verbatim quote | 5 / 5 |
| Drafts written | 16 |
| Drafts rejected by the evidence gate | 1 |
| Items in the final set | 15 |
| Objective coverage | 100% (5/5 with all three tiers) |
| Items whose quote appears in the chapter | 100% |
| Items at or below class reading level +2 | 86.7% |
| Adapted paragraph | grade 7.6 → grade 4.6 (target 3, measured) |

The rejected draft in that run asks why rain in India falls in July and August — a true fact
that is **not in this chapter**. The gate drops it, the writer is re-asked with the reason, and
the replacement quotes a sentence that does exist. That single case is the whole point.

## Layout

```
data/            sample chapter (original text) and class profile
src/ladder/
  tools.py       readability, evidence search, coverage, SM-2, learner store
  agents.py      the six agent definitions and their contracts
  workflow.py    the pipeline, the gate, the rewrite loop, the run report
  models.py      Bedrock wiring + a scripted model for offline runs and tests
  scripted.py    fixed model replies used by the demo and the tests
  cli.py         live CLI
  demo.py        repeatable end-to-end run
tests/           deterministic tests over the real pipeline
```

## Privacy

No names, no email, no school. The learner store holds an opaque id, per-objective mastery
counts and retrieval dates in a local JSON file. Nothing leaves the machine except the model
calls, and the chapter is the only document sent.

## License

MIT — see [LICENSE](LICENSE).
