# ADR-0004: Tiered CAD handlers, sandboxed extraction, and a conversion seam

**Status:** Accepted
**Date:** 2026-07-21

## Context

CAD and mesh files are unlike the prose documents the pipeline was built for: their "text"
is geometry, assembly structure, and PMI, and their formats span open neutral standards
(STEP, STL), OLE-wrapped proprietary parts (SolidWorks, CATIA), and fully proprietary
binaries with no public reader (Creo, NX). They are also untrusted input at Trust Boundary
TB-4 — a malformed or hostile file must never crash a worker or leak content.

Three forces shaped the design:

1. **Formats vary in how much we can recover.** Some yield full geometry, some only
   metadata, some nothing without conversion. Treating them uniformly would either reject
   too much or make unsafe assumptions about missing data.
2. **Toolkits are heavy and environment-specific.** The OCCT binding is conda/large-wheel;
   FreeCAD is a system application, not a pip package. Requiring all of them everywhere
   would make the service uninstallable in constrained environments.
3. **Untrusted parsing must fail as a routed outcome, never a crash or a leak.**

## Decision

1. **Tiered extraction.** Every handler returns a normalized `ExtractedModel` tagged with a
   tier: `full_geometry` (STEP, STL), `metadata_only` (OLE proprietary parts), 
   `needs_conversion` (Creo/CATIA/etc.), `blocked` (policy). Downstream stages consume ONLY
   `ExtractedModel`, so adding a format is adding a handler — stages never change.

2. **Graceful toolkit degradation.** A handler whose toolkit is absent declares itself
   unavailable; the file routes to **review**, not rejection, so enabling the toolkit later
   recovers it. This is the same pattern for OCCT (`cad-step`), olefile (`cad-ole`), and
   FreeCAD (deployment component).

3. **Sandboxed handler execution.** All extraction runs behind `extract/sandbox.py`. Any
   exception, timeout, or missing-toolkit condition becomes a structured `SandboxResult`,
   mapped by `quarantine` to admit / review / reject. The seam is `run_sandboxed`: today
   in-process, hardened to an out-of-process locked-down runner without touching handlers or
   stages. Handlers never execute file contents — they only read bytes.

4. **Conversion seam.** A `ModelConverter` port (`extract/converter.py`) sits between Tier 3
   and Tier 1. When a converter is enabled for a `needs_conversion` file, the file is
   converted to STEP and re-ingested through the Tier-1 path; when none applies, the file
   routes to review. The default is a no-op; `FreecadHeadlessConverter` is the first real
   implementation and runs FreeCAD as a subprocess (the hardening boundary). Swapping in a
   licensed conversion SDK is a change to that one module.

5. **Governance is explicit and fail-closed.** A part with no PLM record is `authority=UNKNOWN`
   with no ACL and is excluded from ranking until reviewed. A PLM-synced part gets an
   `AclPolicy` whose `source_of_truth`/`synced_at` flow into the existing freshness gate.
   Any export-control signal (ITAR/EAR/ECCN) forces `classification=RESTRICTED` regardless
   of PLM state — even an approved part fails closed.

## Consequences

- Adding a CAD format is a handler + registry line; adding a conversion path is a converter
  behind the existing port. No stage or retrieval code changes.
- The tier is carried in provenance (`extraction_tier`), so any CAD artifact is reproducible
  and invalidatable when a handler version changes.
- Security posture is honest: process-local isolation today, with a real subprocess boundary
  already in use for conversion and a documented path to full OS isolation.
- Heavy toolkits stay optional; the service installs and runs (in degraded/review mode) with
  none of them present.

## Revisit trigger

If out-of-process isolation becomes mandatory for all extraction (not just conversion),
promote `run_sandboxed` to the subprocess runner by default and make in-process execution
the opt-in for trusted/dev environments. If a single conversion SDK covers all proprietary
formats, collapse the per-format converter dispatch into it.
