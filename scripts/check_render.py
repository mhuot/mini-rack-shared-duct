"""Check that the rack in the renders is the rack in the design.

    python scripts/check_render.py

This exists because two bugs got all the way into published images without
looking wrong enough to notice.

The first: the rods were built as z-axis cylinders and then rotated onto the y
axis, so every render showed four short vertical posts per rack unit instead of
four 243 mm rods running front to back. It looked like detail. It was nonsense.

The second: the camera azimuths were inverted, so the view captioned "from the
front" was looking at the back of the rack. Both renders were plausible, both
were wrong, and neither would ever have failed a test that only asked whether
the script finished.

So the invariants are asserted instead of eyeballed. Every one of these is a
statement the renders make to a reader, and a reader who measures a render and
gets a different answer than the CAD has been misled by this repo.

Requires trimesh and numpy.
"""

import math
import sys

import numpy as np
import trimesh

import render_shared_duct as render
import shared_duct_params as params

TOLERANCE = 0.01

# What the assembly is made of. A part silently dropped from a render -- an
# exception swallowed, a loop that stopped early -- shows up here as a count.
EXPECTED_COUNTS = {
    "frame": 12,  # 4 posts + 2 frames x (front, rear) + 2 frames x 2 side rails
    "acrylic": 3,  # two sides and the top
    "foot": 4,
    "print": 4 * params.RACK_UNITS + 1,  # ears, front and rear, both sides, plus plate
    "rod": 4 * params.RACK_UNITS,
    "fan": 1,
}

# Every view's caption claims a direction. z grows toward the back of the rack,
# so a camera looking at the front has forward.z > 0.
# Pairs of materials that must never share space, and how much overlap is a
# modelling artifact rather than a collision. Coincident faces -- a laptop
# resting exactly on the seat plane the ear's relief is cut to -- produce
# films a hundredth of a millimetre thick, and calling those collisions would
# mean the check cried wolf and got ignored. Anything above the threshold is a
# part passing through another part.
SLIVER_LIMIT = 25.0  # mm3
FORBIDDEN_PAIRS = (
    ("laptop", "frame", "a laptop cannot pass through the rack's rails"),
    ("laptop", "acrylic", "a laptop cannot pass through the cabinet's side"),
    ("print", "frame", "a printed part cannot occupy the rack's rails"),
    ("print", "acrylic", "a printed part cannot pass through the cabinet's side"),
    ("rod", "frame", "a rod cannot pass through the rack's rails"),
)

VIEW_EXPECTATIONS = (
    ("behind", -1),
    ("front", +1),
    ("head on", +1),
)


class Failures:
    """Collects failures so one run reports all of them, not just the first."""

    def __init__(self):
        self.messages = []

    def check(self, condition, message):
        """Record `message` unless `condition` holds. Returns the condition."""
        if not condition:
            self.messages.append(message)
        return condition

    def report(self, heading):
        """Print what failed under this heading, and how many."""
        print(f"\n=== {heading} ===")
        if not self.messages:
            print("  all checks passed")
        for message in self.messages:
            print(f"  FAIL {message}")
        return len(self.messages)


def check_inventory(parts, failures):
    """Every part present, once, and solid."""
    counts = {}
    for _, colour in parts:
        counts[colour] = counts.get(colour, 0) + 1
    for colour, expected in EXPECTED_COUNTS.items():
        failures.check(
            counts.get(colour, 0) == expected,
            f"expected {expected} {colour} parts, found {counts.get(colour, 0)}",
        )
    failures.check(
        counts.get("macbook", 0) + counts.get("surface", 0) == params.RACK_UNITS,
        f"expected {params.RACK_UNITS} laptops, "
        f"found {counts.get('macbook', 0) + counts.get('surface', 0)}",
    )
    for index, (mesh, colour) in enumerate(parts):
        failures.check(
            mesh.volume > 0,
            f"{colour}[{index}] has zero or inverted volume ({mesh.volume:.3f})",
        )


