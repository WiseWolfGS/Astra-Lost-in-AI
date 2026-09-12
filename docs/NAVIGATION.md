# 짧은 평지 접근과 아이템 수집

## 구현 범위

approach는 가까운 블록을 향해 걷고 마지막에 시선을 맞춘다. collect는 지정된 떨어진 아이템 쪽으로 걷고 획득을 검증한다.
위치 텔레포트, 비행, 점프, 블록 설치/파괴를 사용하지 않는다. 로컬 클라이언트가 실제 충돌 형상을 검사한다.

- 대상까지 초기 수평 거리 최대 4블록. 검색 범위는 시작 발 블록 기준 x/z 각각 ±4, 최대 81칸이다.
- 같은 정수 높이의 평지만 지원한다. 계단·낙하·높이가 다른 아이템·반 블록 등은 보수적으로 거절할 수 있다.
- 네 방향 BFS로 최대 12개 이동 구간을 찾는다. 대각선으로 모서리를 통과하지 않는다.
- 실제 몸체의 이동 영역으로 충돌·유체·알려진 위험 블록을 검사한다. 벽 접촉의 부동소수 오차만 보정한다.
- 경유점 전방에서 지면 마찰과 잔여 속도를 기준으로 전진을 해제하고, 충분히 감속한 뒤 다음 경유점으로 전환한다.
- 해당 영역의 바닥이 로드되어 있고 윗면 전체를 지지하는지 확인한다. 미로드·구멍은 이동 가능한 공기로 취급하지 않는다.
- 매 틱 다음 구간을 다시 검사한다. 장애물 출현, 높이 변화, 체력 감소, 정체, 메뉴·월드 변경, 통신 오류, 시간 초과 시 중단한다.
- 지형이 계속 변하거나 알려지지 않은 위험을 포함하는 환경까지 안전을 보장하는 경로 탐색기는 아니다.

