"""Draw the fan plate from behind: fans, tie slots and how the leads route.

    python scripts/build_wiring_diagram.py

Writes docs/images/fan-wiring.png. Geometry comes from the same constants as
build_rear_fan_plate.py, so the diagram cannot drift from the part.

Requires matplotlib.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle

OUT = Path("docs/images/fan-wiring.png")

PLATE_WIDTH, PLATE_Y0, PLATE_Y1 = 222.0, 0.4, 44.05
FAN_CENTRES_X = (-63.55, 0.0, 63.55)
FAN_CENTRE_Y, FAN_OPENING_DIA, FAN_BODY = 22.225, 39.0, 40.0
FAN_SCREW_PITCH, FAN_SCREW_DIA = 32.0, 3.6
BOSS_X, BOSS_ROWS, CBORE_DIA = 102.82, (15.0, 29.45), 6.5
TIE_SLOT_X = (-31.78, 31.78, 89.44)
TIE_SLOT_Y = (17.5, 27.0)
TIE_SLOT_W, TIE_SLOT_H = 2.5, 5.0

PRINTED = "#e2571e"
FANC = "#5e3d30"
INK = "#22303c"
CABLE = "#c62828"
TIE = "#1462a8"

# The lead leaves the side of the frame at the plate face, at the corner
# nearest the bottom. Routed toward +x, where the bundle leaves for the USB
# supply, each lead is tied down in the first clear span it reaches.
EXIT_Y = 8.0
BUNDLE_Y = 22.225


def draw():
    figure, ax = plt.subplots(figsize=(16, 5.6))

    ax.add_patch(Rectangle((-PLATE_WIDTH / 2, PLATE_Y0), PLATE_WIDTH,
                           PLATE_Y1 - PLATE_Y0, facecolor=PRINTED, alpha=.13,
                           edgecolor=PRINTED, lw=1.8))

    for hole_x in (-BOSS_X, BOSS_X):
        for hole_y in BOSS_ROWS:
            ax.add_patch(Circle((hole_x, hole_y), CBORE_DIA / 2,
                                facecolor="white", edgecolor="#8a3b12", lw=1.1))
    ax.text(BOSS_X, PLATE_Y1 + 3.5, "M3 into the ear", ha="center",
            fontsize=8.5, color="#8a3b12")

    for fan_x in FAN_CENTRES_X:
        ax.add_patch(Rectangle((fan_x - FAN_BODY / 2, FAN_CENTRE_Y - FAN_BODY / 2),
                               FAN_BODY, FAN_BODY, facecolor=FANC, alpha=.16,
                               edgecolor=FANC, lw=1.3, ls="--"))
        ax.add_patch(Circle((fan_x, FAN_CENTRE_Y), FAN_OPENING_DIA / 2,
                            facecolor="white", edgecolor=INK, lw=1.6))
        ax.add_patch(Circle((fan_x, FAN_CENTRE_Y), 7.0, facecolor=FANC,
                            alpha=.55, edgecolor=FANC))
        for dx in (-FAN_SCREW_PITCH / 2, FAN_SCREW_PITCH / 2):
            for dy in (-FAN_SCREW_PITCH / 2, FAN_SCREW_PITCH / 2):
                ax.add_patch(Circle((fan_x + dx, FAN_CENTRE_Y + dy),
                                    FAN_SCREW_DIA / 2, facecolor="white",
                                    edgecolor=INK, lw=.8))
        ax.text(fan_x, FAN_CENTRE_Y, "fan", ha="center", va="center",
                fontsize=8.5, color="white", weight="bold")

    for slot_x in TIE_SLOT_X:
        for slot_y in TIE_SLOT_Y:
            ax.add_patch(Rectangle((slot_x - TIE_SLOT_W / 2, slot_y - TIE_SLOT_H / 2),
                                   TIE_SLOT_W, TIE_SLOT_H, facecolor=TIE,
                                   edgecolor=TIE))
        # the tie itself: a loop through both slots, over the bundle
        ax.add_patch(Rectangle((slot_x - 3.1, TIE_SLOT_Y[0] - 1.0), 6.2,
                               TIE_SLOT_Y[1] - TIE_SLOT_Y[0] + 2.0,
                               facecolor="none", edgecolor=TIE, lw=2.0,
                               joinstyle="round"))

    # The fans bolt flush to the plate, so the bundle can only lie against it
    # in the clear spans between fan bodies. Between them it rides over the
    # 20 mm-deep frames, which is where a tie cannot reach it -- drawn dashed.
    spans, blocked = [], []
    edges = [-PLATE_WIDTH / 2] + [v for f in FAN_CENTRES_X
                                  for v in (f - FAN_BODY / 2, f + FAN_BODY / 2)] \
        + [PLATE_WIDTH / 2]
    for i in range(0, len(edges) - 1):
        (spans if i % 2 == 0 else blocked).append((edges[i], edges[i + 1]))

    start_x = FAN_CENTRES_X[0] + FAN_BODY / 2
    for lo, hi in spans:
        if hi <= start_x:
            continue
        lo = max(lo, start_x)
        joined = sum(1 for f in FAN_CENTRES_X if f + FAN_BODY / 2 <= lo + 0.01)
        ax.plot([lo, hi], [BUNDLE_Y, BUNDLE_Y], color=CABLE,
                lw=1.8 + 0.8 * joined, solid_capstyle="round", zorder=6)
    for lo, hi in blocked:
        if hi <= start_x:
            continue
        joined = sum(1 for f in FAN_CENTRES_X if f + FAN_BODY / 2 <= lo + 0.01)
        ax.plot([lo, hi], [BUNDLE_Y, BUNDLE_Y], color=CABLE,
                lw=1.8 + 0.8 * joined, ls=(0, (4, 3)), alpha=.85, zorder=6)
        ax.text((lo + hi) / 2, BUNDLE_Y + 6.0, "over the frame", ha="center",
                fontsize=7.5, color=CABLE, style="italic")

    # each lead out of the side of its frame, up to the bundle in the span
    for fan_x in FAN_CENTRES_X:
        exit_x, exit_y = fan_x + FAN_BODY / 2, FAN_CENTRE_Y - FAN_SCREW_PITCH / 2
        ax.plot([exit_x, exit_x + 6.0, exit_x + 6.0],
                [exit_y, exit_y, BUNDLE_Y], color=CABLE, lw=1.7,
                solid_capstyle="round", zorder=7)
        ax.plot(exit_x, exit_y, "o", color=CABLE, ms=5, zorder=8)

    ax.add_patch(FancyArrowPatch((95.32, BUNDLE_Y), (112.0, BUNDLE_Y),
                                 arrowstyle="-|>", mutation_scale=16,
                                 color=CABLE, lw=4.2, zorder=6))
    ax.text(116.0, BUNDLE_Y + 5.0, "to the USB supply", ha="right",
            fontsize=9, color=CABLE, weight="bold")

    for slot_x in TIE_SLOT_X:
        ax.text(slot_x, PLATE_Y1 + 2.0, f"{slot_x:+.2f}", ha="center",
                fontsize=8, color=TIE)
    ax.text(0, -8.0, "Solid = the bundle lying on the plate, where a tie can hold it.\n"
                     "Dashed = riding over a fan frame, 20 mm off the plate.",
            ha="center", fontsize=9, color=INK)
    ax.text(89.44, -6.5, "strain relief where\nthe bundle leaves",
            ha="center", fontsize=8.5, color=TIE)

    ax.set_xlim(-118, 118)
    ax.set_ylim(-13, 54)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Fan plate from behind — fans, tie slots and lead routing",
                 fontsize=14, weight="bold", color=INK, pad=10)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(OUT, dpi=130)
    print("wrote", OUT)
    print(f"  {len(FAN_CENTRES_X)} fans at x {list(FAN_CENTRES_X)}")
    print(f"  {len(TIE_SLOT_X)} tie pairs at x {list(TIE_SLOT_X)}, "
          f"y {TIE_SLOT_Y[0]}/{TIE_SLOT_Y[1]}")


if __name__ == "__main__":
    draw()
