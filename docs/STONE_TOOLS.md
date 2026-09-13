# 돌 도구 제작

작업대 직접 행동에 stone_pickaxe, stone_axe, stone_sword, stone_shovel, stone_hoe를 추가했다.
재료 수집·작업대 조준은 사용자가 준비한다. 자동 제작 스킬이나 Astra 반복 실행은 아직 아니다.

재료는 Minecraft의 stone_tool_materials 아이템 태그로 판정한다. 첫 시험에는 조약돌을 사용한다.
곡괭이·도끼는 재료 3개와 막대 2개, 검은 2개와 1개, 삽은 1개와 2개, 괭이는 2개와 2개를 소비한다.
판자를 돌 재료로 세지 않는다. 서버 슬롯 갱신으로 재료·막대 감소와 도구 1개 증가를 함께 검증한다.
필요 capability는 craft_workbench와 stone_tools이며 구형 클라이언트에는 409로 거절한다.
시간 제한·화면 소유권·취소 처리는 [작업대 제작](WORKBENCH_CRAFTING.md)과 같다.

## 실게임 테스트

월드를 저장하고 Minecraft를 정상 종료한 뒤 저장소 루트에서 실행한다.

```powershell
.\scripts\dev.ps1 -Task runClient
```

나무 곡괭이로 조약돌 3개를 확보하고 막대 2개, 빈 인벤토리 칸을 준비한다.
설치된 작업대를 가까이에서 조준하고 화면은 닫는다. 다른 PowerShell에서 실행한다.

```powershell
.\docker\invoke-agent.ps1 -Operation craft-workbench -Recipe stone_pickaxe
```

craft_verified와 inputMaterial=stone_tool_materials, inputConsumed=3,
sticksConsumed=2, outputGained=1을 확인한다. 실제 곡괭이가 생기고 화면이 닫혀야 한다.
일반 인벤토리에 생긴 경우 다음 명령으로 옮기고 선택한다.

```powershell
.\docker\invoke-agent.ps1 -Operation move-hotbar -Item minecraft:stone_pickaxe -Slot 0
.\docker\invoke-agent.ps1 -Operation select-hotbar -Slot 0
```

이미 핫바에 있다면 observe로 슬롯 번호를 확인하고 해당 슬롯의 select-hotbar만 실행한다.
재료 부족 시험에서는 판자가 충분해도 조약돌이 부족하면 insufficient_materials로 종료해야 한다.
기존 wooden_pickaxe 제작도 별도 재료로 재확인한다. 명령은 모델을 호출하지 않는다.

## 검증과 다음 단계

로컬 Fabric build와 Java 39개, Python 135개, Node 26개 테스트를 통과했다.
돌 도구의 실게임 검증은 사용자 테스트가 남아 있다.
후속 작업은 제작→핫바 이동→선택을 제한된 행동 예산의 등록 스킬로 묶고,
그다음 채굴·수집 선행 조건과 연결하는 것이다.
