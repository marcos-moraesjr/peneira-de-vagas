# Abre o Chrome DEDICADO do Peneira de Vagas (perfil próprio, porta de depuração só em localhost).
# Faça login no LinkedIn e no Indeed manualmente nesta janela e deixe-a aberta durante a busca.
# Nunca use o seu perfil pessoal aqui.
$root = Split-Path -Parent $PSScriptRoot
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
if (-not (Test-Path $chrome)) { $chrome = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" }
if (-not (Test-Path $chrome)) { Write-Error "Chrome não encontrado."; exit 1 }

& $chrome `
  --remote-debugging-port=9222 `
  --remote-debugging-address=127.0.0.1 `
  --user-data-dir="$root\data\chrome-profile" `
  --no-first-run
