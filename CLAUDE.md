# Working in this repo

## Terminology

Every part has exactly one name. They drifted once — the same part went by
one name in the README and another in the print plate filenames, and a
second part disagreed with itself between the prose and the CAD — and were
settled in a single pass. Use the left column and nothing else, in prose,
comments, identifiers, and filenames alike.

<!-- terminology-check: ignore -->

| Use | Not | Why this one |
|---|---|---|
| **ear**, front ear, rear ear | bracket | The printed parts that bolt to the rack rails. |
| **fan plate** | fan bar, the bar | The Fusion body is named `Shared Duct Fan Plate`. There is exactly one, for the whole rack. |
| **rack rail** | a bare "rail" for the cabinet | The cabinet's mounting rails. Always qualified, because... |
| **duct rail** | capture rail, ear rail, a bare "rail" | ...the ears also carry rails, the ones the duct panels slide into. Matches the Fusion feature named `Duct rail`. |
| **fan opening** | fan bore | The Ø114 hole in the fan plate. Keeps *bore* meaning one thing: the rod, screw, and insert holes. |
| **duct wall** | duct panel, for *this* project's part | The 2.2 mm fins grown onto the shared plate. |
| **duct panel** | — | Upstream's separate slide-in sheets. They do not exist here, so the term is only ever historical — if you find yourself using it for a part in this repo, you mean **duct wall**. |
| **plenum** | — | The shared cavity itself, as distinct from the **duct** (the whole airway) and the **duct walls** that close it. |

Two places keep a retired word on purpose:

- `docs/index.html` — "A front ear and a rear ear, which is what I call the
  brackets" is a gloss. It hands the reader the vocabulary rather than
  drifting from it. Don't mechanically substitute it away.
- `scripts/build_rack_mockup.py` — `Brackets for Speaker Stand v2` is the
  exact name of a legacy Fusion document that `grab_bodies()` opens.
  Renaming the file would not rename the document inside Fusion.

<!-- terminology-check: resume -->

Run `python scripts/check_terminology.py` before you commit. It greps for
the retired names, exits nonzero on a hit, and knows about both exceptions
above. When you retire a name, add a rule to it; when you need a genuine
exemption, add it to `ALLOWED` **with a note saying why** — an unexplained
exemption is how the drift started.

## Which scripts run where

This matters before you offer to regenerate anything:

- **Fusion 360 only** — `build_shared_fan_plate.py`, `build_rear_ear_v2.py`,
  `build_rack_mockup.py`, `add_duct_rails.py`, `export_front_ear.py`,
  `fix_insert_pockets.py`, `fix_laptop_relief.py`. They `import adsk` and need
  the Fusion documents open. You cannot run these; say so rather than guessing
  at their output.
- **Locally** — `build_shared_fan_plate_mesh.py`, `build_fan_guard_mesh.py`,
  `build_print_plate.py`, `check_rear_assembly.py`, `check_render.py`,
  `render_shared_duct.py`,
  `build_depth_diagram.py`, `build_wiring_diagram.py`, `whiten_renders.py`,
  `build_web_assets.py`. Dependencies are pinned in `requirements.txt` and go
  in `.venv/`, which is gitignored.
- **Standard library only** — `check_terminology.py`, `shared_duct_params.py`.

Unlike upstream, **the plate can be built without Fusion.** The ears earn
their parametric history; a rectangle with two fins does not, and holding it
hostage to a licence would mean nobody could print or check this fork.
`build_shared_fan_plate.py` and `build_shared_fan_plate_mesh.py` build the same
part and both read `shared_duct_params.py`, so they cannot drift. If you change
a dimension, change it there and nowhere else.

Fusion API note: all Fusion API lengths are centimeters. The scripts define
`MM = 0.1` and work in millimeters throughout.

## Fusion viewport rendering, and what it costs to learn twice

Carried over from `mini-rack-laptop-trays`, same Fusion MCP setup. Each of
these cost a debugging cycle there. None of them announce themselves: the
failure is a render that looks merely disappointing, or a save that looks fine.

**The camera only applies on assignment.** Mutating `viewport.camera` in place
does nothing. Read it, set the fields, assign it back — that last line is the
one that does the work:

```python
camera = viewport.camera
camera.eye = ...; camera.target = ...; camera.upVector = ...
viewport.camera = camera        # this is what applies it
viewport.refresh(); adsk.doEvents()
viewport.saveAsImageFile(path, width, height)
```

**`viewExtents` is a linear value in centimetres, not an area.** The camera is
orthographic (`cameraType == 0`). Squaring it renders the model as a speck; two
images came out 99.9% background before anyone noticed. **If a render looks
blank, check this first.**

**Don't guess the extents, measure them.** Let Fusion fit the largest state
once with `isFitView = True`, read `viewport.camera.viewExtents` back, and
reuse that number with `isFitView = False`. Multiply by ~0.74 to fill the
frame: Fusion fits to the viewport's aspect, not the aspect passed to
`saveAsImageFile`.

**`isFitView = True` refits every frame**, so any animation pumps in and out as
the subject grows. Fixed extents from the step above solve it.

