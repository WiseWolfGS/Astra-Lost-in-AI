param(
    [ValidateSet('observe', 'perception', 'mine', 'approach', 'collect', 'wood', 'step', 'health', 'execution', 'cancel', 'skills', 'skill-check', 'skill-run', 'select-hotbar', 'craft', 'place-workbench', 'craft-workbench', 'move-hotbar')][string]$Operation = 'observe',
    [string]$Goal = '주변을 관찰하고 안전한 다음 행동을 정한다.',
    [ValidateRange(20,200)][int]$TimeoutTicks = 200,
    [ValidateRange(-1,2147483647)][int]$EntityId = -1,
    [string]$Item = '',
    [ValidateRange(1,3)][int]$MaxActions = 3,
    [switch]$FullRecord,
    [string]$EnvFile = (Join-Path $PSScriptRoot '.env'),
    [Guid]$ExecutionId = [Guid]::Empty,
    [Guid]$ActionId = [Guid]::Empty,
    [ValidatePattern('^[a-z][a-z0-9_-]*$')][string]$SkillId = 'wood',
    [string]$SkillVersion = '1.1.0',
    [ValidateRange(0,8)][int]$Slot = 0,
    [ValidateRange(9,35)][int]$SourceSlot = 9,
    [ValidateSet('oak_planks','spruce_planks','birch_planks','jungle_planks','acacia_planks','dark_oak_planks','mangrove_planks','cherry_planks','stick','crafting_table','wooden_pickaxe','wooden_axe','wooden_sword','wooden_shovel','wooden_hoe')][string]$Recipe = 'oak_planks'
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
if ($Operation -eq 'move-hotbar') {
    $snapshot = Invoke-RestMethod 'http://127.0.0.1:8000/v1/observation' -Headers $headers -TimeoutSec 10
    if (!$snapshot.connected -or !$snapshot.observation.ready) { throw 'Enter an unpaused survival world and close screens first.' }
    if ($snapshot.observation.capabilities -notcontains 'move_hotbar') { throw 'Restart Minecraft with support for move_hotbar.' }
    $stacks = @($snapshot.observation.player.inventory)
    $sources = @($stacks | Where-Object { $_.slot -ge 9 -and $_.slot -le 35 -and $(if ($Item) { $_.item -eq $Item } else { $_.slot -eq $SourceSlot }) } | Sort-Object slot)
    if (!$sources.Count) { throw 'No matching item in inventory slots 9 through 35. Check observe; the item may already be in the hotbar.' }
    $source = $sources[0]
    $targets = @($stacks | Where-Object slot -eq $Slot)
    $targetItem = if ($targets.Count) { $targets[0].item } else { 'minecraft:air' }
    $targetCount = if ($targets.Count) { [int]$targets[0].count } else { 0 }
    $body = @{action=@{type='move_hotbar';sourceSlot=[int]$source.slot;hotbarSlot=$Slot;
        expectedSource=$source.item;expectedTarget=$targetItem;sourceCount=[int]$source.count;targetCount=$targetCount}} | ConvertTo-Json -Depth 5
    Invoke-RestMethod 'http://127.0.0.1:8000/v1/act' -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 35 | ConvertTo-Json -Depth 25
} elseif ($Operation -eq 'craft-workbench') {
    if ($Recipe -notlike 'wooden_*') { throw 'Choose a wooden tool recipe, for example -Recipe wooden_pickaxe.' }
    $snapshot = Invoke-RestMethod 'http://127.0.0.1:8000/v1/observation' -Headers $headers -TimeoutSec 10
    if (!$snapshot.connected -or !$snapshot.observation.ready) { throw 'Enter an unpaused survival world and close screens first.' }
    if ($snapshot.observation.capabilities -notcontains 'craft_workbench') { throw 'Restart Minecraft with support for craft_workbench.' }
    $target = $snapshot.observation.environment.target
    if ($target.type -ne 'block' -or $target.block.id -ne 'minecraft:crafting_table') { throw 'Aim at a nearby placed crafting table.' }
    $body = @{action=@{type='craft_workbench';recipe=$Recipe;x=[int]$target.position[0];
        y=[int]$target.position[1];z=[int]$target.position[2]}} | ConvertTo-Json -Depth 5
    Invoke-RestMethod 'http://127.0.0.1:8000/v1/act' -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 40 | ConvertTo-Json -Depth 25
} elseif ($Operation -eq 'place-workbench') {
    $snapshot = Invoke-RestMethod 'http://127.0.0.1:8000/v1/observation' -Headers $headers -TimeoutSec 10
    if (!$snapshot.connected -or !$snapshot.observation.ready) { throw 'Enter an unpaused survival world first.' }
    if ($snapshot.observation.capabilities -notcontains 'place_workbench') { throw 'Restart Minecraft with support for place_workbench.' }
    $target = $snapshot.observation.environment.target
    if ($target.type -ne 'block' -or $target.face -ne 'up') { throw 'Aim at the top face of nearby ground.' }
    if ($snapshot.observation.player.mainHand.item -ne 'minecraft:crafting_table') { throw 'Select a hotbar slot holding a crafting table first.' }
    $body = @{action=@{type='place_workbench';x=[int]$target.position[0];y=[int]$target.position[1];
        z=[int]$target.position[2];expectedSupport=$target.block.id}} | ConvertTo-Json -Depth 5
    Invoke-RestMethod 'http://127.0.0.1:8000/v1/act' -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 35 | ConvertTo-Json -Depth 25
} elseif ($Operation -eq 'craft') {
    $body = @{action=@{type='craft';recipe=$Recipe}} | ConvertTo-Json -Depth 5
    Invoke-RestMethod 'http://127.0.0.1:8000/v1/act' -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 35 | ConvertTo-Json -Depth 25
} elseif ($Operation -eq 'select-hotbar') {
    $snapshot = Invoke-RestMethod 'http://127.0.0.1:8000/v1/observation' -Headers $headers -TimeoutSec 10
    if (!$snapshot.connected -or !$snapshot.observation.ready) { throw 'Enter an unpaused survival world first.' }
    if ($snapshot.observation.capabilities -notcontains 'select_hotbar') { throw 'Restart Minecraft with support for select_hotbar.' }
    $stack = @($snapshot.observation.player.inventory | Where-Object slot -eq $Slot)
    $expected = if ($stack.Count) { $stack[0].item } else { 'minecraft:air' }
    $body = @{action=@{type='select_hotbar';slot=$Slot;expectedItem=$expected}} | ConvertTo-Json -Depth 5
    Invoke-RestMethod 'http://127.0.0.1:8000/v1/act' -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 30 | ConvertTo-Json -Depth 25
} elseif ($Operation -in @('skills','skill-check','skill-run')) {
    $url = 'http://127.0.0.1:8000/v1/skills'
    if ($Operation -eq 'skill-check') { $url += "/$SkillId/check" }
    if ($Operation -eq 'skill-run') {
        $body = @{version=$SkillVersion; inputs=@{max_actions=$MaxActions}} | ConvertTo-Json -Depth 5
        Invoke-RestMethod "$url/$SkillId/run" -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 90 | ConvertTo-Json -Depth 30
    } else {
        Invoke-RestMethod $url -Headers $headers -TimeoutSec 10 | ConvertTo-Json -Depth 20
    }
} elseif ($Operation -in @('execution','cancel')) {
    if ($ExecutionId -ne [Guid]::Empty -and $ActionId -ne [Guid]::Empty) { throw 'Choose ExecutionId or ActionId, not both.' }
    if ($ActionId -ne [Guid]::Empty) {
        $url = "http://127.0.0.1:8000/v1/actions/$ActionId"
        if ($Operation -eq 'cancel') {
            Invoke-RestMethod ($url+'/cancel') -Method Post -Headers $headers -ContentType 'application/json' -Body '{}' -TimeoutSec 15 | ConvertTo-Json -Depth 20
        } else {
            Invoke-RestMethod $url -Headers $headers | ConvertTo-Json -Depth 20
        }
    } else {
        if ($ExecutionId -eq [Guid]::Empty) {
            $active = (Invoke-RestMethod 'http://127.0.0.1:8000/v1/execution' -Headers $headers).execution
            if (!$active) { @{status='idle';message='No active execution.'} | ConvertTo-Json; return }
            $ExecutionId = [Guid]$active.id
        }
        $url = "http://127.0.0.1:8000/v1/executions/$ExecutionId"
        if ($Operation -eq 'cancel') {
            $outcome = Invoke-RestMethod ($url+'/cancel') -Method Post -Headers $headers -ContentType 'application/json' -Body '{}' -TimeoutSec 15
            for ($i=0; $i -lt 16 -and !$outcome.finished; $i++) {
                Start-Sleep -Milliseconds 250
                $outcome = Invoke-RestMethod $url -Headers $headers -TimeoutSec 5
            }
        } else { $outcome = Invoke-RestMethod $url -Headers $headers }
        $outcome | ConvertTo-Json -Depth 20
    }
} elseif ($Operation -eq 'observe' -or $Operation -eq 'perception') {
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
            executionId=$record.executionId; cancellation=$record.cancellation
            skill=$record.skill; observationSchemaVersion=$record.observationSchemaVersion
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
