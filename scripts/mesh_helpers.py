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


def ray_crossings(triangles, origin, direction):
    """Where a ray crosses a mesh, as distances along it, sorted.

    A vectorised Moller-Trumbore against every triangle at once. It exists
    because both the seal check and the depth diagram need exact crossings
    along one axis, and trimesh's own ray module wants an rtree index that is
    not worth a dependency for two straight lines.

    Both callers rely on the sorting: a solid is the span between crossing
    pairs, so an unsorted result silently pairs the wrong faces together.
    """
    origin = np.asarray(origin, dtype=float)
    direction = np.asarray(direction, dtype=float)
    corner = triangles[:, 0]
    edge_a, edge_b = triangles[:, 1] - corner, triangles[:, 2] - corner
    pvec = np.cross(direction, edge_b)
    determinant = np.einsum("ij,ij->i", edge_a, pvec)
    usable = np.abs(determinant) > 1e-12
    inverse = np.where(usable, 1.0 / np.where(usable, determinant, 1.0), 0.0)
    to_corner = origin - corner
    bary_u = np.einsum("ij,ij->i", to_corner, pvec) * inverse
    qvec = np.cross(to_corner, edge_a)
    bary_v = np.einsum("j,ij->i", direction, qvec) * inverse
    distance = np.einsum("ij,ij->i", edge_b, qvec) * inverse
    hit = (
        usable & (bary_u >= 0) & (bary_v >= 0) & (bary_u + bary_v <= 1) & (distance > 0)
    )
    return np.sort(distance[hit])


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


def report_mesh(out_path, mesh, density=1.27):
    """Print the numbers worth eyeballing after writing a part.

    Watertight is the one that matters: a mesh that is not is a part the
    slicer will quietly guess at, and the guess is rarely what you drew.
    """
    low, high = mesh.bounds
    print(f"wrote {out_path}")
    print(
        f"  extents mm : x {low[0]:.2f}..{high[0]:.2f}  "
        f"y {low[1]:.2f}..{high[1]:.2f}  z {low[2]:.2f}..{high[2]:.2f}"
    )
    print(
        f"  volume     : {mesh.volume / 1000:.1f} cm3 "
        f"({mesh.volume * density / 1000:.0f} g in PETG)"
    )
    print(f"  watertight : {mesh.is_watertight}")
