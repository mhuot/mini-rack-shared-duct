"""Cut the heat-set insert pockets as one explicit feature.

Run through the Fusion MCP against "MacBook Pro Rear Ear v2 Parametric".

The original pockets came out of a symmetric cut sketched on the plate face,
which reached 3.2 mm *down* into the plate as well as up through the pad. That
left only 0.80 mm of plate under each pocket -- and since the plate starts as a
bridge across the open duct, those two layers were the first bridged ones, with
nothing above them to pull flat. That is the roughness at the bottom of the
insert pocket.

The pad is stacked from z=67 to 72, so a pocket 3.2 mm deep measured from the
pad face floors at z=68.8 and leaves 3.8 mm of plate beneath it. Cutting it
from its own construction plane keeps it independent of the projected-edge
chain the earlier features relied on.
"""

import adsk.core
import adsk.fusion

MM = 0.1  # Fusion API lengths are in cm

DOCUMENT = "MacBook Pro Rear Ear v2 Parametric"
PAD_FACE_Z = 72.0
POCKET_DEPTH = 3.2        # CNC Kitchen M3 x 3 short: 3.0 long, 0.2 of melt room
POCKET_DIAMETER = 4.0
POCKET_X = -7.5
POCKET_ROWS = (15.0, 29.45)
OVERSHOOT = 0.2           # break cleanly through the pad face


def run(_context: str):
    app = adsk.core.Application.get()
    for index in range(app.documents.count):
        if app.documents.item(index).name == DOCUMENT:
            app.documents.item(index).activate()
    if app.activeDocument.name != DOCUMENT:
        raise RuntimeError(f"{DOCUMENT!r} is not open")

    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent
    design.timeline.moveToEnd()

    # Neutralise the old symmetric relief so it stops gouging the plate.
    relief = design.userParameters.itemByName("insert_pocket_relief")
    if relief is not None:
        relief.expression = "0.4 mm"

    names = [design.timeline.item(i).name for i in range(design.timeline.count)]
    if "Insert pocket bore" in names:
        raise RuntimeError("Insert pocket bore already exists")

    floor_z = PAD_FACE_Z - POCKET_DEPTH

    planes = root.constructionPlanes
    plane_input = planes.createInput()
    plane_input.setByOffset(
        root.xYConstructionPlane,
        adsk.core.ValueInput.createByReal(floor_z * MM))
    plane = planes.add(plane_input)
    plane.name = "Insert pocket floor"

    sketch = root.sketches.add(plane)
    sketch.name = "Insert pocket bore"
    for row_y in POCKET_ROWS:
        sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(POCKET_X * MM, row_y * MM, 0),
            POCKET_DIAMETER / 2 * MM)

    profiles = adsk.core.ObjectCollection.create()
    for profile in sketch.profiles:
        profiles.add(profile)
    extrudes = root.features.extrudeFeatures
    extrude_input = extrudes.createInput(
        profiles, adsk.fusion.FeatureOperations.CutFeatureOperation)
    extrude_input.setDistanceExtent(
        False,
        adsk.core.ValueInput.createByReal((POCKET_DEPTH + OVERSHOOT) * MM))
    bore = extrudes.add(extrude_input)
    bore.name = "Insert pocket bore"

    body = root.bRepBodies.itemByName("Rear Ear")

    def column(x_mm, y_mm):
        step, start, spans = 0.05, None, []
        z = 60.0
        while z <= PAD_FACE_Z + 0.0001:
            point = adsk.core.Point3D.create(x_mm * MM, y_mm * MM, z * MM)
            inside = body.pointContainment(point) == \
                adsk.fusion.PointContainment.PointInsidePointContainment
            if inside and start is None:
                start = z
            elif not inside and start is not None:
                spans.append((round(start, 2), round(z - step, 2)))
                start = None
            z += step
        if start is not None:
            spans.append((round(start, 2), PAD_FACE_Z))
        return spans

    for row_y in POCKET_ROWS:
        print(f"  pocket y={row_y}: solid z {column(POCKET_X, row_y)}")
    print(f"  beside the pocket: solid z {column(-5.0, POCKET_ROWS[0])}")
    print(f"  timeline now {design.timeline.count} items")
