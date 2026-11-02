@echo off
cd /d "%~dp0"
start "ACADEMY UZ" cmd /k "START-BACKEND.bat"
timeout /t 8 /nobreak >nul
start "" http://127.0.0.1:8001
