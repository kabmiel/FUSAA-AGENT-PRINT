param(
    [string]$Email,
    [string]$BaseUrl = "http://127.0.0.1:8000"
)
$ErrorActionPreference = "Stop"
if (-not $Email) { $Email = Read-Host 'Adresse e-mail du compte administrateur' }
$recoveryBackend = Join-Path (Split-Path -Parent $PSScriptRoot) 'backend'
Push-Location $recoveryBackend
try {
    py -3.11 -m app.recover_admin --email $Email --base-url $BaseUrl
    if ($LASTEXITCODE -ne 0) { throw 'La création du lien de récupération a échoué.' }
}
finally { Pop-Location }
