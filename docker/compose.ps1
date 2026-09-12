# Pass Docker flags in -ComposeArguments @('run', '--rm', ...) so PowerShell
# does not interpret flags such as -p as its own common parameters.
param(
    [string]$EnvFile = (Join-Path $PSScriptRoot '.env'),
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ComposeArguments = @('ps')
)
$ErrorActionPreference = 'Stop'
if (!(Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw 'Environment file missing. Run setup.ps1 or pass the existing file with -EnvFile.'
}
$resolvedEnvFile = (Resolve-Path -LiteralPath $EnvFile).Path
& docker compose --project-directory $PSScriptRoot --env-file $resolvedEnvFile -f (Join-Path $PSScriptRoot 'compose.yaml') @ComposeArguments
if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed with exit code $LASTEXITCODE" }
