param(
    [ValidateSet('observe', 'perception', 'mine', 'approach', 'collect', 'wood', 'step', 'health')][string]$Operation = 'observe',
    [string]$Goal = '주변을 관찰하고 안전한 다음 행동을 정한다.',
    [ValidateRange(20,200)][int]$TimeoutTicks = 200,
    [ValidateRange(-1,2147483647)][int]$EntityId = -1,
    [string]$Item = '',
    [ValidateRange(1,3)][int]$MaxActions = 3,
    [switch]$FullRecord,
    [string]$EnvFile = (Join-Path $PSScriptRoot '.env')
)
$ErrorActionPreference = 'Stop'
if ($Operation -eq 'health') {
    Invoke-RestMethod 'http://127.0.0.1:8000/health'
    exit
}
$tokenLine = Get-Content -LiteralPath $EnvFile |
    Where-Object { $_ -match '^BRIDGE_TOKEN=' } | Select-Object -First 1
if (!$tokenLine) { throw 'Run setup.ps1 first' }
$headers = @{Authorization = 'Bearer ' + $tokenLine.Substring('BRIDGE_TOKEN='.Length)}
if ($Operation -eq 'observe' -or $Operation -eq 'perception') {
    $endpoint = if ($Operation -eq 'observe') { 'observation' } else { 'perception' }
    Invoke-RestMethod ("http://127.0.0.1:8000/v1/" + $endpoint) -Headers $headers |
        ConvertTo-Json -Depth 20
} elseif ($Operation -eq 'wood') {
    $body = @{max_actions=$MaxActions} | ConvertTo-Json
    $record = Invoke-RestMethod 'http://127.0.0.1:8000/v1/goals/wood' -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 90
    if ($FullRecord) {
        $record | ConvertTo-Json -Depth 30
    } else {
        [ordered]@{
            id=$record.id; result=$record.result; inventoryDelta=$record.inventoryDelta
            initialLogCount=$record.initialLogCount; model_called=$record.model_called
            steps=@($record.steps | ForEach-Object { [ordered]@{action=$_.action;result=$_.result} })
            stopRequest=$record.stopRequest
        } | ConvertTo-Json -Depth 20
    }
} elseif ($Operation -in @('mine','approach','collect')) {
    $snapshot = Invoke-RestMethod 'http://127.0.0.1:8000/v1/observation' -Headers $headers
    if (!$snapshot.connected -or !$snapshot.observation.ready) { throw 'Enter an unpaused survival world first.' }
    if ($snapshot.observation.capabilities -notcontains $Operation) { throw "Restart Minecraft with support for $Operation." }
    if ($Operation -eq 'collect') {
        $candidates = @($snapshot.observation.environment.entities | Where-Object {
            $_.type -eq 'minecraft:item' -and $_.onGround -and
            ($EntityId -lt 0 -or $_.id -eq $EntityId) -and (!$Item -or $_.item -eq $Item)
        } | Sort-Object distance)
        if (!$candidates.Count) { throw 'No matching visible settled item. Check perception or wait for the drop to land.' }
        $body = @{action=@{type='collect';entityId=[int]$candidates[0].id;timeoutTicks=$TimeoutTicks}} | ConvertTo-Json -Depth 5
    } else {
        $target = $snapshot.observation.environment.target
        if ($target.type -ne 'block') { throw 'Aim at a reachable block first.' }
        $body = @{action=@{type=$Operation;x=[int]$target.position[0];y=[int]$target.position[1];
            z=[int]$target.position[2];timeoutTicks=$TimeoutTicks}} | ConvertTo-Json -Depth 5
    }
    Invoke-RestMethod 'http://127.0.0.1:8000/v1/act' -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 30 |
        ConvertTo-Json -Depth 25
} else {
    $body = @{goal=$Goal} | ConvertTo-Json
    Invoke-RestMethod 'http://127.0.0.1:8000/v1/step' -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 90 |
        ConvertTo-Json -Depth 20
}
