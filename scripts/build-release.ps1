# Gera release\peneira.zip: Python embutido + dependências + backend + front, sem exigir Python no usuário.
#   powershell -File scripts\build-release.ps1
# Precisa de: .venv do projeto (a mesma versão do Python vira a embutida), Node/npm e internet (python.org, npm, PyPI).
param([Parameter(Mandatory)][ValidatePattern('^\d+\.\d+\.\d+$')][string]$Versao)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$root = Split-Path $PSScriptRoot -Parent
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
$pyVersao = (& $venvPython -c 'import platform; print(platform.python_version())').Trim()
$saida = Join-Path $root 'release'
$app = Join-Path $saida 'app'

if (Test-Path $saida) { Remove-Item -LiteralPath $saida -Recurse -Force }
New-Item -ItemType Directory -Force $app | Out-Null

Write-Host '1/5 Build do front...'
Push-Location (Join-Path $root 'frontend')
try { npm run build; if ($LASTEXITCODE) { throw 'npm run build falhou' } } finally { Pop-Location }

Write-Host "2/5 Python $pyVersao embutido..."
$embed = Join-Path $saida "python-$pyVersao-embed-amd64.zip"
Invoke-WebRequest "https://www.python.org/ftp/python/$pyVersao/python-$pyVersao-embed-amd64.zip" -OutFile $embed
$python = Join-Path $app 'python'
Expand-Archive -LiteralPath $embed -DestinationPath $python
$pth = Get-ChildItem $python -Filter 'python*._pth' | Select-Object -First 1
# No Python embutido o sys.path vem só deste arquivo: o app (..) e as dependências (..\lib) entram aqui.
Set-Content -LiteralPath $pth.FullName -Encoding ascii -Value @("$($pth.BaseName).zip", '.', '..', '..\lib', 'import site')
Remove-Item -LiteralPath $embed

Write-Host '3/5 Dependências (sem as de teste)...'
$requisitos = Join-Path $saida 'requirements-release.txt'
Get-Content (Join-Path $root 'backend\requirements.txt') | Where-Object { $_ -and $_ -notmatch '^pytest' } | Set-Content $requisitos
& $venvPython -m pip install -r $requisitos --target (Join-Path $app 'lib') --only-binary=:all: --disable-pip-version-check
if ($LASTEXITCODE) { throw 'pip install falhou' }
Remove-Item -LiteralPath $requisitos

Write-Host '4/5 Backend, front e comandos...'
robocopy (Join-Path $root 'backend') (Join-Path $app 'backend') /E /XD tests scripts __pycache__ /XF *.pyc /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) { throw 'robocopy do backend falhou' }
robocopy (Join-Path $root 'frontend\dist') (Join-Path $app 'frontend\dist') /E /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) { throw 'robocopy do front falhou' }
Copy-Item (Join-Path $PSScriptRoot 'release\*') $app
# O app compara esta versão com a última Release do GitHub (aviso de atualização na tela).
Set-Content -LiteralPath (Join-Path $app 'versao.txt') -Value $Versao -Encoding ascii

Write-Host '5/5 Compactando...'
$zip = Join-Path $saida 'peneira.zip'
Compress-Archive -Path (Join-Path $app '*') -DestinationPath $zip
$mb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host "Pronto: $zip ($mb MB)"
Write-Host "Publicar: gh release create v$Versao release\peneira.zip --repo marcos-moraesjr/peneira-de-vagas"
