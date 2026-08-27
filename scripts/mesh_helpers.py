"""Primitives shared by the local mesh builder and the renderer.

Both of them need a box from two corners and a mirrored copy that survives the
reflection, and having each keep its own was how the upstream project's
constants drifted in the first place. One copy, imported twice.

Requires trimesh and numpy.
"""

import numpy as np
import trimesh

CYLINDER_SECTIONS = 128


def box(x_range, y_range, z_range):
    """An axis-aligned box from three (low, high) pairs."""
    low = np.array([x_range[0], y_range[0], z_range[0]], dtype=float)
    high = np.array([x_range[1], y_range[1], z_range[1]], dtype=float)
    mesh = trimesh.creation.box(extents=high - low)
    mesh.apply_translation((low + high) / 2)
    return mesh


def cylinder(centre_x, centre_y, diameter, z_range, sections=CYLINDER_SECTIONS):
    """A z-axis cylinder spanning (low, high)."""
    mesh = trimesh.creation.cylinder(
        radius=diameter / 2, height=z_range[1] - z_range[0], sections=sections
    )
    mesh.apply_translation([centre_x, centre_y, (z_range[0] + z_range[1]) / 2])
    return mesh


def conical_ring(inner_radius, outer_radius, z_low, z_high, sections=CYLINDER_SECTIONS):
    """A ring of revolution whose bore tapers, for cutting a chamfer.

    The profile is a triangle in (radius, height): wide at `z_high`, narrow at
    `z_low`. Subtracted from a plate it leaves a conical inlet -- the radius
    grows with z, so on a printer that face is a receding staircase rather than
    an overhang, and needs no support.
    """
    profile = np.array(
        [
            [inner_radius, z_low],
            [outer_radius, z_high],
            [inner_radius, z_high],
            [inner_radius, z_low],
        ]
    )
    ring = trimesh.creation.revolve(profile, sections=sections)
    if ring.volume < 0:  # the profile's winding decides which way it faces
        ring.invert()
    return ring


def mirrored_x(mesh):
    """Mirror across x, fixing the winding the reflection inverts.

    Older trimesh does not correct face winding on a reflection, which leaves
    an inside-out mesh that still looks fine on screen and booleans wrong.
    """
    out = mesh.copy()
    out.apply_transform(np.diag([-1.0, 1.0, 1.0, 1.0]))
    if out.volume < 0:
        out.invert()
    return out
