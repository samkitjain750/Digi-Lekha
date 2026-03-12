# App icons for packaging

Place the following files here for PyInstaller to use:

- **app_icon.icns** — macOS (used by `build_mac.sh`)
- **app_icon.ico** — Windows (used by `build_win.bat`)

If these files are missing, the build still runs; the app will use the default icon.

To generate a simple icon from a 256×256 PNG or from code, you can use Pillow to create `app_icon.ico` (multi-size). On macOS, create an iconset and run `iconutil -c icns app_icon.iconset` to produce `app_icon.icns`.
