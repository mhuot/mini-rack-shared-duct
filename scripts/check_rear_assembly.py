"""Fit the rear parts together and check for interference and air leaks.

Run against the exported STLs, not Fusion:

    python scripts/check_rear_assembly.py

Three questions get answered.

Does it assemble? Every pair of parts is intersected exactly, so any overlap
shows up as a positive volume rather than as a surprise on the bed.

Is the duct sealed? A cross-section is taken by casting one ray along +x per
scan line, which makes the x extents exact and leaves only y sampled. The air
in that section is then flood-filled from a point inside the duct; if the duct
region reaches the edge of the frame, air is getting out somewhere it should
not. Between z~10 and z~60 the parts are prismatic, so a section there holds
for that whole stretch rather than being a spot check.

Is the fan opening big enough? The same cross-section measures the plenum's
free area with the laptops in it, which is the number the opening has to be
compared against. Upstream did this arithmetically from nominal dimensions;
measuring it off the actual meshes catches the case where a part changed and
the prose did not.

What replaced the old panel-seating sweep: the modular duct panels had play in
their rail slots, so the seal had to hold with a panel against either wall.
The one-piece plate has no such play. What it has instead is six ears stacked
three high, and the model butts them at exactly 44.45 mm. A real rack's rail
holes are not perfect, so the gap sweep below opens a deliberate seam between
stacked ears and reports what leaks -- the one failure this fork can have that
upstream could not.

Requires trimesh, numpy, scipy and manifold3d.
"""

import itertools
import math

import numpy as np
import trimesh
from scipy import ndimage

import build_shared_fan_plate_mesh as plate_builder
import shared_duct_params as params
from mesh_helpers import box, mirrored_x

FRAME_X = (-135.0, 135.0)
FRAME_Y = (-2.0, params.DUCT_HEIGHT + 4.0)
SCAN_STEP = 0.02  # resolves a 0.1 mm clearance five times over

# The laptops, only so the free-area figure is the real one. Same numbers as
# render_shared_duct.py; they are reference bodies, not parts.
LAPTOP_SEAT_Y = 10.22
LAPTOP_THICKNESS = {"macbook": 15.5, "surface": 17.5}
LAPTOP_WIDTH = {"macbook": 221.2, "surface": 220.0}
STACK = ("macbook", "surface", "macbook")

# How far apart stacked ears might sit if the rack's rail holes are not exact.
EAR_GAPS = (0.0, 0.2, 0.5)

# Each duct wall stops this far short of the ear's groove floor, per end, so it
# can slide into the duct rail at all. It is the one deliberate hole in the
# duct, and the reason the as-built seal test reports a leak.
SLIDE_CLEARANCE = params.GROOVE_FLOOR_X - params.WALL_HALF_WIDTH


def assemble(ear_gap=0.0, with_laptops=False, seal_walls=False):
    """Place every rear part in the rack frame.

    `ear_gap` opens a seam between vertically stacked ears, standing in for a
    rack whose rail holes are not exactly one rack unit apart. `seal_walls`
    swaps in a plate whose duct walls run all the way to the groove floor,
    which is not buildable -- it is how the tests separate "leaks through the
    slide clearance" from "leaks through a face somebody forgot".
    """
    parts = {}

    ear = trimesh.load_mesh("exports/rear_ear_v2.stl")
    mirrored = mirrored_x(ear)
    for unit_index in range(params.RACK_UNITS):
        unit_y = unit_index * (params.RACK_UNIT + ear_gap)
        for side, source, side_x in (
            ("right", ear, params.EAR_OFFSET_X),
            ("left", mirrored, -params.EAR_OFFSET_X),
        ):
            placed = source.copy()
            placed.apply_translation([side_x, unit_y, 0.0])
            parts[f"ear_{side}_u{unit_index + 1}"] = placed

    if seal_walls:
        plate = plate_builder.build_plate(wall_overhang=SLIDE_CLEARANCE)
    else:
        plate = trimesh.load_mesh("exports/shared_fan_plate.stl")
    plate.apply_translation([0.0, 0.0, params.EAR_DEPTH])
    parts["shared_fan_plate"] = plate

    if with_laptops:
        for unit_index, name in enumerate(STACK):
            unit_y = unit_index * (params.RACK_UNIT + ear_gap) + LAPTOP_SEAT_Y
            parts[f"laptop_u{unit_index + 1}"] = box(
                (-LAPTOP_WIDTH[name] / 2, LAPTOP_WIDTH[name] / 2),
                (unit_y, unit_y + LAPTOP_THICKNESS[name]),
                (-10.0, params.EAR_DEPTH - 7.0),
            )
    return parts


