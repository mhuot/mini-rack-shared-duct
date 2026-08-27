"""Fusion 360 script: export the Front Ear STL with tangency relief.

Run inside Fusion via the MCP execute tool with the 'MacBook Pro Front Ear'
document open. Copies the proven 'Front Ear' body unchanged except for a
0.12 mm relief on the laptop slot faces in the rod band: the stock design's
rod bores are exactly tangent to those faces (rod centers 6.22/38.23 + r4),
which produces non-manifold edges that slicers report as open. The relief
makes the intersections transversal; the laptop rides on the rods either
way. Exports exports/front_ear.stl and leaves no document open.
"""

import adsk.core
import adsk.fusion

MM = 0.1  # Fusion API lengths are in cm

SOURCE_DOC = "MacBook Pro Front Ear"
TANGENCY_X0, TANGENCY_X1 = -12.5, -2.5
TANGENCY_Y0, TANGENCY_Y1 = 10.10, 34.35
STL_PATH = "/Users/mhuot/mini-rack/exports/front_ear.stl"


def run(_context: str):
    app = adsk.core.Application.get()
    source_doc = None
    for doc in app.documents:
        if doc.name.startswith(SOURCE_DOC):
            source_doc = doc
            break
    if source_doc is None:
        raise RuntimeError("Document '%s' is not open" % SOURCE_DOC)
    source_doc.activate()
    source_design = adsk.fusion.Design.cast(app.activeProduct)

    temp_mgr = adsk.fusion.TemporaryBRepManager.get()
    body = source_design.rootComponent.bRepBodies.itemByName("Front Ear")
    combined = temp_mgr.copy(body)

    center = adsk.core.Point3D.create(
        (TANGENCY_X0 + TANGENCY_X1) / 2 * MM,
        (TANGENCY_Y0 + TANGENCY_Y1) / 2 * MM, 4.0 * MM)
    relief = temp_mgr.createBox(adsk.core.OrientedBoundingBox3D.create(
        center,
        adsk.core.Vector3D.create(1, 0, 0),
        adsk.core.Vector3D.create(0, 1, 0),
        (TANGENCY_X1 - TANGENCY_X0) * MM,
        (TANGENCY_Y1 - TANGENCY_Y0) * MM, 12.0 * MM))
    temp_mgr.booleanOperation(
        combined, relief, adsk.fusion.BooleanTypes.DifferenceBooleanType)

    new_doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    new_design = adsk.fusion.Design.cast(app.activeProduct)
    new_design.designType = adsk.fusion.DesignTypes.DirectDesignType
    new_body = new_design.rootComponent.bRepBodies.add(combined)
    new_body.name = "Front Ear"

    stl = new_design.exportManager.createSTLExportOptions(new_body, STL_PATH)
    stl.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
    new_design.exportManager.execute(stl)
    print("exported %s" % STL_PATH)
