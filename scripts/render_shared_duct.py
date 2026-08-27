"""Render the shared duct assembly to PNGs, locally, from the exported STLs.

    python scripts/render_shared_duct.py

Upstream's renders come out of Fusion and get post-processed by
build_web_assets.py. That needs a Fusion session to produce the frames, which
is exactly the thing this fork keeps having to work around, and it cannot draw
a part that has not been built in Fusion yet. This draws the assembly from the
meshes themselves so a design can be looked at before anyone commits to it.

It is a painter's-algorithm renderer in about eighty lines: project the
triangles orthographically, drop the back faces, sort by depth, shade each one
by its angle to a fixed light. No GL context, no display, no extra dependency
beyond matplotlib -- which matters, because the machine that checks this
project is usually headless.

Requires trimesh, numpy and matplotlib.
"""

import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # pylint: disable=wrong-import-position

import matplotlib.pyplot as plt  # noqa: E402  (must follow the Agg switch)
import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402

import shared_duct_params as params  # noqa: E402
from mesh_helpers import box as box_mesh  # noqa: E402
from mesh_helpers import mirrored_x  # noqa: E402

EXPORTS = Path("exports")
IMAGES = Path("docs/images")
GLB_PATH = Path("docs/models/shared-duct.glb")

# The rack, in the frame build_rack_mockup.py uses: z is depth into the rack,
# the rear rack rail sits at z = 200, and y climbs the stack from the floor of
# the bottom rack unit.
REAR_RAIL_Z = 200.0
LAPTOP_STOP_Z = 265.0
LAPTOP_SEAT_Y = 10.22
ROD_ROWS_PER_UNIT = (6.22, 38.23)
ROD_DIA = 8.0
ROD_Z = (-2.0, 241.0)

# sRGB, matching build_web_assets.py so the two sets of renders agree.
COLOURS = {
    "print": (247 / 255, 84 / 255, 3 / 255),
    "rod": (215 / 255, 215 / 255, 220 / 255),
    "macbook": (45 / 255, 45 / 255, 48 / 255),
    "surface": (28 / 255, 28 / 255, 30 / 255),
    "fan": (94 / 255, 61 / 255, 48 / 255),
}

LAPTOPS = {
    "macbook": {"width": 221.2, "length": 312.6, "thickness": 15.5},
    "surface": {"width": 220.0, "length": 301.0, "thickness": 17.5},
}
# Bottom rack unit upward. The duct does not care which is which; the mix is
# here so the render shows the real thing rather than three identical blocks.
STACK = ("macbook", "surface", "macbook")

LIGHT_DIRECTION = np.array([0.35, 0.6, -0.72])
LIGHT_DIRECTION = LIGHT_DIRECTION / np.linalg.norm(LIGHT_DIRECTION)


