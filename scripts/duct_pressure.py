"""Estimate what the shared duct asks of a fan, in pascals.

    python scripts/duct_pressure.py

A fan's advertised airflow is its *free-air* figure: the flow it moves against
no resistance at all. What it actually delivers is where its pressure-flow
curve crosses the system's resistance curve, and the only way to know that is
to know both. This works out the system half from the areas the assembly check
measures, so the README can talk about the operating point with numbers
attached instead of adjectives.

**This is a first-order estimate, not CFD and not a measurement.** It models the
duct as two losses in series -- accelerating the air into the plenum, then
pushing it through the fan opening -- with textbook loss coefficients. Real
ducts have corners, a laptop in the middle of them and a fan that does not
produce uniform flow. Treat the numbers as an order of magnitude, which is
enough to answer the question actually being asked: is this a system where a
big slow fan wins, or one where small fast fans do.

Standard library only.
"""

import math

AIR_DENSITY = 1.2  # kg/m3 at 20 C, sea level
PA_PER_MM_H2O = 9.80665
CFM_TO_M3S = 0.0004719474

# Measured by check_rear_assembly.py off the actual meshes, with three laptops
# in the rack. Not nominal dimensions -- the numbers that script prints.
PLENUM_FREE_AREA_MM2 = 13649.0
FAN_OPENING_AREA_MM2 = 10207.0
RACK_UNITS = 3

# Entry loss coefficients, relative to the dynamic pressure at the opening.
# A sharp-edged hole in a plate makes the flow separate at the lip and form a
# vena contracta, so the throat that passes air is smaller than the hole; the
# textbook figure is about 0.5. Easing the lip suppresses the separation. A
# 45-degree chamfer of a few millimetres is worth roughly 0.2, and a full
# bellmouth radius about 0.05. This design chamfers 3 mm.
K_SHARP_ORIFICE = 0.5
K_CHAMFERED = 0.2
K_PLENUM_ENTRY = 0.5  # air turning into the plenum through each unit's exit gap

SURVEY_CFM = (15.0, 30.0, 45.0, 60.0)

# The two ways to fill this duct, for the comparison the README has to make
# honestly. Peak static pressure scales roughly with tip speed squared, so tip
# speed is the fair way to compare a big slow fan with a small fast one --
# diameter alone says nothing.
FAN_OPTIONS = (
    ("one 120 mm case fan", 120.0, 1, 1200.0),
    ("one 120 mm at full tilt", 120.0, 1, 2000.0),
    ("nine 40 mm NF-A4x20", 39.0, 9, 5000.0),
)


def dynamic_pressure(flow_m3s, area_mm2):
    """Velocity pressure of `flow` through `area`, in pascals."""
    velocity = flow_m3s / (area_mm2 * 1e-6)
    return 0.5 * AIR_DENSITY * velocity**2, velocity


def system_pressure(flow_cfm, opening_k):
    """Total static pressure the fan must produce at this flow, in pascals."""
    flow = flow_cfm * CFM_TO_M3S
    # Each rack unit passes its share through its own slice of the plenum.
    per_unit_area = PLENUM_FREE_AREA_MM2 / RACK_UNITS
    plenum_q, plenum_v = dynamic_pressure(flow / RACK_UNITS, per_unit_area)
    opening_q, opening_v = dynamic_pressure(flow, FAN_OPENING_AREA_MM2)
    # The air keeps its velocity head leaving the opening, so that term counts
    # once on its own account plus the entry loss it costs to get there.
    total = K_PLENUM_ENTRY * plenum_q + (opening_k + 1.0) * opening_q
    return {
        "flow_cfm": flow_cfm,
        "plenum_velocity": plenum_v,
        "opening_velocity": opening_v,
        "plenum_loss": K_PLENUM_ENTRY * plenum_q,
        "opening_loss": (opening_k + 1.0) * opening_q,
        "total_pa": total,
        "total_mm_h2o": total / PA_PER_MM_H2O,
    }


