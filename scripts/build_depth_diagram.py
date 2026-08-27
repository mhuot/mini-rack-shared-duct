"""Draw the side section showing how far the laptops reach into the rear ears.

    python scripts/build_depth_diagram.py

Writes docs/images/laptop-depth.png. The geometry is not drawn by eye: the
depth at which the laptop stops is read out of exports/rear_ear_v2.stl by
finding where the laptop channel closes and the back plate begins.

Requires numpy, trimesh and matplotlib.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # pylint: disable=wrong-import-position
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

OUT = Path("docs/images/laptop-depth.png")
EAR_STL = Path("exports/rear_ear_v2.stl")

RACK_UNIT = 44.45
RAIL_DEPTH = 200.0  # front rail face to rear rail face
RAIL_THICK = 20.0
EAR_DEPTH = 72.0  # rear ear, behind the rear rail face
FRONT_EAR = (-2.0, 6.0)
PLATE = (272.0, 276.0)  # fan plate
FAN_DEPTH = 25.0  # a 120 mm case fan, not a 40 mm Noctua
ROD_Z = (-2.0, 241.0)
ROD_ROWS = (6.22, 38.23)
ROD_DIA = 8.0
LAPTOP_SEAT = 10.22  # the laptop rests on the lower rods
# Only the bottom rack unit has a wall below it and only the top one has a
# wall above; a middle unit opens straight into the shared duct. Drawn here
# for the bottom unit, which is the case that has both a wall and a laptop.
DUCT = ((2.1, 4.3),)
DUCT_Z = (200.0, 274.0)

LAPTOPS = (
    ("MacBook Pro 14", 312.6, 15.5, "#2f3437"),
    ("Surface Laptop 13.8", 301.0, 17.5, "#1d1f21"),
)

INK = "#22303c"
PRINTED = "#e2571e"
METAL = "#9aa4ad"
DIM = "#0b6b3a"


def channel_closes(stl_path):
    """Depth into the ear at which the laptop channel gives way to the plate."""
    mesh = trimesh.load_mesh(stl_path)
    triangles = mesh.triangles
    origin = np.array([-14.0, 22.0, -20.0])
    direction = np.array([0.0, 0.0, 1.0])
    corner = triangles[:, 0]
    edge_a, edge_b = triangles[:, 1] - corner, triangles[:, 2] - corner
    pvec = np.cross(direction, edge_b)
    determinant = np.einsum("ij,ij->i", edge_a, pvec)
    usable = np.abs(determinant) > 1e-9
    inverse = np.where(usable, 1.0 / np.where(usable, determinant, 1.0), 0.0)
    to_corner = origin - corner
    bary_u = np.einsum("ij,ij->i", to_corner, pvec) * inverse
    qvec = np.cross(to_corner, edge_a)
    bary_v = np.einsum("j,ij->i", direction, qvec) * inverse
    distance = np.einsum("ij,ij->i", edge_b, qvec) * inverse
    hit = (
        usable & (bary_u >= 0) & (bary_v >= 0) & (bary_u + bary_v <= 1) & (distance > 0)
    )
    crossings = np.sort(origin[2] + distance[hit])
    if len(crossings) < 2:
        raise SystemExit("could not find the back plate face in the ear")
    return float(crossings[0])


def dimension(ax, y, x0, x1, text, colour=DIM, above=True):
    """A dimension line with its number, above or below."""
    ax.annotate(
        "",
        xy=(x0, y),
        xytext=(x1, y),
        arrowprops={"arrowstyle": "<->", "color": colour, "lw": 1.6},
    )
    ax.text(
        (x0 + x1) / 2,
        y + (2.0 if above else -5.5),
        text,
        ha="center",
        fontsize=10.5,
        color=colour,
        weight="bold",
    )


def draw(ax, name, length, thickness, colour, stop_z):
    """One laptop's side section, from the front rail to the fan."""
    # rack rails
    for z0, z1, label in (
        (0.0, RAIL_THICK, "front rail"),
        (RAIL_DEPTH - RAIL_THICK, RAIL_DEPTH, "rear rail"),
    ):
        ax.add_patch(
            Rectangle(
                (z0, -6),
                z1 - z0,
                RACK_UNIT + 12,
                facecolor=METAL,
                alpha=0.35,
                edgecolor=METAL,
            )
        )
        ax.text(
            (z0 + z1) / 2,
            RACK_UNIT + 7.5,
            label,
            ha="center",
            fontsize=8.5,
            color="#5b6770",
        )

    # rear ear: body to the channel, then the solid back plate
    ax.add_patch(
        Rectangle(
            (RAIL_DEPTH, 0),
            EAR_DEPTH,
            RACK_UNIT,
            facecolor=PRINTED,
            alpha=0.16,
            edgecolor=PRINTED,
            lw=1.4,
        )
    )
    ax.add_patch(
        Rectangle(
            (stop_z, 0),
            RAIL_DEPTH + EAR_DEPTH - stop_z,
            RACK_UNIT,
            facecolor=PRINTED,
            alpha=0.55,
            edgecolor=PRINTED,
            lw=1.4,
        )
    )
    ax.text(
        stop_z + 3.5,
        RACK_UNIT / 2,
        "back\nplate",
        fontsize=8.5,
        color="#8a3b12",
        ha="left",
        va="center",
    )

    ax.add_patch(
        Rectangle(
            (FRONT_EAR[0], 0),
            FRONT_EAR[1] - FRONT_EAR[0],
            RACK_UNIT,
            facecolor=PRINTED,
            alpha=0.55,
            edgecolor=PRINTED,
            lw=1.2,
        )
    )

    for band in DUCT:
        ax.add_patch(
            Rectangle(
                (DUCT_Z[0], band[0]),
                DUCT_Z[1] - DUCT_Z[0],
                band[1] - band[0],
                facecolor=PRINTED,
                edgecolor=PRINTED,
                lw=0.8,
            )
        )
    ax.add_patch(
        Rectangle(
            (PLATE[0], 0.4),
            PLATE[1] - PLATE[0],
            RACK_UNIT - 0.8,
            facecolor=PRINTED,
            alpha=0.85,
            edgecolor=PRINTED,
        )
    )
    ax.add_patch(
        Rectangle(
            (PLATE[1], 2.7),
            FAN_DEPTH,
            RACK_UNIT - 5.4,
            facecolor="#5e3d30",
            alpha=0.75,
            edgecolor="#5e3d30",
        )
    )
    ax.text(
        PLATE[1] + FAN_DEPTH / 2,
        RACK_UNIT / 2,
        "fan",
        ha="center",
        va="center",
        fontsize=8,
        color="white",
        rotation=90,
    )

    # The bore is open all the way to the back plate -- the same face the
    # laptop stops against -- but the 243 mm rod ends well short of it.
    for row in ROD_ROWS:
        ax.add_patch(
            Rectangle(
                (RAIL_DEPTH, row - ROD_DIA / 2),
                stop_z - RAIL_DEPTH,
                ROD_DIA,
                facecolor="none",
                edgecolor=METAL,
                lw=0.9,
                ls=(0, (3, 2)),
            )
        )
        ax.add_patch(
            Rectangle(
                (ROD_Z[0], row - ROD_DIA / 2),
                ROD_Z[1] - ROD_Z[0],
                ROD_DIA,
                facecolor=METAL,
                edgecolor="#6d7780",
                lw=0.8,
            )
        )
    ax.text(
        120,
        ROD_ROWS[0],
        "8 mm rod, 243 long",
        fontsize=8.5,
        color="#404a52",
        ha="center",
        va="center",
    )
    ax.annotate(
        f"{stop_z - ROD_Z[1]:.0f} mm of bore left empty:\n"
        f"the rod stops {stop_z - ROD_Z[1]:.0f} short of the back plate",
        xy=((ROD_Z[1] + stop_z) / 2, ROD_ROWS[1]),
        xytext=(PLATE[1] + FAN_DEPTH + 6, ROD_ROWS[1] + 6),
        fontsize=9,
        color="#7a4b00",
        va="center",
        arrowprops={"arrowstyle": "->", "color": "#7a4b00", "lw": 1.1},
    )

    front = stop_z - length
    ax.add_patch(
        Rectangle(
            (front, LAPTOP_SEAT),
            length,
            thickness,
            facecolor=colour,
            edgecolor="black",
            lw=1.0,
        )
    )
    ax.text(
        front + length * 0.42,
        LAPTOP_SEAT + thickness / 2,
        name,
        color="white",
        fontsize=10,
        ha="center",
        va="center",
        weight="bold",
    )

    dimension(ax, -13.0, front, 0.0, f"{-front:.1f} out the front")
    dimension(ax, -13.0, RAIL_DEPTH, stop_z, f"{stop_z - RAIL_DEPTH:.0f} into the ear")
    dimension(ax, RACK_UNIT + 16.0, 0.0, RAIL_DEPTH, f"{RAIL_DEPTH:.0f} rail to rail")
    dimension(
        ax, RACK_UNIT + 16.0, RAIL_DEPTH, RAIL_DEPTH + EAR_DEPTH, f"{EAR_DEPTH:.0f} ear"
    )
    # The duct exit is only 7 mm, far narrower than any label, so dimension it
    # below the section and lead a line up to the gap it refers to.
    exit_y = -19.0
    ax.annotate(
        "",
        xy=(stop_z, exit_y),
        xytext=(PLATE[0], exit_y),
        arrowprops={"arrowstyle": "<->", "color": "#1462a8", "lw": 1.6},
    )
    for x in (stop_z, PLATE[0]):
        ax.plot([x, x], [exit_y, LAPTOP_SEAT - 1.0], color="#1462a8", lw=0.8, ls=":")
    ax.text(
        PLATE[1] + FAN_DEPTH + 6,
        exit_y,
        f"{PLATE[0] - stop_z:.0f} mm duct exit:\nthe gap the air turns through",
        ha="left",
        va="center",
        fontsize=9.5,
        color="#1462a8",
        weight="bold",
    )

    ax.annotate(
        "2.2 mm duct wall, grown onto the plate\n(bottom rack unit only)",
        xy=(232, DUCT[0][1]),
        xytext=(206, RACK_UNIT + 4.5),
        fontsize=8.5,
        color="#8a3b12",
        arrowprops={"arrowstyle": "->", "color": "#8a3b12", "lw": 0.9},
    )

    ax.axvline(stop_z, color=INK, ls="--", lw=1.1)
    ax.set_xlim(-70, 470)
    ax.set_ylim(-26, RACK_UNIT + 24)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(
        f"{name} — {length:.1f} mm deep, {thickness} mm thick",
        fontsize=12.5,
        weight="bold",
        color=INK,
        pad=4,
    )