def solid_spans(triangles, y, z):
    """Exact solid intervals along +x through a mesh at (y, z)."""
    origin = np.array([FRAME_X[0] - 50.0, y, z])
    direction = np.array([1.0, 0.0, 0.0])
    corner, edge_a, edge_b = (
        triangles[:, 0],
        triangles[:, 1] - triangles[:, 0],
        triangles[:, 2] - triangles[:, 0],
    )
    pvec = np.cross(direction, edge_b)
    determinant = np.einsum("ij,ij->i", edge_a, pvec)
    usable = np.abs(determinant) > 1e-12
    inverse = np.where(usable, 1.0 / np.where(usable, determinant, 1.0), 0.0)
    to_corner = origin - corner
    bary_u = np.einsum("ij,ij->i", to_corner, pvec) * inverse
    qvec = np.cross(to_corner, edge_a)
    bary_v = np.einsum("j,ij->i", direction, qvec) * inverse
    distance = np.einsum("ij,ij->i", edge_b, qvec) * inverse
    hit = (
        usable & (bary_u >= 0) & (bary_v >= 0) & (bary_u + bary_v <= 1) & (distance > 0)
    )
    crossings = np.sort(origin[0] + distance[hit])
    return [(crossings[i], crossings[i + 1]) for i in range(0, len(crossings) - 1, 2)]


def label_air(parts, z):
    """Label connected air regions in the x-y cross-section at depth z."""
    rows = np.arange(FRAME_Y[0], FRAME_Y[1], SCAN_STEP)
    columns = int((FRAME_X[1] - FRAME_X[0]) / SCAN_STEP)
    solid = np.zeros((len(rows), columns), dtype=bool)
    triangle_sets = [part.triangles for part in parts.values()]
    for row_index, y in enumerate(rows):
        # nudge off exact feature boundaries so grazing rays stay well defined
        for triangles in triangle_sets:
            for start, end in solid_spans(triangles, y + 0.0013, z):
                low = int(np.ceil((start - FRAME_X[0]) / SCAN_STEP))
                high = int(np.floor((end - FRAME_X[0]) / SCAN_STEP))
                if high >= low:
                    solid[row_index, low : high + 1] = True
    labels, _ = ndimage.label(~solid)
    return labels


def region_at(labels, x, y):
    """The air region id at a point, in millimetres."""
    return labels[
        int(round((y - FRAME_Y[0]) / SCAN_STEP)),
        int(round((x - FRAME_X[0]) / SCAN_STEP)),
    ]


def reaches_ambient(labels, region):
    """True if this air region touches the edge of the scanned frame."""
    edges = (
        set(labels[0, :]) | set(labels[-1, :]) | set(labels[:, 0]) | set(labels[:, -1])
    )
    return region in edges


def report_interference(parts):
    """Boolean every pair of parts against each other."""
    print("=== interference (exact boolean, any volume > 0 is a clash) ===")
    clashes = 0
    for (name_a, part_a), (name_b, part_b) in itertools.combinations(parts.items(), 2):
        low_a, high_a = part_a.bounds
        low_b, high_b = part_b.bounds
        if np.any(high_a < low_b) or np.any(high_b < low_a):
            continue
        overlap = trimesh.boolean.intersection([part_a, part_b], engine="manifold")
        volume = 0.0 if overlap is None or overlap.is_empty else overlap.volume
        if volume > 1e-6:
            clashes += 1
            print(f"  CLASH {name_a} vs {name_b}: {volume:.4f} mm3")
    print(f"  {clashes} clash(es)")
    return clashes


