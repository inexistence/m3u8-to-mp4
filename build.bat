@echo off
setlocal

if not exist .venv\Scripts\python.exe (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo Building exe...
python -m PyInstaller --clean build.spec

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Build succeeded: dist\m3u8-to-mp4.exe
) else (
    echo.
    echo Build failed.
    exit /b 1
)
