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
ICON_ARG=""
if [[ -f "assets/icons/app_icon.icns" ]]; then
  ICON_ARG="--icon assets/icons/app_icon.icns"
elif [[ -f "assets/icons/app_icon.ico" ]]; then
  ICON_ARG="--icon assets/icons/app_icon.ico"
fi
python3 -m PyInstaller \
  --windowed \
  --name "Digi Lekha" \
  $ICON_ARG \
  --add-data "config:config" \
  --add-data "assets:assets" \
  --hidden-import=PIL \
  --hidden-import=PIL._tkinter_finder \
  --hidden-import=google.generativeai \
  --hidden-import=customtkinter \
  --collect-all customtkinter \
  main.py
echo "Done. App: dist/Digi Lekha.app"
