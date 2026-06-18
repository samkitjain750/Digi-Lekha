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

if [[ ! -f "assets/icons/app_icon.ico" ]]; then
  echo "Generating app icon..."
  python3 scripts/make_icons.py
fi

python3 -m PyInstaller DigiLekha.spec --noconfirm --clean
echo "Done. App: dist/Digi Lekha.app"