def main():
    """Draw a section per laptop and write the PNG."""
    stop_local = channel_closes(EAR_STL)
    stop_z = RAIL_DEPTH + stop_local
    print(
        f"laptop channel closes at ear-local z = {stop_local:.1f} mm "
        f"-> stop at {stop_z:.1f}"
    )

    figure, axes = plt.subplots(len(LAPTOPS), 1, figsize=(16.5, 7.0))
    for ax, (name, length, thickness, colour) in zip(axes, LAPTOPS):
        draw(ax, name, length, thickness, colour, stop_z)
        front = stop_z - length
        print(
            f"  {name:22s} front edge {front:+.1f} mm, "
            f"noses {-front:.1f} mm past the front rail"
        )

    figure.suptitle(
        "How far the laptops reach into the rear ears  ·  side section, "
        "every rack unit identical",
        fontsize=14,
        weight="bold",
        color=INK,
        y=0.98,
    )
    figure.text(
        0.5,
        0.015,
        "Rear edge stops where the ear's laptop channel closes and the "
        "back plate begins. That face holds the laptop clear of the fan "
        "plate, and the gap it leaves is where this unit feeds the "
        "shared duct. Behind the rear rack rail: 72 ear + 4 plate + "
        "25 fan = 101 mm.",
        ha="center",
        fontsize=10.5,
        color="#44515c",
    )
    figure.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.075, hspace=0.28)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUT, dpi=130)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
