# 단일 블록 채굴

## 현재 범위

현재 바라보는 도달 가능한 블록 하나를 현재 손의 도구로 채굴한다.
mine 자체는 자동 이동·시선 회전·도구 선택·수집을 하지 않는다. 접근과 수집은 별도 [approach/collect](NAVIGATION.md) 동작으로 추가되었다.
월드를 직접 수정하지 않고 Minecraft의
[ClientPlayerInteractionManager](https://maven.fabricmc.net/docs/yarn-1.21.1+build.3/net/minecraft/client/network/ClientPlayerInteractionManager.html)
attackBlock/updateBlockBreakingProgress를 사용한다. 파괴 속도, 도구 내구도, 서버 권한은 바닐라 동작을 따른다.
[PlayerEntity](https://maven.fabricmc.net/docs/yarn-1.21.1+build.3/net/minecraft/entity/player/PlayerEntity.html)
canInteractWithBlockAt(pos,0)와 canHarvest를 사용하며 추가 도달 거리를 부여하지 않는다.

기본 Minecraft 입력은 마우스가 잠겨 있지 않으면 진행 중 채굴을 취소한다.
PowerShell로 포커스를 옮긴 상태에서도 작동하도록 AI 채굴 동안만 handleBlockBreaking/doAttack을 Mixin으로 억제한다.
실제 진행 API는 START_CLIENT_TICK에서 한 번씩 호출해 중복 진행을 방지한다.
시선 raycast와 crosshair가 모두 지정 블록을 가리켜야 하며, 다른 블록을 관통해 캐지 않는다.

## 요청과 결과

```json
{"type":"mine","x":1,"y":70,"z":2,"timeoutTicks":200}
```

좌표는 정수, x/z는 ±29,999,999 이내, y는 -64~319이다. 현재 기본 Minecraft 차원의 범위만 지원한다.
timeoutTicks는 20~200이고 권장값은 200(20 TPS에서 10초)이다.
클라이언트가 capabilities에 mine을 제공하지 않으면 브리지와 에이전트가 요청을 거절한다.
좌표는 채굴 시작 시 다시 검증하므로 오래된 관측의 다른 블록을 대신 캐지 않는다.

| 결과 | 의미 |
|---|---|
| queued / running | 대기 / 진행. running.progress에 breaking/settling과 elapsedTicks |
| completed | 원래 블록 종류가 바뀐 상태를 약 20틱 관측 |
| rejected | 시작 조건 실패, 바닐라 요청 거절 또는 블록 복원 |
| cancelled | 메뉴, 사망, 모드/월드 전환, 통신 오류, 시선/도구/위치/체력 변화 |
| timed_out | 클라이언트의 tick 또는 실제 시간 예산 초과 |
| expired | 전달/결과 확인 시간 초과 또는 heartbeat 단절; 성공으로 해석하지 않음 |

주요 reason: target_not_in_crosshair, out_of_reach, unsuitable_tool, unbreakable,
target_unloaded, tool_changed, player_moved, health_decreased, control_interrupted,
block_restored, tick_timeout, wall_timeout, block_change_observed.
위치 변경은 시작점에서 거리 0.5블록을 초과하면 중단한다.

시작 직후 또는 진행 중 블록이 바뀌면 공격을 멈추고 약 20틱 관찰한다.
원래 블록 종류가 되돌아오면 block_restored로 거절하며 자동으로 다시 공격하지 않는다.
두 번째 블록을 향해 자동 채굴을 이어가지 않는다.

결과 details:

- target, originalBlock, observedBlock, blockChanged
- inventoryDelta: 아이템 ID별 순증감. 예: {"minecraft:oak_log":1}
- inventoryObserved: 같은 플레이어/월드에서 수집한 비교인지 표시
- elapsedTicks, verification=client_observation, collectionGuaranteed=false

completed는 아이템 획득 성공을 의미하지 않는다.
inventoryDelta가 비어 있어도 블록 파괴가 관측될 수 있고, 획득 지연·거리·드롭 조건 때문에 아이템이 없을 수 있다.
순증감은 같은 시간에 일어난 다른 아이템 획득도 포함할 수 있어 채굴 대상의 드롭 출처를 증명하지 않는다.
블록 변화 역시 클라이언트 관측이며, 약 20틱 대기만으로 명시적인 서버 확인이나 제3자와의 인과관계를 증명하지 않는다.

브리지의 큐 대기는 5초, mine 전달 후 제한은 timeoutTicks×50ms+4초다.
heartbeat가 5초 이상 끊어지면 결과 조회 시 expired로 처리된다.
클라이언트의 실제 시간 상한은 timeoutTicks×50ms+2.5초다.
서버/클라이언트 지연으로 틱이 느려져도 무기한 채굴하지 않는다.
stop은 기존 단일 큐 정책상 진행 중 작업을 선점하지 않으므로, 수동 중단은 게임 메뉴를 연다.

## 직접 시험

[공통 준비](README.md) 후 도달 가능한 흙/원목을 조준한다.

```powershell
.\docker\invoke-agent.ps1 -Operation mine
.\docker\invoke-agent.ps1 -Operation mine -TimeoutTicks 20
```

명령은 현재 target을 읽어 POST /v1/act의 action 객체로 보낸다. 모델 호출 없이 실제 채굴한다.
한 블록만 사라지는지, 뒤 블록은 유지되는지, inventoryDelta가 실제 변화와 맞는지 확인한다.
메뉴·시선 변경으로 cancelled, 맨손 돌 채굴은 unsuitable_tool,
느린 원목에 20틱 예산은 timed_out과 입력 해제를 확인한다. 원격 중단은 [cancel](CANCELLATION.md)을 사용한다.

step의 모델 Plan도 mine을 허용하지만 한 번의 계획·행동만 실행한다. DRY_RUN=false이면 모델 과금 가능성이 있다.
현재 검증은 [진행 상태](PROGRESS.md)를 따른다. 기존 직접 채굴 성공 기록은 유료 모델 채굴의 증거와 구분한다.
