param([Parameter(Mandatory)][string]$TrustedDevice)
$ErrorActionPreference = 'Stop'
$ip = [System.Net.IPAddress]::Parse($TrustedDevice)
if ($ip.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { throw 'Use the Steam Deck private IPv4 address' }
$bytes = $ip.GetAddressBytes()
if (-not ($bytes[0] -eq 10 -or ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) -or ($bytes[0] -eq 192 -and $bytes[1] -eq 168))) { throw 'Only private device addresses are allowed' }
$config = Get-Content -LiteralPath (Join-Path $PSScriptRoot '.local/config.json') -Raw | ConvertFrom-Json
if ($config.bind -eq '127.0.0.1') { throw 'Re-run Install-Server.ps1 with -BindAddress set to the Workbench LAN IP first' }
New-NetFirewallRule -DisplayName 'Dross Translation Gateway - trusted Steam Deck' -Direction Inbound -Action Allow -Protocol TCP -LocalPort $config.port -LocalAddress $config.bind -RemoteAddress $TrustedDevice -Profile Private -Program (Join-Path (Split-Path $PSScriptRoot -Parent) '.venv\Scripts\python.exe')
