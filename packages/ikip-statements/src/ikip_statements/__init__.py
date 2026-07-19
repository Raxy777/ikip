"""ikip-statements — the safety-critical claim layer.

Two jobs:
  1. classify(claim, evidence) -> StatementClass — is this a historical observation, a
     recommendation, an approved procedure, completed work, or an inference?
  2. validate_support(answer, evidence) -> bool — does every claim cite evidence that
     actually supports it, with the correct statement class?

Conflating these classes is the primary way this platform could cause industrial harm,
so this package's tests carry the highest bar and feed evaluation/suites/grounding_and_citation.
"""

__all__: list[str] = []
