"""Every number the shared duct is built from, in one importable place.

The upstream project put its constants at the top of each Fusion script, which
worked while each part was built once and checked by eye. This fork cannot do
that. The plate is the only genuinely new part, and it has to agree with three
things at once: the ears it bolts to, the fan it carries, and the mesh builder
that lets someone without a Fusion licence print it. Three copies of 133.35
would have drifted by the second commit.

So the constants live here, this module imports nothing outside the standard
library, and both `build_shared_fan_plate.py` (Fusion) and
`build_shared_fan_plate_mesh.py` (local trimesh) read from it.

All lengths are millimetres. The Fusion scripts convert with their own MM
factor, because the Fusion API works in centimetres.
"""

# --- The rack -------------------------------------------------------------

RACK_UNIT = 44.45
RACK_UNITS = 3  # laptops sharing the duct; 2 also builds, see FAN_SIZES
DUCT_HEIGHT = RACK_UNITS * RACK_UNIT  # 133.35 at three

# --- The rear ear, as built by build_rear_ear_v2.py -----------------------
# The plate keys into these; they are not ours to change.

EAR_DEPTH = 72.0  # duct rail plane to the pad face
EAR_OFFSET_X = 110.32  # ear local x=-15 lands at global x=95.32
EAR_WALL = 2.0  # duct rail wall
EAR_SLOT_HEIGHT = 2.4  # duct rail slot
GROOVE_FLOOR_X = 97.32  # ear groove floor, per side
BOSS_X = 102.82  # M3 insert bosses, per side
BOSS_ROWS_PER_UNIT = (15.0, 29.45)  # within one rack unit

# --- The plate ------------------------------------------------------------

PLATE_WIDTH = 222.0
PLATE_EDGE_INSET = 0.4  # keeps the plate off the cabinet's inner corners
PLATE_Y0 = PLATE_EDGE_INSET
PLATE_Y1 = DUCT_HEIGHT - PLATE_EDGE_INSET
PLATE_THICKNESS = 4.0

SCREW_CLEAR_DIA = 3.4
HEAD_CBORE_DIA = 6.5
HEAD_CBORE_DEPTH = 2.0

# --- The duct walls, grown forward off the plate --------------------------
# Only two, at the very top and the very bottom of the stack. Every rack unit
# in between keeps its duct rails, but they open into the shared plenum and are
# closed at their outboard end by the ear itself, so they are dead-end grooves
# rather than leak paths. Filling them would divide the plenum, which is the
# one thing this fork exists to avoid.

WALL_HALF_WIDTH = 194.44 / 2  # reaches into the duct rails, as upstream
WALL_THICKNESS = 2.2
WALL_DEPTH = EAR_DEPTH
SLOT_SLACK = (EAR_SLOT_HEIGHT - WALL_THICKNESS) / 2  # centre it in the slot
WALL_BANDS = (
    (EAR_WALL + SLOT_SLACK, EAR_WALL + SLOT_SLACK + WALL_THICKNESS),
    (
        DUCT_HEIGHT - EAR_WALL - SLOT_SLACK - WALL_THICKNESS,
        DUCT_HEIGHT - EAR_WALL - SLOT_SLACK,
    ),
)

# --- The fan --------------------------------------------------------------
# A stock PC case fan on 12 V, so a drawer of pulled case fans is a valid BOM.
# Frame, screw pitch and hole size are the sizes every vendor already builds
# to; only the opening is ours, sized to clear the corner screw holes.

FAN_SIZES = {
    80: {"frame": 80.0, "opening": 76.0, "pitch": 71.5, "depth": 25.0},
    92: {"frame": 92.0, "opening": 88.0, "pitch": 82.5, "depth": 25.0},
    120: {"frame": 120.0, "opening": 114.0, "pitch": 105.0, "depth": 25.0},
}
FAN_SIZE = 120
FAN_FRAME = FAN_SIZES[FAN_SIZE]["frame"]
FAN_OPENING_DIA = FAN_SIZES[FAN_SIZE]["opening"]
FAN_SCREW_PITCH = FAN_SIZES[FAN_SIZE]["pitch"]
FAN_DEPTH = FAN_SIZES[FAN_SIZE]["depth"]
FAN_SCREW_DIA = 4.5  # clearance for M4 or #6-32, the two the fans ship with
FAN_CENTRE_X = 0.0
FAN_CENTRE_Y = DUCT_HEIGHT / 2