def assemble():
    """Every part of the rear assembly, placed in the rack frame."""
    parts = []

    ear = trimesh.load_mesh(EXPORTS / "rear_ear_v2.stl")
    for unit_index in range(params.RACK_UNITS):
        unit_y = unit_index * params.RACK_UNIT
        for side_mesh, side_x in (
            (ear, params.EAR_OFFSET_X),
            (mirrored_x(ear), -params.EAR_OFFSET_X),
        ):
            placed = side_mesh.copy()
            placed.apply_translation([side_x, unit_y, REAR_RAIL_Z])
            parts.append((placed, "print"))

    plate = trimesh.load_mesh(EXPORTS / "shared_fan_plate.stl")
    plate.apply_translation([0.0, 0.0, REAR_RAIL_Z + params.EAR_DEPTH])
    parts.append((plate, "print"))

    # The fan as a plain frame with its throat bored out: enough to read the
    # size and the depth it adds, without pretending to model a rotor.
    fan_front_z = REAR_RAIL_Z + params.EAR_DEPTH + params.PLATE_THICKNESS
    half_frame = params.FAN_FRAME / 2
    frame = box_mesh(
        (-half_frame, half_frame),
        (params.FAN_CENTRE_Y - half_frame, params.FAN_CENTRE_Y + half_frame),
        (fan_front_z, fan_front_z + params.FAN_DEPTH),
    )
    throat = trimesh.creation.cylinder(
        radius=params.FAN_OPENING_DIA / 2, height=params.FAN_DEPTH + 2, sections=96
    )
    throat.apply_translation(
        [params.FAN_CENTRE_X, params.FAN_CENTRE_Y, fan_front_z + params.FAN_DEPTH / 2]
    )
    parts.append(
        (trimesh.boolean.difference([frame, throat], engine="manifold"), "fan")
    )

    for unit_index, laptop_name in enumerate(STACK):
        unit_y = unit_index * params.RACK_UNIT
        spec = LAPTOPS[laptop_name]
        parts.append(
            (
                box_mesh(
                    (-spec["width"] / 2, spec["width"] / 2),
                    (
                        unit_y + LAPTOP_SEAT_Y,
                        unit_y + LAPTOP_SEAT_Y + spec["thickness"],
                    ),
                    (LAPTOP_STOP_Z - spec["length"], LAPTOP_STOP_Z),
                ),
                laptop_name,
            )
        )
        for rod_y in ROD_ROWS_PER_UNIT:
            for rod_x in (-params.BOSS_X, params.BOSS_X):
                rod = trimesh.creation.cylinder(
                    radius=ROD_DIA / 2, height=ROD_Z[1] - ROD_Z[0], sections=24
                )
                rod.apply_transform(
                    trimesh.transformations.rotation_matrix(
                        math.pi / 2, [1.0, 0.0, 0.0]
                    )
                )
                rod.apply_translation(
                    [rod_x, unit_y + rod_y, (ROD_Z[0] + ROD_Z[1]) / 2]
                )
                parts.append((rod, "rod"))

    return parts


def srgb_to_linear(rgb):
    """glTF baseColorFactor is linear; the palette is authored in sRGB.

    Skipping this conversion is why an untreated export looks washed out next
    to the same colours in a PNG.
    """
    srgb = np.array(rgb, dtype=np.float64)
    return np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)


