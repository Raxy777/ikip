"""Separate untrusted document text from platform instructions.

Retrieved document content is DATA. It is placed in a delimited evidence region and never
concatenated into the instruction region. Embedded prompts, hidden text, or adversarial
passages in evidence cannot override platform policy (Security invariant #2).
"""
from __future__ import annotations


def build_evidence_only_prompt(instructions: str, evidence_blocks: list[str]) -> dict:
    """Return a structured prompt with instructions and evidence kept in separate fields.

    Kept structured (not a single concatenated string) so the boundary between trusted
    instructions and untrusted evidence is explicit at the provider call site.
    """
    return {
        "instructions": instructions,
        "evidence": evidence_blocks,  # untrusted; treated as data only
    }
