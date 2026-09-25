# 작업대 설치 및 상호작용

작업대 설치(`place_workbench`)는 메인 핸드에 든 작업대를 시선이 닿는 바닥 블록 윗면에 단일 배치하는 직접 행동이다.
이 문서는 설치 행동을 설명한다. [3×3 나무 도구 제작](WORKBENCH_CRAFTING.md)은 별도 직접 행동으로 구현했다. 모델을 호출하지 않는다.

## 동작과 제한

POST /v1/act 본문:

```json
{"action":{"type":"place_workbench","x":0,"y":64,"z":0,"expectedSupport":"minecraft:dirt"}}
```

인증과 실행 잠금·취소 규약은 기존 직접 행동과 같다. `place_workbench` capability가 없는 클라이언트는 거절한다.

1. **사전 조건**:
   - 플레이어의 메인 핸드에 `minecraft:crafting_table`이 장착되어 있어야 한다 (`workbench_not_in_hand`).
   - 인벤토리 커서가 비어 있고 다른 컨테이너를 열고 있지 않아야 한다 (`inventory_busy`).
   - 대상 바닥 블록(`expectedSupport`)의 윗면(Direction.UP)을 직접 조준(crosshair 및 raycast)하고 있어야 한다 (`aim_at_support_top`).
   - 허용 바닥: `minecraft:dirt`, `minecraft:grass_block`, `minecraft:stone`, `minecraft:cobblestone`의 견고한 윗면 (`unsupported_ground`).
   - 설치 위치(바닥 블록의 바로 위 `y + 1`)는 공기 블록이어야 하며 개체나 플레이어의 히트박스와 겹치지 않아야 한다 (`destination_occupied`, `destination_entity_collision`).
   - 블록 상호작용 거리 내에 도달할 수 있어야 한다 (`out_of_reach`).

2. **실행 및 검증**:
   - 우클릭 상호작용(`interactBlock`) 패킷을 1회 전송한다.
   - 최소 5틱 관측 대기 후 인벤토리에서 작업대 1개가 감소하고 목표 위치에 작업대 블록이 관측되는지 확인한다.
   - 이 대기는 서버 확정 응답을 대신하지 않는다. `serverConfirmed=false`로 클라이언트 관측임을 명시한다.
   - 타임아웃은 100틱/벽시계 7초(브리지 실행 기한 14초)다.
   - 성공 결과는 `completed/workbench_placed`이며 `details.verification=client_observation`, `inventoryConsumed=1`, `blockObserved=true`를 기록한다.

후속 제작은 [3×3 도구 제작](WORKBENCH_CRAFTING.md)을 사용한다.

## 사용자 테스트

[공통 준비](README.md) 후 아래 조건으로 실행한다.

1. 참나무 원목을 채집하고 2×2 제작을 통해 작업대를 확보한다:
```powershell
.\docker\invoke-agent.ps1 -Operation craft -Recipe oak_planks
.\docker\invoke-agent.ps1 -Operation craft -Recipe crafting_table
```

2. 제작 결과는 일반 인벤토리에 들어갈 수도 있으므로 필요하면 작업대를 직접 핫바로 옮긴다.
   작업대가 위치한 슬롯을 선택한다. 아래 0은 첫 번째 슬롯의 예시다:
```powershell
.\docker\invoke-agent.ps1 -Operation select-hotbar -Slot 0
```

3. 도달 가능한 평지 바닥 블록(흙/잔디/돌)의 윗면을 조준하고 설치를 실행한다:
```powershell
.\docker\invoke-agent.ps1 -Operation place-workbench
```

결과에서 `status=completed`, `reason=workbench_placed`, `inventoryConsumed=1`, `blockObserved=true`를 확인한다.

| 실패 이유 | 확인할 항목 |
|---|---|
| `workbench_not_in_hand` | 핫바 선택 및 손에 든 아이템이 작업대인지 확인 |
| `aim_at_support_top` | 바닥 블록의 윗면(UP)을 정확히 조준하고 있는지 확인 |
| `unsupported_ground` | 흙/잔디/돌 등 단단한 바닥 블록인지 확인 |
| `destination_occupied` | 설치될 상단 위치에 다른 블록이나 물/용암이 없는지 확인 |
| `destination_entity_collision` | 플레이어 자신이나 몹의 위치가 설치 위치와 겹치지 않는지 확인 |
| `out_of_reach` | 도달 가능 거리(약 4.5블록 이내)인지 확인 |

취소는 이미 보낸 설치 요청을 되돌리지 않는다. `pendingChangesPossible=true`이면 월드와 인벤토리를
확인한 뒤 다시 요청한다. 설치 위치는 완전한 공기를 요구하므로 짧은 풀도 먼저 제거해야 한다.

## 검증 상태

현재 자동·실게임 확인과 남은 작업은 [진행 상태](PROGRESS.md)에서 관리한다.
