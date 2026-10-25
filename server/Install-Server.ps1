param(
    [string]$Python = 'python',
    [string]$BindAddress = '127.0.0.1',
    [string]$OllamaPath = '',
    [string]$ModelsPath = ''
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$venv = Join-Path $repoRoot '.venv'
& $Python -m venv $venv
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 or 3.13 is required' }
$venvPython = Join-Path $venv 'Scripts\python.exe'
& $venvPython -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
$localDir = Join-Path $PSScriptRoot '.local'
New-Item -ItemType Directory -Force $localDir | Out-Null
if (-not $OllamaPath) {
    $OllamaPath = Join-Path $localDir 'ollama\ollama.exe'
    if (-not (Test-Path -LiteralPath $OllamaPath)) {
        $archive = Join-Path $localDir 'ollama.zip'
        Invoke-WebRequest 'https://github.com/ollama/ollama/releases/download/v0.40.11/ollama-windows-amd64.zip' -OutFile $archive
        if ((Get-FileHash $archive -Algorithm SHA256).Hash.ToLower() -ne 'bda4a493ba8a7c24d57263cd843cd68cee84f44aed4299eeed532acad7eda12a') { throw 'Ollama checksum mismatch' }
        Expand-Archive -LiteralPath $archive -DestinationPath (Split-Path $OllamaPath) -Force
    }
}
if (-not $ModelsPath) { $ModelsPath = Join-Path $localDir 'models' }
& $venvPython (Join-Path $PSScriptRoot 'setup_config.py') --bind $BindAddress --ollama $OllamaPath --models $ModelsPath
if ($LASTEXITCODE -ne 0) { throw 'Configuration failed' }
$account = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls.exe $localDir /inheritance:r /grant:r "${account}:(OI)(CI)F" 'SYSTEM:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not protect local credentials' }
Write-Output 'Installed. Run Start-Server.ps1, then pull the selected model using Pull-Models.ps1.'
