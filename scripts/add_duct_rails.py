"""Add the duct rails to "MacBook Pro Rear Ear v2 Parametric".

Run through the Fusion MCP against that document. The rails project inboard
from the ear's inner face into the empty 1U space above and below the laptop,
so the duct panel is gripped over 12 mm instead of the 2 mm the bare groove
gave it. The panel itself does not change size.

Everything lands as named sketches and extrudes so the timeline stays editable,
and the four numbers worth tuning become user parameters.
"""

import adsk.core
import adsk.fusion

MM = 0.1  # Fusion works in centimetres

RAIL_LENGTH = 10.0  # how far the rail reaches toward the rack centre
SLOT_HEIGHT = 2.4  # 2.0 mm panel plus 0.2 mm of slip per face
WALL_THICKNESS = 2.0  # matches the 2 mm walls used elsewhere in the design
GROOVE_DEPTH = 2.0  # the original pocket cut into the ear's inner face

INNER_FACE_X = -15.0  # ear face toward the rack centre
EAR_DEPTH = 72.0  # rail plane to fan plate face
RACK_UNIT = 44.45

PARAMETERS = (
    ("duct_rail_length", RAIL_LENGTH, "rail reach toward the rack centre"),
    ("duct_slot_height", SLOT_HEIGHT, "panel thickness plus running clearance"),
    ("duct_wall", WALL_THICKNESS, "wall either side of the panel slot"),
    ("duct_groove_depth", GROOVE_DEPTH, "pocket cut into the ear inner face"),
)


def ensure_parameters(design):
    """Create the tuning parameters, leaving any existing values alone."""
    units = design.unitsManager
    for name, value, comment in PARAMETERS:
        if design.userParameters.itemByName(name) is None:
            design.userParameters.add(
                name,
                adsk.core.ValueInput.createByReal(value * MM),
                units.defaultLengthUnits,
                comment,
            )


def add_rectangle(sketch, x0_mm, y0_mm, x1_mm, y1_mm):
    """A two-point rectangle on a sketch, in millimetres."""
    corner = adsk.core.Point3D.create(x0_mm * MM, y0_mm * MM, 0)
    opposite = adsk.core.Point3D.create(x1_mm * MM, y1_mm * MM, 0)
    return sketch.sketchCurves.sketchLines.addTwoPointRectangle(corner, opposite)


def extrude(component, sketch, operation, distance_mm=None):
    """Extrude every profile on a sketch, joining or cutting."""
    profiles = adsk.core.ObjectCollection.create()
    for profile in sketch.profiles:
        profiles.add(profile)
    features = component.features.extrudeFeatures
    definition = features.createInput(profiles, operation)
    if distance_mm is None:
        definition.setAllExtent(adsk.fusion.ExtentDirections.SymmetricExtentDirection)
    else:
        definition.setDistanceExtent(
            False, adsk.core.ValueInput.createByReal(distance_mm * MM)
        )
    return features.add(definition)


def run(_context: str):
    """Add the duct rails to the parametric rear ear document."""
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent

    if app.activeDocument.name != "MacBook Pro Rear Ear v2 Parametric":
        raise RuntimeError(f"wrong document open: {app.activeDocument.name!r}")

    existing = [design.timeline.item(i).name for i in range(design.timeline.count)]
    if "Duct rail" in existing:
        raise RuntimeError("Duct rail already exists; remove it before rebuilding")

    ensure_parameters(design)

    block_height = 2 * WALL_THICKNESS + SLOT_HEIGHT
    rail_x = INNER_FACE_X - RAIL_LENGTH

    # The added material: one block low, one high, both clear of the laptop.
    rail_sketch = root.sketches.add(root.xYConstructionPlane)
    rail_sketch.name = "Duct rail"
    add_rectangle(rail_sketch, rail_x, 0.0, INNER_FACE_X, block_height)
    add_rectangle(
        rail_sketch, rail_x, RACK_UNIT - block_height, INNER_FACE_X, RACK_UNIT
    )
    rail = extrude(
        root, rail_sketch, adsk.fusion.FeatureOperations.JoinFeatureOperation, EAR_DEPTH
    )
    rail.name = "Duct rail"

    # The slot, cut through the new rail and on into the ear's inner face so
    # the panel still bottoms out against the original groove floor.
    slot_far_x = INNER_FACE_X + GROOVE_DEPTH
    slot_sketch = root.sketches.add(root.xYConstructionPlane)
    slot_sketch.name = "Duct panel slot"
    add_rectangle(
        slot_sketch,
        rail_x - 0.1,
        WALL_THICKNESS,
        slot_far_x,
        WALL_THICKNESS + SLOT_HEIGHT,
    )
    add_rectangle(
        slot_sketch,
        rail_x - 0.1,
        RACK_UNIT - WALL_THICKNESS - SLOT_HEIGHT,
        slot_far_x,
        RACK_UNIT - WALL_THICKNESS,
    )
    slot = extrude(root, slot_sketch, adsk.fusion.FeatureOperations.CutFeatureOperation)
    slot.name = "Duct panel slot"

    body = root.bRepBodies.itemByName("Rear Ear")
    box = body.boundingBox
    print(f"bodies: {[b.name for b in root.bRepBodies]}")
    print(
        f"Rear Ear extents mm: "
        f"x {box.minPoint.x / MM:.2f}..{box.maxPoint.x / MM:.2f}  "
        f"y {box.minPoint.y / MM:.2f}..{box.maxPoint.y / MM:.2f}  "
        f"z {box.minPoint.z / MM:.2f}..{box.maxPoint.z / MM:.2f}"
    )
    print(f"timeline now {design.timeline.count} items")
