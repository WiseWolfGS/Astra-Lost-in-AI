# 문서 안내

처음 읽는 순서: **[프로젝트 분석·진행 상태](PROGRESS.md) → [다음 작업](ROADMAP.md) → [전체 계획](MASTER_PLAN.md)**.
현재 상태·최신 테스트 결과는 PROGRESS 한 곳에서 관리한다. 기능 문서는 명령·제약·성공 증거,
오류 보고서는 과거 원인과 회귀 조건을 설명한다. 2026-09-25에 중복 설명과 오래된 다음 작업을 압축했다.

| 목적 | 문서 |
|---|---|
| 설치·실행 | [프로젝트 README](../README.md), [Docker](../docker/README.md) |
| 관측 | [환경 스키마](OBSERVATION.md) |
| 이동·채굴·수집 | [채굴](MINING.md), [평지 이동](NAVIGATION.md), [원목 목표](WOOD_GOAL.md) |
| 인벤토리 | [핫바 선택](INVENTORY.md), [슬롯 교환](HOTBAR_TRANSFER.md) |
| 제작 | [2×2](CRAFTING.md), [작업대 설치](WORKBENCH.md), [3×3](WORKBENCH_CRAFTING.md), [돌 도구](STONE_TOOLS.md) |
| 스킬·실행 제어 | [스킬 조회·실행](SKILLS.md), [취소](CANCELLATION.md) |
| 개발·공개 | [CI](CI.md), [공개 저장소 기준](PUBLISHING.md) |
| 오류 이력 | [충돌·감속](NAVIGATION_FIX.md), [수집 경로](COLLECTION_PATH_FIX.md), [후보 범위](WOOD_FAILURE_DIAGNOSIS.md) |

## 공통 실행·검증 규칙

명령 예시는 저장소 루트 기준이며 운영 설정은 Git 제외 `docker/.env`다.
모드를 수정했다면 게임을 저장·정상 종료한 후 `./scripts/dev.ps1 -Task runClient`로 다시 실행한다.
서바이벌 테스트 월드에서 메뉴를 닫고 F3+P로 포커스 상실 일시정지를 해제한다.
`observe`의 connected/ready와 필요한 capability를 확인한 뒤 기능별 시험을 수행한다.

- 직접 행동과 스킬은 **DRY_RUN=true에서도 실제 게임을 조작**하며 모델을 호출하지 않는다.
- `step`만 DRY_RUN=true에서 관측·기록으로 끝나고, false에서는 단일 모델 계획과 행동을 실행한다.
- health 외 API는 bearer 인증이 필요하다. 동시 실행은 409로 거절한다.
- HTTP 200이나 개별 행동 completed를 목표 달성으로 해석하지 않는다. 각 문서의 성공 증거를 확인한다.
- 취소는 후속 행동·입력을 멈춘다. 이미 보낸 제작·설치·교환을 되돌리지 않으므로 지연 결과와 인벤토리를 확인한다.
- 실제 월드 확인은 자동·합성 시험과 구분한다. 원본 관측·에피소드·인증 정보는 공개 문서에 넣지 않는다.

기존 파일명은 링크 호환을 위해 유지했다. 전체 분석에서 확인한 코드 보완점은 PROGRESS에 기록한다.
