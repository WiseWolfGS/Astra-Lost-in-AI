# 결정적 스킬 등록과 실행

첫 등록 스킬은 wood@1.1.0이다. 목록에는 ID·버전·입력 JSON Schema·필요 capability·선행 조건·
행동/시간/모델 호출 예산·성공 조건을 제공한다. 등록 항목은 코드로 검토하고 Git으로 버전 관리한다.
실행 중 생성 코드나 외부 스킬 파일을 불러오지 않는다. 자동 학습·임베딩 검색·자동 목표 선택은 아직 없다.

## 조회와 실행

저장소 루트의 PowerShell에서 아래 명령을 사용한다. 기본 설정 파일은 docker/.env다.

```powershell
.\docker\invoke-agent.ps1 -Operation skills
.\docker\invoke-agent.ps1 -Operation skill-check -SkillId wood
.\docker\invoke-agent.ps1 -Operation skill-run -SkillId wood -SkillVersion 1.1.0 -MaxActions 3
```

skills는 월드 없이 목록을 조회한다. skill-check는 관측만 읽으며 eligible과 이유를 반환한다.
eligible=true는 현재 관측에서 후보를 찾았다는 뜻으로 경로 성공을 보장하거나 후보를 예약하지 않는다.
실행 시 최신 관측과 기존 안전 검사를 다시 적용한다. skill-run은 DRY_RUN과 무관하게 실제 월드를 조작한다.
세 명령 모두 모델을 호출하지 않는다. 기존 -Operation wood도 같은 등록 스킬 실행기를 사용한다.

| API | 동작 |
|---|---|
| GET /v1/skills | 등록 목록 |
| GET /v1/skills/wood | 상세 규약 |
| GET /v1/skills/wood/check | 현재 선행 조건 검사 |
| POST /v1/skills/wood/run | 버전 지정 실행 |

모두 기존 bearer 인증이 필요하다. 실행 본문은 다음과 같다.

```json
{"version":"1.1.0","inputs":{"max_actions":3}}
```

알 수 없는 ID는 404, 지원하지 않는 버전은 409, 범위 밖 입력·추가 필드는 422다.
max_actions는 1~3 정수이며 문자열과 boolean을 거절한다. 중복 실행은 기존처럼 409다.
취소는 [기존 실행 ID 기반 API](CANCELLATION.md)를 그대로 사용한다.

## 결과와 버전 관리

에피소드에는 skill.id, skill.version, skill.inputs와 observationSchemaVersion을 추가한다.
기존 steps·inventoryDelta·result·executionId도 보존한다. 관측 전 실패하면 관측 스키마 버전은 null이다.
성공 판정 함수는 실행 전후의 원목 인벤토리 합계를 비교한다. 행동 completed나 기록된 delta 값만으로 성공하지 않는다.
실행 결과는 기존 로컬 에피소드 볼륨에 저장되고 등록 정의는 저장소의 docker/agent/skills.py에 있다.
스킬 행동·조건·성공 판정을 바꿀 때 버전을 갱신한다. 현재는 한 버전만 지원하며 옛 버전으로 자동 대체하지 않는다.

## 사용자 확인

1.1.0의 수집 정지 위치 재탐색은 Fabric 변경을 포함하므로 월드를 저장하고 게임을 정상 종료한 뒤
저장소 루트에서 `./scripts/dev.ps1 -Task runClient`로 새 모드를 실행한다.
평지의 가까운 원목이나 원목 드롭 주변에서 위 명령을 실행한다.

1. 목록에 wood, 1.1.0, 최대 3행동/60초/모델 0회가 표시되는지 확인한다.
2. 조건 조회가 eligible=true인지 확인한다. false이면 reason을 확인하고 후보가 있는 곳으로 이동한다.
3. 실행 결과 skill.version=1.1.0, result.reason=log_inventory_increased, inventoryDelta>=1을 확인한다.
4. 실행 중 다른 PowerShell에서 -Operation cancel을 호출해 다음 행동이 시작되지 않는지 확인한다.

자동 테스트는 기존 실행과 버전 지정 실행의 동일한 결과, 입력 검증, 사전 조회 후 상태 변화,
버전 기록 보존, 인벤토리 증거와 취소 동작을 검증한다. Python 88개·Node 18개와 합성 연결·취소 시험을 통과했다.
1.0.0에서는 접근·채굴 후 collect=no_flat_path로 중단된 사례가 있었다.
후속 1.1.0 운영 기록에서는 획득 성공 3건과 후보 범위 밖 중단 2건을 확인했다.
성공한 수집은 search.passes=1이므로 반경 확대 및 대체 후보 분기의 실게임 확인은 남아 있다.
모델 호출은 없었고 원본 결과는 local/에 보관했다. [후보 선택 실패 진단](WOOD_FAILURE_DIAGNOSIS.md)을 참고한다.
1.1.0에서 no_flat_path 거절 후 다른 후보를 한 번 선택하는 기능과 Fabric의 수집 정지 위치 재탐색을 추가했다.
상세 원인·예산·실게임 확인 기준은 [수집 경로 수정](COLLECTION_PATH_FIX.md)을 따른다.
