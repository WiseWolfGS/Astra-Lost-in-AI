# 핫바 슬롯 선택

`select_hotbar`는 0~8 슬롯(숫자 키 1~9)을 직접 선택한다. [준비·공통 규칙](README.md)을 따른다.
[일반 인벤토리 교환](HOTBAR_TRANSFER.md), [제작](CRAFTING.md)은 별도 행동이며 방어구 장착은 미구현이다.

```powershell
.\docker\invoke-agent.ps1 -Operation select-hotbar -Slot 0
.\docker\invoke-agent.ps1 -Operation select-hotbar -Slot 8
```

POST /v1/act:

```json
{"action":{"type":"select_hotbar","slot":0,"expectedItem":"minecraft:air"}}
```

PowerShell은 먼저 해당 슬롯의 아이템 ID를 관측한다. expectedItem은 필수이고 빈 슬롯은 minecraft:air다.
적용 시 ID가 다르면 slot_item_changed로 거절한다. 수량·내구도 일치 검사까지 하는 것은 아니다.
slot은 정수 0~8이며 capability가 없으면 409, 사용 중 아이템·컨테이너·커서가 있으면 inventory_busy다.

성공은 completed/hotbar_selected다. details에 previousSlot, selectedSlot, item, packetSent=true,
verification=client_selection, serverConfirmed=false를 기록한다. 이는 선택과 변경 패킷 전송 증거이며 서버 확정은 아니다.
완료 후 취소는 이전 슬롯으로 되돌리지 않는다. 모델 Plan에는 포함되지 않고 직접 행동·도구 스킬에서 사용한다.

서로 다른 아이템이 든 처음/마지막 슬롯과 빈 슬롯을 시험하고 손의 아이템과 후속 observe.player.selectedSlot을 비교한다.
선택한 도구의 실제 채굴은 별도 mine으로 확인한다. 현재 자동·실게임 검증은 [진행 상태](PROGRESS.md)를 따른다.
