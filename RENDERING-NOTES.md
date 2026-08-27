# Why the assembly renders look wrong, and what upstream does

Notes from the `mini-rack-laptop-trays` side, after looking at
`images/shared-duct-assembly.png`. Not committed — read it, act on it, delete it.

## The root cause is one line

`scripts/render_shared_duct.py`:

```python
order = np.argsort(-projected[:, :, 2].mean(axis=1))  # far to near
```

That is a painter's algorithm sorting **whole triangles by centroid depth**, and
it cannot be made correct. Three cases break it no matter how the sort is tuned:

- **Interpenetrating geometry.** Two triangles that cross have no valid order —
  one must be in front at some pixels and behind at others.
- **Centroid ≠ occlusion.** A large triangle with a far centroid can still be
  nearer at some pixels than a small one with a near centroid.
- **Adjacent and coplanar faces.** Ordering is arbitrary, so seams flicker.

That is what the ragged silhouette on the duct is, and the black laptop slabs
punching through the orange wall in the "from behind" panel. `antialiased=False`
with `edgecolors="none"` then leaves hairline gaps between neighbours, which
reads as tearing.

The docstring's reasoning is sound — headless, no Fusion session, no GL context,
draw a part before it is built. Keep all of that. **The renderer just needs a
depth buffer instead of a sort.**

## The fix that keeps every constraint

Replace the sort with a per-pixel z-buffer rasteriser. Same inputs, same
dependencies, still headless, comparable length:

1. Project triangles to screen space as now, keeping the depth coordinate.
2. Allocate `depth = np.full((h, w), np.inf)` and `colour = np.zeros((h, w, 3))`.
3. For each triangle: compute its pixel bounding box, evaluate barycentric
   coordinates over that box, interpolate depth per pixel, and write colour only
   where `z < depth`, updating `depth` there.
4. Write the array out with `plt.imsave`, or keep matplotlib only for the
   annotation layer on top.

Vectorised per triangle over its own bounding box, this is fast enough for these
part counts and is **exactly correct** — no sorting heuristics, no seams, and
interpenetration resolves itself. Supersample 2× and box-filter down if you want
clean edges without touching the maths.

If a real renderer is ever acceptable, `trimesh` + `pyrender` with the EGL
backend runs headless. But the z-buffer above needs nothing new installed.

## What upstream actually does, and the traps in it

Upstream renders from Fusion's viewport, which is a GPU render with a real depth
buffer — that is the whole reason those images do not have this problem. If you
do go that route, these all cost me a cycle each:

- **The camera only applies on assignment.** Mutate `viewport.camera`, then
  assign it back: `viewport.camera = camera`. Setting fields alone does nothing.
- **`viewExtents` is a linear value in cm, not an area.** Squaring it renders the
  model as a speck. This silently produced two blank images before I caught it.
- **`isFitView = True` refits every frame**, so an animation pumps in and out.
  Fit once at the largest state, read the resulting `viewExtents` back, then reuse
  that fixed number with `isFitView = False` for every frame.
- **`BoundingBox3D.combine()` returns a bool and mutates in place.** Accumulate
  min/max by hand.
- **To frame a subset**, set `body.isLightBulbOn = False` on everything else and
  fit — restore in a `finally`.
- **Fusion's canvas background is a dark gradient with no API to change it.**
  `scripts/whiten_renders.py` (you already have it) estimates the background per
  row from the outermost columns so it follows the gradient, and replaces only
  pixels that are both near that estimate **and** connected to the image border.
  That last condition is what stops it eating dark parts of the model.
- **Name-based colour classification bites.** "duct panel" matched a `panel` rule
  and rendered as smoked acrylic; "fan plate" matched a `fan` rule and came out
  Noctua brown. Assert the group counts after classifying.
- **glTF `baseColorFactor` is linear.** Convert sRGB → linear or every colour
  washes out. Also rotate Z-up → Y-up.

## Cheapest possible check

A blank or near-blank render is not obvious in a thumbnail. Measure the fraction
of background pixels and fail loudly above ~95%. That is how I caught both of my
blank frames, and it is two lines.

## What you are already doing better than upstream

- `check_render.py` is the right instinct and upstream has no equivalent. The two
  bugs in its docstring — rods as vertical posts, inverted azimuths — are exactly
  the class that survives review.
- `images/shared-fan-plate.png` is genuinely good. Dimensioned 2D drawings
  generated from the same constants as the CAD are the strongest thing in either
  repo, because they cannot drift from the part. **Keep those in matplotlib.**
  It is only the shaded 3D views that need the z-buffer.
