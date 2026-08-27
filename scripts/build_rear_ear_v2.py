"""Fusion 360 script: build Rear Ear v2 = existing Rear Ear + fan plate bosses.

Run inside Fusion via the MCP execute tool with the 'MacBook Pro Rear Ear'
document open. Copies the proven 'Rear Ear' and 'Back Plate' bodies unchanged,
fuses them, and adds two bosses on the back plate's rear face sized for CNC
Kitchen M3 x 3 SHORT heat-set inserts (hole diameter 4.0, depth 3.2). The
result lands in a new unsaved direct-modeling document as one printable body.

The bosses live in a single full-height rib (9 wide x 3 proud, z = 69..72)
running down the plate's rear face on the rod line (x = -7.5). The rib
lands the fan plate at the same 3 mm standoff as the earlier round pads but
seals the side gap between the back plate and the fan plate, so the duct can't
draw leak air around the plate edges. Insert pockets sit at y = 15.0 and
29.45 — symmetric about the 1U mid-height (22.225), clear of the 8 mm rod
holes — and are blind, leaving 1.8 mm of plate in front so nothing pokes
the laptop's rear edge.
"""

import adsk.core
import adsk.fusion

MM = 0.1  # Fusion API lengths are in cm

SOURCE_DOC = "MacBook Pro Rear Ear"
SOURCE_BODIES = ("Rear Ear", "Back Plate")

