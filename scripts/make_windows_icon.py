"""Draw the ARGUS eye icon used by the Windows executables and installer.

Run from the repository root:  python scripts/make_windows_icon.py
Colors come from the default ``arc_reactor`` palette in design/tokens.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "argus.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]
CANVAS = 1024


def _palette() -> dict[str, str]:
    tokens = json.loads((ROOT / "design" / "tokens.json").read_text(encoding="utf-8"))
    return tokens["palettes"][tokens["default_theme"]]


def draw(size: int = CANVAS) -> Image.Image:
    colors = _palette()
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    unit = size / 64

    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=14 * unit, fill=colors["BG"])
    # Almond eye outline built from two circle arcs meeting at the corners.
    stroke = round(3.5 * unit)
    box = (-10 * unit, 17 * unit, 74 * unit, 101 * unit)
    draw.arc(box, start=232, end=308, fill=colors["PRI"], width=stroke)
    box = (-10 * unit, -37 * unit, 74 * unit, 47 * unit)
    draw.arc(box, start=52, end=128, fill=colors["PRI"], width=stroke)
    # Iris, pupil and highlight.
    draw.ellipse((20 * unit, 20 * unit, 44 * unit, 44 * unit), outline=colors["ENERGY"], width=stroke)
    draw.ellipse((27 * unit, 27 * unit, 37 * unit, 37 * unit), fill=colors["PRI"])
    draw.ellipse((33 * unit, 26 * unit, 37 * unit, 30 * unit), fill=colors["WHITE"])
    return image


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    draw().save(OUTPUT, format="ICO", sizes=[(size, size) for size in SIZES])
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