def check_rods(parts, failures):
    """Rods run front to back, full length, on the rod lines.

    This is the check that would have caught the rotated rods. A rod's longest
    axis has to be z; if the mesh is 243 mm tall instead of 243 mm deep, the
    render is drawing scaffolding, not a drawer slide.
    """
    rods = [mesh for mesh, colour in parts if colour == "rod"]
    expected_length = render.ROD_Z[1] - render.ROD_Z[0]
    expected_positions = {
        (round(rod_x, 2), round(unit_index * params.RACK_UNIT + rod_y, 2))
        for unit_index in range(params.RACK_UNITS)
        for rod_y in render.ROD_ROWS_PER_UNIT
        for rod_x in (-params.BOSS_X, params.BOSS_X)
    }
    seen = set()
    for index, rod in enumerate(rods):
        extents = rod.extents
        failures.check(
            abs(extents[2] - expected_length) < TOLERANCE,
            f"rod[{index}] is {extents[2]:.1f} mm deep, expected {expected_length:.1f} "
            "-- is it rotated onto the wrong axis?",
        )
        failures.check(
            abs(extents[0] - render.ROD_DIA) < TOLERANCE
            and abs(extents[1] - render.ROD_DIA) < TOLERANCE,
            f"rod[{index}] cross-section is {extents[0]:.1f} x {extents[1]:.1f}, "
            f"expected {render.ROD_DIA} x {render.ROD_DIA}",
        )
        centre = rod.bounds.mean(axis=0)
        seen.add((round(centre[0], 2), round(centre[1], 2)))
    failures.check(
        seen == expected_positions,
        f"rods are not on the rod lines: {sorted(seen - expected_positions)} "
        f"unexpected, {sorted(expected_positions - seen)} missing",
    )


def check_rasteriser(failures):
    """The depth test resolves what triangle sorting could not.

    Three properties, each one a case the painter's algorithm got wrong:

    Order independence -- a far triangle drawn after a near one must not paint
    over it. Sorting by centroid gets this right only when the centroid order
    happens to match the pixel order.

    Interpenetration -- two triangles that pass through each other have no
    correct draw order at all. Each has to win the pixels where it is nearer,
    which is only expressible per pixel.

    Transparency -- a clear triangle in front of an opaque one tints it rather
    than replacing it, and must not write depth.
    """
    size = 8
    red = np.array([1.0, 0.0, 0.0, 1.0])
    green = np.array([0.0, 1.0, 0.0, 1.0])
    corner = (1, 1)

    def flat(depth_value):
        return np.array(
            [
                [0.0, 0.0, depth_value],
                [size, 0.0, depth_value],
                [0.0, size, depth_value],
            ]
        )

    for label, first, second, first_colour in (
        ("far drawn after near", flat(1.0), flat(5.0), red),
        ("near drawn after far", flat(5.0), flat(1.0), green),
    ):
        image = np.tile(render.BACKGROUND, (size, size, 1))
        depth = np.full((size, size), np.inf)
        render.fill(first, image, depth, red, 1.0)
        render.fill(second, image, depth, green, 1.0)
        failures.check(
            (
                np.allclose(image[corner], first_colour[:3])
                if label.startswith("far")
                else np.allclose(image[corner], green[:3])
            ),
            f"{label}: the nearer triangle did not win the pixel",
        )

    # A triangle whose depth ramps across x, crossed by a flat one at 5.
    image = np.tile(render.BACKGROUND, (size, size, 1))
    depth = np.full((size, size), np.inf)
    ramp = np.array([[0.0, 0.0, 0.0], [size, 0.0, 10.0], [0.0, size, 0.0]])
    render.fill(ramp, image, depth, red, 1.0)
    render.fill(flat(5.0), image, depth, green, 1.0)
    left_is_red = np.allclose(image[1, 1], red[:3])
    right_is_green = np.allclose(image[1, size - 2], green[:3])
    failures.check(
        left_is_red and right_is_green,
        "interpenetrating triangles did not each win the pixels where they "
        f"are nearer (left={image[1, 1]}, right={image[1, size - 2]})",
    )

    # A clear triangle in front of an opaque one tints without replacing it.
    image = np.tile(render.BACKGROUND, (size, size, 1))
    depth = np.full((size, size), np.inf)
    render.fill(flat(5.0), image, depth, red, 1.0)
    render.fill(flat(1.0), image, depth, green, 0.5)
    tinted = image[corner]
    failures.check(
        np.allclose(tinted, [0.5, 0.5, 0.0]),
        f"a transparent triangle did not blend over the opaque one: {tinted}",
    )
    failures.check(
        np.isclose(depth[corner], 5.0),
        f"a transparent triangle wrote to the depth buffer: {depth[corner]}",
    )


