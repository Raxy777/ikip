# Conflict Disclosure & Authority Ranking (UNDESIGNED HARD PART)

**Status:** Policy stated; composition logic not yet designed.

## Problem

The plan says answers should "prefer the approved, applicable source but disclose
material conflicts." This is one of the hardest generation behaviors to make an LLM do
reliably, and it is currently a policy statement rather than a design in both the plan and
the diagrams.

## What "authority ranking" must decide

When two authorized sources disagree, rank by:

1. **Authority state** — `approved` > `draft`; `superseded`/`withdrawn` excluded from
   current guidance (they may still be shown as history, clearly labeled).
2. **Applicability** — source scoped to the specific asset/site/equipment family
   outranks a general one.
3. **Recency of revision** — newer approved revision outranks older.

## What "conflict disclosure" must guarantee

- A material conflict is **surfaced, not silently resolved**. The answer states that
  sources disagree and cites both, with authority indicators.
- The system does not fabricate a reconciliation the evidence does not support. If it
  cannot ground a single answer, it abstains with reason `conflicting`.

## Design tasks

- Define "material" vs. immaterial conflict (numeric tolerance? contradictory
  procedure?).
- Specify the answer-composition prompt and the post-generation validator in
  `ikip-statements` that checks conflicts were disclosed when present.
- Design the UX for showing conflicting sources with authority indicators.

## Enforcement points

- `services/retrieval/.../pipeline/merge_rerank.py` — authority ranking.
- `packages/ikip-statements` — validates conflict disclosure before an answer is shown.
- `evaluation/suites/grounding_and_citation/` — includes conflicting-source cases.
