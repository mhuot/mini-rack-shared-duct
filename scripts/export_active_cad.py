"""Export the active Fusion document to cad/<NAME>.f3d and cad/<NAME>.step.

Run inside Fusion via the MCP execute tool, straight after a build script has
left its part in the active document. Set NAME to the file stem you want:

    NAME = "rear_fan_plate"     ->  cad/rear_fan_plate.f3d + .step

Only build_fan_plug.py writes its own CAD; every other part is exported with
this, so the STEP and F3D beside a part stay in step with its STL instead of
quietly ageing. A stale F3D is worse than a missing one -- it opens fine and
shows the wrong geometry.
"""

import adsk.core
import adsk.fusion

CAD_DIR = "/Users/mhuot/mini-rack/cad"
NAME = "part"


def run(_context: str):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("active document is not a design")
    root = design.rootComponent
    if root.bRepBodies.count == 0:
        raise RuntimeError(
            f"no bodies in {app.activeDocument.name!r} -- nothing to export")

    export_mgr = design.exportManager
    step_path = f"{CAD_DIR}/{NAME}.step"
    archive_path = f"{CAD_DIR}/{NAME}.f3d"
    export_mgr.execute(export_mgr.createSTEPExportOptions(step_path, root))
    export_mgr.execute(export_mgr.createFusionArchiveExportOptions(
        archive_path, root))

    bodies = [root.bRepBodies.item(i).name for i in range(root.bRepBodies.count)]
    print(f"exported {NAME}: {len(bodies)} body/bodies {bodies}")
    print(f"  {step_path}")
    print(f"  {archive_path}")
