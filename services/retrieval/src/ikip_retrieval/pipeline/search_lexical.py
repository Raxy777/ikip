"""Lexical (keyword/BM25) channel over document text.

Implements the SearchChannel port (ports/search_channel.py). Returns raw Candidates; it
does NOT authorize them — authorization is applied uniformly in merge_rerank before any
ranking, so this channel cannot become a leak path.

The live implementation is `adapters/lexical_index.py::LexicalIndex`, an in-memory BM25
index. It resolves each candidate's ACL from the shared AclStore at search time, so ACL
updates and revocations applied by the sync layer take effect without reindexing.
"""
