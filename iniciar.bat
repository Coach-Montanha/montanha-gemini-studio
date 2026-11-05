@echo off
title Montanha Gemini Studio
cd /d "C:\Users\Administrator\Documents\Projetos\Montanha Gemini Studio"

:: Verificar se já está rodando na porta 4192
netstat -ano | findstr :4192 >nul
if %errorlevel% neq 0 (
    start "" /b python "C:\Users\Administrator\Documents\Projetos\Montanha Gemini Studio\server.py"
    timeout /t 1 /nobreak >nul
)

:: Abrir como App Desktop nativo no Microsoft Edge
if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
    start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --app="http://localhost:4192" --window-size=1200,820
) else if exist "C:\Program Files\Microsoft\Edge\Application\msedge.exe" (
    start "" "C:\Program Files\Microsoft\Edge\Application\msedge.exe" --app="http://localhost:4192" --window-size=1200,820
) else (
    start "" "http://localhost:4192"
)
exit
