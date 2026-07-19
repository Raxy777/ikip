"""Retrieval & Answer Service — hybrid retrieval and grounded generation.

Runs exact, lexical, semantic, and relationship retrieval under identical authorization
filters; reranks and checks authority; assembles the minimum authorized evidence; and
either produces a claim-cited answer or a safe abstention.
"""

__all__: list[str] = []
