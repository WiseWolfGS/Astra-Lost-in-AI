param([ValidateSet('build','runClient')][string]$Task = 'build')
$ErrorActionPreference = 'Stop'
if (!$env:JAVA_HOME) {
    $candidate = Join-Path $env:USERPROFILE '.jdks\ms-21.0.12.1'
    if (Test-Path -LiteralPath "$candidate\bin\java.exe") { $env:JAVA_HOME = $candidate }
    else { throw 'Set JAVA_HOME to your JDK 21 directory.' }
}
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    & .\gradlew.bat $Task
    if ($LASTEXITCODE -ne 0) { throw "Gradle failed with exit code $LASTEXITCODE" }
} finally { Pop-Location }
