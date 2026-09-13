# 지속적 통합(CI)

설정: [.github/workflows/ci.yml](../.github/workflows/ci.yml).
Push, pull request, 수동 workflow_dispatch에서 두 작업을 실행한다.
같은 브랜치의 새 실행은 이전 실행을 취소한다. Commit/Push·릴리스 배포·실제 게임 실행을 자동 수행하지 않는다.

| 작업 | 실행 | 결과 |
|---|---|---|
| Fabric build and tests | Ubuntu 24.04, Java 21, 저장소 Gradle wrapper의 build | 모드 컴파일·패키징·Java 테스트 |
| Agent, bridge and isolated transport | Ubuntu 24.04, PowerShell 7, scripts/test-docker.ps1 | Docker 빌드·Python/Node 테스트·합성 연결 시험 |

작업 시간 상한은 Fabric 25분, Docker 20분이다. 저장소 권한은 contents:read이며 checkout 인증을 남기지 않는다.
GitHub 공식 Actions를 커밋 SHA로 고정하고, 버전 설명을 주석으로 기록했다.
이는 [GitHub의 Actions 보안 지침](https://docs.github.com/en/actions/reference/security/secure-use)을 따른다.
사용한 공식 액션은 [checkout](https://github.com/actions/checkout), [setup-java](https://github.com/actions/setup-java),
[upload-artifact](https://github.com/actions/upload-artifact)다.

## 운영 설정과의 분리

운영은 docker/.env를 사용한다. 이 파일은 Git에 넣지 않으며 CI secret으로도 등록할 필요가 없다.
CI 스크립트는 --env-file docker/.env.example과 compose.smoke.yaml을 명시적으로 선택한다.
테스트 환경의 OpenAI 키는 빈 값, DRY_RUN은 true이며 실제 Minecraft 포트와 운영 볼륨을 사용하지 않는다.
각 실행에는 별도 Compose 프로젝트 이름을 부여한다.
스킬 단위 테스트의 행동 실행은 모의 객체이며, 연결 시험은 합성 클라이언트 메시지만 전송한다.

## 로컬에서 동일한 검사 실행

PowerShell 7, JDK 21, Docker Desktop이 필요하다. 저장소 루트에서:

```powershell
.\scripts\dev.ps1 -Task build
.\scripts\test-docker.ps1
```

Docker 스크립트는 시험 결과를 확인하고 테스트 컨테이너·네트워크·자동 생성 이미지를 정리한다.
운영 astralostinai 프로젝트에는 down을 실행하지 않는다.
키를 출력할 수 있는 운영 docker compose config는 로그에 남기지 않는다.

## 실패 진단

GitHub 실행의 Artifacts에서 다음 자료를 7일간 받을 수 있다.

- fabric-test-reports: Gradle HTML 및 JUnit XML.
- docker-test-reports: Python JUnit XML, Node 시험 출력, 합성 연결 출력, 격리 서비스 상태·로그.

로컬 Docker 보고서는 Git 제외 경로인 local/ci-results/docker에 저장된다.
새 실행은 이전 보고서를 교체하므로 실행이 시작조차 못했을 때 과거 성공 결과를 재사용하지 않는다.
일반적인 실패에서도 로그 회수와 정리를 시도한다. 프로세스 강제 종료나 Docker 엔진 중단은 수동 정리가 필요할 수 있다.
Python 보고서는 Docker cp로 회수할 수 있도록 /tmp에 기록한다. 합성 에피소드용 /data는 메모리 마운트다.

## 검증 상태

로컬 Fabric build 성공(Java 37개), Python 129개·Node 26개 및 합성 연결·취소 확인 시험 통과.
보고서 생성·회수와 테스트 환경 정리까지 검증했으며 actionlint로 워크플로 구문을 확인했다.
Linux용 wrapper 줄바꿈은 .gitattributes에서 LF로 고정하고 bash로 실행한다.

2026-09-12 사용자가 이전 커밋의 GitHub 호스팅 CI 두 작업과 보고서의 성공을 확인했다.
이번 작업대 설치 변경의 원격 결과는 다음 Commit/Push 후 별도로 확인한다.
새 컴퓨터에서의 실제 게임 설치·실게임 행동 검증 역시 이 자동 테스트에 포함되지 않는다.
