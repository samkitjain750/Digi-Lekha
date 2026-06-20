#!/usr/bin/env bash
# Build macOS .app bundle with PyInstaller.
# Run from project root: ./build_mac.sh
# Output: dist/Digi Lekha.app
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! python3 -m PyInstaller --help &>/dev/null; then
  echo "PyInstaller not found. Install with: pip install pyinstaller"
  exit 1
fi

echo "Generating app icons from logo..."
python3 scripts/make_icons.py

python3 -m PyInstaller DigiLekha.spec --noconfirm --clean

APP="dist/Digi Lekha.app"
PLIST="$APP/Contents/Info.plist"
# macOS expects CFBundleIconFile without the .icns extension
/usr/libexec/PlistBuddy -c "Set :CFBundleIconFile app_icon" "$PLIST" 2>/dev/null || true
touch "$APP"

echo "Done. App: $APP"
