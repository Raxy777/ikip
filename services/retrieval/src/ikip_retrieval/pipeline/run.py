"""The full query pipeline, head to tail.

    authorize_scope            (gate the request)
      -> fan out over SearchChannels (exact | lexical | semantic | relationship)
      -> merge_and_rank        (authorize-filter BEFORE ranking; authority ranking)
      -> assemble              (minimum authorized evidence)
      -> compose_answer        (synthesize -> validate -> answer | abstain)

This module is the single place the ordering invariant is realised: scope is gated first,
every channel result is authorization-filtered before ranking, and the model only ever
sees the assembled authorized evidence. A scope denial or empty evidence short-circuits to
a safe abstention without calling the model.
"""
from __future__ import annotations

from ikip_authz import AuthorizationContext, authorize_scope
from ikip_contracts import Answer

from ikip_retrieval.pipeline import abstain
from ikip_retrieval.pipeline.assemble_evidence import assemble
from ikip_retrieval.pipeline.compose import compose_answer
from ikip_retrieval.pipeline.merge_rerank import merge_and_rank
from ikip_retrieval.pipeline.types import RetrievalQuery
from ikip_retrieval.ports.answer_gateway import AnswerGateway
from ikip_retrieval.ports.search_channel import SearchChannel

DEFAULT_CHANNEL_LIMIT = 50


def run_query(
    *,
    request_id: str,
    ctx: AuthorizationContext,
    query: RetrievalQuery,
    channels: list[SearchChannel],
    gateway: AnswerGateway,
    config_version: str,
    channel_limit: int = DEFAULT_CHANNEL_LIMIT,
) -> Answer:
    """Execute the query end to end, returning a grounded Answer or a safe abstention."""
    # 1. Gate the request. A denial abstains without leaking that content may exist.
    if not authorize_scope(ctx).allowed:
        return abstain.as_answer(request_id, config_version, abstain.unauthorized_scope())

    # 2. Fan out across channels. Each returns raw, unauthorized candidates.
    channel_results = [ch.search(query, limit=channel_limit) for ch in channels]

    # 3. Authorize-filter (before ranking) + authority ranking, in one guarded stage.
    ranked = merge_and_rank(ctx, channel_results)

    # 4. Assemble the minimum authorized evidence set.
    evidence = assemble(ranked)

    # 5. Synthesize -> validate -> answer | abstain. Handles no-evidence and gateway
    #    failure internally, and never returns an unvalidated draft.
    return compose_answer(
        request_id=request_id,
        question=query.question,
        authorized_evidence=evidence,
        gateway=gateway,
        config_version=config_version,
    )
