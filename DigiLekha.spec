# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Digi Lekha (macOS + Windows).
# macOS: Digi Lekha.app only (onedir bundle)
# Windows: Digi Lekha.exe (onefile)

import os
import sys
from PyInstaller.utils.hooks import collect_all

block_cipher = None
is_mac = sys.platform == "darwin"

root = os.path.abspath(SPECPATH)
icns_path = os.path.join(root, "assets", "icons", "app_icon.icns")
ico_path = os.path.join(root, "assets", "icons", "app_icon.ico")
if is_mac and os.path.isfile(icns_path):
    icon_arg = icns_path
elif os.path.isfile(ico_path):
    icon_arg = ico_path
else:
    icon_arg = None

ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all("customtkinter")

a = Analysis(
    ["main.py"],
    pathex=[root],
    binaries=ctk_binaries,
    datas=[
        (os.path.join(root, "config"), "config"),
        (os.path.join(root, "assets"), "assets"),
        *ctk_datas,
    ],
    hiddenimports=[
        "PIL",
        "PIL._tkinter_finder",
        "openai",
        "customtkinter",
        "fitz",
        "pandas",
        "openpyxl",
        "tkinter",
        "tkinter.ttk",
    ]
    + list(ctk_hiddenimports),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "torchaudio",
        "torchvision",
        "transformers",
        "sklearn",
        "scipy",
        "matplotlib",
        "IPython",
        "jupyter",
        "notebook",
        "sympy",
        "tensorflow",
        "keras",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if is_mac:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="Digi Lekha",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_arg,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="Digi Lekha",
    )
    app = BUNDLE(
        coll,
        name="Digi Lekha.app",
        icon=icon_arg,
        bundle_identifier="com.digilekha.app",
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="Digi Lekha",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_arg,
    )
