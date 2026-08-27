"""Build the shared duct fan plate as a mesh, locally, without Fusion.

    python scripts/build_shared_fan_plate_mesh.py

Upstream every part came out of Fusion, which is fine when you have a licence
and a hard reason -- the ears are full of tangency and relief work that only
survives as parametric history. The plate is not that part. It is a rectangle,
two fins, and eleven holes, and holding it hostage to a licence would mean
nobody could print this fork, check it, or change the fan size without opening
Fusion first.

So it is built here from primitives and booleaned with manifold, straight to a
printable STL. `build_shared_fan_plate.py` builds the identical part inside
Fusion for anyone who wants the editable history; both read their numbers from
shared_duct_params.py, so the two cannot drift.

Requires trimesh, numpy and manifold3d.
"""

import argparse
from pathlib import Path

import trimesh

import shared_duct_params as params
from mesh_helpers import box as _box
from mesh_helpers import cylinder as _cylinder

EXPORTS = Path("exports")
STL_PATH = EXPORTS / "shared_fan_plate.stl"

# Every cut runs past the face it starts from, so coplanar faces never meet.
# A boolean between two surfaces at exactly the same z is the classic way to
# get a hole that is a hole in CAD and a dimple in the slicer.
OVERSHOOT = 1.0


def build_plate(wall_overhang=0.0):
    """The plate and its two duct walls, less every opening.

    Built in the plate's own frame, the same one the Fusion script uses: the
    plate occupies z 0..4 and the walls grow forward into negative z, so the
    front face -- the one that faces into the rack -- is z = 0. The assembly
    puts it in the rack by translating +EAR_DEPTH in z.

    `wall_overhang` widens each duct wall by that much at each end. It is zero
    for the real part, which needs the clearance to slide into the duct rails.
    check_rear_assembly.py builds an interference-fit copy with it, to prove
    that the slide clearance is the only way air leaves the duct.
    """
    params.check_fits()

    half_width = params.PLATE_WIDTH / 2
    solid = _box(
        (-half_width, half_width),
        (params.PLATE_Y0, params.PLATE_Y1),
        (0.0, params.PLATE_THICKNESS),
    )

    wall_half_width = params.WALL_HALF_WIDTH + wall_overhang
    walls = [
        _box(
            (-wall_half_width, wall_half_width),
            band,
            (-params.WALL_DEPTH, 0.0),
        )
        for band in params.WALL_BANDS
    ]
    solid = trimesh.boolean.union([solid, *walls], engine="manifold")

    through = (-OVERSHOOT, params.PLATE_THICKNESS + OVERSHOOT)
    cuts = [
        _cylinder(
            params.FAN_CENTRE_X, params.FAN_CENTRE_Y, params.FAN_OPENING_DIA, through
        )
    ]
    cuts += [
        _cylinder(screw_x, screw_y, params.FAN_SCREW_DIA, through)
        for screw_x, screw_y in params.fan_screw_centres()
    ]

    # M3 clearance all the way through, then a counterbore from the rear face
    # so the screw heads sit flush and the fan can sit hard against the plate.
    for boss_x in (-params.BOSS_X, params.BOSS_X):
        for boss_y in params.boss_rows():
            cuts.append(_cylinder(boss_x, boss_y, params.SCREW_CLEAR_DIA, through))
            cuts.append(
                _cylinder(
                    boss_x,
                    boss_y,
                    params.HEAD_CBORE_DIA,
                    (
                        params.PLATE_THICKNESS - params.HEAD_CBORE_DEPTH,
                        params.PLATE_THICKNESS + OVERSHOOT,
                    ),
                )
            )

    for slot_x in params.TIE_SLOT_X:
        for slot_y in params.TIE_SLOT_Y:
            cuts.append(
                _box(
                    (slot_x - params.TIE_SLOT_W / 2, slot_x + params.TIE_SLOT_W / 2),
                    (slot_y - params.TIE_SLOT_H / 2, slot_y + params.TIE_SLOT_H / 2),
                    through,
                )
            )

    return trimesh.boolean.difference([solid, *cuts], engine="manifold")


def main():
    """Build the plate and write it out as an STL."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=STL_PATH, help="where to write the STL"
    )
    arguments = parser.parse_args()

    plate = build_plate()
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    plate.export(arguments.out)

    low, high = plate.bounds
    print(f"wrote {arguments.out}")
    print(
        f"  extents mm : x {low[0]:.2f}..{high[0]:.2f}  "
        f"y {low[1]:.2f}..{high[1]:.2f}  z {low[2]:.2f}..{high[2]:.2f}"
    )
    print(
        f"  volume     : {plate.volume / 1000:.1f} cm3 "
        f"({plate.volume * 1.27 / 1000:.0f} g in PETG)"
    )
    print(f"  watertight : {plate.is_watertight}")


if __name__ == "__main__":
    main()
