"""Fusion 360 script: the ducted fan plate, an alternative to the modular duct.

Run inside Fusion via the MCP execute tool. Creates a new parametric document
with named sketches and features, per the project rule that everything built
here stays editable.

One part instead of three: the fan plate with the two duct walls grown onto
it. The walls are 194.44 mm wide, the same as the separate duct panels, so
they slide into the duct rails on the rear ears exactly as the panels do. That
matters -- the original one-piece version had 189.60 mm walls that stopped
0.52 mm short of each ear, leaving an open slot down all four edges straight
to ambient at the fan inlet. Reaching the rails closes it by construction, and
the capture groove the modular plate needs disappears with it.

Three fan openings, not four. The duct's own free area is about 3880 mm2 with
a MacBook in it; three Ø39 openings are 3584, which is where the openings stop
being the restriction and the duct starts. Two would be 2389, throttling the
duct to 62% and leaving a 47.7 mm fan-free span across the middle of the
laptop. Four is past the crossover and buys noise rather than air.

Positions are the centroids of three equal-width zones across the duct, so
each fan draws its own third: x = 0 and +/-63.55.

The trade against the modular duct: the fan count is fixed in the geometry
here. Three is the least painful number to fix it at, since there is nothing
above it worth adding.
"""

import adsk.core
import adsk.fusion

MM = 0.1  # Fusion API lengths are in cm

RACK_UNIT = 44.45
PLATE_WIDTH = 222.0
PLATE_Y0, PLATE_Y1 = 0.4, 44.05
PLATE_THICKNESS = 4.0

# Duct walls, grown forward off the plate's front face into the duct rails.
WALL_HALF_WIDTH = 194.44 / 2      # matches the separate duct panels
WALL_THICKNESS = 2.2
WALL_DEPTH = 72.0                 # rail plane to the plate's front face
EAR_WALL, EAR_SLOT_HEIGHT = 2.0, 2.4   # the rail slot, build_rear_ear_v2.py
_SLOT_SLACK = (EAR_SLOT_HEIGHT - WALL_THICKNESS) / 2   # centre it in the slot
WALL_BANDS = (
    (EAR_WALL + _SLOT_SLACK, EAR_WALL + _SLOT_SLACK + WALL_THICKNESS),
    (RACK_UNIT - EAR_WALL - _SLOT_SLACK - WALL_THICKNESS,
     RACK_UNIT - EAR_WALL - _SLOT_SLACK),
)

# Mounting into the rear ear insert bosses
BOSS_X = 102.82
BOSS_ROWS = (15.0, 29.45)
SCREW_CLEAR_DIA = 3.4
HEAD_CBORE_DIA = 6.5
HEAD_CBORE_DEPTH = 2.0

# Fans: Noctua NF-A4x20 5V, unchanged from the four-fan plate
FAN_CENTRES_X = (-63.55, 0.0, 63.55)
FAN_CENTRE_Y = 22.225
FAN_OPENING_DIA = 39.0
FAN_SCREW_PITCH = 32.0
FAN_SCREW_DIA = 3.6

# Zip-tie slot pairs: one per fan. Each fan's lead is tied down in the first
# clear span it reaches heading toward the USB supply, and the outboard pair
# is strain relief where the bundle leaves. This makes the plate handed --
# route the bundle the other way and there is no outboard tie on that side. The fan fills the unit to within 1.8 mm top and bottom,
# so those spans are the only places a lead can cross the plate -- and the
# NF-A4x20's lead leaves the side of the frame at the plate face, landing
# straight in one. Each fan's lead is tied in the adjacent span; the outboard
# pair is strain relief where the bundle leaves for the USB supply.
#
# The pair straddles the lead in y, because the bundle runs along the plate in
# x and a tie has to cross what it holds. 9.5 mm apart is enough to thread and
# cinch a ~3 mm three-wire lead; the previous 16 mm let it wander. Both rows
# clear the fan screw holes at y = 6.225 and 38.225.
TIE_SLOT_X = (-31.78, 31.78, 89.44)
TIE_SLOT_Y = (17.5, 27.0)
TIE_SLOT_W = 2.5
TIE_SLOT_H = 5.0


