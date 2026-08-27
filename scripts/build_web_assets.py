"""Assemble the README turntable GIF and the Pages viewer GLB.

Inputs are produced by running build_rack_mockup.py inside Fusion and then
exporting (a) one STL per body into a parts directory and (b) a sequence of
turntable PNG frames. This script runs locally:

    python scripts/build_web_assets.py --parts-dir <dir> --frames-dir <dir>

Requires: pillow, trimesh, numpy (pip install pillow trimesh numpy).

Color notes:
- The palette below is authored in sRGB to match the Fusion renders; glTF's
  baseColorFactor is linear, so values are converted with the sRGB EOTF
  before export. Skipping that conversion washes every color out.
- Fusion de-duplicates repeated body names ("... fan (1)"), so parts are
  classified by substring, not exact suffix.
"""

import argparse
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

GIF_PATH = Path("docs/images/rack-turntable.gif")
EXPLODE_GIF_PATH = Path("docs/images/rack-explode.gif")
GLB_PATH = Path("docs/models/rack-mockup.glb")

# sRGB, matching the appearances in build_rack_mockup.py
PALETTE = {
    "frame": (196, 199, 204, 255),
    "foot": (25, 25, 25, 255),
    "rod": (215, 215, 220, 255),
    "macbook": (45, 45, 48, 255),
    "surface": (28, 28, 30, 255),
    "fan": (94, 61, 48, 255),
    "print": (247, 84, 3, 255),  # Prusament Prusa Orange
    "panel": (40, 40, 46, 90),  # smoked acrylic, alpha-blended
}

METALLIC = {"frame": 0.6, "rod": 0.6}
ROUGHNESS = {"rod": 0.35}


def classify(stem: str) -> str:  # pylint: disable=too-many-return-statements
    """Map an exported body filename to a palette group."""
    lower = stem.lower()
    if "duct" in lower:
        return "print"  # a printed duct panel, not the acrylic kind
    if "panel" in lower:
        return "panel"
    if "foot" in lower:
        return "foot"
    if lower.split("_", 1)[-1].startswith("frame"):
        return "frame"
    if "ref" in lower and "macbook" in lower:
        return "macbook"
    if "ref" in lower and "surface" in lower:
        return "surface"
    if "fan_plate" in lower:
        return "print"  # the printed plate, not a Noctua
    if "fan" in lower:
        return "fan"
    if "rod" in lower:
        return "rod"
    return "print"


def srgb_to_linear(rgba_255):
    """Convert 0-255 sRGB to linear floats per the sRGB EOTF (alpha passes through)."""
    srgb = np.array(rgba_255[:3], dtype=np.float64) / 255.0
    linear = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
    return np.append(linear, rgba_255[3] / 255.0)


def build_gif(frames_dir: Path) -> None:
    """Assemble the turntable frames into a GIF."""
    frames = []
    for frame_path in sorted(frames_dir.glob("frame_*.png")):
        image = Image.open(frame_path).convert("RGB")
        frames.append(image.quantize(colors=128, dither=Image.Dither.FLOYDSTEINBERG))
    if not frames:
        raise SystemExit(f"no frames found in {frames_dir}")
    frames[0].save(
        GIF_PATH,
        save_all=True,
        append_images=frames[1:],
        duration=90,
        loop=0,
        optimize=True,
    )
    print(
        f"GIF: {GIF_PATH} ({GIF_PATH.stat().st_size / 1e6:.2f} MB, {len(frames)} frames)"
    )


def build_glb(parts_dir: Path) -> None:
    """Colour the exported bodies and pack them into a GLB."""
    # Z-up (Fusion world) -> Y-up (glTF)
    z_to_y_up = np.array(
        [
            [1, 0, 0, 0],
            [0, 0, 1, 0],
            [0, -1, 0, 0],
            [0, 0, 0, 1],
        ],
        dtype=np.float64,
    )

    scene = trimesh.Scene()
    counts = {}
    for stl_path in sorted(parts_dir.glob("*.stl")):
        mesh = trimesh.load_mesh(stl_path)
        mesh.apply_transform(z_to_y_up)
        group = classify(stl_path.stem)
        counts[group] = counts.get(group, 0) + 1
        mesh.visual = trimesh.visual.TextureVisuals(
            material=trimesh.visual.material.PBRMaterial(
                baseColorFactor=srgb_to_linear(PALETTE[group]),
                metallicFactor=METALLIC.get(group, 0.1),
                roughnessFactor=ROUGHNESS.get(group, 0.6),
                alphaMode="BLEND" if group == "panel" else "OPAQUE",
            )
        )
        scene.add_geometry(mesh, node_name=stl_path.stem)
    if not counts:
        raise SystemExit(f"no part STLs found in {parts_dir}")
    GLB_PATH.parent.mkdir(parents=True, exist_ok=True)
    scene.export(GLB_PATH)
    print(f"GLB: {GLB_PATH} ({GLB_PATH.stat().st_size / 1e6:.2f} MB); groups: {counts}")


def build_explode_gif(explode_dir: Path) -> None:
    """Ping-pong the explode states so the parts fly out and back in.

    The states are rendered open-only; playing them forward then backward
    gives the return trip for free and guarantees a seamless loop. Both ends
    hold for a beat so the assembled and exploded views are readable.
    """
    states = sorted(explode_dir.glob("state_*.png"))
    if not states:
        raise SystemExit(f"no explode states found in {explode_dir}")
    frames = [Image.open(path).convert("RGB") for path in states]
    sequence = frames + frames[-2:0:-1]
    hold = 900
    step = 70
    durations = [step] * len(sequence)
    durations[0] = hold
    durations[len(frames) - 1] = hold
    sequence[0].save(
        EXPLODE_GIF_PATH,
        save_all=True,
        append_images=sequence[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    size = EXPLODE_GIF_PATH.stat().st_size / 1e6
    print(
        f"explode GIF: {EXPLODE_GIF_PATH} ({size:.2f} MB, "
        f"{len(sequence)} frames from {len(frames)} states)"
    )


def main() -> None:
    """Build whichever web assets the arguments ask for."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--explode-dir",
        type=Path,
        default=None,
        help="directory of exploded-state PNGs (state_*.png)",
    )
    parser.add_argument(
        "--parts-dir",
        type=Path,
        required=True,
        help="directory of per-body STL exports",
    )
    parser.add_argument(
        "--frames-dir",
        type=Path,
        required=True,
        help="directory of turntable frame PNGs",
    )
    args = parser.parse_args()
    build_gif(args.frames_dir)
    build_glb(args.parts_dir)
    if args.explode_dir:
        build_explode_gif(args.explode_dir)


if __name__ == "__main__":
    main()
