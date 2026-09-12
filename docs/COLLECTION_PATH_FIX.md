# 수집 경로 실패와 제한된 재탐색

## 확인한 원인과 한계

이전 실게임 실행은 approach·mine 완료 후 collect=no_flat_path, inventoryDelta=0으로 끝났다.
저장된 관측에는 같은 발 높이의 드롭과 그 위에 남아 있는 원목이 있다.
기존 탐색은 드롭 반경 0.72블록 안의 칸 중심만 목표로 허용한다. 해당 배치에서는 그 칸 중심에
머리 높이 원목이 있어 설 수 없고, 안전한 인접 칸 중심은 반경을 조금 벗어난다.
위치를 원점 부근으로 옮기고 단순화한 합성 테스트에서 기존 탐색 실패와 수정 탐색 성공을 확인했다.
원본 월드 좌표·세션·엔티티 ID는 공개 테스트에 포함하지 않았다.

기존 safetyFailure는 탐색 중 정상 구간 검사로 초기화되어 빈 객체가 될 수 있었다.
그래서 원본 실패의 모든 내부 검사 결과를 복원할 수는 없다. 확인된 배치로 같은 실패 조건을 재현했으며
실게임에서 수정 효과가 나타나는지는 새 모드로 별도 확인해야 한다.

## 변경

- Fabric collect는 기존 0.72블록 후보 탐색이 실패하면 반경 1블록의 정지 위치를 한 번 탐색한다.
- 두 탐색 모두 동일한 몸체 충돌·바닥 지지·유체/위험·시야 검사를 통과해야 한다.
- 각 탐색은 기존 9×9 영역·최대 12간선으로 제한되며 기존 행동 시간 제한을 연장하지 않는다.
- 정지 위치 후보에 도달한 것만으로 완료하지 않는다. 기존 pickup 이벤트와 인벤토리 증가를 모두 확인한다.
- results.details.search에 passes, nearCandidates, blockedEdges, blockedGoals, hiddenGoals, lastBlocked를 기록한다.
  수치는 두 탐색의 누적 검사 횟수다. lastBlocked는 마지막 차단 사례이며 실패 전체의 단일 원인이라는 뜻은 아니다.
- wood@1.1.0은 실행 전 no_flat_path 거절에 한해 다른 후보를 최대 한 번 선택한다.
  같은 후보를 다시 보내지 않고 collect는 다른 원목 드롭만 선택한다. 대체 직전 새 관측과 안전 상태를 검사한다.
- 거절 행동과 대체 행동 모두 원래 최대 3행동/60초 예산을 소비한다. 세 번째 행동이 거절되면 추가 행동은 없다.
- 취소·시간 초과·체력 감소·세션 변화·실행 중 경로 차단에는 이 재시도를 적용하지 않는다.

등록된 현재 버전과 PowerShell 기본 버전은 1.1.0이다. 명시적 1.0.0 실행 요청은 409로 거절한다.
Python의 대체 후보 선택과 Fabric의 동일 대상 정지 위치 재탐색은 서로 다른 단계다.

## 검증

Fabric build와 Java 27개 테스트, Python 88개, Node 18개, 격리 연결·취소 시험을 통과했다.
합성 테스트는 머리 위 장애물 아래 드롭, 차단된 경로 유지, 반경 상한, 다른 후보 선택,
예산 소진, 대체 후보 부재, 두 번째 거절, 체력 감소 및 재시도 금지 상태를 다룬다.
유료 모델 호출은 없었다. Docker 에이전트는 운영 docker/.env를 사용하며 새 모드 적용에는 게임 재시작이 필요하다.

## 사용자 실게임 확인

월드를 저장하고 Minecraft를 정상 종료한 다음 저장소 루트에서 실행한다.

```powershell
.\scripts\dev.ps1 -Task runClient
```

테스트 월드에서 메뉴를 닫고 F3+P로 포커스 상실 일시정지를 해제한다.
남은 원목 아래의 드롭이 여전히 있다면 먼저 collect를 실행한다. 없으면 평지 나무 주변에서 스킬을 실행한다.

```powershell
.\docker\invoke-agent.ps1 -Operation collect -Item minecraft:oak_log
.\docker\invoke-agent.ps1 -Operation skill-run -SkillVersion 1.1.0
```

collect 성공 기준은 result.reason=pickup_verified와 details.verifiedCollectedCount>=1이다.
스킬 성공 기준은 result.reason=log_inventory_increased와 inventoryDelta>=1이다.
재탐색이 사용되면 수집 행동 details.search.passes=2가 표시된다. 성공 결과에 2가 항상 필요한 것은 아니다.
다시 실패하면 해당 행동의 reason과 details.search를 확인한다. 원본 결과는 local/에 저장한다.
실행 중 다른 창에서 -Operation cancel로 입력 해제와 후속 행동 억제도 확인한다.

후속 운영 기록에서 1.1.0의 실제 획득 성공 3건을 확인했다. 성공한 수집의 search.passes는 1이므로
반경 확대 passes=2 및 대체 후보 분기의 실게임 성공은 별도로 확인해야 한다.
최신 상태는 [진행 상태](PROGRESS.md), 후보 범위 밖 중단은 [실패 진단](WOOD_FAILURE_DIAGNOSIS.md)을 따른다.
