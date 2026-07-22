"""Format handlers. Each implements the registry `Handler` protocol.

Tier 1: stl_trimesh (STL), step_occt (STEP, optional OCCT toolkit).
Tier 2: ole_props (OLE compound-file metadata/thumbnail, optional olefile).
Tier 3: blocked (recognized proprietary formats requiring conversion — always available).
"""
