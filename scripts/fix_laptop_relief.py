"""Re-cut the laptop relief in "MacBook Pro Rear Ear v2 Parametric".

Run through the Fusion MCP against that document.

The ear carries a 2 mm outboard side wall so the fans cannot draw leak air
around the ear's open side. The laptop's edge has to pass through that wall,
so a 0.65 mm relief is cut into it across the laptop band.

In the parametric document those two happen in the wrong order: the relief is
cut at timeline item 12 and the side wall is joined at item 18, which fills
the relief back in. The result is a clear opening of 220.64 mm between the
side walls, and a MacBook Pro 14 is 221.20 mm wide -- 0.56 mm too much. The
self-tap and nut-trap variants come from build_rear_ear_v2.py, which unions
the wall before cutting the relief, so they were never affected.

Cutting it again at the end of the timeline restores the 221.94 mm opening
without disturbing the features in between.
"""

import adsk.core
import adsk.fusion

MM = 0.1  # Fusion API lengths are in cm

DOCUMENT = "MacBook Pro Rear Ear v2 Parametric"
RELIEF_X0, RELIEF_X1 = -0.05, 0.65  # into the 2 mm side wall
RELIEF_Y0, RELIEF_Y1 = 9.7, 34.7  # the laptop band
RELIEF_DEPTH = 67.1  # the laptop's rear edge stops at 65


def run(_context: str):
    """Recut the laptop relief on the rear ear."""
    app = adsk.core.Application.get()
    for index in range(app.documents.count):
        if app.documents.item(index).name == DOCUMENT:
            app.documents.item(index).activate()
    if app.activeDocument.name != DOCUMENT:
        raise RuntimeError(f"{DOCUMENT!r} is not open")

    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent
    design.timeline.moveToEnd()

    names = [design.timeline.item(i).name for i in range(design.timeline.count)]
    if "Laptop relief recut" in names:
        raise RuntimeError("Laptop relief recut already exists")

    sketch = root.sketches.add(root.xYConstructionPlane)
    sketch.name = "Laptop relief recut"
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(RELIEF_X0 * MM, RELIEF_Y0 * MM, 0),
        adsk.core.Point3D.create(RELIEF_X1 * MM, RELIEF_Y1 * MM, 0),
    )

    profiles = adsk.core.ObjectCollection.create()
    for profile in sketch.profiles:
        profiles.add(profile)
    extrudes = root.features.extrudeFeatures
    definition = extrudes.createInput(
        profiles, adsk.fusion.FeatureOperations.CutFeatureOperation
    )
    definition.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(RELIEF_DEPTH * MM)
    )
    cut = extrudes.add(definition)
    cut.name = "Laptop relief recut"

    body = root.bRepBodies.itemByName("Rear Ear")

    def solid(x_mm, y_mm, z_mm):
        point = adsk.core.Point3D.create(x_mm * MM, y_mm * MM, z_mm * MM)
        return (
            body.pointContainment(point)
            == adsk.fusion.PointContainment.PointInsidePointContainment
        )

    print(f"  relief void at x=0.3, laptop band : {not solid(0.3, 22.0, 30.0)}")
    print(f"  side wall still there at x=1.3    : {solid(1.3, 22.0, 30.0)}")
    print(f"  wall intact below the laptop      : {solid(0.3, 5.0, 30.0)}")
    print(f"  wall intact above the laptop      : {solid(0.3, 40.0, 30.0)}")
    print(f"  wall intact behind the stop       : {solid(0.3, 22.0, 69.0)}")
    print(f"  timeline now {design.timeline.count} items")