[Yarn CollisionView](https://maven.fabricmc.net/docs/yarn-1.21.1+build.3/net/minecraft/world/CollisionView.html)의
isSpaceEmpty와 블록의 실제 collision shape 및 윗면 지지 검사를 사용한다.
모델용 관측 요약의 collision boolean만으로 경로를 결정하지 않는다.

## 명령 규약

```json
{"type":"approach","x":1,"y":70,"z":2,"timeoutTicks":200}
{"type":"collect","entityId":123,"timeoutTicks":200}
```

시간은 20~200틱, 기본 200이다. 좌표 범위는 mine과 같고 entityId는 0~2147483647 정수다.
approach/collect 각각의 capability가 없으면 서버와 에이전트가 실행을 거절한다.
전달 및 실행 예산은 mine과 같은 정책이다. 현재 step은 모델 요청 한 번과 행동 하나만 실행한다.

approach는 대상 중심까지 수평 2블록 이내이며 시선이 통하는 정지 위치를 찾는다.
도착 후 약 6틱 동안 입력을 해제하고 대상 도달 거리와 가림을 다시 확인한다.
completed/approach_verified는 접근 완료이며 채굴 성공을 의미하지 않는다.

collect는 관측에 있는 item entity ID를 지정한다. 해당 아이템은 보이고, 땅에 놓여 있고, 같은 높이에 있어야 한다.
경로를 만드는 동안에는 아이템 위치를 고정해 사용하며, 이후 수평 0.35블록 넘게 이동하면 재추적 대신 중단한다.
가까운 아이템이라도 다른 높이에 있거나 바닥 지지가 부족하면 거절한다.

## 수집 성공의 근거

[ItemPickupAnimationS2CPacket](https://maven.fabricmc.net/docs/yarn-1.21.1+build.3/net/minecraft/network/packet/s2c/play/ItemPickupAnimationS2CPacket.html)을
클라이언트 스레드에서 처리한 뒤 대상 entityId, 수집한 플레이어 ID, 개수를 기록한다.
완료하려면 다음 두 조건이 모두 필요하다.

1. 지정 아이템을 현재 플레이어가 수집했다는 서버 이벤트의 개수 > 0.
2. 행동 시작 전보다 해당 아이템 ID의 인벤토리 개수가 증가.

verifiedCollectedCount는 두 개수 중 작은 값이다. 다른 아이템 엔티티나 다른 수집자의 이벤트는 무시한다.
대상 소멸만으로 성공하지 않으며, 이벤트만 먼저 도착하면 인벤토리 동기화를 제한 시간 안에서 기다린다.
부분 수집이라도 1개 이상 검증되면 완료한다. 이벤트와 인벤토리 증거는 제공하지만,
원래 어떤 블록에서 떨어졌는지까지 추적하거나 동시의 모든 인벤토리 변동을 분리하는 시스템은 아니다.

관측의 item entity에는 item(레지스트리 ID), count, onGround가 추가된다.
결과 details에는 path, position, elapsedTicks와 아래 수집 증거가 포함된다.

- item / targetEntityId
- pickupPacketCount
- inventoryDelta: 선택한 아이템 ID의 순증감 정수
- verifiedCollectedCount / inventoryObserved

mine의 inventoryDelta는 ID→개수 맵이고, collect는 선택한 아이템 하나에 대한 정수라는 차이에 유의한다.

## 사용자 테스트

새 모드를 사용하려면 기존 게임에서 월드를 저장하고 정상 종료한 뒤 실행한다.
이미 새 클라이언트가 기동되어 있다면 해당 클라이언트로 테스트 월드에 들어간다.

```powershell
cd C:\Projects\AstraLostInAI
.\scripts\dev.ps1 -Task runClient
```

서바이벌 월드에서 F3+P로 포커스 상실 시 일시정지를 해제하고 메뉴를 닫는다.
별도 PowerShell에서:

```powershell
cd C:\Projects\AstraLostInAI\docker
.\invoke-agent.ps1 -Operation observe
.\invoke-agent.ps1 -Operation perception
```

connected=true, ready=true이고 capabilities에 approach/collect가 있어야 한다.
이하 직접 명령은 OpenAI 호출이 없으며, DRY_RUN=true여도 실제 게임 행동을 실행한다.

### 1. 평지에서 블록 접근

같은 높이의 넓고 평평한 땅에 서서 수평 3~4블록 거리의 원목 블록을 바라본다.
나무 위·반 블록·물가 대신 처음에는 주변 바닥이 연속된 흙/잔디 평지에서 시험한다.

```powershell
.\invoke-agent.ps1 -Operation approach
```

성공 기준: result.status=completed, reason=approach_verified, 좌표 변화가 있고 대상 쪽으로 시선이 정렬된다.
이미 가까웠다면 이동 거리가 작을 수 있다. 끝난 후 앞으로 계속 걷지 않아야 한다.

### 2. 원목 채굴 후 드롭 획득

```powershell
.\invoke-agent.ps1 -Operation mine
.\invoke-agent.ps1 -Operation perception
.\invoke-agent.ps1 -Operation collect -Item minecraft:oak_log
```

실제로 떨어진 원목이 남아 있고 땅에 내려앉은 뒤 collect를 실행한다.
채굴하면서 이미 원목을 획득했다면 수집 대상이 없는 것이 정상이다. 이 경우 인벤토리 원목 하나를
Q로 던지고 1~2블록 물러나 아이템이 내려앉은 뒤 시험한다. 자동으로 먼저 주워지지 않았는지 확인한다.

성공 기준: result.status=completed, reason=pickup_verified,
pickupPacketCount>=1, inventoryDelta>=1, verifiedCollectedCount>=1이며 실제 인벤토리도 증가한다.
아이템이 사라졌지만 이 조건이 없으면 성공으로 판정하지 않는다.

여러 드롭 중 직접 선택하려면 perception에서 ID를 읽어:

```powershell
.\invoke-agent.ps1 -Operation collect -EntityId 123
```

123은 예시이므로 실제 ID로 바꾼다. -Item을 생략하면 관측된 땅 위 아이템 중 가까운 대상을 선택한다.

### 3. 중단·경로 제한 시험

- 접근 중 Esc 메뉴를 열면 cancelled와 입력 해제가 되어야 한다.
- 같은 높이에서 장애물을 사이에 둔 대상: 우회 가능한 평지 경로가 있으면 우회하고, 없으면 no_flat_path/path_blocked로 끝나야 한다.
- 계단이나 물을 반드시 지나야 하는 대상: 강행하지 않고 거절/중단해야 한다.
- 긴 경로에 -TimeoutTicks 20을 주면 제한 시간 안에 완료하지 못한 경우 timed_out이 나와야 한다.

```powershell
.\invoke-agent.ps1 -Operation approach -TimeoutTicks 20
docker compose exec -T agent tail -n 1 /data/episodes.jsonl
```

### 4. 선택적 Astra 시험 — 유료 설정이면 과금

직접 시험을 통과한 뒤 드롭이 존재하는 상태에서 한 번:

```powershell
.\invoke-agent.ps1 -Operation step -Goal '관측에 있는 가까운 땅 위 참나무 원목 아이템 하나를 collect로 획득해라. timeoutTicks는 200으로 설정해라.'
```

plan.action이 collect이고 동일한 수집 증거를 반환하는지 확인한다.
대상이 없다면 다시 드롭을 준비한다. 아직 여러 행동을 자동 연결하는 반복 루프는 없다.

## 결과 해석과 다음 단계

| reason | 의미 / 대응 |
|---|---|
| requires_flat_ground / left_flat_ground | 정수 높이의 평지에서 다시 시험 |
| unsafe_start / no_flat_path | 몸 주변 지지·충돌·유체·위험 또는 경로 제한 확인 |
| target_outside_local_range | 수평 4블록 안으로 수동 접근 |
| item_not_settled_or_visible / item_on_other_level | 같은 평지에 내려앉고 보이는 아이템 선택 |
| item_moved | 굴러가는 아이템이 멈춘 뒤 다시 관측 |
| item_disappeared_without_pickup | 사라짐만 확인, 획득 성공 아님 |
| path_blocked / path_became_unsafe | 실행 중 경로 조건이 바뀌어 중단 |
| stuck / navigation_timeout | 정체 또는 실행 예산 초과 |
| pickup_verified | 대상 이벤트와 인벤토리 증가를 함께 확인 |

최신 검증: Fabric 빌드, Java 20개/Python 56개 테스트 통과.
Node 10개는 직전 변경에서 통과했으며 이후 Node 코드 변경은 없다.
[원목 획득 실행 루프](WOOD_GOAL.md)도 구현했으며 개별 행동 실패 시 중단한다.

후속 오류 수정과 실게임 재검증: [원인·수정·검증 보고서](NAVIGATION_FIX.md).
과도한 0.15블록 충돌 여유 폭과 경유점 감속 누락을 수정했다.
이전에 실패하던 저장 위치에서 collect의 pickup_verified 및 원목 +1을 직접 확인했고,
별도 wood 실행의 approach→mine→collect 연결과 최종 원목 +1도 확인했다.
새 실패 결과 details.safetyFailure에는 검사 이유·블록·좌표가 포함된다.
