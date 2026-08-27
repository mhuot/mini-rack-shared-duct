"""Fusion 360 script: build the 1U rear exhaust fan plate for the MacBook Pro tray.

Run inside Fusion via the MCP execute tool. Creates a new unsaved design
document containing a single body, "Rear Fan Plate".

v2 — mounts to the REAR EAR BACK PLATES, not the rack rails. The rear ears
extend 67 mm behind the rear rail (rear_depth 65 + thickness 2), so the plate
sits just behind the laptop's rear edge, screwed with M3 socket-head screws
into CNC Kitchen M3 x 3 short heat-set inserts in the Rear Ear v2 bosses
(built by build_rear_ear_v2.py).

Design intent (all values in mm):
- Back plates span x = 95.3..110.3 per side (rod line at +/-102.82); the plate
  is 222 wide so its tabs cover the plates while 4x Noctua NF-A4x20 5V fans
  (40x40x20, 32 mm screw pitch) nest between them, exhausting rearward.
- Plate front face lands on the ear bosses' 3 mm pads; total stack behind the
  rear rail = 69 (ear) + 3 (pad) + 4 (plate) + 20 (fan) = 96 mm.
- Integrated duct shell: 1.8 mm top and bottom panels project 72 mm forward
  from the plate face, spanning between the ear inner faces (x = +/-95.3) and
  reaching the rear rail plane. The panels sit inboard of the ear flanges and
  of the rack posts, so they run into the open 1U slot with nothing to foul.
  With the ear frames closing the sides, the fans can only draw air from
  inside the rack, through the channels above the lid and under the chassis,
  instead of short-circuiting from the open air around the rear overhang.
"""

import adsk.core
import adsk.fusion

MM = 0.1  # Fusion API lengths are in cm

# Overall plate
PLATE_WIDTH = 222.0
PLATE_Y_MIN = 0.4
PLATE_Y_MAX = 44.05
PLATE_THICKNESS = 4.0

# Mounting into Rear Ear v2 insert bosses (M3 socket-head screws)
BOSS_X = 102.82          # rod line: rail hole span/2 - 15.44
BOSS_ROWS = (15.0, 29.45)  # symmetric about U mid-height 22.225, clear of rod bores
SCREW_CLEAR_DIA = 3.4
HEAD_CBORE_DIA = 6.5
HEAD_CBORE_DEPTH = 2.0

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
TIE_SLOT_W = 2.5          # across the plate
TIE_SLOT_H = 5.0          # along the plate

# Fans: Noctua NF-A4x20 5V, three of them at the centroids of three equal
# zones across the duct. The duct's own free area is about 3880 mm2 with a
# MacBook in it; three Ø39 openings are 3584, which is the crossover where
# the openings stop being the restriction. Four was 4778, past it.
FAN_CENTERS_X = (-63.55, 0.0, 63.55)
FAN_CENTER_Y = 22.225
FAN_OPENING_DIA = 39.0
FAN_SCREW_PITCH = 32.0
FAN_SCREW_DIA = 3.6

# Duct panel capture. The panels are held only in the duct rails, 10 mm at each
# end, which leaves 170 mm of free 2 mm sheet whose rear edge has nothing
# holding it against this plate. Butted like that it cannot seal. A shallow
# groove in the front face turns the butt into a lap: the panel grows to 73 mm
# and its last millimetre lands in here, which seals the joint and pulls the
# edge flat at the same time.
#
# Along the panel line each fan opening is only ~8.6 mm wide in x, so the groove
# is solid for about 69% of the panel edge; the rest opens into a fan opening,
# which is where the air is going anyway.
DUCT_GROOVE = True
GROOVE_DEPTH = 2.0        # 2 mm of lap in a 4 mm plate
GROOVE_X_HALF = 97.6      # covers the 194.44 panel, stops short of the bosses
PANEL_THICKNESS = 2.0
EAR_WALL = 2.0            # duct rail wall in build_rear_ear_v2.py
EAR_SLOT_HEIGHT = 2.4     # duct rail slot in build_rear_ear_v2.py
RACK_UNIT = 44.45

