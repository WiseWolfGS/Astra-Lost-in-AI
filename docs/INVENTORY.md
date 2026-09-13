# 인벤토리 제어 — 핫바 선택

S1의 첫 구현은 직접 핫바 슬롯 선택이다. 슬롯은 0~8이며 게임의 숫자 키 1~9에 대응한다.
일반 인벤토리의 아이템 이동과 장착 슬롯 변경은 후속 작업이다. [2×2 제작](CRAFTING.md)은 별도 직접 행동이다.

## 사용과 결과

수정 모드로 Minecraft를 다시 실행하고 서바이벌 월드에서 메뉴를 닫는다.
저장소 루트의 PowerShell에서 실행한다. 설정은 docker/.env를 사용한다.

```powershell
.\scripts\dev.ps1 -Task runClient
```

다른 PowerShell에서:

```powershell
.\docker\invoke-agent.ps1 -Operation select-hotbar -Slot 0
.\docker\invoke-agent.ps1 -Operation select-hotbar -Slot 8
```

명령은 해당 슬롯의 아이템 ID를 먼저 관측하고 POST /v1/act에 전달한다.
클라이언트가 적용할 때 아이템 ID가 다르면 slot_item_changed로 거절한다.
같은 종류 아이템의 수량·내구도 변화까지 일치시키는 검사는 아니다.

```json
{"action":{"type":"select_hotbar","slot":0,"expectedItem":"minecraft:air"}}
```

expectedItem은 필수이며 빈 슬롯은 minecraft:air다. API는 기존 bearer 인증을 요구한다.
예전 모드는 select_hotbar capability가 없어 409로 거절된다. slot은 정수 0~8만 허용한다.
사용 중 아이템, 열린 컨테이너 또는 커서 아이템이 있으면 inventory_busy로 거절한다.
메뉴·월드 준비·실행 잠금·큐·취소 규약도 기존 직접 행동과 같다.

정상 결과는 completed/hotbar_selected이며 details에 previousSlot, selectedSlot, item,
packetSent=true, verification=client_selection, serverConfirmed=false를 기록한다.
이는 클라이언트에서 슬롯을 선택하고 서버로 변경 패킷을 보냈다는 증거다.
서버 확정이나 그 도구로 채굴할 수 있다는 증거는 아니며 이후 실제 행동과 새 관측으로 확인한다.
즉시 완료되는 행동이므로 완료 후 취소해도 이전 슬롯으로 되돌리지 않는다.
직접 명령은 DRY_RUN과 무관하게 게임을 조작하지만 모델은 호출하지 않는다. 모델 Plan에는 아직 추가하지 않았다.

## 검증과 다음 단계

Fabric build와 Java 30개, Python 98개, Node 20개 및 격리 연결·취소 시험을 통과했다.
슬롯 경계·아이템 변경·조작 중 거절·구형 모드 거절·응답 증거 보존을 자동 검사했다.
후속 사용자 테스트에서 실게임 슬롯 변경 성공을 확인했다.

사용자는 서로 다른 아이템이 든 첫 슬롯과 마지막 슬롯을 선택하고 손에 든 아이템 및
후속 observe의 player.selectedSlot이 각각 0과 8인지 확인한다. 빈 슬롯도 같은 방식으로 확인한다.
기존 mine을 사용할 때 선택한 도구가 실제 채굴에 반영되는지 별도로 확인한다.

다음 S1 단위인 2×2 제작의 슬롯/레시피 규약과 재료 감소·산출물 증가 검증을 구현했다.
제작에는 현재 슬롯 선택의 client_selection보다 강한 서버 인벤토리 동기화 증거가 필요하다.
S0의 반경 확대·대체 후보 실게임 확인은 [진행 상태](PROGRESS.md)의 잔여 항목으로 유지한다.
