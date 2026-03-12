@echo off
REM Build Windows .exe with PyInstaller.
REM Run from project root: build_win.bat
REM Output: dist\Digi Lekha.exe
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"
where pyinstaller >nul 2>nul || (
  echo PyInstaller not found. Install with: pip install pyinstaller
  exit /b 1
)
set ICON_ARG=
if exist "assets\icons\app_icon.ico" set ICON_ARG=--icon assets/icons/app_icon.ico
pyinstaller --windowed --name "Digi Lekha" %ICON_ARG% --add-data "config;config" --add-data "assets;assets" --hidden-import=PIL --hidden-import=PIL._tkinter_finder --hidden-import=google.generativeai --hidden-import=customtkinter --collect-all customtkinter main.py
echo Done. Exe: dist\Digi Lekha.exe