# The groove is the duct rail slot continued, not a tighter version of it. The panel
# has 0.4 mm of play in the duct rail and gravity rests it on the rail's lower
# wall, so a groove sized to the panel rather than to the slot would sit 0.1 mm
# high and the plate would jam on the panel edge instead of seating on the pads.
GROOVE_BANDS = (
    (EAR_WALL, EAR_WALL + EAR_SLOT_HEIGHT),
    (RACK_UNIT - EAR_WALL - EAR_SLOT_HEIGHT, RACK_UNIT - EAR_WALL),
)
# Note: this puts the groove's inner wall 0.025 mm from the fan screw holes
# (Ø3.6 on the 32 mm Noctua pitch, nearest edge y=4.425). That wall cannot be
# printed and the two will merge. It is harmless -- the screw fills the hole and
# the far end dead-ends in the fan's own boss -- but it is deliberate, not an
# oversight. The panel line and the fan screw line are 0.225 mm apart; nothing
# short of moving the fans changes that.


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
        for i in range(sketch.profiles.count):
            collection.add(sketch.profiles.item(i))
        return collection

    # 1. Base plate
    plate_sketch = root.sketches.add(root.xYConstructionPlane)
    plate_sketch.sketchCurves.sketchLines.addTwoPointRectangle(
        point(-PLATE_WIDTH / 2, PLATE_Y_MIN), point(PLATE_WIDTH / 2, PLATE_Y_MAX))
    plate = extrudes.addSimple(
        plate_sketch.profiles.item(0),
        adsk.core.ValueInput.createByReal(PLATE_THICKNESS * MM),
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    body = plate.bodies.item(0)
    body.name = "Rear Fan Plate"

    # 2. Fan openings + fan screw holes + M3 mounting holes (all through-cuts)
    cut_sketch = root.sketches.add(root.xYConstructionPlane)
    circles = cut_sketch.sketchCurves.sketchCircles
    for fan_x in FAN_CENTERS_X:
        circles.addByCenterRadius(point(fan_x, FAN_CENTER_Y), FAN_OPENING_DIA / 2 * MM)
        for dx in (-FAN_SCREW_PITCH / 2, FAN_SCREW_PITCH / 2):
            for dy in (-FAN_SCREW_PITCH / 2, FAN_SCREW_PITCH / 2):
                circles.addByCenterRadius(
                    point(fan_x + dx, FAN_CENTER_Y + dy), FAN_SCREW_DIA / 2 * MM)
    for hole_x in (-BOSS_X, BOSS_X):
        for hole_y in BOSS_ROWS:
            circles.addByCenterRadius(point(hole_x, hole_y), SCREW_CLEAR_DIA / 2 * MM)
    through_cut = extrudes.createInput(
        all_profiles(cut_sketch), adsk.fusion.FeatureOperations.CutFeatureOperation)
    through_cut.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(PLATE_THICKNESS * MM))
    extrudes.add(through_cut)

    # 3. Zip-tie slots for the fan wiring
    tie_sketch = root.sketches.add(root.xYConstructionPlane)
    for slot_x in TIE_SLOT_X:
        for slot_y in TIE_SLOT_Y:
            tie_sketch.sketchCurves.sketchLines.addTwoPointRectangle(
                point(slot_x - TIE_SLOT_W / 2, slot_y - TIE_SLOT_H / 2),
                point(slot_x + TIE_SLOT_W / 2, slot_y + TIE_SLOT_H / 2))
    tie_cut = extrudes.createInput(
        all_profiles(tie_sketch), adsk.fusion.FeatureOperations.CutFeatureOperation)
    tie_cut.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(PLATE_THICKNESS * MM))
    extrudes.add(tie_cut)

    # 4. Counterbores for the M3 screw heads, cut from the rear face
    planes = root.constructionPlanes
    plane_input = planes.createInput()
    plane_input.setByOffset(
        root.xYConstructionPlane,
        adsk.core.ValueInput.createByReal(PLATE_THICKNESS * MM))
    rear_plane = planes.add(plane_input)
    cbore_sketch = root.sketches.add(rear_plane)
    for hole_x in (-BOSS_X, BOSS_X):
        for hole_y in BOSS_ROWS:
            cbore_sketch.sketchCurves.sketchCircles.addByCenterRadius(
                point(hole_x, hole_y), HEAD_CBORE_DIA / 2 * MM)
    cbore_cut = extrudes.createInput(
        all_profiles(cbore_sketch), adsk.fusion.FeatureOperations.CutFeatureOperation)
    cbore_cut.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(-HEAD_CBORE_DEPTH * MM))
    extrudes.add(cbore_cut)

    # 5. Duct panel capture grooves in the front face (the face that lands on
    #    the ear pads). Cut last so it takes whatever the fan openings left.
    if DUCT_GROOVE:
        groove_sketch = root.sketches.add(root.xYConstructionPlane)
        for band_y0, band_y1 in GROOVE_BANDS:
            groove_sketch.sketchCurves.sketchLines.addTwoPointRectangle(
                point(-GROOVE_X_HALF, band_y0), point(GROOVE_X_HALF, band_y1))
        groove_cut = extrudes.createInput(
            all_profiles(groove_sketch),
            adsk.fusion.FeatureOperations.CutFeatureOperation)
        groove_cut.setDistanceExtent(
            False, adsk.core.ValueInput.createByReal(GROOVE_DEPTH * MM))
        extrudes.add(groove_cut)

    app.activeViewport.fit()
    print("Created document '%s' with body '%s' (%d faces)" % (
        doc.name, body.name, body.faces.count))
    for band_y0, band_y1 in GROOVE_BANDS:
        print("  capture groove y %.2f..%.2f, %.1f deep, x +/-%.1f" % (
            band_y0, band_y1, GROOVE_DEPTH, GROOVE_X_HALF))
