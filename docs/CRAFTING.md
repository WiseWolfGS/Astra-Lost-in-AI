# 2×2 제작

직접 craft 행동은 개인 제작 칸에서 레시피 1회분을 요청한다. 모델을 호출하지 않는다.
지원: oak/spruce/birch/jungle/acacia/dark_oak/mangrove/cherry_planks, stick, crafting_table.
판자는 해당 기본 원목을 사용한다. 껍질 벗긴 원목·목재·네더 판자는 이 초기 규약의 지원 대상이 아니다.
혼합 재료는 서버 레시피 채우기 동작에 따르므로 재료 합계가 충분해도 제작 불가능할 수 있다.

## 동작과 제한

POST /v1/act 본문:

```json
{"action":{"type":"craft","recipe":"oak_planks"}}
```

인증과 실행 잠금·취소 규약은 기존 직접 행동과 같다. craft capability가 없는 클라이언트는 거절한다.
제작 칸·결과 칸·커서가 비어 있고 다른 컨테이너나 아이템을 사용 중이지 않아야 한다.
빈 인벤토리 슬롯을 최소 1개 요구한다. 수량 지정과 반복 제작은 지원하지 않는다.
현재 모델 Plan이나 wood 실행에 자동 제작을 추가하지 않았다.

레시피 채우기 요청 1회 후 서버가 보고한 결과 칸을 확인하고 결과를 QUICK_MOVE로 1회 가져온다.
제작 제한은 200틱/벽시계 12초이며 브리지 실행 기한은 14초다. 응답 유실 시 자동 재전송하지 않는다.
성공은 서버 슬롯 패킷의 재료 총량 감소·인벤토리 결과물 증가·제작 입력 칸 비움을 함께 확인한다.
클라이언트의 낙관적 슬롯 변경만으로 완료하지 않는다.

| 레시피 | 재료 감소 | 산출물 증가 |
|---|---|---|
| 각 종류 판자 | 해당 원목 1 | 판자 4 |
| stick | 지원 판자 2 | 막대 4 |
| crafting_table | 지원 판자 4 | 작업대 1 |

성공 결과는 completed/craft_verified, details.verification=server_slot_packets다.
inputConsumed와 outputGained로 위 수량을 확인한다. 다른 플레이어의 자원 전달 등 동시 변화가 있으면
단순한 수량 증거가 불명확해질 수 있으므로 첫 검증은 독립된 개인 인벤토리에서 수행한다.

취소는 추가 요청을 중단한다. 이미 서버에 보낸 요청은 되돌릴 수 없다.
pendingChangesPossible=true이면 취소 후에도 슬롯 갱신이 도착할 수 있으며,
gridMayContainMaterials는 마지막으로 확인한 제작 칸 상태다. 빈 칸 복구를 자동 수행하지 않는다.
실패·취소 후 인벤토리 화면에서 제작 칸과 커서를 확인하고 재료를 회수한 뒤 다시 실행한다.

## 사용자 테스트

게임을 저장·정상 종료하고 새 모드를 실행한다.

```powershell
.\scripts\dev.ps1 -Task runClient
```

서바이벌 월드에서 참나무 원목 2개 이상과 빈 인벤토리 칸을 준비한다.
기존 제작 칸과 커서는 비우고 인벤토리 화면을 닫는다. 다른 PowerShell에서 순서대로 실행한다.

```powershell
.\docker\invoke-agent.ps1 -Operation craft -Recipe oak_planks
.\docker\invoke-agent.ps1 -Operation craft -Recipe oak_planks
.\docker\invoke-agent.ps1 -Operation craft -Recipe stick
.\docker\invoke-agent.ps1 -Operation craft -Recipe crafting_table
```

각 요청에서 craft_verified를 확인한다. 모두 성공하면 시작 대비 원목 -2, 판자 +2, 막대 +4, 작업대 +1이다.
작업대 설치와 3×3 제작은 아직 포함하지 않는다. 명령은 DRY_RUN 설정과 무관하게 실제 제작한다.

| 실패 이유 | 확인할 항목 |
|---|---|
| insufficient_materials | 필요한 종류와 수량 |
| inventory_full | 빈 슬롯 최소 1개 |
| crafting_grid_not_empty | 제작/결과/커서 슬롯, 다른 컨테이너 또는 아이템 사용 |
| recipe_unavailable | 해당 버전의 레시피 존재 |
| crafting_sync_timeout | 레시피 해금·재료 호환·서버 슬롯 갱신·잔여 제작 칸; 재요청 전 직접 확인 |
| world_or_handler_changed / health_decreased | 월드·화면·체력 변화 |

## 검증 상태

Fabric build, Java 33개·Python 113개·Node 23개 및 기존 합성 연결·취소 시험 통과.
제작 증거 함수, 레시피 허용 목록, 구형 클라이언트 거절, 실행 기한과 취소 증거를 자동 검사했다.
사용자가 실제 서바이벌 월드에서 판자, 막대, 작업대 순차 제작 및 수량 증거 검증의 실게임 성공을 확인했다.
후속 작업으로 작업대 설치([작업대 설치 및 상호작용](WORKBENCH.md))와 3×3 도구 제작을 진행한다.