def main():
    """Print the system curve, and what the chamfer is worth on it."""
    print("Shared duct system resistance, first-order estimate")
    print(f"  plenum free area   : {PLENUM_FREE_AREA_MM2:8.0f} mm2 (measured)")
    print(f"  fan opening        : {FAN_OPENING_AREA_MM2:8.0f} mm2 (measured)")
    print()
    print("  flow    plenum    opening   static pressure the fan must make")
    print("  (CFM)    (m/s)     (m/s)      sharp lip      3 mm chamfer   saved")
    print("  " + "-" * 68)
    for flow_cfm in SURVEY_CFM:
        sharp = system_pressure(flow_cfm, K_SHARP_ORIFICE)
        eased = system_pressure(flow_cfm, K_CHAMFERED)
        saved = sharp["total_pa"] - eased["total_pa"]
        print(
            f"  {flow_cfm:5.0f}   {sharp['plenum_velocity']:6.2f}    "
            f"{sharp['opening_velocity']:6.2f}   "
            f"{sharp['total_pa']:6.2f} Pa       {eased['total_pa']:6.2f} Pa    "
            f"{saved:5.2f} Pa "
            f"({saved / sharp['total_pa'] * 100:3.0f}%)"
        )

    print()
    print("  In mm H2O, the unit fan curves are published in:")
    for flow_cfm in SURVEY_CFM:
        eased = system_pressure(flow_cfm, K_CHAMFERED)
        print(f"    {flow_cfm:5.0f} CFM -> {eased['total_mm_h2o']:5.3f} mm H2O")

    print()
    print("  A typical 120 mm case fan peaks around 1.0-2.5 mm H2O, and this duct")
    print("  asks under 0.4 mm H2O even at 45 CFM. The fan therefore runs near")
    print("  the free-delivery end of its curve: this is a LOW resistance system,")
    print("  and static pressure is not what limits it.")
    print()
    print("  So what does? Compare the two ways to fill the same duct:")
    print()
    print("  option                        swept area   tip speed   pressure")
    print("  " + "-" * 62)
    for label, diameter, count, rpm in FAN_OPTIONS:
        swept = count * math.pi * (diameter / 2) ** 2
        tip = math.pi * (diameter / 1000.0) * (rpm / 60.0)
        # Peak static pressure goes as tip speed squared, so this is a ratio,
        # not an absolute -- normalised to the slow 120 for readability.
        reference = math.pi * (120.0 / 1000.0) * (1200.0 / 60.0)
        print(
            f"  {label:28s} {swept:7.0f} mm2   {tip:5.2f} m/s   "
            f"{(tip / reference) ** 2:4.2f}x"
        )
    print()
    _noise_estimate()
    print()
    print("  Swept area is a near tie. The 40 mm array spins 4.2x the rpm, which")
    print("  is 1.35x the tip speed, so it has MORE pressure headroom and more")
    print("  peak flow -- not less. But the duct needs neither: it asks for a")
    print("  fraction of what either can produce, so pressure does not decide")
    print("  between them and neither does swept area.")
    print()
    print("  What is left is noise and the number of things to wire. Those are")
    print("  the reasons to run one big fan here. Not static pressure, which is")
    print("  the argument usually reached for and does not apply to a duct this")
    print("  open.")


def _noise_estimate():
    """Why the array is louder, in dB, from tip speed and source count.

    Two independent effects, both rules of thumb rather than measurements:
    broadband fan noise rises with roughly the fifth power of tip speed, and
    nine uncorrelated sources of equal output sum to 10*log10(9) above one.
    """
    slow_tip = math.pi * 0.120 * (1200.0 / 60.0)
    array_tip = math.pi * 0.039 * (5000.0 / 60.0)
    from_speed = 50.0 * math.log10(array_tip / slow_tip)  # 10*log10(ratio**5)
    from_count = 10.0 * math.log10(9.0)
    print("  And the noise, as rules of thumb rather than measurements:")
    print(
        f"    tip speed {array_tip / slow_tip:.2f}x, at a fifth-power law : "
        f"{from_speed:+5.1f} dB"
    )
    print(f"    nine uncorrelated sources instead of one    : {from_count:+5.1f} dB")
    print(
        f"    the 40 mm array is therefore on the order of "
        f"{from_speed + from_count:+5.1f} dB louder"
    )


if __name__ == "__main__":
    main()
