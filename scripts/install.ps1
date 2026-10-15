# Instala a Peneira de Vagas para o usuário atual (sem administrador, sem Python instalado).
#   irm https://raw.githubusercontent.com/marcos-moraesjr/peneira-de-vagas/main/scripts/install.ps1 | iex
# O que faz: baixa o último peneira.zip da Release do GitHub, extrai em %LOCALAPPDATA%\PeneiraDeVagas\app
# e põe essa pasta no PATH do usuário. Os dados (banco, config, logs, perfil do Chrome) ficam em
# %LOCALAPPDATA%\PeneiraDeVagas e nunca são tocados; reinstalar atualiza só o app.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$repo = 'marcos-moraesjr/peneira-de-vagas'
$dados = Join-Path $env:LOCALAPPDATA 'PeneiraDeVagas'
$app = Join-Path $dados 'app'

# Edita o PATH do usuário sem expandir %VARIAVEIS% (SetEnvironmentVariable regravaria o valor expandido).
function Set-UserPathEntry([string]$entrada, [bool]$presente, [string]$nome = 'Path') {
    $chave = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', $true)
    try {
        $atual = [string]$chave.GetValue($nome, '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
        $partes = @($atual -split ';' | Where-Object { $_ -and ($_ -ne $entrada) })
        if ($presente) { $partes += $entrada }
        $chave.SetValue($nome, ($partes -join ';'), [Microsoft.Win32.RegistryValueKind]::ExpandString)
    } finally { $chave.Close() }
    # Avisa o Explorer: sem isto, terminais abertos pelo menu Iniciar só enxergam o PATH após novo login.
    [Environment]::SetEnvironmentVariable('PENEIRA_REFRESH', '1', 'User')
    [Environment]::SetEnvironmentVariable('PENEIRA_REFRESH', $null, 'User')
}

# PENEIRA_ZIP: caminho de um peneira.zip local (testes de empacotamento); PENEIRA_NO_PATH=1: não mexe no PATH.
$zip = $env:PENEIRA_ZIP
$baixado = $false
if (-not $zip) {
    $zip = Join-Path $env:TEMP 'peneira.zip'
    Write-Host 'Baixando a Peneira de Vagas...'
    Invoke-WebRequest "https://github.com/$repo/releases/latest/download/peneira.zip" -OutFile $zip
    $baixado = $true
}

New-Item -ItemType Directory -Force $dados | Out-Null
if (Test-Path $app) {
    try {
        Remove-Item -LiteralPath $app -Recurse -Force
    } catch {
        throw 'Não consegui substituir a versão instalada. Feche a Peneira de Vagas (Ctrl+C no terminal dela) e rode de novo.'
    }
}
Expand-Archive -LiteralPath $zip -DestinationPath $app -Force
if ($baixado) { Remove-Item -LiteralPath $zip -Force }

if ($env:PENEIRA_NO_PATH -ne '1') {
    Set-UserPathEntry $app $true
    if (($env:Path -split ';') -notcontains $app) { $env:Path = "$env:Path;$app" }
}

$chromes = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
if (-not ($chromes | Where-Object { Test-Path $_ })) {
    Write-Host 'Aviso: o Google Chrome não foi encontrado. LinkedIn e Indeed precisam dele; a Gupy funciona sem.' -ForegroundColor Yellow
}

Write-Host ''
Write-Host 'Peneira de Vagas instalada. Digite  peneira  para abrir a interface.'
Write-Host "Seus dados ficam em: $dados"
