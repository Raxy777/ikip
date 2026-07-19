"""The query pipeline, in enforced order.

    authorize -> (exact | lexical | semantic | relationship) -> merge_rerank
              -> assemble_evidence -> [gateway] -> validate -> answer | abstain

Every search stage takes an AuthorizationContext, so retrieval cannot run before
authorization. The gateway call and output validation live in services/gateway and
packages/ikip-statements respectively; this package orchestrates and, on any failure,
routes to abstain.
"""

__all__: list[str] = []
