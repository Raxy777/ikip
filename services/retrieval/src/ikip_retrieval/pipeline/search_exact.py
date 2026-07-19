"""Exact-match channel: identifiers, codes, tag numbers, exact phrases.

Implements the SearchChannel port (ports/search_channel.py). Returns raw Candidates; it
does NOT authorize them — authorization is applied uniformly in merge_rerank before any
ranking, so this channel cannot become a leak path. Concrete data-store wiring lives in
../adapters.
"""
