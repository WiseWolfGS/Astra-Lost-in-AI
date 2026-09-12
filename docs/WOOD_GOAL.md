# 원목 1개 획득 실행 루프

## 현재 동작

`POST /v1/goals/wood`와 `invoke-agent.ps1 -Operation wood`는 모델을 호출하지 않는 첫 고수준 스킬이다.
DRY_RUN과 무관하게 실제 월드를 조작한다. 기존 유료 단일 행동 `step`의 동작은 동일하다.
자유 탐험·자동 커리큘럼·생성 코드 실행까지 구현한 Voyager 에이전트는 아직 아니다.

1. 연결·월드 준비·capability·관측 시각을 검사하고 최초 원목 인벤토리 개수를 저장한다.
2. 같은 높이에서 보이는 땅 위 원목 드롭이 수평 4블록 이내에 있으면 collect를 우선한다.
3. 드롭이 없으면 관측 격자에서 발 높이부터 두 블록 위까지의 가까운 원목을 선택해 approach한다.
4. 새 관측의 조준 대상이 선택한 원목과 일치하고 도달·채굴 가능하면 mine한다.
5. 자동으로 주워졌으면 끝낸다. 아니면 드롭이 내려앉는 것을 제한적으로 기다려 collect한다.
6. 최초 관측 대비 원목 인벤토리 합계가 1개 이상 증가했을 때만 목표 성공으로 기록한다.

대상은 참나무·가문비나무·자작나무·정글나무·아카시아·짙은참나무·맹그로브·벚나무의 기본 `_log`이다.
껍질 벗긴 원목, 네더 자루, 판자는 포함하지 않는다. 시작할 때 가지고 있던 원목은 새 획득으로 세지 않는다.
원목 후보에는 가려진 블록도 포함될 수 있으며 실제 접근 가능성은 Fabric 경로 검사에서 판정한다.
발 아래 지지 블록은 채굴 대상으로 선택하지 않는다. wood@1.1.0은 실행 전 no_flat_path 거절에 한해
실패 후보를 제외하고 다른 후보를 최대 한 번 선택한다. 전체 3행동/60초 예산을 공유하며 거절도 행동 수에 포함한다.
collect의 대체 후보는 다른 원목 드롭으로 제한한다. 취소·체력 감소·세션 변화·시간 초과에는 재시도하지 않는다.
대체 후보가 없으면 no_alternative_candidate로 종료한다. 선택 변경은 에피소드 replans에 기록한다.

## 제한과 결과

- 최대 3개 행동, 목표 실행 예산 60초. 각 행동 최대 200틱.
- `max_actions`는 1~3 정수로 더 줄일 수 있다. 기본 3.
- 각 행동 후 완료 조회 이후보다 새로운 관측을 기다린다. 3초보다 오래된 관측은 거절한다.
- 세션·차원·체력·준비 상태 변화를 확인한다. 행동 rejected/cancelled/timed_out이면 후속 행동을 중단한다.
- `step`, `act`, `wood`는 같은 실행 잠금을 사용한다. 중복 요청은 HTTP 409다.
- 통신/시간 제한으로 마지막 행동 종료 여부가 불명확하면 알려진 action ID로 취소를 요청한다.
  정리 요청 예산은 추가 최대 8초이며, `cancellation.cancelConfirmed=true`로 확인 여부를 구분한다.
  전송 응답을 잃어 ID를 모르면 취소를 보장하지 않는다. [취소 규약](CANCELLATION.md)을 따른다.
  클라이언트의 행동 시간 제한과 통신 오류 시 입력 해제도 유지된다.
- 에피소드에는 before/after, initialLogCount, inventoryDelta, steps의 행동·관측·결과를 저장한다.
- PowerShell wood 기본 출력은 result와 단계별 행동·결과를 먼저 보여준다. `-FullRecord`로 원본 관측까지 출력한다.
- 행동 실패 시 최상위 result.actionReason과 result.safetyFailure에도 상세 원인을 표시한다.

목표 성공은 `result.status=completed`, `result.reason=log_inventory_increased`, `inventoryDelta>=1`이다.
개별 행동의 completed와 목표의 completed는 다르다. collect 행동 자체의 성공은 기존처럼
대상 pickup 이벤트와 인벤토리 증가를 함께 검증한다. 목표는 채굴 중 자동 획득도 인정하므로
항상 collect 행동이 포함되는 것은 아니다. 특정 나무에서 나온 드롭의 출처까지 추적하지는 않는다.
시험 중 수동 아이템 이동·다른 원목 획득을 병행하면 인벤토리 증가의 원인이 섞일 수 있다.

