"""The query pipeline, in enforced order.

    authorize -> (exact | lexical | semantic | relationship) -> merge_rerank
              -> assemble_evidence -> [gateway] -> validate -> answer | abstain

Every search stage takes an AuthorizationContext, so retrieval cannot run before
authorization. The gateway call goes through the AnswerGateway port; output validation
uses packages/ikip-statements. `compose.compose_answer` orchestrates the generation ->
validate -> answer|abstain tail and, on any validation or gateway failure, routes to a
safe abstention — an unvalidated draft never reaches the user.
"""

__all__: list[str] = []
