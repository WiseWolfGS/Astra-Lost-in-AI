# PowerShell 7: local and GitHub-hosted Linux runners use the same commands.
# Never read docker/.env or attach production ports/volumes in this suite.
param()
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $repositoryRoot 'docker/compose.smoke.yaml'
$templateFile = Join-Path $repositoryRoot 'docker/.env.example'
$projectName = 'astralostinai-ci-' + [Guid]::NewGuid().ToString('N').Substring(0, 12)
$reportDirectory = Join-Path $repositoryRoot 'local/ci-results/docker'
New-Item -ItemType Directory -Force -Path $reportDirectory | Out-Null
# A previous run's report must not be mistaken for this run's output.
foreach ($name in @('python-tests.xml','node-tests.txt','smoke.txt','compose-ps.txt','compose.log')) {
    $reportPath = Join-Path $reportDirectory $name
    if (Test-Path -LiteralPath $reportPath) { Remove-Item -LiteralPath $reportPath }
}
$composeBase = @('compose', '--project-name', $projectName, '--env-file', $templateFile, '-f', $composeFile)
function Invoke-TestCompose {
    param([string[]]$CommandArguments)
    & docker @composeBase @CommandArguments
    if ($LASTEXITCODE -ne 0) { throw "Isolated Compose command failed: $($CommandArguments[0]) (exit $LASTEXITCODE)" }
}
$failure = $null
try {
    Invoke-TestCompose @('up','-d','--build','--wait','--wait-timeout','90')
    # Keep reports on the container filesystem: docker cp cannot reliably read
    # the memory-backed /data mount used for synthetic episodes on all engines.
    Invoke-TestCompose @('exec','-T','agent','python','-m','pytest','-q','-p','no:cacheprovider','--junit-xml=/tmp/python-tests.xml')
    Invoke-TestCompose @('exec','-T','bridge','npm','test') |
        Tee-Object -FilePath (Join-Path $reportDirectory 'node-tests.txt')
    Invoke-TestCompose @('exec','-T','agent','python','smoke.py') |
        Tee-Object -FilePath (Join-Path $reportDirectory 'smoke.txt')
} catch {
    $failure = $_
} finally {
    # These are synthetic services only. Do not log production Compose config.
    & docker @composeBase ps --all 2>&1 | Set-Content -LiteralPath (Join-Path $reportDirectory 'compose-ps.txt')
    & docker @composeBase logs --no-color 2>&1 | Set-Content -LiteralPath (Join-Path $reportDirectory 'compose.log')
    & docker @composeBase cp agent:/tmp/python-tests.xml (Join-Path $reportDirectory 'python-tests.xml')
    $copyExitCode = $LASTEXITCODE
    & docker @composeBase down --remove-orphans --rmi local
    $cleanupExitCode = $LASTEXITCODE
    if (!$failure -and ($copyExitCode -ne 0 -or $cleanupExitCode -ne 0)) {
        $failure = 'Could not preserve the test report or remove the isolated test services.'
    }
}
if ($failure) { throw $failure }
Write-Host 'PASS: Python, Node and isolated transport tests; no paid model or production world used.'
