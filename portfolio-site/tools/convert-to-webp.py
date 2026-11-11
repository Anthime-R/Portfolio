"""Create .webp copies of the .jpg/.png images in the assets folder.

The page loads assets/<name>.webp first and automatically falls back to
assets/<name>.jpg when the .webp file is missing, so running this script is
optional — it only makes the page lighter.

Usage (from the site folder):
    pip install pillow
    python tools/convert-to-webp.py
"""
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parent.parent / "assets"
MAX_SIDE = 1600   # longest side in pixels
QUALITY = 80      # WebP quality (0-100)


def main() -> None:
    for src in sorted(ASSETS.iterdir()):
        if src.suffix.lower() not in {".jpg", ".jpeg", ".png"} or src.name == "og-image.png":
            continue
        dst = src.with_suffix(".webp")
        if dst.exists():
            print(f"skip   {dst.name} (already exists)")
            continue
        with Image.open(src) as im:
            im = im.convert("RGB")
            im.thumbnail((MAX_SIDE, MAX_SIDE))
            im.save(dst, "WEBP", quality=QUALITY, method=6)
        print(f"wrote  {dst.name}  ({src.stat().st_size // 1024} KB -> {dst.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
