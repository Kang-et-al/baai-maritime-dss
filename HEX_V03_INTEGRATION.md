# 육각 확장판 통합 안내 (아직 반영 전)

이 문서는 GitHub 저장소 루트에서 읽는다. overlay의 `extensions/hex_v03/`와 새 CI 파일을 추가한 뒤 기존 파일에는 아래 내용을 **추가**한다. 기존 README 전체를 확장판 README로 덮어쓰지 않는다.

## 루트 README에 추가할 안내

### 육각·연속 운항 확장판 (공유 후보)

[확장판 소개·설치·실행](extensions/hex_v03/README.md) · [수학적 모델](extensions/hex_v03/docs/CURRENT_MATHEMATICAL_STRUCTURE_KO.md) · [기존 모델과의 차이](extensions/hex_v03/docs/BASELINE_DIFF.md) · [팀원/AI 안내](extensions/hex_v03/docs/TEAM_HEX_GUIDE.md)

기존 사각 baseline은 계속 이 저장소 루트에서 실행합니다. 확장판은 `extensions/hex_v03` 폴더를 열고 별도 가상환경을 구성하세요. 확장판의 기본 알고리즘은 고유 기상장1개일 때 전체DP 내부 병렬, 여러 개일 때 선택적DP 시나리오 병렬입니다. 기존 태그 v0.2.0-draft.1은 보존합니다.

## 루트 AGENTS.md에 추가할 분기

- 사용자가 사각 baseline을 요청하면 기존 루트 지침을 따른다.
- 육각/추진 반응 확장판을 요청하면 `extensions/hex_v03/AGENTS.md`, README, docs/VERSION_SPEC.md를 추가로 읽고 그 폴더를 실행 루트로 사용한다. 확장 설정·결과는 그 아래에서 관리한다.
- 상위 VERSIONING.md의 브랜치/PR/태그 불변 규칙은 양쪽에 적용한다. 확장 모형의 λ=0/α=.8은 원래 사각 baseline λ=.5와 별개다. 기존 lock을 확장 모형 기준으로 바꾸지 않는다.

## 팀 인계·변경기록에 추가할 사항

독립 확장 경로와 기본 자동 계산 정책, 작은 문제 검증, 보존한 과거 완주 증거, 새 자동 실행기의 전체 항해 재실행 미실시를 기록한다. docs/VERSIONS.md에는 실제 새 태그·Release가 생긴 뒤 등록하고, 지금은 미배포 후보로만 안내한다.

확장판의 manifest는 독립 소스 스냅샷 SHA와 파일 해시다. 팀 저장소에 통합한 커밋 SHA와 같지 않다. 새 실험에서 팀 저장소 통합 커밋·dirty 상태를 별도로 기록한다.
