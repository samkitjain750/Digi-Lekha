"""
Generate app_icon.ico (Windows) and app_icon.icns (macOS) from the Digi Lekha logo.
Run from project root: python scripts/make_icons.py
"""
import os
import shutil
import subprocess
import sys

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Install Pillow: pip install Pillow")
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS_DIR = os.path.join(ROOT, "assets", "icons")
LOGO_PATH = os.path.join(ICONS_DIR, "Digi lekha logo.png")
os.makedirs(ICONS_DIR, exist_ok=True)


def _base_icon_image():
    if os.path.isfile(LOGO_PATH):
        img = Image.open(LOGO_PATH).convert("RGBA")
        w, h = img.size
        if w != h:
            side = max(w, h)
            square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            square.paste(img, ((side - w) // 2, (side - h) // 2))
            img = square
        if img.width < 1024:
            img = img.resize((1024, 1024), Image.Resampling.LANCZOS)
        return img

    # Fallback placeholder if logo missing
    w, h = 256, 256
    img = Image.new("RGBA", (w, h), (59, 130, 246, 255))
    draw = ImageDraw.Draw(img)
    margin = w // 16
    draw.rounded_rectangle(
        [margin, margin, w - margin, h - margin],
        radius=w // 12,
        fill=(255, 255, 255, 230),
    )
    return img


def make_ico():
    ico_path = os.path.join(ICONS_DIR, "app_icon.ico")
    img = _base_icon_image()
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(ico_path, format="ICO", sizes=sizes)
    print(f"Wrote {ico_path}")


def make_icns():
    icns_path = os.path.join(ICONS_DIR, "app_icon.icns")
    iconset = os.path.join(ICONS_DIR, "app_icon.iconset")
    if os.path.isdir(iconset):
        shutil.rmtree(iconset)
    os.makedirs(iconset, exist_ok=True)

    img = _base_icon_image()
    # macOS iconset required sizes
    mapping = [
        ("icon_16x16.png", 16),
        ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32),
        ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512),
        ("icon_512x512@2x.png", 1024),
    ]
    for filename, size in mapping:
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(os.path.join(iconset, filename))

    if sys.platform == "darwin" and shutil.which("iconutil"):
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns_path], check=True)
        shutil.rmtree(iconset)
        print(f"Wrote {icns_path}")
    else:
        print("iconutil not available — skipping app_icon.icns (macOS build only)")


if __name__ == "__main__":
    make_ico()
    make_icns()
