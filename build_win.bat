@echo off
REM Build Windows .exe with PyInstaller.
REM Run from project root on a Windows PC: build_win.bat
REM Output: dist\Digi Lekha.exe
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

where python >nul 2>nul || (
  echo Python not found. Install Python 3.10+ from https://www.python.org/downloads/
  exit /b 1
)

python -m pip show pyinstaller >nul 2>nul || (
  echo PyInstaller not found. Install with: pip install pyinstaller
  exit /b 1
)

if not exist "assets\icons\app_icon.ico" (
  echo Generating app icon...
  python scripts\make_icons.py
)

python -m PyInstaller DigiLekha.spec --noconfirm --clean
if errorlevel 1 exit /b 1

REM Folder icon in Explorer: point desktop.ini at the exe icon
(
echo [.ShellClassInfo]
echo IconResource=Digi Lekha.exe,0
echo ConfirmFileOp=0
echo InfoTip=Digi Lekha - Document Extractor
) > "dist\Digi Lekha\desktop.ini"
attrib +s "dist\Digi Lekha"
attrib +h "dist\Digi Lekha\desktop.ini"

echo.
echo Done. Windows app folder: dist\Digi Lekha\
echo Run: dist\Digi Lekha\Digi Lekha.exe
echo Zip that folder before sharing (do not send raw .exe over WhatsApp).
