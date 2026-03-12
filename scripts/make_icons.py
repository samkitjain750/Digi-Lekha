"""
Generate placeholder app_icon.ico (and optionally .icns) for packaging.
Run from project root: python scripts/make_icons.py
Requires: Pillow. On macOS, .icns can be created with iconutil from a .iconset.
"""
import os
import sys

try:
    from PIL import Image
except ImportError:
    print("Install Pillow: pip install Pillow")
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS_DIR = os.path.join(ROOT, "assets", "icons")
os.makedirs(ICONS_DIR, exist_ok=True)


def make_ico():
    from PIL import ImageDraw
    # Simple 256x256 blue document-style icon
    w, h = 256, 256
    img = Image.new("RGBA", (w, h), (59, 130, 246, 255))
    draw = ImageDraw.Draw(img)
    margin = w // 16
    draw.rounded_rectangle([margin, margin, w - margin, h - margin], radius=w // 12, fill=(255, 255, 255, 230))
    ico_path = os.path.join(ICONS_DIR, "app_icon.ico")
    img.save(ico_path, format="ICO", sizes=[(256, 256), (48, 48), (32, 32), (16, 16)])
    print(f"Wrote {ico_path}")


if __name__ == "__main__":
    make_ico()
