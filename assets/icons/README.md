# App icons for packaging

Place the following files here for PyInstaller to use:

- **Digi lekha logo.png** — source artwork (used by `scripts/make_icons.py`)
- **app_icon.icns** — macOS (generated; used by `build_mac.sh`)
- **app_icon.ico** — Windows (generated; used by `build_win.bat`)

Regenerate icons after changing the logo:

```bash
python scripts/make_icons.py
```
