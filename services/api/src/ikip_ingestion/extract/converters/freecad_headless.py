"""FreeCAD headless converter: proprietary CAD → STEP AP242. Tier-3 conversion seam (§G).

Implements the ModelConverter port (extract/converter.py). FreeCAD is a SYSTEM/conda
dependency, NOT a pip wheel — it ships as an application with its own Python. So this
converter never imports FreeCAD in-process; it invokes `freecadcmd` (or `FreeCADCmd`) as a
SUBPROCESS running a small conversion macro. That subprocess boundary is also the sandbox
hardening boundary (Phase 4): the untrusted file is parsed by FreeCAD in a separate process
with its own resource limits, never in the worker.

Enablement is explicit. The converter is DISABLED unless a FreeCAD executable is configured
(constructor arg or IKIP_FREECAD_CMD env var) AND found on disk. When disabled, `convert`
returns None so the caller routes the file to review — enabling FreeCAD later recovers it,
exactly like the Tier-1 toolkit-degradation pattern.

Swapping FreeCAD for a licensed conversion SDK is a change to `_build_command` only.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# Extensions FreeCAD's importers can open and re-export to STEP.
_CONVERTIBLE_EXTS = frozenset({
    ".prt", ".asm",            # Creo / NX
    ".catpart", ".catproduct",  # CATIA V5
    ".ipt", ".iam",            # Inventor
    ".sldprt", ".sldasm",       # SolidWorks (when geometry recoverable)
    ".par", ".psm",            # Solid Edge
})

# Per-conversion wall-clock budget. A hostile/huge file cannot hang ingestion.
_CONVERT_TIMEOUT_SECONDS = 120

# The FreeCAD macro: open the input, export the whole document to STEP. Kept inline so the
# deployment has nothing extra to install. `{inp}`/`{out}` are filled with quoted paths.
_MACRO = (
    "import FreeCAD, Import, Part;"
    "doc = FreeCAD.open({inp});"
    "objs = [o for o in doc.Objects if hasattr(o, 'Shape')];"
    "Import.export(objs, {out}) if objs else Part.export(doc.Objects, {out})"
)


class FreecadHeadlessConverter:
    """ModelConverter that shells out to FreeCAD to produce STEP. Disabled when unconfigured."""

    def __init__(self, freecad_cmd: str | None = None, *, timeout: int = _CONVERT_TIMEOUT_SECONDS) -> None:
        # Resolution order: explicit arg → env var → common executable names on PATH.
        self._cmd = self._resolve_cmd(freecad_cmd)
        self._timeout = timeout

    @staticmethod
    def _resolve_cmd(explicit: str | None) -> str | None:
        candidate = explicit or os.environ.get("IKIP_FREECAD_CMD")
        if candidate:
            # Accept an absolute path that exists, or a bare name resolvable on PATH.
            if Path(candidate).is_file() or shutil.which(candidate):
                return candidate
            return None
        for name in ("freecadcmd", "FreeCADCmd", "freecad"):
            found = shutil.which(name)
            if found:
                return found
        return None

    @property
    def enabled(self) -> bool:
        """True only when a usable FreeCAD executable was resolved."""
        return self._cmd is not None

    def can_convert(self, path: Path) -> bool:
        return self.enabled and Path(path).suffix.lower() in _CONVERTIBLE_EXTS

    def convert(self, path: Path, output_dir: Path) -> Path | None:
        """Convert `path` to STEP in `output_dir`. Returns the STEP path, or None on any failure.

        Never raises: a converter failure must become a routed outcome (review), not a crash.
        """
        if not self.can_convert(path):
            return None

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / (Path(path).stem + ".step")

        macro = _MACRO.format(inp=repr(str(path)), out=repr(str(out_path)))
        try:
            proc = subprocess.run(  # noqa: S603 — command is our resolved executable, not user input
                [self._cmd, "-c", macro],
                capture_output=True,
                timeout=self._timeout,
                # Do NOT pass the untrusted file on the command line as anything but a path;
                # the macro reads it, FreeCAD parses it in this isolated subprocess.
                cwd=str(output_dir),
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError):
            return None

        if proc.returncode != 0 or not out_path.is_file() or out_path.stat().st_size == 0:
            return None
        return out_path


__all__ = ["FreecadHeadlessConverter"]