def report_seal():
    """Sample the prismatic stretch of the duct, as built and interference-fit.

    As built the duct leaks, and it is supposed to: each wall end stops 0.10 mm
    short of the ear's groove floor so the plate can be assembled at all. What
    matters is that this is the *only* path out, so the same section is run
    against a plate whose walls reach the groove floor. If that one seals, the
    duct has no hole in it beyond the clearance; if it still leaks, something
    is genuinely open and the number below says how much.
    """
    print("\n=== is the shared duct sealed? ===")
    unexplained = []
    for label, seal_walls in (
        (f"as built, {SLIDE_CLEARANCE:.2f} mm slide clearance", False),
        ("walls run out to the groove floor", True),
    ):
        for depth in (20.0, 36.0, 55.0):
            labels = label_air(assemble(seal_walls=seal_walls), depth)
            duct = region_at(labels, 0.0, params.FAN_CENTRE_Y)
            area = int((labels == duct).sum()) * SCAN_STEP**2
            leaks = reaches_ambient(labels, duct)
            if leaks and seal_walls:
                unexplained.append(f"z={depth:.0f}")
            print(
                f"  {label:38s} z={depth:5.1f}  plenum {area:9.1f} mm2  "
                f"{'open' if leaks else 'sealed'}"
            )
    return unexplained


def report_leak_area():
    """How much hole the slide clearance actually is."""
    ends = 2 * len(params.WALL_BANDS)  # two walls, two ends each
    leak = SLIDE_CLEARANCE * params.WALL_THICKNESS * ends
    opening = math.pi * (params.FAN_OPENING_DIA / 2) ** 2
    print("\n=== the slide clearance, as a hole ===")
    print(f"  wall end to ear groove floor  : {SLIDE_CLEARANCE:8.2f} mm")
    print(f"  leak area, {ends} wall ends        : {leak:8.2f} mm2")
    print(f"  as a share of the fan opening : {leak / opening * 100:8.3f}%")


def report_ear_gaps():
    """Six ears stacked three high only seal if they actually touch.

    Run against the interference-fit walls so the slide clearance does not mask
    the thing being measured: what a rack with imperfect rail spacing costs.
    """
    print("\n=== if the rack's rail holes are not exactly one unit apart ===")
    for gap in EAR_GAPS:
        labels = label_air(assemble(ear_gap=gap, seal_walls=True), 36.0)
        duct = region_at(labels, 0.0, params.FAN_CENTRE_Y + gap)
        leaks = reaches_ambient(labels, duct)
        print(
            f"  {gap:.1f} mm between stacked ears   "
            f"{'OPEN to ambient' if leaks else 'still sealed'}"
        )


def report_free_area():
    """The number the fan opening has to be judged against."""
    labels = label_air(assemble(with_laptops=True), 36.0)
    duct = region_at(labels, 0.0, params.FAN_CENTRE_Y)
    free_area = int((labels == duct).sum()) * SCAN_STEP**2
    opening = math.pi * (params.FAN_OPENING_DIA / 2) ** 2
    print("\n=== free area, measured with the laptops in ===")
    print(f"  plenum free area              : {free_area:8.0f} mm2")
    print(
        f"  fan opening O{params.FAN_OPENING_DIA:.0f}              : {opening:8.0f} mm2"
    )
    print(f"  opening as a share of the duct: {opening / free_area * 100:8.1f}%")
    if opening < free_area:
        print("  the opening is the restriction, not the duct")
    else:
        print("  the duct is the restriction, not the opening")


def main():
    """Run every check and print a verdict."""
    clashes = report_interference(assemble())
    unexplained = report_seal()
    report_leak_area()
    report_ear_gaps()
    report_free_area()
    print("\n=== verdict ===")
    print(f"  assembles without interference : {'no' if clashes else 'yes'}")
    print("  no leak beyond the slide clearance : " f"{'no' if unexplained else 'yes'}")
    if unexplained:
        print("  unexplained leak at: " + ", ".join(unexplained))


if __name__ == "__main__":
    main()
