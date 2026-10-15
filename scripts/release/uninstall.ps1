# Remove o app e a entrada no PATH. NUNCA apaga os dados do usuário (banco, config, logs, perfil do Chrome).
$ErrorActionPreference = 'Stop'
$app = $PSScriptRoot
$dados = Split-Path $app -Parent

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

Set-UserPathEntry $app $false

try {
    Remove-Item -LiteralPath $app -Recurse -Force
} catch {
    Write-Host "Não consegui remover $app. Feche a Peneira de Vagas (Ctrl+C no terminal dela) e tente de novo." -ForegroundColor Yellow
    exit 1
}
Write-Host 'Peneira de Vagas desinstalada.'
Write-Host "Seus dados foram mantidos em: $dados"
Write-Host 'Para apagá-los também, exclua essa pasta manualmente.'
