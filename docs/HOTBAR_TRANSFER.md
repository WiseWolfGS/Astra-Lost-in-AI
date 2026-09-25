# 일반 인벤토리 → 핫바 이동

move_hotbar는 일반 인벤토리 슬롯 9~35와 핫바 슬롯 0~8을 한 번 교환하는 직접 행동이다.
원본 스택 전체를 옮기며, 대상 핫바가 차 있으면 그 스택을 원래 슬롯에 보존한다.
수량 분할·상자·방어구·보조 손·핫바 간 교환은 지원하지 않는다. 모델을 호출하지 않는다.

## 사용

[공통 준비](README.md) 후 실행한다.

제작한 나무 곡괭이가 일반 인벤토리에 있는 상태에서 화면을 닫고 실행한다.

```powershell
.\docker\invoke-agent.ps1 -Operation move-hotbar -Item minecraft:wooden_pickaxe -Slot 0
.\docker\invoke-agent.ps1 -Operation select-hotbar -Slot 0
```

-Item을 주면 일반 인벤토리에서 해당 종류의 가장 앞 슬롯을 선택한다.
같은 종류 도구의 내구도 등을 비교해서 고르지는 않는다. 위치를 직접 지정하려면 -SourceSlot을 사용한다.
두 매개변수를 함께 주면 -Item을 우선한다. 이미 핫바에 있는 도구는 observe로 슬롯을 확인한 뒤 select-hotbar만 실행한다.

```powershell
.\docker\invoke-agent.ps1 -Operation move-hotbar -SourceSlot 9 -Slot 0
```

인벤토리 슬롯 번호는 observe의 player.inventory[].slot을 따른다. 9~17이 일반 인벤토리 첫 줄이다.
이동 명령은 선택 슬롯을 바꾸지 않으므로 원하는 도구를 손에 들려면 select-hotbar를 이어서 사용한다.

## 규약과 검증

POST /v1/act 예시:

```json
{"action":{"type":"move_hotbar","sourceSlot":9,"hotbarSlot":0,"expectedSource":"minecraft:wooden_pickaxe","expectedTarget":"minecraft:air","sourceCount":1,"targetCount":0}}
```

API는 기존 bearer 인증과 실행 잠금을 사용한다. 필요 capability는 move_hotbar다.
PowerShell은 요청 전 양쪽 아이템 ID·수량을 관측한다. 적용 직전 다르면 inventory_changed로 거절한다.
이 사전 검사는 내구도·인챈트의 관측 일치까지 보장하지 않는다. 전송 직전 실제 스택 복사본은 보존한다.
교환 후에는 서버가 보고한 양쪽 스택을 복사본과 비교하며 수량과 데이터 구성요소도 일치해야 한다.
한쪽 패킷이나 클라이언트의 예상 변경만으로 성공하지 않는다.

정상 결과는 hotbar_transfer_verified, verification=server_slot_packets이며
sourcePacketObserved와 targetPacketObserved가 모두 true다. 같은 내용의 스택 간 무의미한 교환은 identical_stacks로 거절한다.
요청은 SWAP 1회이며 100틱/7초 제한, 브리지 기한 14초다. 일반 인벤토리 화면도 닫고 실행해야 한다.

| reason | 의미 |
|---|---|
| source_empty | 원본 슬롯이 비어 있음 |
| inventory_changed | 관측 이후 한쪽 아이템 ID 또는 수량 변경 |
| inventory_busy / cursor_changed | 컨테이너·아이템 사용·커서 상태 변화 |
| identical_stacks | 교환해도 같은 상태인 스택 |
| inventory_sync_timeout | 서버의 양쪽 슬롯 증거를 기한 내 확인하지 못함 |
| world_or_handler_changed / health_decreased | 실행 조건이 변경되어 중단 |

취소는 추가 요청을 막을 뿐 이미 보낸 교환을 되돌리지 않는다.
pendingChangesPossible=true이면 양쪽 슬롯을 직접 확인하고 재요청한다. 자동 재시도는 하지 않는다.

## 사용자 확인과 다음 단계

1. 빈 핫바 칸으로 옮겨 도구가 도착하고 원래 슬롯이 비는지 확인한다.
2. 아이템이 있는 핫바 칸으로 옮겨 기존 스택이 원본 위치에 보존되는지 확인한다.
3. select-hotbar 후 손에 든 도구를 확인하고 안전하게 조준한 돌에 기존 mine을 실행해 도구 사용을 확인한다.

현재 자동·실게임 검증은 [진행 상태](PROGRESS.md)를 따른다.
