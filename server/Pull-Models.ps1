param([ValidateSet('qwen3:0.6b','qwen3:1.7b','qwen3:4b','translategemma:4b')][string[]]$Models = @('qwen3:4b'))
$ErrorActionPreference = 'Stop'
$config = Get-Content -LiteralPath (Join-Path $PSScriptRoot '.local/config.json') -Raw | ConvertFrom-Json
$env:OLLAMA_HOST = '127.0.0.1:11434'
foreach ($model in $Models) {
    & $config.ollama pull $model
    if ($LASTEXITCODE -ne 0) { throw "Model download failed: $model" }
}
