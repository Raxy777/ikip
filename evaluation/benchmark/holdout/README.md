# Blind Holdout Set — ACCESS CONTROLLED

**The contents of this directory are intentionally git-ignored.** Only this README is
tracked.

## Rules

1. The holdout set is **never** committed to the repository.
2. It is **never** used for tuning, prompt engineering, or few-shot examples — doing so
   destroys its value as a blind measure.
3. It is **never** placed in a model prompt except as the question under evaluation.
4. Access is restricted to those running release-gate evaluations.

The holdout gates releases (see `evaluation/`). Building it — expert-graded questions
with annotated expected-evidence IDs — is the platform's critical path and long pole; it
depends on the chosen equipment family, workflow, and canonical identity source being
fixed first.
