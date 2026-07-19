"""The AnswerGateway port — the retrieval service's view of the Model Gateway.

Retrieval never calls a model provider directly; it goes through this port, whose concrete
implementation lives in the gateway service and enforces evidence-only prompts, egress
allow-listing, and provider policy. The port returns an untrusted draft Answer that MUST
still pass validation before it can be shown.
"""
from __future__ import annotations

from typing import Protocol

from ikip_contracts import Answer, Evidence


class GatewayError(Exception):
    """Raised when the gateway or provider is unavailable or returns invalid structure.

    The pipeline treats this as a degraded-mode signal and abstains with `unavailable`
    rather than failing hard (see docs/safety/abstention-policy.md).
    """


class AnswerGateway(Protocol):
    def synthesize(
        self,
        *,
        request_id: str,
        question: str,
        evidence: list[Evidence],
        config_version: str,
    ) -> Answer:
        """Produce a draft Answer from the minimum authorized evidence.

        The returned Answer is UNTRUSTED model output. It is structurally an Answer only
        because the gateway validates the provider's response against the schema; its
        claims are not yet verified against the evidence — that is the validator's job.
        """
        ...
