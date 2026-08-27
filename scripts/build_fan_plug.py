"""Fusion 360 script: blanking plug for unused fan plate openings.

Run inside Fusion via the MCP execute tool. Creates a new parametric
document with a human-usable timeline (named sketches and features), per
the project rule that everything Claude builds in Fusion stays editable.

For running fewer than three fans, the empty openings must be blocked or
the running fans pull backflow through them. The plug press-fits into a
plate opening from the rear (fan side). The flange seats on the plate's
rear face, and duct suction pushes the plug tighter rather than out.
Print flange-down, no supports. To remove, drive an M3 screw a couple
turns into the center pilot and pull.

The press fit and the suction are the retention. For a positive one, a zip
tie through the slot pair either side of the opening crosses the flange and
clamps it; the channel across the flange face keeps the tie from sliding
off the disc. The slots sit at +/-26 from every opening centre, so the tie
crosses squarely whichever opening is plugged.
"""

import adsk.core
import adsk.fusion

MM = 0.1  # Fusion API lengths are in cm

FLANGE_DIA = 43.0
FLANGE_THICK = 1.6
BODY_DIA = 38.7          # press fit in the plate's 39.0 opening
BODY_DEPTH = 4.0         # fills the plate thickness, flush with the duct side
PULLER_PILOT_DIA = 2.5   # M3 screw threads in as a puller
TIE_CHANNEL_W = 3.4      # clears a 2.5 mm zip tie with room to thread
TIE_CHANNEL_DEPTH = 0.8  # of the 1.6 mm flange, so half remains


def run(_context: str):
    app = adsk.core.Application.get()
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent
    sketches = root.sketches
    extrudes = root.features.extrudeFeatures
    origin = adsk.core.Point3D.create(0, 0, 0)

    JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
    CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
    NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    sketch = sketches.add(root.xYConstructionPlane)
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        origin, FLANGE_DIA / 2 * MM)
    sketch.name = "Flange"
    feature_input = extrudes.createInput(sketch.profiles.item(0), NEW)
    feature_input.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(FLANGE_THICK * MM))
    flange = extrudes.add(feature_input)
    flange.name = "Flange"

    plane_input = root.constructionPlanes.createInput()
    plane_input.setByOffset(
        root.xYConstructionPlane,
        adsk.core.ValueInput.createByReal(FLANGE_THICK * MM))
    body_plane = root.constructionPlanes.add(plane_input)
    body_plane.name = "Flange top"
    sketch = sketches.add(body_plane)
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        origin, BODY_DIA / 2 * MM)
    sketch.name = "Press-fit body"
    feature_input = extrudes.createInput(sketch.profiles.item(0), JOIN)
    feature_input.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(BODY_DEPTH * MM))
    body = extrudes.add(feature_input)
    body.name = "Press-fit body"

    sketch = sketches.add(root.xYConstructionPlane)
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        origin, PULLER_PILOT_DIA / 2 * MM)
    sketch.name = "Puller pilot"
    feature_input = extrudes.createInput(sketch.profiles.item(0), CUT)
    feature_input.setSymmetricExtent(
        adsk.core.ValueInput.createByReal(2 * (FLANGE_THICK + BODY_DEPTH) * MM),
        True)
    pilot = extrudes.add(feature_input)
    pilot.name = "Puller pilot"

    plug_body = root.bRepBodies.item(0)
    plug_body.name = "Fan Plug"

    exp = design.exportManager
    stl = exp.createSTLExportOptions(
        plug_body, "/Users/mhuot/mini-rack/exports/fan_plug.stl")
    stl.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
    exp.execute(stl)
    step = exp.createSTEPExportOptions("/Users/mhuot/mini-rack/cad/fan_plug.step")
    exp.execute(step)
    f3d = exp.createFusionArchiveExportOptions(
        "/Users/mhuot/mini-rack/cad/fan_plug.f3d")
    exp.execute(f3d)

    # Retention channel across the exposed flange face, for a zip tie run
    # through the slot pair either side of the opening.
    sketch = sketches.add(root.xYConstructionPlane)
    sketch.name = "Tie channel"
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(
        adsk.core.Point3D.create(-FLANGE_DIA / 2 * MM, -TIE_CHANNEL_W / 2 * MM, 0),
        adsk.core.Point3D.create(FLANGE_DIA / 2 * MM, TIE_CHANNEL_W / 2 * MM, 0))
    feature_input = extrudes.createInput(sketch.profiles.item(0), CUT)
    feature_input.setDistanceExtent(
        False, adsk.core.ValueInput.createByReal(TIE_CHANNEL_DEPTH * MM))
    channel = extrudes.add(feature_input)
    channel.name = "Tie channel"

    app.activeViewport.fit()
    print("Fan plug built parametrically (%d timeline items) and exported"
          % design.timeline.count)
