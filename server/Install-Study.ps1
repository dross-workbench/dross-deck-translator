$ErrorActionPreference = 'Stop'
$python = Join-Path (Split-Path $PSScriptRoot -Parent) '.venv\Scripts\python.exe'
& $python -m pip install -r (Join-Path $PSScriptRoot 'requirements-study.txt')
if ($LASTEXITCODE -ne 0) { throw 'Study dependencies failed to install' }
$dictionaryDir = Join-Path $PSScriptRoot '.local/dictionary'
New-Item -ItemType Directory -Force $dictionaryDir | Out-Null
$source = Join-Path $dictionaryDir 'JMdict_e.gz'
Invoke-WebRequest 'https://www.edrdg.org/pub/Nihongo/JMdict_e.gz' -OutFile $source
& $python (Join-Path $PSScriptRoot 'import_jmdict.py') $source
if ($LASTEXITCODE -ne 0) { throw 'Dictionary import failed' }
Write-Output 'JMdict © EDRDG. CC BY-SA 4.0. https://www.edrdg.org/edrdg/licence.html'
