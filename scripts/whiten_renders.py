"""Flatten Fusion's viewport background to white in exported renders.

Fusion's canvas background is a dark vertical gradient and the API exposes no
way to change it, so viewport captures come out on that gradient. The docs
images have always been on white, so this replaces it after the fact:

    python scripts/whiten_renders.py docs/images/*.png

The background is estimated per row from the outermost columns, which follows
the gradient exactly. Only pixels close to that estimate *and* connected to
the image border are replaced, so dark parts of the model are left alone even
where their colour is near the background's.

Requires numpy, scipy and pillow.
"""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

EDGE_SAMPLE = 4  # columns at each side used to estimate the background
TOLERANCE = 22  # per-channel distance still counted as background


def flatten(path, tolerance=TOLERANCE):
    """Replace the gradient background with white. Returns pixels changed."""
    image = Image.open(path).convert("RGB")
    pixels = np.asarray(image).astype(np.int16)

    left = pixels[:, :EDGE_SAMPLE, :]
    right = pixels[:, -EDGE_SAMPLE:, :]
    row_background = np.median(np.concatenate([left, right], axis=1), axis=1).astype(
        np.int16
    )

    difference = np.abs(pixels - row_background[:, None, :]).max(axis=2)
    candidate = difference <= tolerance

    labels, count = ndimage.label(candidate)
    if count == 0:
        return 0
    border = np.unique(
        np.concatenate([labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]])
    )
    border = border[border != 0]
    background = np.isin(labels, border)

    out = pixels.copy()
    out[background] = 255
    changed = int(background.sum())
    Image.fromarray(out.astype(np.uint8)).save(path)
    return changed


def main():
    """Flatten the viewport gradient to white in every render."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--tolerance", type=int, default=TOLERANCE)
    args = parser.parse_args()
    for path in args.images:
        changed = flatten(path, args.tolerance)
        total = Image.open(path).size[0] * Image.open(path).size[1]
        print(f"  {path.name:28s} background {changed/total*100:5.1f}%")


if __name__ == "__main__":
    main()
