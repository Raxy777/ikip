"""Exact-match channel: identifiers, codes, tag numbers, exact phrases.

Implements the SearchChannel port (ports/search_channel.py). Returns raw Candidates; it
does NOT authorize them — authorization is applied uniformly in merge_rerank before any
ranking, so this channel cannot become a leak path.

The live implementation is `adapters/exact_index.py::ExactIndex`, an in-memory index of
registered identifiers (asset tags, codes, doc numbers) and quoted-phrase matching.
Matching is EXACT: "P-101" matches "P-101" but never "P-1010". ACLs are resolved
fail-closed from the shared AclStore at search time.
"""
