# 공개 저장소 포함·제외 기준

포함: Fabric/Python/Node 소스·테스트, Gradle wrapper·lockfile, Dockerfile·Compose·실행 도구,
비밀값 없는 설정 템플릿과 공개 문서. smoke Compose의 공개 테스트 토큰은 운영 인증 정보가 아니다.

제외: `.env`와 변형 파일·API 키·브리지 토큰·개인키, 실제 설정 JSON,
`run/` 월드·개인 설정·식별 데이터, 빌드·캐시·IDE 상태, 원본 에피소드·로그·개인 실험 기록.
문서에는 개인 절대 경로·계정 설정·원본 실행 ID·월드 관측 대신 placeholder와 최소 합성 재현을 사용한다.

## Commit/Push 전 확인

```powershell
git status --short
git diff --check
git diff --cached --stat
git diff --cached
```

파일을 선택해 스테이징하고 인덱스를 다시 확인한다. `.gitignore`는 이미 추적된 파일을 제거하거나 노출된 키를 무효화하지 않는다.
AM은 staged 이후 추가 수정 상태다. 링크·ignore·비밀값 검사는 실행 범위와 결과를 구분해 기록하며,
과거의 검사 성공을 현재 변경이나 저장소 전체 이력의 비밀 부재 증거로 재사용하지 않는다.
