# 작업대 3×3 나무 도구 제작

후속 확장으로 돌 도구 5종도 지원한다. 재료 규약과 테스트는 [돌 도구 제작](STONE_TOOLS.md)을 따른다.

craft_workbench는 조준한 작업대를 열고 나무 도구 1개를 제작한 뒤 해당 화면을 닫는 직접 행동이다.
기존 개인 2×2 제작은 craft로 유지한다. 두 행동 모두 모델을 호출하지 않는다.

## 규약

```json
{"action":{"type":"craft_workbench","x":0,"y":64,"z":0,"recipe":"wooden_pickaxe"}}
```

좌표는 이미 설치된 작업대다. 도달 거리의 작업대를 직접 조준하고 화면을 닫은 상태에서 시작한다.
웅크리기·아이템 사용·커서 아이템·다른 컨테이너가 있는 상태에서는 시작하지 않는다.
빈 인벤토리 슬롯이 최소 1개 있어야 한다. 지원 판자는 기존 8종 오버월드 판자다.

| recipe | 판자 소비 | 막대 소비 | 도구 증가 |
|---|---|---|---|
| wooden_pickaxe | 3 | 2 | 1 |
| wooden_axe | 3 | 2 | 1 |
| wooden_sword | 2 | 1 | 1 |
| wooden_shovel | 1 | 2 | 1 |
| wooden_hoe | 2 | 2 | 1 |

작업대 열기 1회, 레시피 채우기 1회, 결과물 이동 1회를 요청한다. 자동 재시도는 없다.
전체 제한은 280틱/16초이며 열기 대기는 60틱, 내부 제작은 기존 200틱/12초다. 브리지 기한은 18초다.
필요 capability는 craft_workbench이며 구형 모드에 요청하면 409다. 기존 모델 Plan에는 추가하지 않았다.

서버 슬롯 갱신은 현재 제작 handler의 syncId와 일치할 때만 사용한다.
개인 제작은 입력 1~4·인벤토리 9~44, 작업대는 입력 1~9·인벤토리 10~45로 구분한다.
서버 패킷에 따른 판자 감소, 막대 감소, 도구 증가와 입력 칸 비움을 모두 확인해야 craft_verified다.
inputConsumed는 판자 소비, sticksConsumed는 막대 소비, outputGained는 산출물 증가다.

## 화면과 취소

실행이 열기를 요청한 작업대 화면만 현재 실행의 준비 상태로 인정한다. 다른 화면으로 바뀌면 중단한다.
완료·실패·취소 때 아직 같은 handler를 소유하고 있으면 화면 닫기를 요청한다.
screenCloseSent는 닫기 요청을 뜻하며 반환 재료까지 검증했다는 뜻은 아니다.
열기 응답 전에 취소하면 lateOpenPossible=true일 수 있다. 뒤늦게 화면이 열렸다면 직접 닫는다.
이미 전송된 제작·아이템 이동은 취소로 되돌아가지 않는다.
취소 후에는 제작 칸과 인벤토리를 확인하고, 공간 부족 시 재료가 바닥으로 반환될 가능성도 확인한다.

## 사용자 테스트

[공통 준비](README.md) 후 아래 조건으로 실행한다.

설치된 작업대, 판자 3개 이상, 막대 2개 이상과 빈 인벤토리 칸을 준비한다.
게임에서 작업대를 조준하되 직접 화면을 열지는 않는다. 다른 PowerShell에서 실행한다.

```powershell
.\docker\invoke-agent.ps1 -Operation craft-workbench -Recipe wooden_pickaxe
```

성공 기준은 craft_verified, inputConsumed=3, sticksConsumed=2, outputGained=1이며
실제 인벤토리에 나무 곡괭이가 생기고 작업대 화면이 닫혀야 한다.
추가 검증으로 기존 2×2 판자 제작, 재료 부족 거절, 제작 중 Esc 또는 cancel 후 추가 요청 중단을 확인한다.
원본 실패 결과는 Git 제외 local/에 보관한다.

| reason | 확인 |
|---|---|
| aim_at_workbench / workbench_missing | 조준·거리·실제 작업대 블록 |
| inventory_busy | 웅크리기·아이템 사용·화면·커서 |
| insufficient_materials / inventory_full | 두 종류 재료와 빈 슬롯 |
| workbench_open_timeout | 서버의 화면 열기 응답 |
| crafting_sync_timeout | 레시피 사용 가능 여부·재료 호환·서버 슬롯 갱신 |
| workbench_screen_closed / workbench_or_world_changed | 수동 화면 종료·작업대 소실·월드 변경 |

## 검증 상태

현재 자동·실게임 확인과 남은 작업은 [진행 상태](PROGRESS.md)에서 관리한다.
