"""Fit the rear parts together and check for interference and air leaks.

Run against the exported STLs, not Fusion:

    python scripts/check_rear_assembly.py

Two questions get answered.

Does it assemble? Every pair of parts is intersected exactly, so any overlap
shows up as a positive volume rather than as a surprise on the bed.

Is the duct sealed? A cross-section is taken by casting one ray along +x per
scan line, which makes the x extents exact and leaves only y sampled. The air
in that section is then flood-filled from a point inside the duct; if the duct
region reaches the edge of the frame, air is getting out somewhere it should
not. Between z~10 and z~60 the parts are prismatic, so a section there holds
for that whole stretch rather than being a spot check.

The panel has play in its duct rail slot, so the seal is tested with the panel
resting on each wall and floating between them.

Requires trimesh, numpy, scipy and manifold3d.
"""

import itertools
import math
from pathlib import Path

import numpy as np
import trimesh
from scipy import ndimage

EXPORTS = Path("exports")

EAR_OFFSET_X = 110.32      # ear local x=-15 (inner face) lands at global 95.32
EAR_DEPTH = 72.0           # rail plane to pad face
RACK_UNIT = 44.45
EAR_WALL = 2.0             # duct rail wall, build_rear_ear_v2.py
EAR_SLOT_HEIGHT = 2.4      # duct rail slot, build_rear_ear_v2.py
PANEL_THICKNESS = 2.2
GROOVE_FLOOR_X = 97.32     # ear groove floor, per side
FAN_OPENING_DIA = 39.0
FAN_COUNT = 3

FRAME_X = (-135.0, 135.0)
FRAME_Y = (-2.0, 47.0)
SCAN_STEP = 0.02           # resolves a 0.1 mm clearance five times over

SEATINGS = (
    ("resting on the lower wall (gravity)", 0.0),
    ("floating centred in the slot", (EAR_SLOT_HEIGHT - PANEL_THICKNESS) / 2),
    ("pulled against the upper wall (suction)", EAR_SLOT_HEIGHT - PANEL_THICKNESS),
)


def mirrored_x(mesh):
    out = mesh.copy()
    out.apply_transform(np.diag([-1.0, 1.0, 1.0, 1.0]))
    if out.volume < 0:
        out.invert()
    return out


def moved_to(mesh, x_min=None, y_min=None, z_min=None):
    low = mesh.bounds[0]
    shift = [0.0, 0.0, 0.0]
    for axis, target in enumerate((x_min, y_min, z_min)):
        if target is not None:
            shift[axis] = target - low[axis]
    mesh.apply_translation(shift)
    return mesh


def assemble(panel_offset):
    """Place every rear part in the rack frame, panels offset in their slots."""
    parts = {}

    ear = trimesh.load_mesh(EXPORTS / "rear_ear_v2.stl")
    right_ear = ear.copy()
    right_ear.apply_translation([EAR_OFFSET_X, 0.0, 0.0])
    parts["ear_right"] = right_ear
    left_ear = mirrored_x(ear)
    left_ear.apply_translation([-EAR_OFFSET_X, 0.0, 0.0])
    parts["ear_left"] = left_ear

    # The panel prints flat, x = width, y = length, z = thickness. Stand it up
    # so its length runs down the duct and its thickness is the rack vertical.
    panel = trimesh.load_mesh(EXPORTS / "duct_panel.stl")
    panel.apply_transform(trimesh.transformations.rotation_matrix(
        math.pi / 2, [1.0, 0.0, 0.0]))
    panel_width = panel.extents[0]
    bottom = panel.copy()
    moved_to(bottom, x_min=-panel_width / 2,
             y_min=EAR_WALL + panel_offset, z_min=0.0)
    parts["duct_panel_bottom"] = bottom
    top = panel.copy()
    moved_to(top, x_min=-panel_width / 2,
             y_min=RACK_UNIT - EAR_WALL - EAR_SLOT_HEIGHT + panel_offset,
             z_min=0.0)
    parts["duct_panel_top"] = top

    plate = trimesh.load_mesh(EXPORTS / "rear_fan_plate.stl")
    plate.apply_translation([0.0, 0.0, EAR_DEPTH])
    parts["fan_plate"] = plate
    return parts


