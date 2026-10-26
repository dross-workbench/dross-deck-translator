$ErrorActionPreference = 'Stop'
$localDir = Join-Path $PSScriptRoot '.local'
$config = Get-Content -LiteralPath (Join-Path $localDir 'config.json') -Raw | ConvertFrom-Json
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_CONTEXT_LENGTH = '2048'
$env:OLLAMA_KEEP_ALIVE = '30s'
$env:OLLAMA_MODELS = $config.models
try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 }
catch {
    Start-Process -FilePath $config.ollama -ArgumentList 'serve' -WorkingDirectory $localDir -WindowStyle Hidden -RedirectStandardOutput (Join-Path $localDir 'ollama.stdout.log') -RedirectStandardError (Join-Path $localDir 'ollama.stderr.log')
}
$env:DROSS_TOKEN = $config.token
$env:DROSS_TRANSLATION_MODEL = $config.translation_model
$env:DROSS_ANALYSIS_MODEL = $config.analysis_model
$env:DROSS_ALLOW_IMAGES = if ($config.allow_screenshots) { '1' } else { '0' }
$env:DROSS_ANKI_ENABLED = if ($config.anki_enabled) { '1' } else { '0' }
$env:DROSS_DATA_DIR = Join-Path $localDir 'data'
Set-Location -LiteralPath $PSScriptRoot
& (Join-Path (Split-Path $PSScriptRoot -Parent) '.venv\Scripts\python.exe') -m uvicorn dross_server.app:create_app --factory --host $config.bind --port $config.port --ssl-keyfile (Join-Path $localDir 'server.key') --ssl-certfile (Join-Path $localDir 'server.pem') --no-access-log --limit-concurrency 8
