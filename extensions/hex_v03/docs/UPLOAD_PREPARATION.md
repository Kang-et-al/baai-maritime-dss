# GitHub 공유 준비와 반영 계획

## 현재 상태

로컬 공유 후보 **v0.3.0-draft.1 / 0.3.0.dev1**이다. 번호는 배포 제안이며 원격 태그 생성·Push·PR·main 병합·Release는 하지 않았다. 원래 baseline과 이 독립 로컬 저장소의 이력은 보존했다.

확장판 저장소는 팀 저장소와 독립적인 Git 이력을 갖는다. 따라서 이 로컬 브랜치를 팀 저장소 main에 강제로 올리지 않는다. **팀 저장소 최신 main에서 작업 브랜치를 만들고, `extensions/hex_v03`에 확장판을 추가하는 방식**으로 통합한다. 기존 루트의 `maritime_sim`, configs/baseline.json, baseline.lock, 기존 tests·공유 문서는 그대로 유지한다.

## 준비된 자료

- `version-lock.json`: 현재 모델·알고리즘·설정·지도·고정 의존성 해시.
- `scripts/check_version.py`: 읽기 전용 정본/환경 검사.
- `scripts/prepare_upload.py`: 커밋된 소스만 별도 새 폴더에 모으는 패키지 생성기.
- `examples/reference/`: 기존 비교 KPI·t=3h 값 일치 검증·과거 실제 실행 identity와 복사 해시. 현재 실행기로 새 완주한 결과가 아니다.
- `sharing/.github/workflows/hex-v03.yml`: 별도 확장판 CI. 기존 CI를 덮어쓰지 않는다.
- `sharing/HEX_V03_INTEGRATION.md`: 기존 README/AI 안내/변경기록에 추가할 문구와 경로.
- `sharing/HEX_V03_PR_DRAFT.md`: 실제 변경·검증·한계를 담은 PR 본문 초안.

```powershell
# 소스·문서를 로컬 커밋한 뒤, 존재하지 않는 새 준비 폴더 지정
python scripts/prepare_upload.py --output release-prep/hex-v03-ready
```

생성물은 `github-overlay/`, ZIP, 파일 SHA256 manifest다. ZIP 루트는 팀 저장소에 **추가**할 상대 경로로 구성된다. 기존 파일 충돌이 없는지 먼저 검토한다. 가상환경·캐시·대형 outputs·이전 PDF/임시파일은 포함하지 않는다. 정본 검사 실패/미커밋 변경이 있으면 패키지 생성을 멈춘다.

## 업로드를 요청받은 다음에 할 일

1. 팀 저장소 최신 main의 AGENTS.md와 docs/VERSIONING.md 및 원격 태그를 다시 읽는다. 현재 로컬 원본 폴더를 수정하는 대신 별도 clone에서 진행한다.
2. `feature/<식별자>/hex-v03` 브랜치를 만든다. 다른 사람이 추가한 확장 경로/CI 이름과 충돌하는지 확인한다.
3. overlay를 반영하고 루트 README에 확장판 안내 링크, AI 지침에 확장 폴더별 실행 위치, CHANGELOG/PROJECT_CONTEXT_TEAM에 현재 상태를 추가한다. 원래 사각 baseline 정본은 유지한다.
4. 확장판의 새 venv로 정본 검사/작은 검증을 수행한다. 기존 루트 환경·테스트도 유지하여 기존 사용자 영향이 없는지 확인한다.
5. 문서·코드·작은 증거 파일만 커밋한다. 사용자 요청이 Push·PR까지면 그 작업만 수행한다. main 병합과 버전 배포는 별도 요청/팀 검토 범위다.
6. 원격 CI 통과와 PR 검토 후 병합을 요청받았을 때 병합한다. 아직 생성하지 않은 버전을 배포 완료로 기록하지 않는다.
7. 새 버전의 완주 재현 실험이 요청되면 **통합 후 실제 소스 커밋**에서 새 출력 폴더로 실행한다. 그 실행 커밋을 태그로 고정하고 결과 Release를 등록한다. 기존 완주 결과를 새 커밋의 실행으로 바꾸지 않는다.

## 버전·호환성

기존 `v0.2.0-draft.1`은 계속 이전 모형 재현 기준이다. 새 확장은 설정·상태·결과 형식이 달라 기존 CLI나 결과 등록 스크립트와 직접 호환되지 않는다. 확장판 폴더의 실행기/대시보드를 사용한다. 예전 outputs를 새 기본 실행기로 재개하지 않는다.

`v0.3.0-draft.1` 번호 사용 여부는 실제 배포 직전 원격에서 확인한다. 기존 태그 이동/삭제·강제Push는 하지 않는다. 새 기본 알고리즘은 이번에 고정했지만, 팀의 공통 baseline 승격 및 사각 기준 lock 갱신은 별도 합의 대상이다.

## 원격 운영 지침 사전 확인

2026-11-02에 GitHub main의 AGENTS.md와 docs/VERSIONING.md를 읽기 전용으로 확인했으며, 로컬 비교본과 같은 운영 규칙이었다. 확인 blob SHA는 각각 `34f2762a9ab5e127a87bbc7eb73411e29b4de7bb`, `8b7c3c68a3a4b7a869113cbc615c9d911434a68a`다. 이는 업로드 시점의 최신성 확인을 대신하지 않는다.

정본 lock의 텍스트 해시는 CRLF를 LF로 정규화한 SHA256이다(Windows/Linux Git 줄바꿈 차이 허용). 실행 identity 및 업로드 manifest는 실제 바이트 SHA256을 사용한다. 따라서 실행 재개 검사는 동일 파일 바이트를 요구하며 두 종류의 해시를 혼용하지 않는다.