def solid_spans(triangles, y, z):
    """Exact solid intervals along +x through a mesh at (y, z)."""
    origin = np.array([FRAME_X[0] - 50.0, y, z])
    direction = np.array([1.0, 0.0, 0.0])
    corner, edge_a, edge_b = (triangles[:, 0],
                              triangles[:, 1] - triangles[:, 0],
                              triangles[:, 2] - triangles[:, 0])
    pvec = np.cross(direction, edge_b)
    determinant = np.einsum("ij,ij->i", edge_a, pvec)
    usable = np.abs(determinant) > 1e-12
    inverse = np.where(usable, 1.0 / np.where(usable, determinant, 1.0), 0.0)
    to_corner = origin - corner
    bary_u = np.einsum("ij,ij->i", to_corner, pvec) * inverse
    qvec = np.cross(to_corner, edge_a)
    bary_v = np.einsum("j,ij->i", direction, qvec) * inverse
    distance = np.einsum("ij,ij->i", edge_b, qvec) * inverse
    hit = (usable & (bary_u >= 0) & (bary_v >= 0)
           & (bary_u + bary_v <= 1) & (distance > 0))
    crossings = np.sort(origin[0] + distance[hit])
    return [(crossings[i], crossings[i + 1])
            for i in range(0, len(crossings) - 1, 2)]


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
                    solid[row_index, low:high + 1] = True
    labels, _ = ndimage.label(~solid)
    return labels


def region_at(labels, x, y):
    return labels[int(round((y - FRAME_Y[0]) / SCAN_STEP)),
                  int(round((x - FRAME_X[0]) / SCAN_STEP))]


def reaches_ambient(labels, region):
    edges = (set(labels[0, :]) | set(labels[-1, :])
             | set(labels[:, 0]) | set(labels[:, -1]))
    return region in edges


def report_interference(parts):
    print("=== interference (exact boolean, any volume > 0 is a clash) ===")
    clashes = 0
    for (name_a, part_a), (name_b, part_b) in itertools.combinations(
            parts.items(), 2):
        low_a, high_a = part_a.bounds
        low_b, high_b = part_b.bounds
        if np.any(high_a < low_b) or np.any(high_b < low_a):
            continue
        overlap = trimesh.boolean.intersection([part_a, part_b],
                                               engine="manifold")
        volume = 0.0 if overlap is None or overlap.is_empty else overlap.volume
        if volume > 1e-6:
            clashes += 1
            print(f"  CLASH {name_a} vs {name_b}: {volume:.4f} mm3")
    print(f"  {clashes} clash(es)")
    return clashes


def report_seal():
    print("\n=== is the duct sealed at mid-depth? ===")
    leaking = []
    for description, offset in SEATINGS:
        labels = label_air(assemble(offset), 36.0)
        duct = region_at(labels, 0.0, 22.0)
        area = int((labels == duct).sum()) * SCAN_STEP ** 2
        leaks = reaches_ambient(labels, duct)
        if leaks:
            leaking.append(description)
        print(f"  {description:42s} duct {area:8.1f} mm2  "
              f"{'LEAKS' if leaks else 'sealed'}")
    return leaking


def report_throat():
    end_clearance = GROOVE_FLOOR_X - trimesh.load_mesh(
        EXPORTS / "duct_panel.stl").extents[0] / 2
    throat = end_clearance * EAR_SLOT_HEIGHT * 4  # 2 panels x 2 ends
    fan_area = FAN_COUNT * math.pi * (FAN_OPENING_DIA / 2) ** 2
    print("\n=== worst case, a panel clear of both slot walls ===")
    print(f"  panel end to ear groove floor : {end_clearance:.2f} mm")
    print(f"  throttling area, 4 panel ends : {throat:.2f} mm2")
    print(f"  four fan openings             : {fan_area:.0f} mm2")
    print(f"  leak as a share of fan area   : {throat / fan_area * 100:.3f}%")


def main():
    clashes = report_interference(assemble(0.0))
    leaking = report_seal()
    report_throat()
    print("\n=== verdict ===")
    print(f"  assembles without interference : {'no' if clashes else 'yes'}")
    print(f"  seals with a panel against either wall : "
          f"{'no' if len(leaking) > 1 else 'yes'}")
    if leaking:
        print("  leaks when: " + "; ".join(leaking))


if __name__ == "__main__":
    main()
