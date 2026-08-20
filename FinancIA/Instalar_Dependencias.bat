@echo off
setlocal enabledelayedexpansion
cd /d %~dp0

echo ================================================
echo   FinancIA - Instalador de dependencias Python
echo ================================================
echo.

REM 1) Verifica se o WinPython foi extraido corretamente
if not exist "python\python.exe" (
    echo [ERRO] Nao encontrei python\python.exe
    echo.
    echo Isso significa que o WinPython ainda nao foi extraido direito
    echo dentro da pasta "python". Confira se voce:
    echo   1. Baixou o WinPython64-...dot ^(ou similar^)
    echo   2. Extraiu e copiou o CONTEUDO da subpasta python-3.XX.X
    echo      direto para dentro de FinancIA\python\
    echo   3. O resultado deve ser: FinancIA\python\python.exe
    echo.
    pause
    exit /b 1
)
echo [OK] Python encontrado em python\python.exe
echo.

REM 2) Testa conexao com a internet (necessaria so durante esta instalacao)
echo Verificando conexao com a internet...
ping -n 1 pypi.org >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Nao consegui alcancar pypi.org
    echo.
    echo Causas mais comuns:
    echo   - Sua internet esta fora do ar agora
    echo   - Um firewall/antivirus esta bloqueando o acesso
    echo   - Voce esta numa rede que exige login antes de navegar
    echo     ^(rede de hotel, faculdade, empresa, etc.^)
    echo.
    echo Resolva a conexao e rode este arquivo de novo.
    echo ^(Depois de configurado uma vez, voce NAO precisa mais de
    echo  internet pra usar o FinancIA no dia a dia^)
    echo.
    pause
    exit /b 1
)
echo [OK] Internet disponivel
echo.

REM 3) Atualiza o pip (nao trava a instalacao se isso falhar)
echo Atualizando o pip...
python\python.exe -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo [AVISO] Nao consegui atualizar o pip, mas vou tentar continuar mesmo assim.
)
echo.

REM 4) Instala as dependencias de verdade
echo Instalando pdfplumber e matplotlib (pode demorar alguns minutos)...
echo.
python\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ================================================
    echo   [ERRO] A instalacao falhou
    echo ================================================
    echo.
    echo Causas mais comuns e como resolver cada uma:
    echo.
    echo   1^) Um pacote mudou de nome/versao no PyPI
    echo      Tente instalar um de cada vez pra descobrir qual e o problema:
    echo        python\python.exe -m pip install pdfplumber
    echo        python\python.exe -m pip install matplotlib
    echo.
    echo   2^) Erro de certificado SSL ^(comum em rede corporativa/escolar^)
    echo      Tente com:
    echo        python\python.exe -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
    echo.
    echo   3^) Pendrive em modo "somente leitura" ^(sem permissao de escrita^)
    echo      Botao direito no pendrive na Unidade D: -^> Propriedades -^> confira
    echo      se "Somente leitura" nao esta marcado
    echo.
    echo   4^) Antivirus bloqueando a instalacao
    echo      Alguns antivirus barram scripts baixando arquivos .whl/.tar.gz.
    echo      Verifique se ele nao colocou algo em quarentena.
    echo.
    echo Se nada disso resolver, copie a mensagem de erro que apareceu
    echo ACIMA desta caixa e me mostre que eu te ajudo a resolver.
    echo.
    pause
    exit /b 1
)

echo.
echo ================================================
echo   Tudo instalado com sucesso!
echo   Agora e so usar o Iniciar.bat normalmente.
echo ================================================
pause
