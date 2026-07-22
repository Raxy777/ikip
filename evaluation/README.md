# Evaluation — pilot gate and production roadmap

`python -m evaluation.run --suite all --gate` runs deterministic, provider-free tests for
retrieval behavior regression, grounding/citation regression, abstention behavior regression, and access-isolation security. A
failing selected test set makes the gated command fail. This is meaningful for pilot CI,
but it is **not** a claim of domain answer quality or a replacement for expert evaluation.

Suite names intentionally describe deterministic regression/security checks, not measured recall or precision. They currently map to repository pytest tests; use `--suite NAME` to run one.
Without `--gate`, failures are reported but the command is informational and exits zero.

Production release evaluation still requires governed `benchmark/golden` questions,
access-controlled `benchmark/holdout` data, expert expected-evidence annotations, calibrated
graders, recorded baselines, and regression reports. Restricted holdout content must never
be committed or enter prompts/tuning. Budget expert review and recalibrate graders whenever
models, prompts, or processing versions change.
