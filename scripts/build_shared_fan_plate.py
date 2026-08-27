"""Fusion 360 script: the shared duct fan plate.

Run inside Fusion via the MCP execute tool. Creates a new parametric document
with named sketches and features, per the project rule that everything built
here stays editable.

One plate spanning three rack units, carrying one 120 mm case fan, closing the
back of a duct that all three laptops share. Upstream this part existed once
per tray: three 40 mm fans pulling through a 44.45 mm duct with its own top
and bottom panels. Stacking three of those means nine fans, nine leads and
three separate ducts that cannot help each other.

What makes the shared version cheap is that the rear ears already do the hard
part. Each ear fills its rack unit exactly, so three stacked pairs butt flush
and their outboard side walls become one continuous 133.35 mm wall -- the duct
sides seal without a new part. Only the top and bottom need closing, so the
plate grows two walls instead of six, and the four duct rails in between are
left empty on purpose. They are closed at their outboard end by the ear body,
which makes them dead-end grooves rather than leak paths, and filling them
would divide the plenum this whole fork exists to create.

The fan is a stock PC case fan on 12 V: 120 mm frame, 105 mm screw pitch, the
sizes every vendor already builds to, so a drawer of pulled case fans is a
valid bill of materials. The opening is O114 -- as large as will clear the
fan's own corner screw holes, which sit 74.25 mm out from the centre.

The trade, stated plainly: the opening is now the restriction. The shared
plenum's free area is about 13,350 mm2 and the opening is 10,207, where
upstream's three-fan plate cleared about 92% of its duct. One large fan at low
speed is quieter, needs one lead and one supply, and pulls better against duct
static pressure than nine small ones -- but it is not more nominal airflow.

Geometry comes from shared_duct_params.py so this script and the local mesh
builder cannot disagree about a number.
"""

import os
import sys

import adsk.core
import adsk.fusion

# Fusion runs scripts with the add-in's working directory, not this file's, so
# the sibling import needs help. __file__ is defined when Fusion loads this as
# a script; the fallback covers being exec'd from a string by the MCP tool.
_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else None
for _candidate in (_HERE, os.path.expanduser("~/mini-rack-shared-duct/scripts")):
    if _candidate and _candidate not in sys.path and os.path.isdir(_candidate):
        sys.path.insert(0, _candidate)

import shared_duct_params as params  # noqa: E402  # pylint: disable=wrong-import-position

MM = 0.1  # Fusion API lengths are in cm


