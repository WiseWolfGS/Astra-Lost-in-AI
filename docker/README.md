# Docker 실행 환경

이 폴더는 Fabric 모드와 같은 저장소에서 관리하는 Python 에이전트·Node.js 브리지 소스다.
[프로젝트 README](../README.md), [개발 계획](../docs/ROADMAP.md)을 함께 참고한다.
실제 키·토큰·로그·월드·에피소드는 버전 관리 대상이 아니다.

## 새 설치

JDK 21, Docker Compose가 포함된 Docker Desktop, PowerShell 7을 준비한다.
저장소를 clone한 뒤 이 docker 폴더에서:

```powershell
.\setup.ps1
docker compose up -d --build --wait
.\invoke-agent.ps1 -Operation health
```

setup은 docker/.env와 저장소의 run/config/astralostinai-bridge.json을 생성한다.
둘 다 Git 제외 대상이며 기존 파일을 덮어쓰지 않는다. 일반 런처는 -MinecraftConfigDirectory를 지정한다.
이후 저장소 루트의 scripts/dev.ps1 -Task runClient로 실행하고 서바이벌 월드에 들어간다.
F3+P로 포커스 상실 시 일시정지를 해제하고 메뉴를 닫는다.

```powershell
.\invoke-agent.ps1 -Operation observe
.\invoke-agent.ps1 -Operation wood
```

## 기존 환경 이관

운영 설정은 저장소의 **docker/.env**로 통일한다. 기존 값을 이 파일로 옮겼다면
setup을 다시 실행하거나 토큰을 새로 만들 필요는 없다. 파일은 Git에서 계속 제외된다.
명령은 **저장소의 docker 폴더**에서 실행한다.

```powershell
.\compose.ps1 -ComposeArguments @('up','-d','--build','--wait')
.\invoke-agent.ps1 -Operation health
.\invoke-agent.ps1 -Operation observe
.\invoke-agent.ps1 -Operation wood
```

compose.ps1은 현재 작업 위치와 무관하게 이 폴더의 Compose 파일과 빌드 컨텍스트를 사용한다.
Docker 옵션은 PowerShell 옵션과 충돌하지 않도록 -ComposeArguments 배열로 전달한다.
예를 들어 pytest의 -p를 wrapper에 직접 나열하면 PowerShell 공통 매개변수로 해석될 수 있다.
invoke-agent와 setup도 -EnvFile을 지원한다. 생략하면 docker/.env를 사용하며 외부 파일을 자동 검색하지 않는다.
다른 문서의 실행 예시도 docker/.env 기준이다. -EnvFile은 별도 실험 설정이 필요할 때만 사용하는 선택 기능이다.

Compose 프로젝트 이름 astralostinai와 데이터 볼륨 astralostinai_agent-data는 유지한다.
이관 전 실행 중인 행동을 끝내고 컨테이너를 재생성한다. 재생성 중에는 브리지 연결이 잠시 끊긴다.
새 경로로 바꿔도 기존 에피소드와 인증값은 유지되며 게임 설정의 토큰을 바꿀 필요가 없다.
기존 외부 소스는 삭제하지 않았지만 이후 수정·빌드의 기준은 이 저장소다.
외부 폴더에서 예전 Compose를 다시 실행하면 구버전으로 되돌아갈 수 있다.
볼륨을 삭제하는 down -v는 이관 과정에서 사용하지 않는다.

## 검증

실제 키나 게임 연결이 필요 없는 격리 환경:

저장소 루트에서 `.\scripts\test-docker.ps1`을 실행하면 CI와 같은 시험·보고서 저장·정리를 수행한다.
실제 docker/.env가 있어도 읽지 않고 .env.example을 명시적으로 사용한다.
자세한 GitHub 실행 조건과 보고서는 [CI 문서](../docs/CI.md)를 참조한다.
다음은 개별 명령을 직접 실행하는 방법이다.

```powershell
docker compose -f compose.smoke.yaml up -d --build --wait
try {
    docker compose -f compose.smoke.yaml exec -T agent python -m pytest -q -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) { throw 'Python tests failed' }
    docker compose -f compose.smoke.yaml exec -T bridge npm test
    if ($LASTEXITCODE -ne 0) { throw 'Node tests failed' }
    docker compose -f compose.smoke.yaml exec -T agent python smoke.py
    if ($LASTEXITCODE -ne 0) { throw 'Transport smoke test failed' }
} finally {
    docker compose -f compose.smoke.yaml down
}
```

smoke Compose는 별도 프로젝트·네트워크, 메모리 데이터 디렉터리, 공개 테스트 토큰을 사용한다.
호스트 포트와 운영 볼륨을 사용하지 않고 OPENAI_API_KEY를 비우며 DRY_RUN=true로 고정한다.
운영 Minecraft가 연결되어 있어도 격리 시험이 그 연결을 대체하지 않는다.
일반 compose.yaml의 실행 중 agent에서 smoke.py를 실행하는 것은 다른 작업이므로 혼동하지 않는다.

통합 시 두 이미지 빌드, Python 56개·Node 10개 테스트, 합성 관측→dry-run 기록→행동 전달→완료 응답을 확인했다.
setup의 신규 생성·토큰 일치·기존 파일 보존과 외부 EnvFile 사용도 확인했다.
Fabric 게임 코드는 이번 통합에서 변경하지 않았고 이전 Java 20개 테스트 결과를 유지한다.
CI 워크플로와 공통 실행 스크립트를 추가했고 사용자가 이전 커밋의 GitHub CI 성공을 확인했다.
독립된 새 컴퓨터의 전체 설치는 후속 확인 사항이다. 최신 검증 기준선은 [진행 상태](../docs/PROGRESS.md)를 따른다.

## 동작과 데이터

step은 DRY_RUN=true에서 모델 호출과 게임 행동을 생략한다. 직접 mine/approach/collect와 wood는
DRY_RUN과 무관하게 실제 게임 행동을 실행하며 모델을 호출하지 않는다.
유료 단일 step은 API 키와 모델·DRY_RUN 설정을 지정하고 컨테이너에 반영한 뒤 사용한다.
wood는 최대 3행동/60초다. log_inventory_increased와 inventoryDelta>=1을 성공 기준으로 사용한다.
기본 출력은 결과 중심이며 -FullRecord로 원본 관측을 포함한다.
실패 이유는 result.actionReason과 safetyFailure에서 확인한다.
wood@1.0.0의 등록 목록·사전 조건·버전 지정 실행은 [스킬 문서](../docs/SKILLS.md)를 따른다.

서비스는 loopback 8000/8765를 사용하며 health 이외 API에는 bearer 인증이 필요하다.
에피소드는 운영 데이터 볼륨에 저장된다. 일반 down은 볼륨을 유지한다.
실제 .env·게임 설정·원본 로그·에피소드를 공개 저장소에 올리지 않는다.
