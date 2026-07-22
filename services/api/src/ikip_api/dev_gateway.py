"""A development AnswerGateway that does NOT call a model provider.

This exists so the API runs end to end with no external dependency. It fabricates a
minimal grounded draft that cites the first authorized evidence item, so you can exercise
the answered path, and it honours a couple of query markers so the abstention paths are
demoable too:

  - a question containing "[[boom]]"      -> raises GatewayError (degraded mode demo)
  - a question containing "[[hallucinate]]" -> cites a non-existent evidence id, which the
                                              validator rejects -> abstain(insufficient)

It is registered ONLY under the dev profile. A real deployment wires the Model Gateway
service (evidence-only prompts, egress allow-listing, provider policy) behind this port.
NOTHING here should be mistaken for grounded generation — the "answer" is templated.
"""
from __future__ import annotations

from ikip_contracts import (
    Answer,
    Citation,
    Claim,
    Evidence,
    Outcome,
    StatementClass,
)

from ikip_retrieval.ports.answer_gateway import GatewayError


class DevAnswerGateway:
    """Templated, provider-free gateway for local runs and demos. Not for production."""

    def synthesize(
        self,
        *,
        request_id: str,
        question: str,
        evidence: list[Evidence],
        config_version: str,
    ) -> Answer:
        if "[[boom]]" in question:
            raise GatewayError("dev gateway: simulated provider outage")

        # Cite the highest-ranked authorized evidence item. compose_answer guarantees the
        # list is non-empty before we are called.
        top = evidence[0]
        cited_id = "ev-does-not-exist" if "[[hallucinate]]" in question else top.evidence_id

        claim = Claim(
            claim_id="c1",
            text=(
                f"Based on the authorized evidence, {top.text}"
                if "[[hallucinate]]" not in question
                else "This claim deliberately cites evidence outside the authorized set."
            ),
            citation=Citation(
                claim_id="c1",
                evidence_ids=[cited_id],
                statement_class=StatementClass.HISTORICAL_OBSERVATION,
            ),
        )
        return Answer(
            request_id=request_id,
            outcome=Outcome.ANSWERED,
            config_version=config_version,
            claims=[claim],
        )
