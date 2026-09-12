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

## 직접 시험 — 모델 호출 없음

새 클라이언트 실행 후 테스트 서바이벌 월드에 들어간다.
F3+P로 포커스 상실 시 일시정지를 해제하고 메뉴를 닫는다.
접근 가능한 흙이나 원목 하나를 바라보고 PowerShell에서:

```powershell
cd C:\Docker\astralostinai
.\invoke-agent.ps1 -Operation perception
.\invoke-agent.ps1 -Operation mine
```

mine 명령은 현재 target 좌표를 읽어 POST /v1/act에 전달한다.
이 직접 실행은 **DRY_RUN=true여도 게임 행동을 실행**한다. OpenAI 호출은 없고 에피소드는 model_called=false로 기록된다.
수동 API의 본문은 {"action": 위의 mine 객체}다. 모든 요청에 bearer 인증이 필요하다.

수락 시험:

1. 원목/흙 한 블록이 사라지고 completed가 반환되는지 확인한다.
2. 뒤쪽 블록은 그대로 남는지 확인한다.
3. 인벤토리 변화가 있으면 inventoryDelta와 실제 아이템을 비교한다. 변화가 없다고 파괴 실패로 판단하지 않는다.
4. 느린 블록 채굴 중 메뉴를 열거나 시선을 돌렸을 때 cancelled가 되는지 확인한다.
5. 맨손으로 돌을 바라보고 실행했을 때 unsuitable_tool로 거절되는지 확인한다.
6. 맨손 원목을 바라보고 아래 명령으로 짧은 예산을 줬을 때 timed_out과 입력 해제를 확인한다.

```powershell
.\invoke-agent.ps1 -Operation mine -TimeoutTicks 20
docker compose exec -T agent tail -n 1 /data/episodes.jsonl
```

## Astra가 채굴을 선택하도록 시험

직접 채굴이 검증된 뒤 같은 조건에서:

```powershell
.\invoke-agent.ps1 -Operation step -Goal '현재 바라보는 원목 블록 하나만 mine으로 채굴해라. 이동하지 말고 timeoutTicks는 200으로 지정해라.'
```

현재 DRY_RUN=false이면 모델 호출에 과금될 수 있다. Plan에 mine이 추가되었고 실제 실행기는 직접 시험과 동일하다.
관측의 target에 canHarvest, hardness, inReach가 포함되며, 모델은 현재 target과 동일한 좌표만 고르도록 안내받는다.
에피소드는 계획, 실행 결과, 전후 관측을 저장한다. 자동 반복이나 재시도는 없다.

## 검증 상태

2026-09-12: Fabric 빌드와 Java 6개/Python 23개/Node 8개, 총 37개 자동 테스트 통과.
실제 클라이언트 기동과 mine capability 전송을 확인한 뒤 사용자가 채굴 실행 성공을 보고했다.
에피소드에서도 direct mine의 원목→공기와 completed를 확인했다. 해당 에피소드의 inventoryDelta는 빈 맵이었다.
유료 mine 호출의 별도 에피소드는 이번 확인 자료에 없으므로 direct 채굴 증거와 구분한다.
짧은 접근과 수집 코드를 후속 구현했으며 사용자 시험은 [접근·수집 문서](NAVIGATION.md)를 참고한다.
