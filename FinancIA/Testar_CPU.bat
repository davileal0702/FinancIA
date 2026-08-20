@echo off
setlocal
cd /d %~dp0

echo ================================================
echo   TESTE - forcando modo CPU (ignora a GPU)
echo ================================================
echo.

echo Iniciando o motor de IA em modo CPU...
start "" /min "bin\cpu\llama-server.exe" -m "models\modelo.gguf" -c 4096 --port 8080 -ngl 0

echo Aguardando o modelo carregar (pode demorar mais que o normal, e ok)...
timeout /t 8 /nobreak >nul

echo.
"python\python.exe" "app\main.py"

echo.
echo Encerrando o motor de IA...
taskkill /IM llama-server.exe /F >nul 2>&1

pause