BOSS_X = -7.5
BOSS_ROWS = (15.0, 29.45)
RIB_WIDTH = 15.0   # full plate face: one flat landing level at the rear
RIB_Y_MIN = 0.0
RIB_Y_MAX = 44.45
RIB_Z_START = 69.0
# Heat-set variant (default): pocket for CNC Kitchen M3 x 3 short inserts.
# Self-tap variant (no inserts): set INSERT_HOLE_DIA = 2.5 and
# INSERT_HOLE_DEPTH = 3.5 — the M3 screw thread-forms into the PETG. 3.5 rather
# than the plate's full depth so 1.5 mm of floor is left under the hole; see
# the note on bridging at SCREW_RELIEF_Z0.
# Nut-trap variant (no inserts, metal threads): set NUT_TRAP = True — the
# rib grows to 5 mm proud and each boss gets a side-loading slot for a
# standard M3 hex nut (a DIN 562 square nut fits the same slot). The fan
# fan plate sits 2 mm further back; the same M3 x 8 screws work, with a relief
# bore so the screw tip stops well short of the laptop-facing plate.
NUT_TRAP = False
RIB_Z_END = 74.0 if NUT_TRAP else 72.0
INSERT_HOLE_DIA = 4.0
INSERT_HOLE_DEPTH = 3.2
SCREW_CLEAR_DIA = 3.4
NUT_SLOT_WIDTH = 5.7          # grips the 5.5 across-flats of an M3 nut
NUT_SLOT_Z0, NUT_SLOT_Z1 = 69.4, 72.1
NUT_SLOT_X0, NUT_SLOT_X1 = -15.1, -4.6  # opens at the pad's inboard face
# The plate under these pockets is printed as a bridge across the open duct,
# so whatever is left beneath a pocket is the first bridged layers with nothing
# above to pull them flat. Keep at least 1.5 mm of floor.
SCREW_RELIEF_Z0 = 68.5        # 1.5 mm of plate before the relief bore starts
# Outboard side wall: the stock ear's outboard face is open behind the 2 mm
# flange, exposing the duct interior to outside air. A 2 mm wall closes it,
# attached along the inboard structure's outer face (x = 0), with a 0.6 mm
# relief step in the laptop band (the laptop's edge nominally reaches
# x = +0.28, so the wall clears it there).
SIDE_WALL_X0, SIDE_WALL_X1 = 0.0, 2.0
SIDE_WALL_Y0, SIDE_WALL_Y1 = 0.0, 44.45
SIDE_WALL_Z0 = 0.0  # wall runs to the pad face (RIB_Z_END): no rear notch
LAPTOP_RELIEF_X1 = 0.65
LAPTOP_RELIEF_Y0, LAPTOP_RELIEF_Y1 = 9.7, 34.7
# The laptop's rear edge stops at z = 67, so the relief only needs to run
# that far; the wall stays full thickness across the back plate above it.
LAPTOP_RELIEF_Z0, LAPTOP_RELIEF_Z1 = -0.1, 67.1
# The stock ear's rod bores are exactly tangent to the laptop slot faces
# (rod center 6.22/38.23 + r4 = faces at 10.22/34.23), which produces
# non-manifold edges that slicers report as open. Relieving the slot faces
# 0.12 mm in the rod band makes the intersections transversal; the laptop
# rides on the rods either way.
TANGENCY_X0, TANGENCY_X1 = -12.5, -2.5
TANGENCY_Y0, TANGENCY_Y1 = 10.10, 34.35
# Capture channels for the separate duct panels (modular build). The panels
# slide in from the rear along these and the fan plate caps them, so the duct
# stays with the rack when the fan plate comes off.
#
# A groove cut into the inner face alone gripped the panel over only 2 mm and
# left a 0.4 mm lip at the 1U edge. Instead the material is added inboard: a
# duct rail projects into the empty space above and below the laptop and carries
# the slot with it, so the panel is held over 12 mm at the same size. Walls are
# 2 mm to match the rest of the design and the slot is 2.4 for a 2.0 panel,
# which leaves 0.2 mm of slip per face.
DUCT_GROOVE = True
INNER_FACE_X = -15.0
DUCT_RAIL_LENGTH = 10.0   # reach toward the rack centre from the inner face
DUCT_SLOT_HEIGHT = 2.4
DUCT_WALL = 2.0
GROOVE_DEPTH = 2.0        # pocket into the ear's own inner face
RAIL_X0 = INNER_FACE_X - DUCT_RAIL_LENGTH
RAIL_BLOCK_HEIGHT = 2 * DUCT_WALL + DUCT_SLOT_HEIGHT
RAIL_Z0, RAIL_Z1 = 0.0, 72.0
GROOVE_X0, GROOVE_X1 = RAIL_X0 - 0.1, INNER_FACE_X + GROOVE_DEPTH
GROOVE_BOTTOM_Y0 = DUCT_WALL
GROOVE_BOTTOM_Y1 = DUCT_WALL + DUCT_SLOT_HEIGHT
GROOVE_TOP_Y0 = RIB_Y_MAX - DUCT_WALL - DUCT_SLOT_HEIGHT
GROOVE_TOP_Y1 = RIB_Y_MAX - DUCT_WALL
GROOVE_Z0, GROOVE_Z1 = -0.1, 72.1


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
    source_root = source_design.rootComponent

    temp_mgr = adsk.fusion.TemporaryBRepManager.get()

    combined = None
    for body_name in SOURCE_BODIES:
        source_body = source_root.bRepBodies.itemByName(body_name)
        if source_body is None:
            raise RuntimeError("Body '%s' not found" % body_name)
        copy = temp_mgr.copy(source_body)
        if combined is None:
            combined = copy
        else:
            temp_mgr.booleanOperation(
                combined, copy, adsk.fusion.BooleanTypes.UnionBooleanType)

    def cylinder(x_mm, y_mm, z0_mm, z1_mm, dia_mm):
        return temp_mgr.createCylinderOrCone(
            adsk.core.Point3D.create(x_mm * MM, y_mm * MM, z0_mm * MM),
            dia_mm / 2 * MM,
            adsk.core.Point3D.create(x_mm * MM, y_mm * MM, z1_mm * MM),
            dia_mm / 2 * MM)

    rib_center = adsk.core.Point3D.create(
        BOSS_X * MM, (RIB_Y_MIN + RIB_Y_MAX) / 2 * MM,
        (RIB_Z_START + RIB_Z_END) / 2 * MM)
    rib = temp_mgr.createBox(adsk.core.OrientedBoundingBox3D.create(
        rib_center,
        adsk.core.Vector3D.create(1, 0, 0),
        adsk.core.Vector3D.create(0, 1, 0),
        RIB_WIDTH * MM, (RIB_Y_MAX - RIB_Y_MIN) * MM,
        (RIB_Z_END - RIB_Z_START) * MM))
    temp_mgr.booleanOperation(
        combined, rib, adsk.fusion.BooleanTypes.UnionBooleanType)
    def slab(x0_mm, x1_mm, y0_mm, y1_mm, z0_mm, z1_mm):
        center = adsk.core.Point3D.create(
            (x0_mm + x1_mm) / 2 * MM, (y0_mm + y1_mm) / 2 * MM,
            (z0_mm + z1_mm) / 2 * MM)
        return temp_mgr.createBox(adsk.core.OrientedBoundingBox3D.create(
            center,
            adsk.core.Vector3D.create(1, 0, 0),
            adsk.core.Vector3D.create(0, 1, 0),
            abs(x1_mm - x0_mm) * MM, abs(y1_mm - y0_mm) * MM,
            abs(z1_mm - z0_mm) * MM))

    tangency_relief = slab(TANGENCY_X0, TANGENCY_X1,
                           TANGENCY_Y0, TANGENCY_Y1, -1.0, 67.0)
    temp_mgr.booleanOperation(
        combined, tangency_relief,
        adsk.fusion.BooleanTypes.DifferenceBooleanType)

    side_wall = slab(SIDE_WALL_X0, SIDE_WALL_X1, SIDE_WALL_Y0, SIDE_WALL_Y1,
                     SIDE_WALL_Z0, RIB_Z_END)
    temp_mgr.booleanOperation(
        combined, side_wall, adsk.fusion.BooleanTypes.UnionBooleanType)
    laptop_relief = slab(-0.05, LAPTOP_RELIEF_X1,
                         LAPTOP_RELIEF_Y0, LAPTOP_RELIEF_Y1,
                         LAPTOP_RELIEF_Z0, LAPTOP_RELIEF_Z1)
    temp_mgr.booleanOperation(
        combined, laptop_relief, adsk.fusion.BooleanTypes.DifferenceBooleanType)

    if DUCT_GROOVE:
        # Add the duct rails first, then cut the slot through rail and ear together
        # so the panel still bottoms out on the original groove floor.
        for y0, y1 in ((RIB_Y_MIN, RIB_Y_MIN + RAIL_BLOCK_HEIGHT),
                       (RIB_Y_MAX - RAIL_BLOCK_HEIGHT, RIB_Y_MAX)):
            rail = slab(RAIL_X0, INNER_FACE_X, y0, y1, RAIL_Z0, RAIL_Z1)
            temp_mgr.booleanOperation(
                combined, rail, adsk.fusion.BooleanTypes.UnionBooleanType)
        for y0, y1 in ((GROOVE_BOTTOM_Y0, GROOVE_BOTTOM_Y1),
                       (GROOVE_TOP_Y0, GROOVE_TOP_Y1)):
            groove = slab(GROOVE_X0, GROOVE_X1, y0, y1, GROOVE_Z0, GROOVE_Z1)
            temp_mgr.booleanOperation(
                combined, groove, adsk.fusion.BooleanTypes.DifferenceBooleanType)

    for boss_y in BOSS_ROWS:
        if NUT_TRAP:
            screw_hole = cylinder(BOSS_X, boss_y, SCREW_RELIEF_Z0,
                                  RIB_Z_END + 0.1, SCREW_CLEAR_DIA)
            temp_mgr.booleanOperation(
                combined, screw_hole,
                adsk.fusion.BooleanTypes.DifferenceBooleanType)
            nut_slot = slab(NUT_SLOT_X0, NUT_SLOT_X1,
                            boss_y - NUT_SLOT_WIDTH / 2,
                            boss_y + NUT_SLOT_WIDTH / 2,
                            NUT_SLOT_Z0, NUT_SLOT_Z1)
            temp_mgr.booleanOperation(
                combined, nut_slot,
                adsk.fusion.BooleanTypes.DifferenceBooleanType)
        else:
            pocket = cylinder(BOSS_X, boss_y, RIB_Z_END - INSERT_HOLE_DEPTH,
                              RIB_Z_END + 0.1, INSERT_HOLE_DIA)
            temp_mgr.booleanOperation(
                combined, pocket,
                adsk.fusion.BooleanTypes.DifferenceBooleanType)

    new_doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    new_design = adsk.fusion.Design.cast(app.activeProduct)
    new_design.designType = adsk.fusion.DesignTypes.DirectDesignType
    new_body = new_design.rootComponent.bRepBodies.add(combined)
    new_body.name = "Rear Ear v2"

    app.activeViewport.fit()
    bb = new_body.boundingBox
    print("Created document '%s' with body '%s': %.2f x %.2f x %.2f mm, %d faces" % (
        new_doc.name, new_body.name,
        (bb.maxPoint.x - bb.minPoint.x) * 10,
        (bb.maxPoint.y - bb.minPoint.y) * 10,
        (bb.maxPoint.z - bb.minPoint.z) * 10,
        new_body.faces.count))
