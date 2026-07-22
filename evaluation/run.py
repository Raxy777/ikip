"""Deterministic pilot evaluation gate.

This gate executes named correctness/security test sets. It deliberately does not claim
expert-graded retrieval quality; governed golden and blind holdout data remain a production
follow-up described in ``evaluation/README.md``.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

SUITES: dict[str, tuple[str, ...]] = {
    "retrieval_behavior_regression": ("services/retrieval/tests",),
    "grounding_citation_regression": (
        "services/api/tests/test_api.py::test_answer_grounded_and_cited",
        "services/api/tests/test_api.py::test_answer_hallucination_is_blocked",
    ),
    "abstention_behavior_regression": (
        "services/api/tests/test_api.py::test_answer_abstains_when_no_evidence",
        "services/api/tests/test_api.py::test_answer_gateway_outage_degrades_gracefully",
    ),
    "access_isolation_security": ("tests/security", "services/api/tests/test_api.py"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="IKIP deterministic pilot evaluation")
    parser.add_argument("--suite", default="all", choices=["all", *SUITES])
    parser.add_argument("--gate", action="store_true", help="Return non-zero if a suite fails")
    args = parser.parse_args()
    selected = list(SUITES) if args.suite == "all" else [args.suite]
    failures: list[str] = []
    for name in selected:
        print(f"\n=== {name} ===", flush=True)
        result = subprocess.run(  # noqa: S603 -- executable and test paths are repository constants
            [sys.executable, "-m", "pytest", "-q", *SUITES[name]], check=False
        )
        if result.returncode:
            failures.append(name)
    if failures:
        print(f"Failed suites: {', '.join(failures)}", file=sys.stderr)
        return 1 if args.gate else 0
    print(f"Passed {len(selected)}/{len(selected)} deterministic pilot suites.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
