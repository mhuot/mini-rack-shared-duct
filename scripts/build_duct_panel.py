"""Fusion 360 script: duct panel for the modular rear assembly.

Run inside Fusion via the MCP execute tool. Creates a parametric document
with a named timeline, per the project rule.

Two of these close the top and bottom of the rear overhang. They slide in
from the rear along the capture grooves in the rear ears and are trapped by
the fan plate, so the duct stays with the rack when the plate comes off.
Printed flat they are ten layers of solid sheet, which is quick and has none
of the warping or wobble risk of the 72 mm walls they replace.

Width spans groove floor to groove floor (ear inner faces at +/-95.32 global,
grooves 2 mm outboard to +/-97.32) less 0.2 mm of slide clearance. Length
matches the ear depth so the front edge meets the rear rail plane.
"""

import adsk.core
import adsk.fusion

MM = 0.1  # Fusion API lengths are in cm

PANEL_WIDTH = 194.44      # 2 x 97.32 groove floors, less 0.2 slide clearance
# 72 of ear depth, rail plane to fan plate face, plus 2.0 that lands in the
# capture groove in the fan plate so the rear edge is lapped rather than butted.
PANEL_LENGTH = 74.0
# The slot is 2.4 tall. A 2.0 panel leaves 0.4 mm of free play, and a 37 g
# sheet with that much room next to four fans will buzz on impact whatever its
# natural frequency happens to be. 2.2 is 11 layers at 0.2 and halves the gap
# to a textbook 0.2 mm sliding fit, while stiffening the panel by a third.
PANEL_THICK = 2.2
CHAMFER = 0.6             # lead-in so the panel starts into the slot easily


def run(_context: str):
    app = adsk.core.Application.get()
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent
    extrudes = root.features.extrudeFeatures

    sketch = root.sketches.add(root.xYConstructionPlane)
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(-PANEL_WIDTH / 2 * MM, 0, 0),
        adsk.core.Point3D.create(PANEL_WIDTH / 2 * MM, PANEL_LENGTH * MM, 0))
    sketch.name = "Panel outline"

    feature_input = extrudes.createInput(
        sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    feature_input.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(PANEL_THICK * MM))
    panel = extrudes.add(feature_input)
    panel.name = "Panel"

    body = panel.bodies.item(0)
    body.name = "Duct Panel"

    # Chamfer the two long side edges so the panel leads into the grooves.
    edges = adsk.core.ObjectCollection.create()
    for edge in body.edges:
        box = edge.boundingBox
        along_length = abs(box.maxPoint.y - box.minPoint.y) > PANEL_LENGTH * MM * 0.9
        at_side = abs(abs(box.minPoint.x) - PANEL_WIDTH / 2 * MM) < 1e-4
        if along_length and at_side:
            edges.add(edge)
    if edges.count:
        chamfers = root.features.chamferFeatures
        chamfer_input = chamfers.createInput2()
        chamfer_input.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
            edges, adsk.core.ValueInput.createByReal(CHAMFER * MM), False)
        chamfers.add(chamfer_input).name = "Groove lead-in"

    app.activeViewport.fit()
    bb = body.boundingBox
    print("Duct panel: %.2f x %.2f x %.2f mm, %d timeline items" % (
        (bb.maxPoint.x - bb.minPoint.x) * 10,
        (bb.maxPoint.y - bb.minPoint.y) * 10,
        (bb.maxPoint.z - bb.minPoint.z) * 10,
        design.timeline.count))
