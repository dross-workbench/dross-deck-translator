param([string]$OutputPath = (Join-Path $PSScriptRoot '.local/dross-vocabulary.tsv'))
$ErrorActionPreference = 'Stop'
$python = Join-Path (Split-Path $PSScriptRoot -Parent) '.venv\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'export_vocabulary.py') --output $OutputPath
