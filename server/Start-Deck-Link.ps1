# Optional SSH transport for networks where opening a gateway firewall port is unsuitable.
# The private deck-link.json contains deck_address, identity_file and known_hosts_file.
$ErrorActionPreference = 'Stop'
$localDir = Join-Path $PSScriptRoot '.local'
$link = Get-Content -LiteralPath (Join-Path $localDir 'deck-link.json') -Raw | ConvertFrom-Json
$address = [System.Net.IPAddress]::Parse($link.deck_address)
$octets = $address.GetAddressBytes()
if ($address.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork -or -not (
    $octets[0] -eq 10 -or ($octets[0] -eq 172 -and $octets[1] -ge 16 -and $octets[1] -le 31) -or
    ($octets[0] -eq 192 -and $octets[1] -eq 168))) { throw 'The Deck must have a private LAN IPv4 address.' }
$identityPath = (Resolve-Path -LiteralPath $link.identity_file).Path
$knownHostsPath = (Resolve-Path -LiteralPath $link.known_hosts_file).Path
try {
    $lock = [System.IO.File]::Open((Join-Path $localDir 'deck-link.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
} catch [System.IO.IOException] { Write-Output 'A Deck link is already running.'; exit 0 }
try {
    $PID | Set-Content -LiteralPath (Join-Path $localDir 'deck-link.pid')
    $sshArgs = @('-N', '-T', '-i', $identityPath, '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
        '-o', 'StrictHostKeyChecking=yes', '-o', "UserKnownHostsFile=$knownHostsPath",
        '-o', 'ConnectTimeout=8', '-o', 'ExitOnForwardFailure=yes', '-o', 'ServerAliveInterval=15',
        '-o', 'ServerAliveCountMax=3', '-o', 'LogLevel=ERROR',
        '-R', '127.0.0.1:18765:127.0.0.1:18765', "deck@$address")
    while ($true) {
        # Windows PowerShell 5 treats native stderr as error records. A normal
        # disconnect must reach the retry below rather than terminate the link.
        $ErrorActionPreference = 'Continue'
        try { & ssh.exe @sshArgs 2>> (Join-Path $localDir 'deck-link.log') }
        finally { $ErrorActionPreference = 'Stop' }
        Start-Sleep -Seconds 15
    }
} finally { $lock.Dispose() }