def run(_context: str):
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

    def cut_through(sketch, name, depth=PLATE_THICKNESS):
        definition = extrudes.createInput(
            all_profiles(sketch), adsk.fusion.FeatureOperations.CutFeatureOperation)
        definition.setDistanceExtent(
            False, adsk.core.ValueInput.createByReal(depth * MM))
        feature = extrudes.add(definition)
        feature.name = name
        return feature

    # 1. The plate itself
    plate_sketch = root.sketches.add(root.xYConstructionPlane)
    plate_sketch.name = "Plate"
    plate_sketch.sketchCurves.sketchLines.addTwoPointRectangle(
        point(-PLATE_WIDTH / 2, PLATE_Y0), point(PLATE_WIDTH / 2, PLATE_Y1))
    definition = extrudes.createInput(
        plate_sketch.profiles.item(0),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    definition.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(PLATE_THICKNESS * MM))
    plate = extrudes.add(definition)
    plate.name = "Plate"
    body = plate.bodies.item(0)
    body.name = "Ducted Fan Plate"

    # 2. The duct walls, forward off the front face
    wall_sketch = root.sketches.add(root.xYConstructionPlane)
    wall_sketch.name = "Duct walls"
    for band_y0, band_y1 in WALL_BANDS:
        wall_sketch.sketchCurves.sketchLines.addTwoPointRectangle(
            point(-WALL_HALF_WIDTH, band_y0), point(WALL_HALF_WIDTH, band_y1))
    definition = extrudes.createInput(
        all_profiles(wall_sketch),
        adsk.fusion.FeatureOperations.JoinFeatureOperation)
    definition.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(-WALL_DEPTH * MM))
    walls = extrudes.add(definition)
    walls.name = "Duct walls"

    # 3. Fan openings, fan screw holes and the M3 mounting holes
    cut_sketch = root.sketches.add(root.xYConstructionPlane)
    cut_sketch.name = "Openings and holes"
    circles = cut_sketch.sketchCurves.sketchCircles
    for fan_x in FAN_CENTRES_X:
        circles.addByCenterRadius(
            point(fan_x, FAN_CENTRE_Y), FAN_OPENING_DIA / 2 * MM)
        for dx in (-FAN_SCREW_PITCH / 2, FAN_SCREW_PITCH / 2):
            for dy in (-FAN_SCREW_PITCH / 2, FAN_SCREW_PITCH / 2):
                circles.addByCenterRadius(
                    point(fan_x + dx, FAN_CENTRE_Y + dy), FAN_SCREW_DIA / 2 * MM)
    for hole_x in (-BOSS_X, BOSS_X):
        for hole_y in BOSS_ROWS:
            circles.addByCenterRadius(
                point(hole_x, hole_y), SCREW_CLEAR_DIA / 2 * MM)
    cut_through(cut_sketch, "Openings and holes")

    # 4. Zip-tie slots
    tie_sketch = root.sketches.add(root.xYConstructionPlane)
    tie_sketch.name = "Tie slots"
    for slot_x in TIE_SLOT_X:
        for slot_y in TIE_SLOT_Y:
            tie_sketch.sketchCurves.sketchLines.addTwoPointRectangle(
                point(slot_x - TIE_SLOT_W / 2, slot_y - TIE_SLOT_H / 2),
                point(slot_x + TIE_SLOT_W / 2, slot_y + TIE_SLOT_H / 2))
    cut_through(tie_sketch, "Tie slots")

    # 5. Counterbores for the M3 heads, from the rear face
    plane_input = root.constructionPlanes.createInput()
    plane_input.setByOffset(
        root.xYConstructionPlane,
        adsk.core.ValueInput.createByReal(PLATE_THICKNESS * MM))
    rear_plane = root.constructionPlanes.add(plane_input)
    rear_plane.name = "Rear face"
    cbore_sketch = root.sketches.add(rear_plane)
    cbore_sketch.name = "Head counterbores"
    for hole_x in (-BOSS_X, BOSS_X):
        for hole_y in BOSS_ROWS:
            cbore_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                point(hole_x, hole_y), HEAD_CBORE_DIA / 2 * MM)
    cut_through(cbore_sketch, "Head counterbores", -HEAD_CBORE_DEPTH)

    box = body.boundingBox
    app.activeViewport.fit()
    print("Created '%s' with body '%s' (%d faces)" % (
        doc.name, body.name, body.faces.count))
    print("  extents mm: x %.2f..%.2f  y %.2f..%.2f  z %.2f..%.2f" % (
        box.minPoint.x / MM, box.maxPoint.x / MM,
        box.minPoint.y / MM, box.maxPoint.y / MM,
        box.minPoint.z / MM, box.maxPoint.z / MM))
    print("  fan openings at x %s" % (list(FAN_CENTRES_X),))
    print("  duct walls y %s, %.2f mm thick, %.2f mm wide" % (
        [tuple(round(v, 2) for v in band) for band in WALL_BANDS],
        WALL_THICKNESS, 2 * WALL_HALF_WIDTH))