def _by_material(parts):
    """Group parts by material, with the two laptop colours merged."""
    groups = {}
    for index, (mesh, colour) in enumerate(parts):
        key = "laptop" if colour in render.LAPTOPS else colour
        groups.setdefault(key, []).append((f"{colour}[{index}]", mesh))
    return groups


def check_interference(parts, failures):
    """No part passes through another part.

    This is the check that catches a render being physically impossible rather
    than merely ugly. It found that the cabinet opening was modelled 0.2 mm
    narrower than the MacBook Pro 14 that has to slide through it -- an error
    inherited from upstream, invisible in every render either project has
    published, and obvious the moment anything actually intersected the two.
    """
    groups = _by_material(parts)
    for left, right, why in FORBIDDEN_PAIRS:
        for name_a, mesh_a in groups.get(left, []):
            for name_b, mesh_b in groups.get(right, []):
                low_a, high_a = mesh_a.bounds
                low_b, high_b = mesh_b.bounds
                if np.any(high_a < low_b) or np.any(high_b < low_a):
                    continue
                overlap = trimesh.boolean.intersection(
                    [mesh_a, mesh_b], engine="manifold"
                )
                volume = 0.0 if overlap is None or overlap.is_empty else overlap.volume
                failures.check(
                    volume <= SLIVER_LIMIT,
                    f"{name_a} passes through {name_b} " f"({volume:.1f} mm3) -- {why}",
                )


def check_clearances(failures):
    """Every laptop fits through the opening it has to slide through.

    Stated as a clearance rather than left implicit in an intersection test,
    because the useful thing to know when it fails is by how much.
    """
    for name, spec in render.LAPTOPS.items():
        clearance = 2 * render.POST_X_INNER - spec["width"]
        failures.check(
            clearance > 0,
            f"{name} is {spec['width']:.1f} mm wide and the rails are "
            f"{2 * render.POST_X_INNER:.1f} mm apart: {clearance:+.2f} mm",
        )
    widest = max(spec["width"] for spec in render.LAPTOPS.values())
    failures.check(
        2 * params.EAR_OFFSET_X + 2 * 0.65 >= widest,
        f"the widest laptop ({widest:.1f} mm) does not fit the ears' " "laptop relief",
    )


def check_laptops(parts, failures):
    """Laptops nose out the front by the documented amount, and fit the rack."""
    for (mesh, colour), name in zip(
        [item for item in parts if item[1] in render.LAPTOPS], render.STACK
    ):
        spec = render.LAPTOPS[colour]
        low, high = mesh.bounds
        overhang = -low[2]
        expected = spec["length"] - render.LAPTOP_STOP_Z
        failures.check(
            abs(overhang - expected) < TOLERANCE,
            f"{name} noses {overhang:.1f} mm past the front rail, "
            f"expected {expected:.1f}",
        )
        failures.check(
            abs(high[2] - render.LAPTOP_STOP_Z) < TOLERANCE,
            f"{name} stops at z={high[2]:.1f}, expected {render.LAPTOP_STOP_Z}",
        )
        failures.check(
            high[0] <= render.POST_X_OUTER and low[0] >= -render.POST_X_OUTER,
            f"{name} is wider than the cabinet: x {low[0]:.1f}..{high[0]:.1f}",
        )