| 목표 reason | 의미 |
|---|---|
| log_inventory_increased | 시작 대비 원목 순증가 확인 |
| no_local_log_or_drop | 지원 범위에 후보 없음; 행동 없이 종료 |
| action_rejected / action_cancelled / action_timed_out | 마지막 steps.result.reason에서 상세 원인 확인 |
| action_budget_exhausted | 추가 행동을 실행하기 전에 예산으로 중단 |
| mining_target_not_verified | 접근 후 조준 대상·도달·채굴 조건 불일치 |
| no_settled_log_drop | 채굴 후 수집 가능한 드롭이나 인벤토리 증가 미확인 |
| inventory_gain_not_observed | 행동 완료 후에도 목표 인벤토리 증가 미확인 |
| world_changed / health_decreased / world_not_ready | 월드·플레이어 상태 변화로 중단 |
| stale_observation / observation_not_advancing | 관측이 오래되었거나 새 관측을 받지 못함 |
| goal_timeout / bridge_or_state_error | 시간 제한 또는 통신/실행 직전 상태 검사 실패 |

## 사용자 시험

이번 변경은 Docker agent만 갱신했다. 기존 approach/collect 지원 모드를 그대로 사용한다.
게임이 종료되어 있으면 프로젝트 폴더에서 `.\scripts\dev.ps1 -Task runClient`로 실행한다.
서바이벌의 넓고 평평한 흙/잔디에 서고 F3+P로 포커스 상실 시 일시정지를 해제한 뒤 메뉴를 닫는다.

별도 PowerShell:

```powershell
cd C:\Projects\AstraLostInAI\docker
.\invoke-agent.ps1 -Operation observe
.\invoke-agent.ps1 -Operation wood
```

### A. 드롭 하나 수집

Q로 원목 하나를 바닥에 던지고 1~2블록 물러난다. 드롭이 땅에 내려앉은 후 wood를 실행한다.
드롭을 만들기 **이후**의 인벤토리가 기준이다. steps가 collect 하나이고 목표 성공과 inventoryDelta>=1인지 확인한다.
개별 collect 결과의 pickupPacketCount와 verifiedCollectedCount도 1 이상이어야 한다.

### B. 원목 접근 → 채굴 → 획득

기존 드롭이 없는 평지에서 수평 3~4블록 이내의 원목 옆에 선다. 원목을 미리 조준할 필요는 없다.
wood를 실행하고 steps에 approach → mine → 필요 시 collect가 기록되는지 확인한다.
블록 파괴만으로는 성공이 아니다. 최종 인벤토리가 시작보다 1개 이상 증가해야 한다.
나무 밑 원목 주변에 구멍이나 단차가 있으면 실패할 수 있으므로 첫 시험은 연속된 평지에서 진행한다.

### C. 예산 및 중단

드롭이 없는 원목 근처에서:

```powershell
.\invoke-agent.ps1 -Operation wood -MaxActions 1
```

접근이 정상 완료되고 추가 원목을 자동 획득하지 않았다면 `action_budget_exhausted`로 끝나고 채굴하지 않아야 한다.
별도 정상 wood 실행 중 Esc를 누르면 중단되고 다음 행동으로 넘어가지 않아야 한다.
주변에 원목/드롭이 없으면 `no_local_log_or_drop`, steps=[]가 정상이다.

### 기록 확인

```powershell
docker compose exec -T agent tail -n 1 /data/episodes.jsonl
```

HTTP 요청이 오류 없이 끝났다는 것과 목표 달성은 구분한다. 판정에는 위 result와 inventoryDelta를 사용한다.
실제 월드의 collect 두 번과 approach→mine→collect 전체 연결의 성공을 확인했다.
최신 자동·실게임 검증 기준선은 [진행 상태](PROGRESS.md)를 따른다.
초기 이동 오류 수정 이력은 [수정 보고서](NAVIGATION_FIX.md)를 참조한다.

버전별 등록·조회·실행은 [스킬 문서](SKILLS.md), 다음 작업은 [개발 계획](ROADMAP.md)을 따른다.