def write_glb(parts, out_path):
    """Export the assembly as a GLB, for the viewer on the project page.

    Upstream's GLB came out of a Fusion session by way of build_web_assets.py.
    This one is the same meshes the checks run against, which means the model
    on the page cannot show a version of the duct that was never verified.
    """
    scene = trimesh.Scene()
    for index, (mesh, colour_name) in enumerate(parts):
        coloured = mesh.copy()
        coloured.visual = trimesh.visual.TextureVisuals(
            material=trimesh.visual.material.PBRMaterial(
                baseColorFactor=np.append(srgb_to_linear(COLOURS[colour_name]), 1.0),
                metallicFactor=0.6 if colour_name == "rod" else 0.0,
                roughnessFactor=0.35 if colour_name == "rod" else 0.7,
            )
        )
        scene.add_geometry(coloured, node_name=f"{colour_name}_{index}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(trimesh.exchange.gltf.export_glb(scene))
    return out_path


def camera(azimuth_deg, elevation_deg):
    """Orthographic basis: right and up in the image, plus the view direction."""
    azimuth = math.radians(azimuth_deg)
    elevation = math.radians(elevation_deg)
    forward = np.array(
        [
            math.cos(elevation) * math.sin(azimuth),
            math.sin(elevation),
            math.cos(elevation) * math.cos(azimuth),
        ]
    )
    right = np.cross(np.array([0.0, 1.0, 0.0]), forward)
    right /= np.linalg.norm(right)
    up = np.cross(forward, right)
    return right, up, forward


def draw(axes, parts, azimuth_deg, elevation_deg, title):
    """Paint the assembly into `axes` from one orthographic viewpoint."""
    right, up, forward = camera(azimuth_deg, elevation_deg)

    polygons, facecolours = [], []
    for mesh, colour_name in parts:
        triangles = mesh.triangles
        normals = mesh.face_normals
        facing = normals @ forward < 0  # drop the back faces
        triangles, normals = triangles[facing], normals[facing]
        if triangles.size == 0:
            continue
        projected = np.stack(
            [triangles @ right, triangles @ up, triangles @ forward], axis=-1
        )
        base = np.array(COLOURS[colour_name])
        shade = 0.32 + 0.68 * np.clip(normals @ LIGHT_DIRECTION, 0.0, 1.0)
        polygons.append(projected)
        facecolours.append(np.clip(base * shade[:, None], 0.0, 1.0))

    projected = np.concatenate(polygons)
    facecolours = np.concatenate(facecolours)
    order = np.argsort(-projected[:, :, 2].mean(axis=1))  # far to near

    axes.add_collection(
        PolyCollection(
            projected[order][:, :, :2],
            facecolors=facecolours[order],
            edgecolors="none",
            antialiased=False,
        )
    )
    flat = projected.reshape(-1, 3)
    axes.set_xlim(flat[:, 0].min() - 5, flat[:, 0].max() + 5)
    axes.set_ylim(flat[:, 1].min() - 5, flat[:, 1].max() + 5)
    axes.set_aspect("equal")
    axes.axis("off")
    axes.set_title(title, fontsize=11, color="#222222", pad=6)


def _dimension(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    axes, start, end, label, offset=0.0, vertical=False
):
    """A plain dimension line with the number sitting on it."""
    if vertical:
        axes.annotate(
            "",
            xy=(offset, start),
            xytext=(offset, end),
            arrowprops={"arrowstyle": "<->", "color": "#0b6", "lw": 1.0},
        )
        axes.text(
            offset - 3,
            (start + end) / 2,
            label,
            rotation=90,
            ha="right",
            va="center",
            fontsize=8,
            color="#063",
        )
    else:
        axes.annotate(
            "",
            xy=(start, offset),
            xytext=(end, offset),
            arrowprops={"arrowstyle": "<->", "color": "#0b6", "lw": 1.0},
        )
        axes.text(
            (start + end) / 2,
            offset + 2,
            label,
            ha="center",
            va="bottom",
            fontsize=8,
            color="#063",
        )


def draw_plate_drawing(axes):
    """The plate as a dimensioned elevation, straight from the parameters."""
    half_width = params.PLATE_WIDTH / 2
    axes.add_patch(
        plt.Rectangle(
            (-half_width, params.PLATE_Y0),
            params.PLATE_WIDTH,
            params.PLATE_Y1 - params.PLATE_Y0,
            facecolor="#fde3d0",
            edgecolor=COLOURS["print"],
            lw=1.8,
        )
    )

    # Where the duct walls stand off the back of the plate.
    for band_y0, band_y1 in params.WALL_BANDS:
        axes.add_patch(
            plt.Rectangle(
                (-params.WALL_HALF_WIDTH, band_y0),
                2 * params.WALL_HALF_WIDTH,
                band_y1 - band_y0,
                facecolor="#c25a12",
                edgecolor="none",
            )
        )

    half_frame = params.FAN_FRAME / 2
    axes.add_patch(
        plt.Rectangle(
            (-half_frame, params.FAN_CENTRE_Y - half_frame),
            params.FAN_FRAME,
            params.FAN_FRAME,
            facecolor="none",
            edgecolor="#888",
            ls="--",
            lw=1.0,
        )
    )
    axes.add_patch(
        plt.Circle(
            (params.FAN_CENTRE_X, params.FAN_CENTRE_Y),
            params.FAN_OPENING_DIA / 2,
            facecolor="white",
            edgecolor=COLOURS["print"],
            lw=1.6,
        )
    )
    # The inlet chamfer is on the far side from this view, so it shows as the
    # wider circle the opening flares out to where it meets the duct.
    if params.FAN_INLET_CHAMFER:
        axes.add_patch(
            plt.Circle(
                (params.FAN_CENTRE_X, params.FAN_CENTRE_Y),
                params.FAN_OPENING_DIA / 2 + params.FAN_INLET_CHAMFER,
                facecolor="none",
                edgecolor=COLOURS["print"],
                ls=(0, (4, 3)),
                lw=1.0,
            )
        )
        axes.annotate(
            f"{params.FAN_INLET_CHAMFER:.0f} mm inlet chamfer,\nduct side",
            xy=(
                -(params.FAN_OPENING_DIA / 2 + params.FAN_INLET_CHAMFER) * 0.71,
                params.FAN_CENTRE_Y + (params.FAN_OPENING_DIA / 2) * 0.71,
            ),
            xytext=(-params.PLATE_WIDTH / 2 + 8, params.DUCT_HEIGHT - 16),
            fontsize=8,
            color="#8a3b12",
            arrowprops={"arrowstyle": "->", "color": "#8a3b12", "lw": 0.9},
        )
    for screw_x, screw_y in params.fan_screw_centres():
        axes.add_patch(
            plt.Circle((screw_x, screw_y), params.FAN_SCREW_DIA / 2, color="#444")
        )
    for boss_x in (-params.BOSS_X, params.BOSS_X):
        for boss_y in params.boss_rows():
            axes.add_patch(
                plt.Circle((boss_x, boss_y), params.HEAD_CBORE_DIA / 2, color="#bbb")
            )
            axes.add_patch(
                plt.Circle((boss_x, boss_y), params.SCREW_CLEAR_DIA / 2, color="#444")
            )
    for slot_x in params.TIE_SLOT_X:
        for slot_y in params.TIE_SLOT_Y:
            axes.add_patch(
                plt.Rectangle(
                    (slot_x - params.TIE_SLOT_W / 2, slot_y - params.TIE_SLOT_H / 2),
                    params.TIE_SLOT_W,
                    params.TIE_SLOT_H,
                    color="#444",
                )
            )

    # Rack unit boundaries, so it is obvious the plate spans three of them.
    for unit_index in range(1, params.RACK_UNITS):
        axes.axhline(
            unit_index * params.RACK_UNIT,
            color="#69f",
            ls=":",
            lw=1.0,
            xmin=0.02,
            xmax=0.98,
        )
    for unit_index in range(params.RACK_UNITS):
        axes.text(
            -half_width + 6,
            unit_index * params.RACK_UNIT + 4,
            f"U{unit_index + 1}",
            fontsize=9,
            color="#36c",
        )

    _dimension(axes, -half_width, half_width, f"{params.PLATE_WIDTH:.0f}", offset=-14)
    _dimension(
        axes,
        0.0,
        params.DUCT_HEIGHT,
        f"{params.DUCT_HEIGHT:.2f}  ({params.RACK_UNITS}U)",
        offset=-half_width - 14,
        vertical=True,
    )
    _dimension(
        axes,
        -params.FAN_OPENING_DIA / 2,
        params.FAN_OPENING_DIA / 2,
        f"Ø{params.FAN_OPENING_DIA:.0f} opening",
        offset=params.FAN_CENTRE_Y,
    )
    _dimension(
        axes,
        -params.BOSS_X,
        params.BOSS_X,
        f"{2 * params.BOSS_X:.2f} between M3 columns",
        offset=params.DUCT_HEIGHT + 6,
    )

    axes.set_xlim(-half_width - 34, half_width + 12)
    axes.set_ylim(-26, params.DUCT_HEIGHT + 22)
    axes.set_aspect("equal")
    axes.axis("off")
    axes.set_title(
        "Shared duct fan plate, seen from the rear\n"
        f"{params.PLATE_WIDTH:.0f} × {params.PLATE_Y1 - params.PLATE_Y0:.2f} "
        f"× {params.PLATE_THICKNESS:.0f} mm, 12 M3 into the ears, "
        f"one {params.FAN_SIZE} mm fan",
        fontsize=11,
    )


def draw_depth_section(axes):
    """The depth stack behind the rear rack rail, to scale."""
    spans = (
        ("rear ear", REAR_RAIL_Z, REAR_RAIL_Z + params.EAR_DEPTH, COLOURS["print"]),
        (
            "plate",
            REAR_RAIL_Z + params.EAR_DEPTH,
            REAR_RAIL_Z + params.EAR_DEPTH + params.PLATE_THICKNESS,
            "#c25a12",
        ),
        (
            f"{params.FAN_SIZE} mm fan",
            REAR_RAIL_Z + params.EAR_DEPTH + params.PLATE_THICKNESS,
            REAR_RAIL_Z + params.EAR_DEPTH + params.PLATE_THICKNESS + params.FAN_DEPTH,
            COLOURS["fan"],
        ),
    )
    for label, z0, z1, colour in spans:
        axes.add_patch(
            plt.Rectangle((z0, 0), z1 - z0, 30, facecolor=colour, edgecolor="white")
        )
        axes.text(
            (z0 + z1) / 2,
            34,
            f"{label}\n{z1 - z0:.0f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    axes.axvline(REAR_RAIL_Z, color="#36c", ls="--", lw=1.2)
    axes.text(
        REAR_RAIL_Z - 2, -6, "rear rack rail", ha="right", fontsize=8, color="#36c"
    )
    total = params.EAR_DEPTH + params.PLATE_THICKNESS + params.FAN_DEPTH
    _dimension(
        axes, REAR_RAIL_Z, REAR_RAIL_Z + total, f"{total:.0f} mm total", offset=-14
    )
    axes.set_xlim(REAR_RAIL_Z - 34, REAR_RAIL_Z + total + 14)
    axes.set_ylim(-26, 62)
    axes.set_aspect("equal")
    axes.axis("off")
    axes.set_title("Depth behind the rear rack rail", fontsize=11)


def main():
    """Write both the dimensioned drawing and the shaded assembly views."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=IMAGES / "shared-duct-assembly.png")
    parser.add_argument(
        "--drawing-out", type=Path, default=IMAGES / "shared-fan-plate.png"
    )
    arguments = parser.parse_args()

    figure, axes_grid = plt.subplots(
        1, 2, figsize=(16, 8), facecolor="white", width_ratios=[1.35, 1]
    )
    draw_plate_drawing(axes_grid[0])
    draw_depth_section(axes_grid[1])
    figure.tight_layout()
    arguments.drawing_out.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(arguments.drawing_out, dpi=110, facecolor="white")
    print(f"wrote {arguments.drawing_out}")

    parts = assemble()
    print(f"wrote {write_glb(parts, GLB_PATH)}")
    views = (
        (-38.0, 22.0, "From behind: one duct, one fan, three laptops"),
        (18.0, 14.0, "From the front: the plenum all three share"),
        (-90.0, 0.0, "From the side: 101 mm behind the rear rack rail"),
        (180.0, 0.0, "Head on, from the front of the rack"),
    )

    figure, axes_grid = plt.subplots(2, 2, figsize=(15, 11), facecolor="white")
    for axes, (azimuth, elevation, title) in zip(axes_grid.ravel(), views):
        draw(axes, parts, azimuth, elevation, title)
    figure.suptitle(
        f"Shared duct: {params.RACK_UNITS}U plenum, one {params.FAN_SIZE} mm "
        f"12 V case fan",
        fontsize=14,
    )
    figure.tight_layout()
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(arguments.out, dpi=110, facecolor="white")
    print(f"wrote {arguments.out}")


if __name__ == "__main__":
    main()
