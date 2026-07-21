"""Model converters (Tier-3 → neutral format). Implementations of the ModelConverter port.

A converter takes a proprietary CAD file that has no direct reader and produces a neutral
STEP file, which then re-enters the Tier-1 path. Converters run OUT OF PROCESS (subprocess)
inside the sandbox — the licensed-SDK/FreeCAD swap is a subprocess-command change, not a
code change to any stage.
"""
