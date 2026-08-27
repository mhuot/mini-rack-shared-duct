"""Build the optional fan guard as a mesh, locally, without Fusion.

    python scripts/build_fan_guard_mesh.py

A 120 mm fan spinning in the open back of a rack is the one part of this build
that can hurt you or eat a cable, and the fix is a flat printed grille on the
same four screws that hold the fan. Optional in the sense that the duct works
without it; not optional if anything else lives behind the rack.

It costs nothing aerodynamically at this size. The bars are radial, so they sit
along the flow rather than across it, and the open area is about three quarters
of the opening -- a fraction that only starts to matter on much smaller fans
turning much faster.

It prints flat, no support, in well under an hour. Concentric rings connected
by radial bars, which is the shape every stamped steel fan guard already is,
for the same reason: it is stiff in the plane it needs to be stiff in.

Requires trimesh, numpy and manifold3d.
"""

import argparse
import math
from pathlib import Path

import trimesh

import shared_duct_params as params
from mesh_helpers import box as _box
from mesh_helpers import cylinder as _cylinder
from mesh_helpers import report_mesh

EXPORTS = Path("exports")
STL_PATH = EXPORTS / "fan_guard.stl"

THICKNESS = 3.0
OVERSHOOT = 1.0

# Sized for open area first. A guard that blocks a quarter of the throat is
# not a guard, it is a restrictor: the rings are as narrow as will print
# reliably at 0.4 mm and the gaps are as wide as will still stop a finger.
HUB_RADIUS = 10.0  # solid centre, over the fan's hub, which passes no air
RING_WIDTH = 2.5  # the concentric rings left standing
GAP_WIDTH = 14.0  # the open annuli between them
SPOKE_BARS = 3  # bars across the full diameter, so six radial arms
SPOKE_WIDTH = 4.0


def _open_annuli(limit_radius):
    """The (inner, outer) radii of every gap between hub and rim."""
    annuli = []
    radius = HUB_RADIUS
    while radius + GAP_WIDTH <= limit_radius:
        annuli.append((radius, radius + GAP_WIDTH))
        radius += GAP_WIDTH + RING_WIDTH
    return annuli


def build_guard():
    """The guard: a square plate, cut back to rings and spokes."""
    params.check_fits()

    half_frame = params.FAN_FRAME / 2
    guard = _box((-half_frame, half_frame), (-half_frame, half_frame), (0.0, THICKNESS))

    through = (-OVERSHOOT, THICKNESS + OVERSHOOT)

    # The rim stops where the fan's own frame starts, so the guard never
    # narrows the throat the plate just went to the trouble of chamfering.
    rim_radius = params.FAN_OPENING_DIA / 2
    cuts = []
    for inner, outer in _open_annuli(rim_radius):
        gap = _cylinder(0.0, 0.0, 2 * outer, through)
        core = _cylinder(0.0, 0.0, 2 * inner, through)
        cuts.append(trimesh.boolean.difference([gap, core], engine="manifold"))

    open_area = trimesh.boolean.union(cuts, engine="manifold")

    # Radial spokes: kept, so they are removed from what gets cut away.
    spokes = []
    for index in range(SPOKE_BARS):
        angle = math.pi * index / SPOKE_BARS
        spoke = _box(
            (-rim_radius - 1, rim_radius + 1),
            (-SPOKE_WIDTH / 2, SPOKE_WIDTH / 2),
            through,
        )
        spoke.apply_transform(
            trimesh.transformations.rotation_matrix(angle, [0.0, 0.0, 1.0])
        )
        spokes.append(spoke)
    open_area = trimesh.boolean.difference(
        [open_area, trimesh.boolean.union(spokes, engine="manifold")],
        engine="manifold",
    )

    guard = trimesh.boolean.difference([guard, open_area], engine="manifold")

    # The four corner holes, at the pitch the fan is already drilled to. Same
    # screws, one length longer.
    half_pitch = params.FAN_SCREW_PITCH / 2
    screw_cuts = [
        _cylinder(dx, dy, params.FAN_SCREW_DIA, through)
        for dx in (-half_pitch, half_pitch)
        for dy in (-half_pitch, half_pitch)
    ]
    return trimesh.boolean.difference([guard, *screw_cuts], engine="manifold")


def main():
    """Build the guard and write it out as an STL."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=STL_PATH, help="where to write the STL"
    )
    arguments = parser.parse_args()

    guard = build_guard()
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    guard.export(arguments.out)

    swept = math.pi * (params.FAN_OPENING_DIA / 2) ** 2
    # Everything outside the opening's radius is solid rim and corners, so the
    # part worth reporting is how much of the throat itself is left open.
    solid_area = guard.volume / THICKNESS
    screw_area = 4 * math.pi * (params.FAN_SCREW_DIA / 2) ** 2
    rim_area = params.FAN_FRAME**2 - swept - screw_area
    open_area = swept - (solid_area - rim_area)
    report_mesh(arguments.out, guard)
    print(
        f"  open area  : {open_area:.0f} mm2 of the {swept:.0f} mm2 throat "
        f"({open_area / swept * 100:.0f}%)"
    )


if __name__ == "__main__":
    main()
