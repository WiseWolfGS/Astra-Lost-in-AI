# AstraLostInAI

Minecraft Java **1.21.1 Survival**을 AI가 플레이하도록 만드는 프로젝트다.
최종 목표는 AI의 엔더 드래곤 격파이며, 인간 및 다른 AI와의 협업을 부가 목표로 한다.
전체 구현 과정과 완료 기준은 [MASTER PLAN](docs/MASTER_PLAN.md)에 정리했다.
Fabric 클라이언트 모드가 현재 플레이어의 관측과 제한된 행동을 제공하고,
별도 Docker 환경의 Python 에이전트와 Node.js 브리지가 이를 연결한다.

환경 관측, 직접 행동, Astra 단일 계획 호출, 원목 획득 스킬까지 구현했다.
자유 탐험·제작·자동 커리큘럼을 갖춘 완전한 자율 서바이벌 에이전트는 아직 아니다.
[Voyager](https://github.com/MineDojo/Voyager)의 스킬 저장·피드백·커리큘럼 개념을 참고하되
Mineflayer 대신 실제 Fabric 클라이언트를 사용한다.

## 저장소 범위

**Fabric 모드와 Python/Node/Docker 소스를 하나의 저장소에서 관리한다.** Docker 소스는 `docker/`에 있다.
실제 `.env`, 게임 설정, 로그·월드·에피소드 볼륨은 소스에 포함하지 않는다.
운영 설정 파일은 Git에서 제외되는 `docker/.env`를 기본으로 사용한다.
기존 외부 실행 폴더에서 이전하는 방법은 [Docker 실행 문서](docker/README.md#기존-환경-이관)를 따른다.
문서의 `C:\Projects\AstraLostInAI`와 `C:\Projects\AstraLostInAI\docker`는 **예시 경로**이며 실제 위치로 바꿔 사용한다.

## 구성

```mermaid
flowchart LR
  A[Python / LangChain] -->|단일 계획 요청| O[OpenAI Responses API]
  A -->|관측 / 제한된 행동| N[Node.js bridge :8765]
  F[Fabric client] -->|관측과 결과 polling| N
  N -->|행동| F
  F --> M[Minecraft Survival]
  A --> D[로컬 episode volume]
```

| 구성 | 설정된 버전 |
|---|---|
| Minecraft / Yarn | 1.21.1 / 1.21.1+build.3 |
| Java | 21 |
| Fabric Loader / API | 0.19.5 / 0.116.17+1.21.1 |
| Kotlin / Fabric Language Kotlin | 2.4.20 / 1.14.1+kotlin.2.4.20 |
| Loom / Gradle | 1.17.20 / 9.6.1 |
| Docker Python / Node | 3.12 / 24 |

Fabric 의존성은 Gradle 설정, Docker 의존성은 docker/agent/requirements.lock 및 docker/bridge/package-lock.json이 기준이다.
모델은 OPENAI_MODEL로 설정하며 현재 템플릿은 gpt-6-astra를 사용한다. API 계정의 모델 접근 권한이 필요하다.

## 실행

JDK 21을 설치하고 JAVA_HOME을 지정한다. Fabric 프로젝트를 빌드한다.

```powershell
cd C:\Projects\AstraLostInAI
.\scripts\dev.ps1 -Task build
```

새 환경은 PowerShell 7에서 아래를 실행한다. 기존 환경은 새 토큰을 만들기 전에 위 이관 문서를 확인한다.

```powershell
cd C:\Projects\AstraLostInAI\docker
.\setup.ps1
docker compose up -d --build
.\invoke-agent.ps1 -Operation health
```

setup은 .env와 게임 설정을 생성하고 기존 파일은 보존한다. 브리지 토큰은 양쪽에서 일치해야 한다.
인증 정보가 들어 있는 게임 설정과 .env는 로컬에만 보관한다.

```powershell
cd C:\Projects\AstraLostInAI
.\scripts\dev.ps1 -Task runClient
```

서바이벌 테스트 월드에 들어가 메뉴를 닫는다. F3+P로 포커스 상실 시 일시정지를 해제하면
다른 창에서 명령을 보낼 수 있다. 메뉴·월드 전환·통신 오류 시 진행 중 제어를 중단한다.
일반 런처에서는 빌드한 모드와 Fabric API/Language Kotlin을 설치하고, setup의 설정 경로를
해당 인스턴스의 config 폴더로 지정한다.

## 행동과 목표

| 명령 | 동작 | 모델 호출 |
|---|---|---|
| observe / perception | 원본 관측 / 환경 요약 | 없음 |
| approach | 수평 4블록 이내 블록으로 평지 접근 | 없음 |
| mine | 현재 도구와 조준 대상으로 단일 블록 채굴 | 없음 |
| collect | 관측된 아이템으로 이동 후 획득 검증 | 없음 |
| select-hotbar | 핫바 0~8번 슬롯 직접 선택 | 없음 |
| craft | 개인 2×2 제작 칸에서 레시피 1회 제작 | 없음 |
| place-workbench | 손에 든 작업대를 조준된 바닥 블록 윗면에 설치 | 없음 |
| wood | 최대 3행동·60초로 원목 인벤토리 증가 시도 | 없음 |
| step | 관측 → 계획 한 번 → 행동 하나 | DRY_RUN=false에서 호출 |

직접 행동과 wood는 **DRY_RUN=true여도 실제 게임에서 실행**한다.
step은 기본 DRY_RUN=true에서 관측·기록만 수행한다. 유료 실행은 .env의 OPENAI_API_KEY와
DRY_RUN 설정을 바꾸고 컨테이너에 반영한 뒤 명시적으로 요청한다. 자동 유료 반복 호출은 없다.

```powershell
cd C:\Projects\AstraLostInAI\docker
.\invoke-agent.ps1 -Operation perception
.\invoke-agent.ps1 -Operation wood
```

wood 성공은 result.reason=log_inventory_increased와 inventoryDelta>=1로 확인한다.
개별 행동 completed나 HTTP 200만으로 목표 달성을 판정하지 않는다.
실패 원인은 result.actionReason과 safetyFailure에서 확인한다. 원본 출력은 -FullRecord로 요청한다.
실행 중 원격 취소는 다른 PowerShell에서 `./invoke-agent.ps1 -Operation cancel`로 요청한다.
입력 해제 확인과 사용법은 [취소 프로토콜과 테스트](docs/CANCELLATION.md)를 따른다.
긴급 수동 중단은 게임 메뉴를 연다. 기존 stop 행동은 실행 큐를 선점하지 않는다.

서비스는 호스트 loopback 포트 8000/8765를 사용한다. health 이외 API는 bearer 인증이 필요하다.
관측은 9×6×9 로컬 블록 격자·엔티티·조준 대상·인벤토리를 포함하며 이미지 인식 기반은 아니다.

## 검증과 문서

[문서 안내](docs/README.md)에서 사용법·진행 상태·오류 보고서를 찾을 수 있다.

Fabric 빌드와 Java 39개, Python 135개·Node 26개 테스트 및 합성 취소 연결 시험을 통과했다.
돌 도구 5종 제작을 추가했다. 재료 준비와 실게임 확인은 [돌 도구 테스트](docs/STONE_TOOLS.md)를 따른다.
이전 커밋의 GitHub CI 두 작업과 보고서는 사용자가 성공을 확인했다. 이번 취소 변경의 원격 CI는 Push 후 확인한다.
사용자가 취소 명령 및 핫바 선택, 2×2 제작의 실제 월드 테스트 성공을 확인했다.
실제 월드에서 동일 실패 위치의 드롭 수집과 approach→mine→collect 전체 목표 성공을 확인했다.
이는 모든 지형·서버 환경을 검증했다는 뜻은 아니다.

- [개발 계획과 완료 기준](docs/ROADMAP.md)
- [현재 진행 상태](docs/PROGRESS.md)
- [관측 규약](docs/OBSERVATION.md)
- [핫바 선택·인벤토리 제어](docs/INVENTORY.md)
- [2×2 제작 규약](docs/CRAFTING.md)
- [작업대 설치 및 상호작용](docs/WORKBENCH.md)
- [채굴 규약](docs/MINING.md)
- [평지 접근·수집](docs/NAVIGATION.md)
- [원목 목표와 사용자 테스트](docs/WOOD_GOAL.md)
- [버전별 스킬 조회·실행](docs/SKILLS.md)
- [이동 오류 수정 보고서](docs/NAVIGATION_FIX.md)
- [공개 저장소 포함·제외 기준](docs/PUBLISHING.md)
- [Docker 설치·이관·격리 테스트](docker/README.md)
- [CI 실행 조건·로컬 재현·보고서](docs/CI.md)

원본 에피소드, 월드 세이브, 개인 실행 명령 기록과 인증 정보는 공개 문서에 포함하지 않는다.