def run(_context: str):  # pylint: disable=too-many-locals
    """Build the plate, its duct walls and every opening, then report."""
    params.check_fits()

    app = adsk.core.Application.get()
    doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent
    extrudes = root.features.extrudeFeatures

    def point(x_mm, y_mm, z_mm=0.0):
        return adsk.core.Point3D.create(x_mm * MM, y_mm * MM, z_mm * MM)

    def all_profiles(sketch):
        collection = adsk.core.ObjectCollection.create()
        for index in range(sketch.profiles.count):
            collection.add(sketch.profiles.item(index))
        return collection

    def cut_through(sketch, name, depth=params.PLATE_THICKNESS):
        definition = extrudes.createInput(
            all_profiles(sketch), adsk.fusion.FeatureOperations.CutFeatureOperation
        )
        definition.setDistanceExtent(
            False, adsk.core.ValueInput.createByReal(depth * MM)
        )
        feature = extrudes.add(definition)
        feature.name = name
        return feature

    half_width = params.PLATE_WIDTH / 2

    # 1. The plate itself, spanning the whole stack
    plate_sketch = root.sketches.add(root.xYConstructionPlane)
    plate_sketch.name = "Plate"
    plate_sketch.sketchCurves.sketchLines.addTwoPointRectangle(
        point(-half_width, params.PLATE_Y0), point(half_width, params.PLATE_Y1)
    )
    definition = extrudes.createInput(
        plate_sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    definition.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(params.PLATE_THICKNESS * MM)
    )
    plate = extrudes.add(definition)
    plate.name = "Plate"
    body = plate.bodies.item(0)
    body.name = "Shared Duct Fan Plate"

    # 2. The two duct walls, forward off the front face into the outer rails
    wall_sketch = root.sketches.add(root.xYConstructionPlane)
    wall_sketch.name = "Duct walls"
    for band_y0, band_y1 in params.WALL_BANDS:
        wall_sketch.sketchCurves.sketchLines.addTwoPointRectangle(
            point(-params.WALL_HALF_WIDTH, band_y0),
            point(params.WALL_HALF_WIDTH, band_y1),
        )
    definition = extrudes.createInput(
        all_profiles(wall_sketch), adsk.fusion.FeatureOperations.JoinFeatureOperation
    )
    definition.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(-params.WALL_DEPTH * MM)
    )
    walls = extrudes.add(definition)
    walls.name = "Duct walls"

    # 3. The fan opening, the fan's corner holes and the M3 mounting holes
    cut_sketch = root.sketches.add(root.xYConstructionPlane)
    cut_sketch.name = "Openings and holes"
    circles = cut_sketch.sketchCurves.sketchCircles
    circles.addByCenterRadius(
        point(params.FAN_CENTRE_X, params.FAN_CENTRE_Y),
        params.FAN_OPENING_DIA / 2 * MM,
    )
    for screw_x, screw_y in params.fan_screw_centres():
        circles.addByCenterRadius(
            point(screw_x, screw_y), params.FAN_SCREW_DIA / 2 * MM
        )
    for hole_x in (-params.BOSS_X, params.BOSS_X):
        for hole_y in params.boss_rows():
            circles.addByCenterRadius(
                point(hole_x, hole_y), params.SCREW_CLEAR_DIA / 2 * MM
            )
    cut_through(cut_sketch, "Openings and holes")

    # 4. Zip-tie slots, straddling the one lead this plate now carries
    tie_sketch = root.sketches.add(root.xYConstructionPlane)
    tie_sketch.name = "Tie slots"
    for slot_x in params.TIE_SLOT_X:
        for slot_y in params.TIE_SLOT_Y:
            tie_sketch.sketchCurves.sketchLines.addTwoPointRectangle(
                point(slot_x - params.TIE_SLOT_W / 2, slot_y - params.TIE_SLOT_H / 2),
                point(slot_x + params.TIE_SLOT_W / 2, slot_y + params.TIE_SLOT_H / 2),
            )
    cut_through(tie_sketch, "Tie slots")

    # 5. Counterbores for the M3 heads, from the rear face, so the fan can sit
    #    hard against the plate without riding on a screw head.
    plane_input = root.constructionPlanes.createInput()
    plane_input.setByOffset(
        root.xYConstructionPlane,
        adsk.core.ValueInput.createByReal(params.PLATE_THICKNESS * MM),
    )
    rear_plane = root.constructionPlanes.add(plane_input)
    rear_plane.name = "Rear face"
    cbore_sketch = root.sketches.add(rear_plane)
    cbore_sketch.name = "Head counterbores"
    for hole_x in (-params.BOSS_X, params.BOSS_X):
        for hole_y in params.boss_rows():
            cbore_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                point(hole_x, hole_y), params.HEAD_CBORE_DIA / 2 * MM
            )
    cut_through(cbore_sketch, "Head counterbores", -params.HEAD_CBORE_DEPTH)

    _report(app, doc, body)


def _report(app, doc, body):
    """Print the extents and the numbers worth eyeballing after a rebuild."""
    box = body.boundingBox
    app.activeViewport.fit()
    walls = [tuple(round(v, 2) for v in band) for band in params.WALL_BANDS]
    print(f"Created '{doc.name}' with body '{body.name}' ({body.faces.count} faces)")
    print(
        f"  extents mm: x {box.minPoint.x / MM:.2f}..{box.maxPoint.x / MM:.2f}  "
        f"y {box.minPoint.y / MM:.2f}..{box.maxPoint.y / MM:.2f}  "
        f"z {box.minPoint.z / MM:.2f}..{box.maxPoint.z / MM:.2f}"
    )
    print(
        f"  {params.RACK_UNITS} rack units, one {params.FAN_SIZE} mm fan, "
        f"opening O{params.FAN_OPENING_DIA:.0f}"
    )
    print(
        f"  duct walls y {walls}, {params.WALL_THICKNESS:.2f} mm thick, "
        f"{2 * params.WALL_HALF_WIDTH:.2f} mm wide"
    )
    print(f"  {2 * len(params.boss_rows())} M3 mounting holes into the ear inserts")