**To frame a subset, hide the rest.** Set `body.isLightBulbOn = False` on
everything else, fit, and restore in a `finally`. Zooming with `viewExtents`
instead is what produced the blank frames.

**`BoundingBox3D.combine()` returns a bool and mutates in place.** It does not
return a combined box. Accumulate min/max by hand.

**Fusion suffixes duplicate timeline names.** Naming a sketch and its feature
the same thing gets you `Tie slots` and `Tie slots (1)`, and which one is
suffixed depends on creation order. Matching timeline items by exact name once
deleted only the sketch and left an orphaned cut still removing geometry: the
body came out 533 mm3 light and the save looked fine. Match by type and name
prefix — and in this repo, don't create the collision at all.
`build_shared_fan_plate.py` prefixes every sketch `Sketch: `, so no timeline
name equals another or is even a prefix of another.

**Verify a rebuild against the mesh, not against the save.**
`python scripts/build_shared_fan_plate_mesh.py --compare <exported.stl>`
booleans a Fusion export against the model both scripts are built from and
reports what differs, by location and volume. Use it after every Fusion rebuild
of the plate. Note it does *not* compare total volume: tessellation disagreement
between Fusion and trimesh is worth tens of mm3 on this part's curved faces, and
a percentage tolerance loose enough to survive that is loose enough to hide a
lost feature. It reports connected lumps over 5 mm3 instead, which distinguishes
a missing pocket from rounding.

**The canvas background is a dark gradient and the API cannot change it.**
`graphicsPreferences` has no background property. Post-process instead:
estimate the background per row from the outermost columns so the estimate
follows the gradient, then replace only pixels that are both near that estimate
*and* connected to the image border. That last condition is what stops it
eating dark parts of the model. `whiten_renders.py` does this.

**Name-based colour classification bites.** "duct panel" matched a `panel` rule
and rendered as smoked acrylic; "fan plate" matched a `fan` rule and came out
Noctua brown. This fork hit it again from the other direction: `Shared duct
fan` contains "duct", so a duct-first rule painted the Noctua as a printed
part. Order specific before general, and **assert the group counts after
classifying** — `audit_appearances()` in `build_rack_mockup.py` and
`audit_groups()` in `build_web_assets.py`. A miscoloured body is not a visible
failure; the render still looks like a render.

**glTF `baseColorFactor` is linear.** Convert sRGB to linear or every colour
washes out. Fusion exports STLs Z-up and glTF wants Y-up, so
`build_web_assets.py` rotates them. Note that the *local* renderer does not:
`render_shared_duct.py` builds in the mockup's frame, where y is already the
rack's vertical axis, so its GLB needs no rotation. Check the bounds rather
than assuming either way.

**A script cannot run while a modal dialog is open** — `Cannot perform 'script'
while a command dialog is open`. Handle it rather than retrying blindly.

## Generated assets

Every image in `docs/images/` and the GLB in `docs/models/` is generated
locally, from the exported meshes, by `render_shared_duct.py`,
`build_depth_diagram.py` and `build_wiring_diagram.py`. All three bake text
into the image, so a terminology or dimension change means regenerating them.

Run `check_render.py` after touching `render_shared_duct.py`. Renders fail
quietly -- a wrong one still looks like a rack -- and that script is the only
thing standing between a geometry mistake and a published picture of it. When
you add a view, give its caption a direction the checker knows, and when you
add a part, update `EXPECTED_COUNTS`.

Upstream's photorealistic Fusion renders were deleted rather than kept. Every
one of them showed three 40 mm fans per tray, which is a different product, and
a picture of the wrong thing is worse than no picture. If you rebuild the
mockup in Fusion, better-looking replacements are welcome -- but nothing on the
project page should show geometry the checks have never seen.

`cad/` holds a STEP and an F3D beside each part, exported with
`export_active_cad.py` after the build script leaves the part in the active
document. A stale F3D is worse than a missing one, because it opens fine and
shows the wrong geometry.

**There is no `cad/` entry for the shared fan plate yet**, because nobody has
run `build_shared_fan_plate.py` inside Fusion. `exports/shared_fan_plate.stl`
comes from the local mesh builder and is what the checks and print plates use.
Don't imply the STEP exists.

One trap worth knowing before you regenerate them. **The heat-set rear ear
does not come from `build_rear_ear_v2.py`.** That script builds from the
original `MacBook Pro Rear Ear` document and produces a part 1124 mm3 lighter
than the one that ships — it has a 5 mm back plate where the real one has 7,
and none of the pocket or relief fixes. `exports/rear_ear_v2.stl` and
`cad/rear_ear_v2_heatset.*` come from **`MacBook Pro Rear Ear v2 Parametric`**.
The script is still the source for the self-tap and nut-trap variants, which
have no parametric document of their own.

Regenerating a 3MF or STL on a different trimesh version rewrites float
formatting across the whole file, which buries a real change in noise. If
the mesh itself didn't change, restore it with `git checkout -- exports/`
rather than committing the churn.
