@echo off
setlocal
cd /d %~dp0

where nvidia-smi >nul 2>&1
if %errorlevel%==0 (
    echo Placa de video NVIDIA detectada - usando aceleracao por GPU
    set MOTOR=bin\cuda\llama-server.exe
    set OPCAO_CAMADAS=
) else (
    echo Nenhuma GPU NVIDIA detectada - usando modo CPU
    set MOTOR=bin\cpu\llama-server.exe
    set OPCAO_CAMADAS=-ngl 0
)

echo Iniciando o motor de IA...
start "" "%MOTOR%" -m "models\modelo.gguf" --jinja --reasoning off --reasoning-budget 0 -c 4096 --port 8080 %OPCAO_CAMADAS%

echo Aguardando o modelo carregar...
timeout /t 8 /nobreak >nul

echo.
"python\python.exe" "app\main.py"

echo.
echo Encerrando o motor de IA...
taskkill /IM llama-server.exe /F >nul 2>&1

pause
