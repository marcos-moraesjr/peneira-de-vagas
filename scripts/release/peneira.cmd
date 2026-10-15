@echo off
rem Comando `peneira`: sobe a interface. `peneira atualizar` instala a ultima versao; `peneira desinstalar` remove o app (os dados do usuario ficam).
if /i "%~1"=="atualizar" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/marcos-moraesjr/peneira-de-vagas/main/scripts/install.ps1 | iex"
  exit /b
)
if /i "%~1"=="desinstalar" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"
  exit /b
)
"%~dp0python\python.exe" -m backend.app.launcher %*
