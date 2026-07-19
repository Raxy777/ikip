"""Stage 0 of the query pipeline: authorize BEFORE any search runs.

This module is imported first by the pipeline and produces the authorization scope that
every subsequent search stage requires as an argument. There is no code path from a
question to a search that skips this step.
"""
from __future__ import annotations

from ikip_authz import AuthorizationContext, authorize_scope
from ikip_authz.decision import AccessDecision


def gate_request(ctx: AuthorizationContext) -> AccessDecision:
    """Deny-by-default gate for the whole request. Raises nothing; returns a decision.

    Callers MUST check `.allowed` before proceeding to retrieval. A denial is recorded as
    an audit event and surfaced without revealing restricted content.
    """
    return authorize_scope(ctx)
