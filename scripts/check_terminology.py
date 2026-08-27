"""Fail if a retired part name has crept back into the docs or scripts.

    python scripts/check_terminology.py

Every part in this project has exactly one name. The names drifted once --
the same part went by one name in the README and another in the print plate
filenames, and a second part disagreed with itself between the prose and the
CAD -- so this pins them down. Standard library only, no install needed,
runs in well under a second.

Add a case to RULES when you retire a name. Add a case to ALLOWED when a
retired word is genuinely the right one in some specific spot, and say why
in the note -- an unexplained exemption is how the drift started.

A file that has to spell out the retired names, like this one and CLAUDE.md,
brackets that stretch with "terminology-check: ignore" and
"terminology-check: resume" comments, so only that stretch is skipped and
the prose around it is still checked.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEARCH = ("*.md", "*.html", "*.py")
# terminology-check: ignore
# .venv is here because this fork pins its dependencies and installs them in
# the tree. Walking into it means checking black's own source for the word
# "bracket", which it uses several hundred times and entirely correctly.
# terminology-check: resume
SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "exports",
    "cad",
    "docs/images",
    "docs/models",
}

# terminology-check: ignore
# (retired pattern, the term to use instead, why)
RULES = [
    # Square/curly/angle brackets and bracket notation are not this project's
    # parts. Excluding them here keeps ALLOWED for genuine one-off exemptions
    # rather than filling it with punctuation.
    (
        r"(?<!square )(?<!curly )(?<!angle )(?<!round )\bbrackets?\b(?! notation)",
        "ear / front ear / rear ear",
        "the printed parts that bolt to the rack rails are ears",
    ),
    (
        r"\bfan bars?\b",
        "fan plate",
        "the Fusion body is named Rear Fan Plate and it is a flat 4 mm slab",
    ),
    (
        r"\bfan bores?\b",
        "fan opening",
        "bore is reserved for the rod, screw, and insert holes",
    ),
    (
        r"\bcapture rails?\b",
        "duct rail",
        "matches the Fusion feature already named Duct rail",
    ),
    (
        r"\bear rails?\b",
        "duct rail",
        "matches the Fusion feature already named Duct rail",
    ),
    (
        r"fan_bar",
        "fan_plate",
        "renamed in the ear/fan plate cleanup; covers rear_fan_bar too",
    ),
    (
        r"print_plate_brackets",
        "print_plate_ears",
        "renamed in the ear/fan plate cleanup",
    ),
]

# (path, substring that must be on the line, why it is allowed to stay)
ALLOWED = [
    (
        "docs/index.html",
        "which is what I call the brackets",
        "a gloss that introduces the term 'ear' to a reader who expects "
        "'bracket'. It defines the vocabulary rather than drifting from it.",
    ),
    (
        "scripts/build_rack_mockup.py",
        "Brackets for Speaker Stand v2",
        "the exact name of a legacy Fusion document that grab_bodies() opens. "
        "Renaming the file would not rename the document inside Fusion.",
    ),
]

# Both this file and CLAUDE.md have to name the retired terms to do their job,
# but exempting them wholesale left the conventions file as the one place the
# convention was not enforced. Instead they mark just the stretch that needs
# it, so the prose around it is still checked.
# terminology-check: resume
IGNORE_START = "terminology-check: ignore"
IGNORE_RESUME = "terminology-check: resume"


def allowed(rel_path, line):
    """True if this exact line is on the exemption list."""
    for path, needle, _ in ALLOWED:
        if rel_path == path and needle in line:
            return True
    return False


def files():
    """Every checkable file in the tree, skipping generated and vendored ones."""
    for pattern in SEARCH:
        for path in sorted(ROOT.rglob(pattern)):
            rel = path.relative_to(ROOT).as_posix()
            if any(rel == d or rel.startswith(d + "/") for d in SKIP_DIRS):
                continue
            yield path, rel


def main():
    """Report every retired term found; exit nonzero if there are any."""
    hits = []
    for path, rel in files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        ignoring = False
        for number, line in enumerate(lines, start=1):
            if IGNORE_START in line:
                ignoring = True
                continue
            if IGNORE_RESUME in line:
                ignoring = False
                continue
            if ignoring or allowed(rel, line):
                continue
            for pattern, replacement, why in RULES:
                if re.search(pattern, line, re.IGNORECASE):
                    hits.append((rel, number, line.strip(), replacement, why))

    if not hits:
        checked = sum(1 for _ in files())
        print(f"terminology ok -- {checked} files, no retired terms")
        return 0

    print(f"{len(hits)} retired term(s) found:\n")
    for rel, number, line, replacement, why in hits:
        excerpt = line if len(line) <= 96 else line[:93] + "..."
        print(f"  {rel}:{number}")
        print(f"    {excerpt}")
        print(f"    use '{replacement}' -- {why}\n")
    print(
        "If one of these is genuinely correct where it sits, add it to "
        "ALLOWED in this script with a note saying why."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
