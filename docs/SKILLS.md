# 버전별 스킬 조회와 실행

등록 정의는 [skills.py](../docker/agent/skills.py)에 있으며 검토된 코드만 실행한다.
동적 코드 로딩·자동 학습·임베딩 검색·자동 목표 선택은 없다. 공통 준비는 [문서 안내](README.md)를 따른다.

| 스킬 | 입력·예산 | 현재 성공 의미 |
|---|---|---|
| wood@1.1.0 | max_actions=1~3, 기본 3; 60초·모델 0회 | 최초 대비 기본 원목 합계 +1 이상 |
| craft_tool@1.0.0 | 나무/돌 도구 10종 recipe, slot=0~8(기본 0), max_actions=1~3; 60초·모델 0회 | 요청 도구의 장착; 기존 도구 재사용 가능 |

## 명령과 API

```powershell
.\docker\invoke-agent.ps1 -Operation skills
.\docker\invoke-agent.ps1 -Operation skill-check -SkillId wood
.\docker\invoke-agent.ps1 -Operation skill-run -SkillId wood -SkillVersion 1.1.0 -MaxActions 3
.\docker\invoke-agent.ps1 -Operation skill-check -SkillId craft_tool
.\docker\invoke-agent.ps1 -Operation skill-run -SkillId craft_tool -SkillVersion 1.0.0 -Recipe wooden_pickaxe -Slot 0
```

| API | 역할 |
|---|---|
| GET /v1/skills | 월드 연결 없이 등록 목록 조회 |
| GET /v1/skills/{skill_id} | 입력 스키마·capability·선행 조건·예산·성공 조건 |
| GET /v1/skills/{skill_id}/check | 현재 관측의 기본 선행 조건 검사 |
| POST /v1/skills/{skill_id}/run | 버전 지정 실행 |

실행 본문 예시:

```json
{"version":"1.1.0","inputs":{"max_actions":3}}
```

```json
{"version":"1.0.0","inputs":{"recipe":"stone_pickaxe","slot":0,"max_actions":3}}
```

ID 미등록은 404, 버전 불일치는 409, 범위 밖 입력·추가 필드는 422다. 정수 입력에 문자열·boolean을 허용하지 않는다.
인증과 실행 잠금·[취소](CANCELLATION.md)는 공통 규약을 사용한다. 실행은 DRY_RUN과 무관하게 실제 게임을 조작한다.

## 동작과 결과 해석

wood는 드롭 수집 또는 접근→채굴→필요 시 수집으로 원목 순증가를 검사한다.
거리·높이·재시도·실패 이유는 [원목 목표](WOOD_GOAL.md), 재탐색은 [수집 경로](COLLECTION_PATH_FIX.md)를 따른다.

craft_tool은 도구가 없으면 작업대에서 제작하고, 일반 인벤토리 도구는 핫바로 교환한 뒤 선택한다.
재료·빈 칸·조준된 작업대는 미리 준비한다. 자동 재료 확보·작업대 접근·조준은 없다.
이미 도구를 들고 있으면 추가 행동 없이 끝나며, 다른 핫바에 있으면 지정 slot으로 옮기지 않고 그 슬롯을 선택할 수 있다.
`tool_crafted_and_equipped`는 신규 제작이나 지정 슬롯 배치를 항상 증명하지 않는다.

`eligible=true`는 경로 성공·예약을 보장하지 않는다. 특히 craft_tool 조회는 기본 wooden_pickaxe/slot 0만 검사하므로
stone_pickaxe 등 다른 입력의 실행 조건을 검증하지 않는다. 실행 시 최신 관측과 capability를 다시 검사한다.
현재 도구 스킬은 중단 예외 타입 불일치도 있어 재료 부족 등의 조회/실행 실패가 정상 결과로 반환되지 않을 수 있다.
보완점과 검증 상태는 [진행 상태](PROGRESS.md)를 따른다.

에피소드는 skill.id/version/inputs, observationSchemaVersion, executionId, before/after, steps, result를 기록한다.
관측 전 실패한 경우 schema는 null이다. wood 성공은 전후 원목 합계를 비교하고,
craft_tool 성공은 장착 상태와 수량 조건을 검사하므로 각 스킬의 증거 의미를 구분한다.
행동·조건·성공 판정을 변경하면 버전을 갱신한다. 현재 각 ID는 한 버전만 지원하며 이전 버전으로 자동 대체하지 않는다.

## 확인 기준

목록·버전·예산을 확인하고 wood의 log_inventory_increased와 inventoryDelta>=1을 검사한다.
craft_tool은 제작이 실제 수행되었는지 steps와 재료/산출물 증거, 최종 선택 슬롯·손 아이템을 각각 확인한다.
실행 중 다른 창의 cancel로 다음 행동이 억제되는지도 검사한다. 전체 실게임 완료 여부는 PROGRESS에서 관리한다.
