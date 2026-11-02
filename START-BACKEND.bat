@echo off
cd /d "%~dp0backend"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
if not exist .venv\Scripts\python.exe (%PY% -m venv .venv)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (echo. & echo XATO: kutubxonalar ornatilmadi. Internetni va Python 3.10+ borligini tekshiring. & pause & exit /b 1)
copy /Y .env.example .env >nul
echo.
echo Backend ishga tushmoqda: http://127.0.0.1:8001/api/health
python -m uvicorn main:app --host 127.0.0.1 --port 8001
pause
