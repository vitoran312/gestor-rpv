@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo Gestor de RPV - Gerar executavel Windows
echo.
where py.exe >nul 2>nul
if errorlevel 1 (
    set "PYTHON_GESTOR=python"
) else (
    set "PYTHON_GESTOR=py -3"
)
%PYTHON_GESTOR% -c "import sys,struct; sys.exit(0 if sys.version_info >= (3,10) and struct.calcsize('P') == 8 else 1)"
if errorlevel 1 (
    echo E necessario ter Python 3.10 ou superior, de 64 bits, instalado.
    goto erro
)
%PYTHON_GESTOR% -m venv .venv-build
if errorlevel 1 goto erro
".venv-build\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 goto erro
".venv-build\Scripts\python.exe" gerar_exe.py
if errorlevel 1 goto erro
echo.
echo Pronto! Seu executavel esta na pasta dist.
start "" "%~dp0dist"
pause
exit /b 0
:erro
echo.
echo Nao foi possivel gerar o executavel. Confira a mensagem acima.
pause
exit /b 1
