"""Build the ARGUS app icon (assets/argus.ico) from its pixel-art source.

Run from the repository root:  python scripts/make_windows_icon.py
``--png PATH`` writes only a 256 px PNG instead (the Linux app-menu icon).
The source, assets/argus-icon.png, is the artwork at its native pixel grid
(one image pixel per art pixel, square). Each icon size is scaled up with
nearest-neighbour first so the pixels stay crisp, then down to the target.
The Windows executables, the installer and the desktop window use the result.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "argus-icon.png"
OUTPUT = ROOT / "assets" / "argus.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]
MASTER = 1600


def render(size: int) -> Image.Image:
    art = Image.open(SOURCE).convert("RGBA")
    if art.width != art.height:
        raise ValueError(f"{SOURCE.name} must be square, got {art.size}")
    master = art.resize((MASTER, MASTER), Image.NEAREST)
    return master.resize((size, size), Image.LANCZOS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--png", type=Path, help="write only a 256 px PNG here")
    args = parser.parse_args()

    if args.png:
        render(256).save(args.png, format="PNG")
        print(f"Wrote {args.png}")
        return
    images = [render(size) for size in SIZES]
    images[-1].save(OUTPUT, format="ICO", sizes=[(size, size) for size in SIZES], append_images=images[:-1])
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
