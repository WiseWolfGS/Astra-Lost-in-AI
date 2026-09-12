# 환경 관측 schema 1

전송 프로토콜 1의 observation.environment에 추가된 선택 필드다.
구형 클라이언트의 기존 관측/행동은 유지되고, 요약 API는 client_upgrade_required로 업그레이드 필요를 표시한다.

## 의미와 범위

Fabric이 클라이언트 스레드에서 약 5틱마다 캡처한다. 이 센서는 이미지 인식이 아니라 로컬 게임 데이터에 접근한다.
블록은 가려져 있거나 시야 밖에 있어도 범위 안의 로드된 데이터라면 포함된다. 청크를 새로 요청하거나 생성하지 않는다.
Y 좌표가 월드 높이 밖이거나 청크가 로드되지 않았으면 unknown이다.
[Yarn WorldView](https://maven.fabricmc.net/docs/yarn-1.21.1+build.3/net/minecraft/world/WorldView.html)와
[LivingEntity](https://maven.fabricmc.net/docs/yarn-1.21.1+build.3/net/minecraft/entity/LivingEntity.html)의 1.21.1 API를 사용한다.

| 필드 | 의미 |
|---|---|
| schema / available | 1 / 캡처 가능 여부 |
| source | local_loaded_world |
| sampledAt / worldTime | 호스트 Unix 밀리초 / 월드 tick |
| terrain.origin | 플레이어 발 블록 좌표에서 (-4,-2,-4) |
| terrain.size | [9,6,9], x/y/z 크기 |
| terrain.order | y,z,x; x가 가장 빨리 변함 |
| terrain.palette | 최대 128개 블록 설명 |
| terrain.cells | 486개 정수, 팔레트 인덱스 |
| unknownCells / omittedCells | 값 -1 / 값 -2의 개수 |
| entities | 반경 8블록의 최대 16개 엔티티 |
| entitiesTruncated | 후보 검사/결과 상한에 도달했을 가능성 |
| target | 현재 crosshair의 block/entity/miss |

cells 인덱스는 ((y-originY) × 9 + (z-originZ)) × 9 + (x-originX)다.
-1은 미로드/높이 밖, -2는 팔레트 상한으로 생략된 값이다. 둘 다 공기가 아니다.
팔레트에는 id, air, collision, fluid, potentialHazard를 넣는다.
collision은 충돌 형상이 비어 있지 않다는 뜻이며 완전한 큐브나 보행 가능한 바닥을 의미하지 않는다.
잠재 위험 목록은 용암·불·선인장·마그마·베리 덤불·가루눈·위더 장미·모닥불·뾰족한 점적석이다.
표시는 보수적인 종류 분류여서 꺼진 모닥불도 포함하고, 낙하/질식 등 모든 위험을 탐지하지는 않는다.

엔티티는 살아 있고 invisible이 아니며 거리 8 이내인 후보를 가까운 순으로 최대 64개 검사한다.
player.canSee 가림 검사를 통과한 최대 16개를 전달한다. 이 검사는 카메라 시야각 제한을 적용하지 않는다.
사용자 이름이나 엔티티 표시 이름은 모델에 보내지 않는다. entity ID는 현재 세션에서만 의미가 있다.
ItemEntity에는 item(아이템 ID), count, onGround를 추가한다. 수집 요청은 현재 관측의 entity ID를 사용한다.
target은 게임의 현재 crosshairTarget을 사용하며, 해당 블록 좌표·면·거리 또는 엔티티 ID·종류·거리를 제공한다.
target은 그 블록의 채굴/수집 성공을 보장하지 않는다.
채굴 확장에서는 block target에 canHarvest(현재 도구), hardness, inReach가 추가된다.
player에는 selectedSlot과 mainHand의 아이템·개수·damage·maxDamage가 추가된다.

전송 JSON이 60,000바이트를 넘으면 environment를 available=false, reason=payload_limit로 대체한다.
Node의 요청 상한 64 KiB 안에서 기본 관측 전송을 유지하기 위한 처리다.

## Python 요약

GET /v1/perception은 bearer 인증이 필요하며 OpenAI를 호출하지 않는다.
정상 요약에는 블록 개수, 가까운 종류별 대표 위치 최대 24개,
here/north/south/west/east의 below/feet/head 블록, 엔티티와 target이 포함된다.
north=-Z, south=+Z, west=-X, east=+X로 플레이어 시선과 무관한 월드 방향이다.
blockCounts에는 air가 포함되며 nearestBlockTypes에서는 air를 제외한다.
관측이 없거나 격자 규약이 맞지 않으면 available=false와 이유를 반환한다.
connected=false인 과거 관측은 현재 월드 상태로 사용하면 안 된다.

모델은 요약을 받아 블록 전체 격자의 반복 전송 비용을 줄인다.
대표 위치만으로 그 블록까지의 경로를 알 수 없으며, 인접 열 검사는 경로 탐색이나 안전 검증이 아니다.
에피소드 before/after에는 전체 원본 격자가 남는다.

## 적용 및 수락 시험

Docker agent는 갱신된 이미지로 실행한다. Fabric은 기존 게임을 정상 종료한 뒤 프로젝트에서:

```powershell
.\scripts\dev.ps1 -Task runClient
```

테스트 월드에 들어가 F3+P로 포커스 상실 시 일시정지를 해제하고 메뉴를 닫는다.
Docker 폴더에서:

```powershell
.\invoke-agent.ps1 -Operation perception
```

1. connected=true, perception.available=true인지 확인한다.
2. here.below가 발 아래 블록과 일치하는지 확인한다.
3. 블록을 바라보면 target.type=block과 좌표가 맞고, 하늘을 바라보면 miss가 되는지 확인한다.
4. 가까운 나무·물·장애물의 종류와 대표 좌표를 실제 위치와 비교한다.
5. 엔티티를 가까이 두고, 반경·가림에 따른 포함 여부를 확인한다. 빈 entities는 주변 조건에 따라 정상이다.
6. 메뉴 진입/월드 종료로 ready 또는 connected가 달라지는지 기존 observe 명령으로 확인한다.

관측만 확인하는 위 시험은 유료 호출을 발생시키지 않는다.
실제 Astra 입력 전달을 재확인하려면 아래를 한 번 실행한다(현재 DRY_RUN=false이면 과금 가능).

```powershell
.\invoke-agent.ps1 -Operation step -Goal '주변 관측의 블록 종류를 reason에 요약하고 stop 행동을 선택해라.'
```

2026-09-12 사용자 후속 보고로 환경 관측 실게임 시험을 통과했다.
작업 시작 시 읽은 마지막 관측에서도 available=true, 486칸, 원목/잎 종류와 block target을 확인했다.
이때 connected=false였으므로 해당 자료는 마지막 저장 관측으로 해석했다.
신규 채굴 기능의 시험 상태는 [채굴 문서](MINING.md)에서 별도로 관리한다.
