"""Generate typed models from contracts/ into every consuming language.

Python  -> packages/ikip-contracts/src/ikip_contracts/_generated.py
Web     -> web/src/lib/generated/contracts.ts

This is a stub. Wire it to datamodel-code-generator (Python) and
json-schema-to-typescript (web) so `just codegen` produces committed artifacts.
Generated files must never be hand-edited — edit the schema and regenerate.
"""
from __future__ import annotations

import sys
from pathlib import Path

CONTRACTS = Path(__file__).resolve().parents[1]
SCHEMAS = sorted(CONTRACTS.glob("schemas/*.schema.json"))


def main() -> int:
    if not SCHEMAS:
        print("No schemas found under contracts/schemas/", file=sys.stderr)
        return 1
    print(f"Would generate models from {len(SCHEMAS)} schema(s):")
    for s in SCHEMAS:
        print(f"  - {s.name}")
    print("TODO: invoke datamodel-code-generator and json-schema-to-typescript.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
