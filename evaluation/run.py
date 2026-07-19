"""Evaluation gate entry point: `python -m evaluation.run --suite all --gate`.

Runs the suites and, with --gate, exits non-zero on regression against recorded
baselines so CI blocks the merge. This is a stub; wire suites in as they are built.
"""
from __future__ import annotations

import argparse
import sys

SUITES = [
    "retrieval_recall",
    "grounding_and_citation",
    "abstention_precision_recall",
    "access_isolation",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="IKIP evaluation gate")
    parser.add_argument("--suite", default="all", choices=["all", *SUITES])
    parser.add_argument("--gate", action="store_true", help="Fail on regression.")
    args = parser.parse_args()

    selected = SUITES if args.suite == "all" else [args.suite]
    print(f"Running evaluation suites: {', '.join(selected)}")
    print("TODO: execute suites against the golden/holdout sets and compare to baseline.")
    # Until suites exist, do not give a false green on a gated run.
    if args.gate:
        print("Gate requested but suites are not implemented yet.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
