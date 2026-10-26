param([Parameter(Mandatory)][string]$BindAddress)
$ErrorActionPreference = 'Stop'
$localDir = Join-Path $PSScriptRoot '.local'
$config = Get-Content -LiteralPath (Join-Path $localDir 'config.json') -Raw | ConvertFrom-Json
$python = Join-Path (Split-Path $PSScriptRoot -Parent) '.venv\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'setup_config.py') --bind $BindAddress --ollama $config.ollama --models $config.models
if ($LASTEXITCODE -ne 0) { throw 'Connection configuration failed' }
Write-Output 'Restart the Dross translation server, then pair the new certificate fingerprint on the Deck. Existing models and vocabulary were retained.'
