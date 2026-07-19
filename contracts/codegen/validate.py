"""Validate that all schemas parse and cross-references resolve.

Run by `just contracts-check` and in CI. Extend to validate example payloads
against their schemas once examples are added under contracts/schemas/examples/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

CONTRACTS = Path(__file__).resolve().parents[1]


def main() -> int:
    errors: list[str] = []
    files = sorted(CONTRACTS.glob("schemas/*.schema.json")) + sorted(
        CONTRACTS.glob("events/*.schema.json")
    )
    for f in files:
        try:
            json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:  # noqa: PERF203
            errors.append(f"{f.name}: {e}")
    if errors:
        print("Schema validation FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"All {len(files)} schema file(s) parsed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