# An inlet chamfer on the duct side of the opening. A sharp-edged hole in a
# 4 mm plate makes the flow separate at the lip, so the throat that actually
# passes air is smaller than the one that was cut. That costs more here than it
# would have upstream, because check_rear_assembly measures the opening as the
# restriction -- 10,207 mm2 against 13,649 of plenum. Easing the inlet is the
# cheapest thing that helps.
#
# It is free to print. The plate goes on the bed rear-face-down, so the duct
# side faces up and the hole widens as it rises: every layer sits fully on the
# one below, and none of it is an overhang. It costs nothing on the fan side
# either -- the chamfer stops 1 mm short of the rear face, so the land the fan
# frame seals against is untouched at its full 3 mm width.
FAN_INLET_CHAMFER = 3.0

# --- Zip-tie slots --------------------------------------------------------
# One lead now instead of nine, so one run and two tie pairs: the first catches
# it off the fan frame, the second is strain relief where it leaves the plate.
# Both straddle the lead in y, because the lead runs in x and a tie has to
# cross what it holds. 9.5 mm apart threads and cinches a sleeved four-wire
# case-fan lead; the run is at the fan's mid-height, the widest clear span the
# plate has between the opening edge and the boss column.

TIE_SLOT_X = (72.0, 92.0)
TIE_SLOT_Y = (FAN_CENTRE_Y - 4.75, FAN_CENTRE_Y + 4.75)
TIE_SLOT_W = 2.5
TIE_SLOT_H = 5.0


def boss_rows():
    """Every M3 mounting row up the stack, one pair per rack unit."""
    return [
        unit_index * RACK_UNIT + row
        for unit_index in range(RACK_UNITS)
        for row in BOSS_ROWS_PER_UNIT
    ]


def fan_screw_centres():
    """The four fan corner holes, at the pitch the fan is drilled to."""
    half_pitch = FAN_SCREW_PITCH / 2
    return [
        (FAN_CENTRE_X + dx, FAN_CENTRE_Y + dy)
        for dx in (-half_pitch, half_pitch)
        for dy in (-half_pitch, half_pitch)
    ]


def check_fits():
    """Fail loudly if the chosen fan cannot live inside the duct.

    Two ways it can fail: the frame is taller than the clear height between the
    duct walls, or the opening runs into the walls and stops sealing. Both are
    silent in CAD -- you get a part that looks right and leaks -- so they are
    asserted here, where every consumer of these numbers sees them.
    """
    clear_height = WALL_BANDS[1][0] - WALL_BANDS[0][1]
    if FAN_FRAME > clear_height:
        raise ValueError(
            f"{FAN_SIZE} mm fan frame ({FAN_FRAME}) will not fit the "
            f"{clear_height:.2f} mm clear height of a {RACK_UNITS}U duct"
        )
    if FAN_OPENING_DIA > clear_height:
        raise ValueError(
            f"fan opening {FAN_OPENING_DIA} exceeds the {clear_height:.2f} mm "
            "clear height; it would cut into the duct walls"
        )
    corner_radius = (FAN_SCREW_PITCH / 2) * 2**0.5
    if FAN_OPENING_DIA / 2 > corner_radius - FAN_SCREW_DIA / 2:
        raise ValueError("fan opening runs into the fan's corner screw holes")
    if FAN_INLET_CHAMFER >= PLATE_THICKNESS:
        raise ValueError("the inlet chamfer would break through the fan's sealing face")
    chamfered_dia = FAN_OPENING_DIA + 2 * FAN_INLET_CHAMFER
    if chamfered_dia > clear_height:
        raise ValueError("the chamfered opening would cut into the duct walls")
    if FAN_FRAME / 2 > BOSS_X - HEAD_CBORE_DIA / 2:
        raise ValueError("fan frame overlaps the M3 mounting bosses")
    return clear_height
