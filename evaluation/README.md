# Evaluation — Release Gate

Evaluation is a **product artifact**, not test scaffolding — hence its top-level
placement. `just eval` runs the suites and fails the build on regression.

## Structure

| Path | Contents |
|---|---|
| `benchmark/golden/` | Curated, expert-graded questions (pointers + metadata; no restricted content committed) |
| `benchmark/holdout/` | Blind set — access-controlled, git-ignored, never in prompts or tuning |
| `benchmark/annotations/` | Expected-evidence IDs per question |
| `graders/` | LLM-as-judge, calibrated against human labels so ongoing eval stays affordable |
| `suites/retrieval_recall/` | Did we retrieve the expected evidence? |
| `suites/grounding_and_citation/` | Are claims supported, cited, correctly classed, conflicts disclosed? |
| `suites/abstention_precision_recall/` | Do we abstain when we should, and only then? |
| `suites/access_isolation/` | Does restricted content ever surface or get inferred? |
| `reports/` | Regression outputs, published by CI (git-ignored) |

## Critical path

The golden + holdout sets gate everything downstream and require scarce domain-expert
time. Budget expert hours explicitly; treat this as the release long pole.

## Affordability

Expert-graded metrics do not scale to every CI run. Graders in `graders/` are LLM-as-judge
calibrated against a human-labeled subset; recalibrate when the grader model or prompt
changes (tracked as a processing version in provenance).
