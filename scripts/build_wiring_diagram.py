"""Draw the shared duct fan plate from behind: the fan, the tie slots, the lead.

    python scripts/build_wiring_diagram.py

Writes docs/images/fan-wiring.png. Geometry comes from shared_duct_params.py,
so the diagram cannot drift from the part.

Upstream this drawing had to explain nine fans' worth of splices. One 12 V
case fan needs almost none of that, so the second panel spends the space on
the thing that is actually easy to get wrong: where the 12 V comes from. Three
supplies are drawn, because all three are reasonable and which one is right
depends on what is already in the rack.

Requires matplotlib.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # pylint: disable=wrong-import-position

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Rectangle  # noqa: E402

import shared_duct_params as params  # noqa: E402

OUT = Path("docs/images/fan-wiring.png")

PRINTED = "#e2571e"
FAN_BODY = "#5e3d30"
INK = "#22303c"
CABLE = "#c62828"
NEUTRAL = "#37474f"
TIE = "#1462a8"

# A case fan's lead leaves one corner of the frame, not the middle of a side.
# Drawn from the corner nearest the tie slots, which is the one to point at
# the plate when you fit it -- turn the fan 90 degrees and the lead has to
# cross the opening to reach the slots.
LEAD_CORNER = (
    params.FAN_FRAME / 2,
    params.FAN_CENTRE_Y - params.FAN_FRAME / 2,
)


def draw_plate(axes):
    """The plate from behind, with the fan on it and the lead tied down."""
    half_width = params.PLATE_WIDTH / 2
    axes.add_patch(
        Rectangle(
            (-half_width, params.PLATE_Y0),
            params.PLATE_WIDTH,
            params.PLATE_Y1 - params.PLATE_Y0,
            facecolor=PRINTED,
            alpha=0.16,
            edgecolor=PRINTED,
            lw=1.4,
        )
    )
    for unit_index in range(1, params.RACK_UNITS):
        axes.axhline(
            unit_index * params.RACK_UNIT,
            color="#69f",
            ls=":",
            lw=0.9,
            xmin=0.03,
            xmax=0.97,
        )

    axes.add_patch(
        Rectangle(
            (-params.FAN_FRAME / 2, params.FAN_CENTRE_Y - params.FAN_FRAME / 2),
            params.FAN_FRAME,
            params.FAN_FRAME,
            facecolor=FAN_BODY,
            alpha=0.20,
            edgecolor=FAN_BODY,
            lw=1.2,
        )
    )
    axes.add_patch(
        Circle(
            (params.FAN_CENTRE_X, params.FAN_CENTRE_Y),
            params.FAN_OPENING_DIA / 2,
            facecolor="white",
            edgecolor=PRINTED,
            lw=1.4,
        )
    )
    axes.text(
        params.FAN_CENTRE_X,
        params.FAN_CENTRE_Y,
        f"{params.FAN_SIZE} mm\n12 V case fan\nØ{params.FAN_OPENING_DIA:.0f} opening",
        ha="center",
        va="center",
        fontsize=10,
        color=INK,
    )
    for screw_x, screw_y in params.fan_screw_centres():
        axes.add_patch(
            Circle((screw_x, screw_y), params.FAN_SCREW_DIA / 2, color=NEUTRAL)
        )
    for boss_x in (-params.BOSS_X, params.BOSS_X):
        for boss_y in params.boss_rows():
            axes.add_patch(
                Circle((boss_x, boss_y), params.HEAD_CBORE_DIA / 2, color="#cfd8dc")
            )
            axes.add_patch(
                Circle((boss_x, boss_y), params.SCREW_CLEAR_DIA / 2, color=NEUTRAL)
            )

    for slot_x in params.TIE_SLOT_X:
        for slot_y in params.TIE_SLOT_Y:
            axes.add_patch(
                Rectangle(
                    (slot_x - params.TIE_SLOT_W / 2, slot_y - params.TIE_SLOT_H / 2),
                    params.TIE_SLOT_W,
                    params.TIE_SLOT_H,
                    facecolor=TIE,
                    edgecolor=TIE,
                )
            )

    # The lead: out of the fan's corner, up to the run, along it and away.
    axes.plot(
        [LEAD_CORNER[0], LEAD_CORNER[0] + 8, params.TIE_SLOT_X[-1] + 24],
        [LEAD_CORNER[1], params.FAN_CENTRE_Y, params.FAN_CENTRE_Y],
        color=CABLE,
        lw=2.2,
        solid_capstyle="round",
        zorder=5,
    )
    axes.annotate(
        "one lead, tied twice:\nfirst off the frame,\nthen strain relief",
        xy=(params.TIE_SLOT_X[0], params.FAN_CENTRE_Y),
        xytext=(params.TIE_SLOT_X[0] - 4, params.FAN_CENTRE_Y + 26),
        fontsize=9,
        color=TIE,
        ha="center",
        arrowprops={"arrowstyle": "->", "color": TIE, "lw": 0.9},
    )
    axes.annotate(
        "to 12 V",
        xy=(params.TIE_SLOT_X[-1] + 24, params.FAN_CENTRE_Y),
        xytext=(params.TIE_SLOT_X[-1] + 6, params.FAN_CENTRE_Y - 24),
        fontsize=9.5,
        color=CABLE,
        arrowprops={"arrowstyle": "->", "color": CABLE, "lw": 0.9},
    )

    axes.set_xlim(-half_width - 12, half_width + 34)
    axes.set_ylim(-16, params.DUCT_HEIGHT + 16)
    axes.set_aspect("equal")
    axes.axis("off")
    axes.set_title(
        "The plate from behind, fan fitted", fontsize=12.5, weight="bold", color=INK
    )


SUPPLIES = (
    (
        "12 V wall wart",
        "12 V, 1 A or better, 5.5/2.1 mm barrel.\n"
        "Barrel-to-bare-wire pigtail, red to red,\n"
        "black to black. Nothing else in the rack\n"
        "has to exist for this to work.",
    ),
    (
        "A PC power supply's Molex",
        "Yellow is +12 V, the black beside it is\n"
        "ground. Right if a supply is already in\n"
        "the rack, and it matches where the fan\n"
        "most likely came from.",
    ),
    (
        "12 V through a fan controller",
        "An inline PWM or voltage controller\n"
        "between supply and fan. One more thing\n"
        "to mount, and the only option that lets\n"
        "you trim the noise after the fact.",
    ),
)


def draw_supplies(axes):
    """Three ways to get 12 V to the plate, none of them wrong."""
    axes.axis("off")
    axes.set_xlim(0, 1)
    axes.set_ylim(0, 1)
    axes.set_title("Where the 12 V comes from", fontsize=12.5, weight="bold", color=INK)
    for index, (name, body) in enumerate(SUPPLIES):
        top = 0.94 - index * 0.315
        axes.add_patch(
            Rectangle(
                (0.02, top - 0.25),
                0.96,
                0.26,
                facecolor="#f4f6f7",
                edgecolor="#cfd8dc",
                lw=1.0,
                transform=axes.transAxes,
            )
        )
        axes.text(
            0.06, top - 0.03, name, fontsize=11, weight="bold", color=CABLE, va="top"
        )
        axes.text(0.06, top - 0.085, body, fontsize=9.5, color=INK, va="top")

    axes.text(
        0.06,
        -0.02,
        "A 4-pin fan on plain 12 V runs at full speed: the PWM pin idles high.\n"
        "Leave the tach pin unconnected unless something is listening to it.",
        fontsize=9.5,
        color="#44515c",
        va="top",
    )


def main():
    """Draw both panels and write the PNG."""
    figure, axes = plt.subplots(
        1, 2, figsize=(17, 8.4), width_ratios=[1.5, 1], facecolor="white"
    )
    draw_plate(axes[0])
    draw_supplies(axes[1])
    figure.suptitle(
        f"Wiring one {params.FAN_SIZE} mm fan on a {params.RACK_UNITS}U shared duct",
        fontsize=14.5,
        weight="bold",
        color=INK,
    )
    figure.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUT, dpi=130, facecolor="white")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
