# 실행 중 취소

직접 행동, wood, step 실행에 고유 execution ID를 부여한다. 취소는 일반 행동 큐를 우회하며
목표의 다음 행동을 막고, 현재 action ID에 대해 Fabric의 입력 해제 응답을 기다린다.
기존 stop 행동은 진행 중 큐를 선점하지 않는다.

## 상태와 확인 기준

| 상황 | 결과 |
|---|---|
| 아직 클라이언트에 전달하지 않은 행동 | cancelled, cancelConfirmed=true, confirmation=never_dispatched |
| 실행 중 취소 요청 | cancelling, cancelConfirmed=false |
| 같은 action ID·세션의 클라이언트가 입력 해제를 보고 | cancelled, details.inputsReleased=true, cancelConfirmed=true |
| 완료가 취소보다 먼저 도착 | completed 유지, 취소 성공으로 바꾸지 않음 |
| 연결 단절·확인 시간 초과 | cancelConfirmed=false; cancel_ack_timeout 또는 confirmation_unavailable |
| 오래된 실행/행동 ID로 재요청 | 새 실행을 취소하지 않음 |

Fabric은 취소를 받으면 이동·점프·질주·채굴 입력과 진행 중 제어기를 해제한다.
브리지는 취소 메시지를 tick 응답으로 반복 전달하고 확인 대기 시간을 최대 5초로 제한한다.
Python의 취소 요청·조회 예산은 최대 8초다. 반복 취소로 브리지 기한이 늘어나지 않는다.
실행 조회의 finished는 Python 처리가 끝났다는 뜻이다. 입력 해제 확인은 actionResult.cancelConfirmed로 판단한다.
이미 파괴한 블록이나 이동한 위치를 되돌리지는 않는다.

## API

모두 기존 bearer 인증이 필요하다. POST 본문은 빈 객체 `{}`다.

- GET /v1/execution: 현재 실행 또는 execution=null.
- GET /v1/executions/{executionId}: 특정 실행 상태.
- POST /v1/executions/{executionId}/cancel: 목표 후속 행동 차단과 현재 행동 취소.
- GET /v1/actions/{actionId}: 개별 행동 상태.
- POST /v1/actions/{actionId}/cancel: 해당 행동과 이를 소유한 실행의 후속 행동 취소.

실행 목록은 단일 Python worker 메모리에 최근 100개를 보관한다. 재시작 후 조회는 유지되지 않는다.
에피소드에는 executionId와 cancelRequested를 기록하며 wood 출력에는 cancellation을 포함한다.
행동 전송 응답을 잃어 ID를 모르는 경우 dispatchPending=true와 확인 불가 상태를 남긴다.
이 경우 원격 취소를 보장하지 않는다. 게임의 메뉴 중단·행동 시간 제한·통신 오류 시 해제도 유지된다.
모델 응답 대기 중 취소는 응답 후 행동 전송을 막지만 이미 시작한 유료 API 호출의 취소나 비용 환불을 보장하지 않는다.

## 적용과 사용자 테스트

[공통 준비](README.md) 후 관측 capabilities에 cancel이 포함되는지 확인한다.

1. 맨손으로 천천히 캐지는 블록을 조준한다. 첫 PowerShell에서 아래 채굴을 시작한다.

```powershell
.\docker\invoke-agent.ps1 -Operation mine -TimeoutTicks 200
```

2. 채굴 중 두 번째 PowerShell에서 실행 상태를 확인하고 취소한다.

```powershell
.\docker\invoke-agent.ps1 -Operation execution
.\docker\invoke-agent.ps1 -Operation cancel
```

성공 기준은 채굴 입력이 멈추고 actionResult.status=cancelled,
actionResult.details.inputsReleased=true, actionResult.cancelConfirmed=true인 것이다.
완료가 먼저 일어났다면 느린 블록으로 다시 시험한다. idle은 취소 확인이 아니다.

3. 평지의 가까운 원목으로 wood를 시작하고 이동 또는 채굴 중 두 번째 창에서 취소한다.

```powershell
.\docker\invoke-agent.ps1 -Operation wood -FullRecord
```

이동·질주가 멈추고 다음 mine/collect가 새로 시작되지 않아야 한다. 취소 전 끝난 행동은 그대로 기록된다.
두 번째 창의 cancel 응답에서 id를 보관하고 같은 -ExecutionId로 재요청해 새 실행에 영향이 없는지도 확인한다.
연결 단절 때 cancelConfirmed=false를 성공으로 해석하지 않는다. 필요하면 게임 메뉴를 열어 수동 중단한다.
원본 실행 결과는 local/ 등 Git 제외 경로에만 보관한다. 이 테스트는 모델을 호출하지 않는다.

## 검증 범위

자동 시험은 ID·세션 일치, 실행 잠금 우회, 완료 경합, 중복 취소, 연결 단절, 목표 단계 사이 취소를 다룬다.
기존 사용자 실게임 성공 보고가 있으며 최신 결과와 미확인 범위는 [진행 상태](PROGRESS.md)를 따른다.