def check_cabinet(parts, failures):
    """The rack is a 4U cabinet and everything printed lives inside its width."""
    frame = [mesh for mesh, colour in parts if colour == "frame"]
    low = np.min([mesh.bounds[0] for mesh in frame], axis=0)
    high = np.max([mesh.bounds[1] for mesh in frame], axis=0)
    failures.check(
        abs(high[0] - render.POST_X_OUTER) < TOLERANCE,
        f"cabinet is {high[0] * 2:.1f} mm wide, expected "
        f"{render.POST_X_OUTER * 2:.1f}",
    )
    failures.check(
        abs((high[1] - low[1]) - (render.RACK_U * params.RACK_UNIT + 24.0)) < TOLERANCE,
        f"cabinet frame is {high[1] - low[1]:.1f} mm tall, expected "
        f"{render.RACK_U * params.RACK_UNIT + 24.0:.1f}",
    )
    failures.check(
        params.DUCT_HEIGHT <= render.RACK_U * params.RACK_UNIT,
        f"a {params.RACK_UNITS}U duct does not fit a {render.RACK_U}U cabinet",
    )

    feet = [mesh for mesh, colour in parts if colour == "foot"]
    for index, foot in enumerate(feet):
        failures.check(
            foot.bounds[1][1] <= render.FRAME_Y0 + TOLERANCE,
            f"foot[{index}] reaches y={foot.bounds[1][1]:.1f}, "
            f"which is above the bottom of the frame at {render.FRAME_Y0}",
        )
        failures.check(
            abs(foot.extents[1] - render.FOOT_HEIGHT) < TOLERANCE,
            f"foot[{index}] is {foot.extents[1]:.1f} mm tall, expected "
            f"{render.FOOT_HEIGHT} -- is it rotated onto the wrong axis?",
        )


def check_duct_placement(parts, failures):
    """The plate and fan sit where the depth diagram says they do."""
    plate = max(
        (mesh for mesh, colour in parts if colour == "print"),
        key=lambda mesh: mesh.extents[0],
    )
    failures.check(
        abs(
            plate.bounds[1][2]
            - (render.REAR_RAIL_Z + params.EAR_DEPTH + params.PLATE_THICKNESS)
        )
        < TOLERANCE,
        f"the plate's rear face is at z={plate.bounds[1][2]:.1f}, expected "
        f"{render.REAR_RAIL_Z + params.EAR_DEPTH + params.PLATE_THICKNESS:.1f}",
    )
    fan = next(mesh for mesh, colour in parts if colour == "fan")
    stack = fan.bounds[1][2] - render.REAR_RAIL_Z
    failures.check(
        abs(stack - (params.EAR_DEPTH + params.PLATE_THICKNESS + params.FAN_DEPTH))
        < TOLERANCE,
        f"the stack behind the rear rail is {stack:.1f} mm, expected "
        f"{params.EAR_DEPTH + params.PLATE_THICKNESS + params.FAN_DEPTH:.1f} "
        "-- the README quotes this number",
    )


def check_views(failures):
    """Each caption's claimed direction matches where the camera actually looks."""
    for azimuth, elevation, title in render.VIEWS:
        _, _, forward = render.camera(azimuth, elevation)
        failures.check(
            abs(np.linalg.norm(forward) - 1.0) < 1e-9,
            f'view "{title}" has a non-unit view direction',
        )
        # Match on the caption's leading clause, before the colon. An earlier
        # version used startswith() against the bare word, which never matched
        # "From behind: ..." or "From the front: ..." -- so two of the three
        # rules silently did nothing and the suite looked green either way.
        clause = title.lower().split(":", 1)[0]
        matched = False
        for phrase, expected_sign in VIEW_EXPECTATIONS:
            if phrase not in clause:
                continue
            matched = True
            looking_at = "front" if forward[2] > 0 else "rear"
            claimed = "rear" if expected_sign < 0 else "front"
            failures.check(
                math.copysign(1, forward[2]) == expected_sign,
                f'view "{title}" is captioned as the {claimed} but the camera '
                f"looks at the {looking_at}",
            )
        failures.check(
            matched or "side" in clause,
            f'view "{title}" claims no direction this check knows how to '
            'verify -- add it to VIEW_EXPECTATIONS or say "side"',
        )


def main():
    """Run every render check and exit nonzero if any failed."""
    parts = render.assemble()
    print(f"checking the render assembly: {len(parts)} parts")

    failed = 0
    for heading, runner in (
        ("inventory", lambda f: check_inventory(parts, f)),
        ("rods", lambda f: check_rods(parts, f)),
        ("laptops", lambda f: check_laptops(parts, f)),
        ("clearances", check_clearances),
        ("interference", lambda f: check_interference(parts, f)),
        ("cabinet", lambda f: check_cabinet(parts, f)),
        ("duct placement", lambda f: check_duct_placement(parts, f)),
        ("view directions", check_views),
        ("rasteriser", check_rasteriser),
    ):
        failures = Failures()
        runner(failures)
        failed += failures.report(heading)

    print("\n=== verdict ===")
    print(f"  the render shows the design : {'no' if failed else 'yes'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
