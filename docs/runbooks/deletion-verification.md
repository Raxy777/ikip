# Runbook: Deletion Verification

Schema: `contracts/events/deletion-job.schema.json`. Lifecycle: diagram 07.

A deletion is **not complete** until residual-artifact tests pass and a minimal,
policy-permitted verification record (tombstone) is written.

## Steps

1. **Authorize & hold check.** Confirm authority; confirm no legal or record hold.
2. **Enumerate scope.** Use provenance lineage to list every derivative: originals,
   previews, OCR outputs, chunks, embeddings, lexical/vector indexes, entities,
   relationships, caches, and future-answer references.
3. **Purge active data.** Delete all enumerated artifacts.
4. **History treatment.** Delete, redact, or retain minimum audit metadata per policy.
5. **Backup treatment.** Cryptographic erasure or scheduled expiry so ordinary restore
   cannot resurrect deleted data.
6. **Verify.** Run residual-artifact search tests. If any residual is found, return to
   step 3. Confirm backup policy applied.
7. **Tombstone.** Write scope, authority, time, and verification result — with **no
   prohibited source content**.

## Restore invariant

Restoring a backup must **replay deletion records** before the restored environment is
made available. A restore that resurrects deleted data is an incident.
