"""Validate JSON Schemas and the separately authored static OpenAPI document.

Runtime response examples are validated in the API tests because those tests can exercise
real serialized payloads. This check validates schema metasyntax and static OpenAPI YAML;
the FastAPI-generated ``/openapi.json`` remains a separate Pydantic-derived document.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import validators

CONTRACTS = Path(__file__).resolve().parents[1]


def main() -> int:
    errors: list[str] = []
    files = sorted(CONTRACTS.glob("schemas/*.schema.json")) + sorted(
        CONTRACTS.glob("events/*.schema.json")
    )
    for path in files:
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            validators.validator_for(schema).check_schema(schema)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:  # noqa: PERF203
            errors.append(f"{path.name}: {exc}")

    openapi_path = CONTRACTS / "openapi" / "api.v1.yaml"
    try:
        openapi = yaml.safe_load(openapi_path.read_text(encoding="utf-8"))
        if openapi.get("openapi") != "3.1.0" or not isinstance(openapi.get("paths"), dict):
            errors.append(f"{openapi_path.name}: expected an OpenAPI 3.1 document with paths")
    except (yaml.YAMLError, AttributeError) as exc:
        errors.append(f"{openapi_path.name}: {exc}")

    if errors:
        print("Contract validation FAILED:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(f"Validated {len(files)} JSON Schemas and {openapi_path.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
