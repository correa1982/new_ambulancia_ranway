@echo off
REM ProbarTodo: revisa el entorno y la sintaxis, y corre TODAS las pruebas.
REM Uso: doble clic. Para una corrida parcial: ProbarTodo.bat -k formularios
chcp 65001 >nul
cd /d "%~dp0\.."
set "PY=python"
where python >nul 2>nul || set "PY=py -3"
%PY% tests\probar_todo.py %*
set "CODIGO=%ERRORLEVEL%"
echo.
pause
exit /b %CODIGO%
