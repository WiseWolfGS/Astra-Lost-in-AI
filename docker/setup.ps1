param(
    [string]$MinecraftConfigDirectory = (Join-Path (Split-Path -Parent $PSScriptRoot) 'run\config'),
    [string]$EnvFile = (Join-Path $PSScriptRoot '.env')
)
$ErrorActionPreference = 'Stop'
if (!(Test-Path -LiteralPath $envFile)) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent ([IO.Path]::GetFullPath($EnvFile))) | Out-Null
    $tokenBytes = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Fill($tokenBytes)
    $token = [Convert]::ToHexString($tokenBytes).ToLowerInvariant()
    $template = Get-Content -LiteralPath (Join-Path $PSScriptRoot '.env.example') -Raw
    $template.Replace('replace-with-a-random-token-of-at-least-32-characters', $token) |
        Set-Content -LiteralPath $envFile -Encoding utf8
}
$tokenLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^BRIDGE_TOKEN=' } | Select-Object -First 1
if (!$tokenLine) { throw 'BRIDGE_TOKEN missing from .env' }
$bridgeToken = $tokenLine.Substring('BRIDGE_TOKEN='.Length)
if ($bridgeToken.Length -lt 32) { throw 'BRIDGE_TOKEN must have at least 32 characters' }
New-Item -ItemType Directory -Force -Path $MinecraftConfigDirectory | Out-Null
$configPath = Join-Path $MinecraftConfigDirectory 'astralostinai-bridge.json'
if (!(Test-Path -LiteralPath $configPath)) {
    @{enabled=$true;url='http://127.0.0.1:8765';token=$bridgeToken} |
        ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding utf8NoBOM
    Write-Host "Created bridge config: $configPath"
} else {
    Write-Host "Existing config preserved: $configPath (enable and match token manually if needed)"
}
Write-Host 'Environment ready. Run compose.ps1 with the same -EnvFile to start services.'
