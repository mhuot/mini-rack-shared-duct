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

## Fusion

The general Fusion API traps, the render-capture pipeline and the verification
techniques live in the **`fusion-360-mcp` skill**, which loads automatically.
Units, camera assignment, `viewExtents`, timeline name suffixing, feature
ordering, colour classification, glTF colour space, `pointContainment` probes,
ray-cast solid spans, exact booleans, BRep-versus-mesh comparison: all there,
none of it repeated here. What follows is only what is true of *this repo*.

**Fusion caches imported modules between runs.** Its interpreter persists, so
`shared_duct_params` stays in `sys.modules` from the previous execution with the
previous numbers. Change a dimension, re-run `build_shared_fan_plate.py`, and it
rebuilds the old geometry and reports success — which defeats the single-source-
of-truth module entirely. The script pops the module before importing it; don't
remove that.

**Sketch names are prefixed `Sketch: `.** The skill explains why matching
timeline items by exact name is dangerous; this is the convention adopted in
response. `build_shared_fan_plate.py` names every sketch `Sketch: plate`,
`Sketch: tie slots` and so on, so no timeline name equals another *or is a
prefix of another* — which matters because the safe matching strategy is by
prefix.

**Colour classification: order is load-bearing in a way specific to these
names.** The skill's examples are a `panel` rule eating "duct panel" and a
`fan` rule eating "fan plate". This repo hits it from the other end: the body
`Shared duct fan` contains "duct", so a duct-first rule paints the Noctua as a
printed part. Specific before general, and the counts are asserted by
`audit_appearances()` in `build_rack_mockup.py` and `audit_groups()` in
`build_web_assets.py`. Auditing also caught `Frame front post` falling through
every rule, because the frame rule only handled a `<slot>_frame_...` prefix.

**The local renderer needs no Z-up to Y-up rotation.** The skill's rule is for
Fusion exports, and `build_web_assets.py` follows it. But
`render_shared_duct.py` builds in the mockup's own frame, where y is already
the rack's vertical axis, so rotating its GLB would tip the rack on its side.
Check the exported bounds rather than applying the rule reflexively.

**Verifying a plate rebuild: use `--compare`, and note why it is not a volume
ratio.**

```
python scripts/build_shared_fan_plate_mesh.py --compare <exported.stl>
```

`--compare` does not threshold on total volume, for the reason the skill now
records: a lost feature is a fixed volume and a percentage tolerance scales
with the part, so the 533 mm3 that was loud on a rear ear would be 0.39% here.
It booleans both directions and reports **connected lumps over 5 mm3 with their
bounds** instead.

That 5 mm3 is calibrated on this part, against real Fusion exports at low,
medium and high refinement: faceting produced 1,078–2,070 components and the
largest single fragment was 0.50 mm3 every time, all of them thin arcs around
the chamfered bore. So 5 mm3 has about 10x headroom. Run `--compare` after
every Fusion rebuild of the plate.

**`whiten_renders.py`** is this repo's implementation of the background
replacement the skill describes.

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

`cad/shared_fan_plate.{step,f3d}` come from running
`build_shared_fan_plate.py` inside Fusion and then `export_active_cad.py`.
`exports/shared_fan_plate.stl` still comes from the local mesh builder, and
should stay that way: it is the reproducible one, and the checks and print
plates are built against it. The two agree — Fusion's BRep is 135,366.2 mm3
against the mesh's 135,383.7, a 0.013% faceting gap, and a component diff of
Fusion's STL against the model is clean at every refinement level.

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
