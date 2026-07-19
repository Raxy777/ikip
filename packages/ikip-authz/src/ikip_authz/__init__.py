"""ikip-authz — the single authorization authority for the platform.

INVARIANT (Security #1): authorization happens BEFORE retrieval. Restricted text must
never enter ranking, prompts, citations, previews, summaries, logs, or inference-visible
context.

No other package may decide authorization. Retrieval, API, gateway, and ingestion all
call into here. This module is deny-by-default: if a decision cannot be made confidently
(including a stale ACL), it denies.
"""

from ikip_authz.context import AuthorizationContext
from ikip_authz.decision import AccessDecision, Effect
from ikip_authz.filter import authorize_scope, evaluate_document, filter_candidates
from ikip_authz.freshness import check_freshness
from ikip_authz.sync import (
    AclEvent,
    AclSource,
    AclStore,
    EventType,
    InMemoryAclStore,
    SyncReport,
    apply_event,
    reconcile,
)

__all__ = [
    "AuthorizationContext",
    "AccessDecision",
    "Effect",
    "authorize_scope",
    "evaluate_document",
    "filter_candidates",
    "check_freshness",
    "AclEvent",
    "AclSource",
    "AclStore",
    "EventType",
    "InMemoryAclStore",
    "SyncReport",
    "apply_event",
    "reconcile",
]
