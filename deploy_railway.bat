@echo off
cd /d "%~dp0"
set RAILWAY=.\tools\railway.exe

echo === Railway login (brauzer ochiladi) ===
%RAILWAY% login
if errorlevel 1 (
  echo Login xato. Qayta urinib ko'ring.
  pause
  exit /b 1
)

echo === Project yaratish / ulash ===
%RAILWAY% link 2>nul
if errorlevel 1 (
  %RAILWAY% init
)

echo === Env o'zgaruvchilarni yuklash ===
.\.venv\Scripts\python.exe tools\push_railway_env.py
if errorlevel 1 (
  echo Env yuklashda xato.
  pause
  exit /b 1
)

echo === Volume (DB saqlansin) ===
%RAILWAY% volume add /data 2>nul

echo === Deploy ===
%RAILWAY% up --detach
if errorlevel 1 (
  echo Deploy xato.
  pause
  exit /b 1
)

echo.
echo OK: Bot Railway serverda ishga tushdi.
echo Endi lokal botni TO'XTATING (aks holda 409 conflict).
echo.
pause
