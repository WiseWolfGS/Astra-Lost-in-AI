# 문서 안내

현재 구현과 검증 결과는 [진행 상태](PROGRESS.md), 후속 작업은 [개발 계획](ROADMAP.md)을 기준으로 한다.
엔더 드래곤 격파와 인간·AI 협업까지의 전체 과정은 [MASTER PLAN](MASTER_PLAN.md)을 따른다.
설치와 실행은 [프로젝트 README](../README.md)와 [Docker 문서](../docker/README.md)를 따른다.

| 목적 | 문서 |
|---|---|
| 최종 목표·단계별 완료 기준 | [MASTER PLAN](MASTER_PLAN.md) |
| 관측 데이터 형식 | [관측 규약](OBSERVATION.md) |
| 핫바 선택·인벤토리 제어 | [인벤토리 규약](INVENTORY.md) |
| 개인 제작 칸의 판자·막대·작업대 제작 | [2×2 제작](CRAFTING.md) |
| 직접 채굴·이동·수집 | [채굴](MINING.md), [평지 접근·수집](NAVIGATION.md) |
| 원목 목표·버전 지정 실행 | [wood 동작](WOOD_GOAL.md), [스킬 등록](SKILLS.md) |
| 실행 상태 조회·취소 | [취소 규약](CANCELLATION.md) |
| 테스트 실행·CI 보고서 | [CI](CI.md) |
| Commit/Push 전 포함·제외 기준 | [공개 저장소 기준](PUBLISHING.md) |

## 오류 분석과 수정 이력

- [이동 오류 수정](NAVIGATION_FIX.md): 충돌 여유 폭과 경유점 감속 문제.
- [수집 경로 수정](COLLECTION_PATH_FIX.md): 정지 위치 후보 제한과 예산 내 재탐색.
- [후보 선택 실패 진단](WOOD_FAILURE_DIAGNOSIS.md): 높이·거리 제한으로 행동 시작 전 종료된 사례.

수정 이력의 테스트 수는 당시 기준일 수 있다. 현재 전체 테스트 수와 미검증 범위는 PROGRESS.md에서 확인한다.
문서의 예시 경로는 실제 저장소 위치로 바꿔 사용한다. 인증 정보와 원본 월드 기록은 공개 문서에 포함하지 않는다.
