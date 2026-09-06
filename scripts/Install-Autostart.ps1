param([switch]$AgentOnly)
$ErrorActionPreference = 'Stop'
$fusaaRoot = Split-Path $PSScriptRoot -Parent
$fusaaPython = (& py -3.11 -c "import sys; print(sys.executable)").Trim()
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 introuvable' }
$fusaaPythonWindowless = Join-Path (Split-Path $fusaaPython -Parent) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $fusaaPythonWindowless)) { throw 'pythonw.exe introuvable' }
$fusaaStartup = [Environment]::GetFolderPath('Startup')
$fusaaShortcutPath = Join-Path $fusaaStartup 'FUSAA Service.lnk'
$fusaaShell = New-Object -ComObject WScript.Shell
$fusaaShortcut = $fusaaShell.CreateShortcut($fusaaShortcutPath)
$fusaaShortcut.TargetPath = $fusaaPythonWindowless
$fusaaShortcut.Arguments = '"' + (Join-Path $PSScriptRoot 'windows_runtime.py') + '" supervise'
$fusaaShortcut.WorkingDirectory = $fusaaRoot
if ($AgentOnly) {
    $fusaaShortcut.Arguments = '-m fusaa_agent.main'
    $fusaaShortcut.WorkingDirectory = Join-Path $fusaaRoot 'local-agent'
}
$fusaaShortcut.WindowStyle = 7
$fusaaShortcut.Description = 'FUSAA : API, agent Windows, Ollama et sauvegarde quotidienne'
$fusaaShortcut.Save()
Write-Output "Demarrage a la connexion Windows installe : $fusaaShortcutPath"
