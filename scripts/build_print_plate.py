"""Assemble the print plates as 3MFs for PrusaSlicer.

Loads the exported STLs, orients each part print-side down, bakes the
mirrored copies (left/right ears), arranges everything on the bed, and writes
a vanilla 3MF that PrusaSlicer opens as separate objects:

    python scripts/build_print_plate.py            # heat-set rear ears
    python scripts/build_print_plate.py --variant nuttrap
    python scripts/build_print_plate.py --variant selftap

Three plates, and a full rack needs three of the first and one of each other:

- `ears_<variant>`, one rack unit's worth of ears. Print it once per laptop.
- `shared_fan_plate`, the whole duct in one part. Print it once.
- `fan_guard`, optional, and on its own plate because it is optional.

The plate does not fit a Prusa Mini and never will -- it is 222 mm across a
180 mm bed -- so asking for it on that bed is refused by name rather than
failing somewhere inside the packer.

Requires: trimesh, numpy (pip install trimesh numpy).
"""

import argparse
import zipfile
from pathlib import Path

import numpy as np
import trimesh

EXPORTS = Path("exports")
REAR_EAR_FILES = {
    "heatset": "rear_ear_v2.stl",
    "selftap": "rear_ear_v2_selftap.stl",
    "nuttrap": "rear_ear_v2_nuttrap.stl",
}

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
"""

RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel0"
  Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""


def mirrored(mesh):
    """Bake an X-mirrored copy with corrected face winding."""
    copy = mesh.copy()
    copy.apply_transform(np.diag([-1.0, 1.0, 1.0, 1.0]))
    if copy.volume < 0:  # older trimesh doesn't fix winding on reflections
        copy.invert()
    return copy


def flipped(mesh):
    """Turn a part over, print-side down, keeping the winding valid."""
    copy = mesh.copy()
    copy.apply_transform(
        trimesh.transformations.rotation_matrix(np.pi, [1.0, 0.0, 0.0])
    )
    if copy.volume < 0:
        copy.invert()
    return copy


def place(mesh, x_center, y_center):
    """Drop the mesh so it sits on z=0 centered at (x_center, y_center)."""
    lo, hi = mesh.bounds
    mesh.apply_translation(
        [x_center - (lo[0] + hi[0]) / 2, y_center - (lo[1] + hi[1]) / 2, -lo[2]]
    )
    return mesh


BEDS = {"coreone": (250.0, 220.0), "mini": (180.0, 180.0)}

# Plates that only exist on a bed big enough for them.
BED_ONLY = {"shared_fan_plate": ("coreone",)}


def build_parts(variant):
    """Two sets. The ears are per laptop; the plate is one for the rack."""
    front = trimesh.load_mesh(EXPORTS / "front_ear.stl")
    rear = trimesh.load_mesh(EXPORTS / REAR_EAR_FILES[variant])
    plate = trimesh.load_mesh(EXPORTS / "shared_fan_plate.stl")
    guard = trimesh.load_mesh(EXPORTS / "fan_guard.stl")

    return {
        # Printed plate-down, so the first layer is the full solid rectangle
        # and the duct walls rise 72 mm behind it as two 2.2 mm fins. That is
        # the cost of integrating them, and it is why this is a long print for
        # one part rather than a quick one for three.
        "shared_fan_plate": [
            ("shared_fan_plate", flipped(plate)),
        ],
        # Optional, and on its own plate because it is optional. Flat, no
        # support, fits any bed here.
        "fan_guard": [
            ("fan_guard", guard.copy()),
        ],
        f"ears_{variant}": [
            ("rear_ear_R", rear.copy()),
            ("rear_ear_L", mirrored(rear)),
            ("front_ear_R", front.copy()),
            ("front_ear_L", mirrored(front)),
        ],
    }


def arrange(parts, bed, margin=8.0, gap=6.0):
    """Row-pack left to right, wrapping down. Raises naming the part that
    did not fit, so the failure is actionable rather than a bare error."""
    bed_w, bed_h = bed
    x = y = margin
    row_depth = 0.0
    for name, mesh in parts:
        lo, hi = mesh.bounds
        width, depth = hi[0] - lo[0], hi[1] - lo[1]
        if width > bed_w - 2 * margin or depth > bed_h - 2 * margin:
            raise SystemExit(
                f"{name} is {width:.0f} x {depth:.0f} mm and will not fit "
                f"a {bed_w:.0f} x {bed_h:.0f} bed at all"
            )
        if x + width > bed_w - margin:
            x = margin
            y += row_depth + gap
            row_depth = 0.0
        if y + depth > bed_h - margin:
            raise SystemExit(
                f"ran out of bed placing {name} on " f"{bed_w:.0f} x {bed_h:.0f}"
            )
        place(mesh, x + width / 2, y + depth / 2)
        x += width + gap
        row_depth = max(row_depth, depth)

    # Pull the whole arrangement to the middle of the bed. Packing from a
    # corner is fine for fitting, but the extreme front-left is the worst-
    # adhering region of this bed and a set with room to spare has no reason
    # to sit there. Plates that genuinely fill the bed barely move.
    lows = [m.bounds[0] for _, m in parts]
    highs = [m.bounds[1] for _, m in parts]
    span_x = max(h[0] for h in highs) - min(l[0] for l in lows)
    span_y = max(h[1] for h in highs) - min(l[1] for l in lows)
    shift_x = (bed_w - span_x) / 2 - min(l[0] for l in lows)
    shift_y = (bed_h - span_y) / 2 - min(l[1] for l in lows)
    for _, mesh in parts:
        mesh.apply_translation([shift_x, shift_y, 0.0])
    return parts


def write_3mf(parts, out_path):
    """Hand-write a vanilla 3MF PrusaSlicer opens as separate objects."""
    objects_xml = []
    items_xml = []
    for index, (name, mesh) in enumerate(parts, start=1):
        vertices = "".join(
            f'<vertex x="{v[0]:.4f}" y="{v[1]:.4f}" z="{v[2]:.4f}"/>'
            for v in mesh.vertices
        )
        triangles = "".join(
            f'<triangle v1="{t[0]}" v2="{t[1]}" v3="{t[2]}"/>' for t in mesh.faces
        )
        objects_xml.append(
            f'<object id="{index}" name="{name}" type="model"><mesh>'
            f"<vertices>{vertices}</vertices><triangles>{triangles}</triangles>"
            "</mesh></object>"
        )
        items_xml.append(f'<item objectid="{index}"/>')

    resources = "".join(objects_xml)
    build = "".join(items_xml)
    model = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        f"<resources>{resources}</resources><build>{build}</build></model>"
    )

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", RELS)
        archive.writestr("3D/3dmodel.model", model)


def main():
    """Arrange and write every plate the arguments ask for."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variant",
        choices=sorted(REAR_EAR_FILES),
        default="heatset",
        help="rear ear variant to plate",
    )
    parser.add_argument(
        "--bed", choices=sorted(BEDS), default="coreone", help="target printer bed"
    )
    parser.add_argument(
        "--set",
        dest="which",
        default=None,
        help="only emit this set, e.g. ears_heatset",
    )
    args = parser.parse_args()
    bed = BEDS[args.bed]
    suffix = "" if args.bed == "coreone" else "_" + args.bed

    for plate_name, parts in build_parts(args.variant).items():
        if args.which and plate_name != args.which:
            continue
        allowed = BED_ONLY.get(plate_name)
        if allowed and args.bed not in allowed:
            print(
                f"[{plate_name}] skipped: needs a "
                f"{' or '.join(allowed)} bed, not {args.bed}\n"
            )
            continue
        print(f"[{plate_name} on {args.bed} " f"{bed[0]:.0f}x{bed[1]:.0f}]")
        parts = arrange(parts, bed)
        boxes = []
        for name, mesh in parts:
            assert mesh.volume > 0, f"{name} has inverted winding"
            lo, hi = mesh.bounds
            boxes.append((name, lo, hi))
            print(
                f"  {name:20s} {hi[0]-lo[0]:6.1f} x {hi[1]-lo[1]:5.1f} x "
                f"{hi[2]-lo[2]:5.1f} at x {lo[0]:.0f}..{hi[0]:.0f} "
                f"y {lo[1]:.0f}..{hi[1]:.0f}"
            )
        for i, (n1, lo1, hi1) in enumerate(boxes):
            for n2, lo2, hi2 in boxes[i + 1 :]:
                if (
                    lo1[0] < hi2[0]
                    and lo2[0] < hi1[0]
                    and lo1[1] < hi2[1]
                    and lo2[1] < hi1[1]
                ):
                    raise SystemExit(f"{n1} overlaps {n2} on plate {plate_name}")
        for name, lo, hi in boxes:
            if lo[0] < 0 or lo[1] < 0 or hi[0] > bed[0] or hi[1] > bed[1]:
                raise SystemExit(f"{name} runs off the {args.bed} bed")

        out_path = EXPORTS / f"print_plate_{plate_name}{suffix}.3mf"
        write_3mf(parts, out_path)
        print(f"wrote {out_path} ({out_path.stat().st_size / 1e6:.2f} MB)\n")


if __name__ == "__main__":
    main()
