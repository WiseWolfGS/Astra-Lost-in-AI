# 공개 저장소 포함·제외 기준

## 포함할 파일

- Fabric 소스·테스트·Gradle 설정·wrapper 스크립트 및 wrapper JAR.
- 공개용 README, API/동작 규약, 일반화한 오류 보고서, 개발 계획.
- 비밀값이 없는 설정 템플릿. 환경변수 이름·loopback 포트·예시 좌표는 비밀값이 아니다.
- docker/의 Python/Node 소스·테스트·Dockerfile·Compose 파일·lockfile·실행 도구 및 .env.example.
- compose.smoke.yaml의 토큰은 외부에 포트를 공개하지 않는 합성 시험용 공개 상수이며 운영 인증 정보가 아니다.

## 로컬에만 둘 파일

- .env와 변형 파일, API 키, 브리지 토큰, 개인키.
- 실제 토큰이 들어 있는 astralostinai-bridge.json.
- run 폴더의 월드·게임 설정·사용자 식별 데이터, 빌드·캐시·IDE 상태.
- episodes*.jsonl, promptlog*.txt, *.log와 개인 실험 스크립트.

공개 문서에는 개인 절대 경로·현재 계정 설정·원본 에피소드 ID·원본 월드 관측을 옮기지 않는다.
버그 설명에 필요한 수치나 합성 좌표는 남길 수 있다. 실제 API 키 대신 명확한 placeholder를 사용한다.

## 직접 Commit/Push하기 전 확인

```powershell
git status --short
git diff --check
git diff --cached --stat
git diff --cached
```

.gitignore는 이미 추적된 파일을 제거하거나 이미 노출된 키를 무효화하지 않는다.
파일을 선택해 스테이징한 뒤 최종 diff를 다시 확인한다. 이번 문서 정리는 기존 인덱스를 변경하지 않았다.
AM 표시는 이미 staged인 파일을 추가로 수정했다는 뜻이므로 최신 수정까지 포함할지 확인해야 한다.
원격 저장소와 과거 모든 이력에 대한 비밀 탐지는 이번 작업 범위에 포함하지 않았다.

현재 문서·추적 후보·인덱스에서 로컬에 설정된 키/토큰과 일치하는 문자열 및 대표적인
키 패턴을 확인했으며 실제 비밀값은 발견되지 않았다. 이는 모든 형식의 비밀을 보장하는 검사는 아니다.
