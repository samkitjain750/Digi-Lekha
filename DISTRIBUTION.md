# Distributing Digi Lekha

This document describes how to build and distribute the application as a standalone desktop app for **macOS** and **Windows**.

## Prerequisites

- Python 3.10+ with dependencies installed (`pip install -r requirements.txt`)
- **PyInstaller**: `pip install pyinstaller`
- App icon: `assets/icons/app_icon.ico` (Windows) — run `python scripts/make_icons.py` if missing.
- Optional macOS icon: `assets/icons/app_icon.icns`

### Important: build on the target OS

PyInstaller builds for the machine it runs on. You **cannot** create a Windows `.exe` on macOS (or vice versa) without a VM or CI.

| Where you are | How to get Windows `.exe` |
|---------------|---------------------------|
| **Windows PC** | Run `build_win.bat` locally |
| **macOS (you)** | Push to GitHub and run the **Build desktop apps** workflow (see below) |

---

## Building on GitHub (Windows + macOS)

If the repo is on GitHub, use Actions to build both platforms without a Windows PC:

1. Push this project to GitHub.
2. Open **Actions** → **Build desktop apps** → **Run workflow**.
3. When finished, download artifacts:
   - **Digi-Lekha-Windows** → `Digi Lekha.exe`
   - **Digi-Lekha-macOS** → `Digi-Lekha-macOS.zip`

The workflow also runs automatically when you push a version tag like `v1.0.0`.

---

## Building

### macOS (.app bundle)

From the project root:

```bash
chmod +x build_mac.sh
./build_mac.sh
```

**Output:** `dist/Digi Lekha.app`

- The app is **windowed** (no terminal).
- Config and assets are bundled; the app uses the first-run screen to store the API key in a writable location (e.g. `~/Library/Application Support/Digi Lekha`).

### Windows (.exe)

From the project root (Command Prompt or PowerShell):

```bat
build_win.bat
```

**Output:** `dist/Digi Lekha.exe`

- Same behaviour: windowed, bundled config/assets, first-run API key setup.

---

## Distribution

### macOS

1. **Zip the app:** Compress `dist/Digi Lekha.app` into a ZIP (e.g. `Digi-Lekha-macOS.zip`).
2. **Share the ZIP:** Users download it, unzip, and move the `.app` to Applications (or run from the folder).
3. **First run:** Double-click the app. If the Gemini API key is not set, the first-run dialog appears; after saving the key, the app opens normally.

### Windows

1. **Share the exe:** Distribute `dist/Digi Lekha.exe` (or put it in a ZIP for download).
2. **First run:** User double-clicks the exe. Same first-run API key prompt if the key is not stored.

---

## User experience

- **No Python required:** Users do not install Python or run any terminal commands.
- **Double-click to run:** Same as any desktop app.
- **First-run setup:** If the Gemini API key is missing, a dialog asks for it and stores it in:
  - **macOS:** `~/Library/Application Support/Digi Lekha/config/api_key.json`
  - **Windows:** `%APPDATA%\Digi Lekha\config\api_key.json`
- **Settings:** Extraction settings and API key are stored in that same writable config area when running the packaged app.
- **Input/Output folders:** Default locations are under the same Application Support (or AppData) folder so the app does not need write access next to the executable.

---

## Build options reference

| Platform | Command / script | Output |
|----------|------------------|--------|
| macOS    | `./build_mac.sh` | `dist/Digi Lekha.app` |
| Windows  | `build_win.bat`  | `dist/Digi Lekha.exe`  |

Both use:

- `--windowed` (no console)
- `--add-data` for `config` and `assets`
- Optional `--icon` if `assets/icons/app_icon.icns` or `app_icon.ico` exists
- Hidden imports and `--collect-all customtkinter` for a self-contained bundle
