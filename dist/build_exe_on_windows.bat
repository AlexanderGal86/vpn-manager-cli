@echo off
title Build VPN-Manager-Setup.exe
color 0A
echo.
echo  =============================================================
echo   VPN/Proxy Manager - Build Windows EXE
echo  =============================================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorLevel% NEQ 0 (
    echo  [!] Python not found. Install Python 3.10+ and retry.
    pause & exit /b 1
)

:: Install PyInstaller
echo  [*] Installing PyInstaller...
python -m pip install pyinstaller -q
if %errorLevel% NEQ 0 (
    echo  [!] Failed to install PyInstaller.
    pause & exit /b 1
)

:: Build EXE
echo  [*] Building exe...
pyinstaller --onefile --console --name "VPN-Manager-Setup" --icon NONE build_exe_source.py

if %errorLevel% EQU 0 (
    echo.
    echo  [+] Done! File: dist\VPN-Manager-Setup.exe
    for %%F in (dist\VPN-Manager-Setup.exe) do echo      %%~zF bytes
) else (
    echo  [!] Build failed.
)
echo.
pause
