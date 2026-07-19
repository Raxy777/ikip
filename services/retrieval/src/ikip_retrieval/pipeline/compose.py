"""Answer composition orchestrator — the tail of the query pipeline.

Ties together the steps after evidence has been assembled:

    authorized evidence
        -> [no evidence]        -> abstain(insufficient)
        -> gateway.synthesize   -> draft (UNTRUSTED)
              -> [GatewayError]  -> abstain(unavailable)   (degraded mode)
        -> validate_draft
              -> [ok]            -> return the grounded answer
              -> [conflict only] -> abstain(conflicting)
              -> [otherwise]     -> abstain(insufficient)   (unsupported/hallucinated)

This encodes the "Adequate evidence exists" → validation branch of the query-flow
sequence diagram. Authorization happened earlier in the pipeline; `authorized_evidence`
is the already-filtered set and is the ONLY evidence the validator trusts.
"""
from __future__ import annotations

from ikip_contracts import Answer, Evidence

from ikip_retrieval.pipeline import abstain
from ikip_retrieval.pipeline.validate import validate_draft
from ikip_retrieval.ports.answer_gateway import AnswerGateway, GatewayError
from ikip_statements import ViolationCode


def compose_answer(
    *,
    request_id: str,
    question: str,
    authorized_evidence: list[Evidence],
    gateway: AnswerGateway,
    config_version: str,
) -> Answer:
    """Return a grounded Answer or a safe abstention. Never returns an unvalidated draft."""
    # No authorized evidence -> abstain before spending a model call.
    if not authorized_evidence:
        return abstain.as_answer(request_id, config_version, abstain.insufficient())

    # Draft is untrusted model output.
    try:
        draft = gateway.synthesize(
            request_id=request_id,
            question=question,
            evidence=authorized_evidence,
            config_version=config_version,
        )
    except GatewayError:
        # Degraded mode: prefer a safe abstention over a hard failure.
        return abstain.as_answer(request_id, config_version, abstain.unavailable())

    # Enforce claim support, citation coverage, statement labels, and conflict disclosure.
    result = validate_draft(draft, authorized_evidence)
    if result.ok:
        return draft

    # Map validation failure to the most informative safe abstention. If the ONLY problem
    # is an undisclosed conflict, say so; otherwise the draft is unsupported/fabricated.
    codes = {v.code for v in result.violations}
    if codes == {ViolationCode.UNDISCLOSED_CONFLICT}:
        return abstain.as_answer(request_id, config_version, abstain.conflicting())
    return abstain.as_answer(request_id, config_version, abstain.insufficient())
