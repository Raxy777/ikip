"""STEP handler backed by OCCT via the cadquery-ocp (OCP) binding. Tier 1.

STEP AP242 carries what STL cannot: assembly structure, part names/numbers, properties, and
PMI (GD&T, notes). This handler reads it through OCCT's XCAF document model.

IMPORTANT — optional toolkit. OCP is an optional extra (`uv sync --extra cad-step`; conda
alternative: pythonocc-core). When it is not installed, `available()` returns False and the
registry routes STEP files to the review queue as "needs conversion / toolkit unavailable"
rather than crashing. The extraction code below is written against the OCP API but is only
exercised where OCP is installed; the degraded (unavailable) path is what runs — and is
verified — in a workspace without the extra.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from ikip_ingestion.extract.sandbox import HandlerUnavailable
from ikip_ingestion.extract.types import (
    CadCoordinate,
    ExtractedModel,
    ExtractionTier,
    PartRecord,
    PmiNote,
)

_STEP_MAGIC = b"ISO-10303-21"


def _ocp_installed() -> bool:
    """True if the OCP binding is importable, without importing it."""
    return importlib.util.find_spec("OCP") is not None


class StepOcctHandler:
    """Extract assembly structure, PMI, properties, and a tessellated mesh from STEP."""

    format_key = "STEP"

    def sniff(self, head: bytes, filename: str) -> bool:
        name = filename.lower()
        if name.endswith((".step", ".stp", ".p21")):
            return True
        return _STEP_MAGIC in head[:256]

    def available(self) -> bool:
        return _ocp_installed()

    def extract(self, path: Path) -> ExtractedModel:
        if not _ocp_installed():
            # Defensive: registry already gates on available(), but a handler must never
            # half-run. Signal cleanly so the sandbox maps this to UNAVAILABLE -> review.
            raise HandlerUnavailable("OCP (cadquery-ocp) not installed")

        # --- OCCT / OCP imports (only reached when the toolkit is present) --------------
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPCAFControl import STEPCAFControl_Reader
        from OCP.TCollection import TCollection_AsciiString
        from OCP.TDataStd import TDataStd_Name
        from OCP.TDF import TDF_LabelSequence
        from OCP.TDocStd import TDocStd_Document
        from OCP.XCAFApp import XCAFApp_Application
        from OCP.XCAFDoc import XCAFDoc_DocumentTool

        app = XCAFApp_Application.GetApplication_s()
        doc = TDocStd_Document(TCollection_AsciiString("MDTV-XCAF"))
        app.InitDocument(doc)

        reader = STEPCAFControl_Reader()
        reader.SetNameMode(True)
        reader.SetColorMode(True)
        reader.SetGDTMode(True)  # read PMI / GD&T
        reader.SetPropsMode(True)

        status = reader.ReadFile(str(path))
        if status != IFSelect_RetDone:
            raise ValueError(f"OCCT could not read STEP file (status={status})")
        reader.Transfer(doc)

        shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

        parts = self._read_parts(shape_tool, TDF_LabelSequence, TDataStd_Name)
        pmi = self._read_pmi(doc, XCAFDoc_DocumentTool, TDF_LabelSequence)
        canonical, metrics, warnings = self._tessellate(shape_tool, TDF_LabelSequence)

        properties: dict[str, str] = {"units": canonical.units if canonical else "mm"}
        if parts and parts[0].properties:
            properties.update(parts[0].properties)

        return ExtractedModel(
            source_format="STEP",
            tier=ExtractionTier.FULL_GEOMETRY,
            geometry_available=canonical is not None,
            metrics=metrics,
            canonical_mesh=canonical,
            parts=parts or [PartRecord(part_ref="part-0", name=path.stem)],
            pmi=pmi,
            properties=properties,
            geometry_kernel=self._occt_version(),
            tessellation="occt-incremental-mesh:0.1",
            warnings=warnings,
        )

    # -- helpers (OCP objects passed in to keep imports local) --------------------------
    def _read_parts(self, shape_tool, TDF_LabelSequence, TDataStd_Name) -> list[PartRecord]:
        labels = TDF_LabelSequence()
        shape_tool.GetFreeShapes(labels)
        parts: list[PartRecord] = []
        for i in range(1, labels.Length() + 1):
            label = labels.Value(i)
            name = self._label_name(label, TDataStd_Name)
            ref = f"part-{i - 1}"
            parts.append(PartRecord(part_ref=ref, name=name, part_number=name))
        return parts

    def _label_name(self, label, TDataStd_Name) -> str | None:
        from OCP.TDataStd import TDataStd_Name as _Name  # noqa: F811

        attr = _Name()
        if label.FindAttribute(_Name.GetID_s(), attr):
            return attr.Get().ToExtString()
        return None

    def _read_pmi(self, doc, XCAFDoc_DocumentTool, TDF_LabelSequence) -> list[PmiNote]:
        """Read GD&T / dimension PMI entities, each tied to a citable CAD coordinate."""
        notes: list[PmiNote] = []
        dgt_tool = XCAFDoc_DocumentTool.DimTolTool_s(doc.Main())
        labels = TDF_LabelSequence()
        dgt_tool.GetDimensionLabels(labels)
        for i in range(1, labels.Length() + 1):
            label = labels.Value(i)
            entry = self._label_entry(label)
            notes.append(
                PmiNote(
                    text=f"Dimension/GD&T entity {entry}",
                    coordinate=CadCoordinate(entity_type="pmi", entity_id=entry, label=f"pmi-{i}"),
                )
            )
        return notes

    def _label_entry(self, label) -> str:
        from OCP.TCollection import TCollection_AsciiString
        from OCP.TDF import TDF_Tool

        s = TCollection_AsciiString()
        TDF_Tool.Entry_s(label, s)
        return s.ToCString()

    def _tessellate(self, shape_tool, TDF_LabelSequence):
        """Mesh all free shapes into one canonical tessellation with metrics."""
        import numpy as np
        from OCP.BRepMesh import BRepMesh_IncrementalMesh
        from OCP.TopAbs import TopAbs_FACE
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopLoc import TopLoc_Location
        from OCP.BRep import BRep_Tool
        from OCP.TopoDS import TopoDS

        from ikip_ingestion.extract.mesh import canonical_from_arrays, metrics_from_arrays

        labels = TDF_LabelSequence()
        shape_tool.GetFreeShapes(labels)

        all_v: list = []
        all_f: list = []
        offset = 0
        warnings: list[str] = []

        for i in range(1, labels.Length() + 1):
            shape = shape_tool.GetShape_s(labels.Value(i))
            BRepMesh_IncrementalMesh(shape, 0.1, False, 0.5, True)
            exp = TopExp_Explorer(shape, TopAbs_FACE)
            while exp.More():
                face = TopoDS.Face_s(exp.Current())
                loc = TopLoc_Location()
                tri = BRep_Tool.Triangulation_s(face, loc)
                if tri is not None:
                    trsf = loc.Transformation()
                    nb_nodes = tri.NbNodes()
                    for n in range(1, nb_nodes + 1):
                        p = tri.Node(n).Transformed(trsf)
                        all_v.append((p.X(), p.Y(), p.Z()))
                    for t in range(1, tri.NbTriangles() + 1):
                        a, b, c = tri.Triangle(t).Get()
                        all_f.append((offset + a - 1, offset + b - 1, offset + c - 1))
                    offset += nb_nodes
                exp.Next()

        if not all_v:
            warnings.append("no tessellation produced; geometry unavailable")
            return None, None, warnings

        v = np.asarray(all_v, dtype=float)
        f = np.asarray(all_f, dtype=np.int64)
        canonical = canonical_from_arrays(v, f, units="mm")
        metrics = metrics_from_arrays(v, f)
        return canonical, metrics, warnings

    def _occt_version(self) -> str:
        try:
            from OCP.Standard import Standard_Version

            return f"OCCT-{Standard_Version.Get_s()}"
        except Exception:  # noqa: BLE001
            return "OCCT-unknown"
