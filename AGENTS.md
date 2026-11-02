> **현재 팀 기본 (v0.3.0-draft.1):** 육각 확장판 extensions/hex_v03에서 별도 가상환경으로 실행한다. 그 폴더의 AGENTS.md와 README.md가 현재 모델/기본 알고리즘 지침이다. 아래 루트 실행·사각 설정 설명은 이전 v0.2.0-draft.1 재현에 적용한다. 버전관리·태그 보존 규칙은 공통이다.

# AI 작업 지침 — BAAI Maritime DSS

먼저 README.md, PROJECT_CONTEXT_TEAM.md, docs/BASELINE.md, docs/TEAM_GUIDE.md를 읽는다.
이 저장소의 최상위 폴더에서 Python을 실행한다. 별도의 솔버·기상 API·AI API 키는 필요 없다.
모델 개선·GitHub 업로드·버전 배포 작업에서는 docs/VERSIONING.md와 docs/VERSIONS.md도 읽는다.
개선 코드는 작업 브랜치에 Push하고, main 병합과 새 태그/Release 생성은 해당 범위의 사용자 요청에 따른다.
Push만으로 새 버전이 생성되었다고 보고하지 않는다. 배포 태그는 실제 실행 소스 커밋을 가리키며 기존 태그는 이동하지 않는다.
작업 시작 시 원격의 최신 운영 지침을 확인한다. 미커밋 변경이 있으면 무리하게 Pull하지 말고 origin/main의 문서를 읽어 비교한다.
과거 태그에는 최신 운영 문서가 없을 수 있다. 과거 소스를 선택하기 전에 최신 main의 AGENTS.md와 docs/VERSIONING.md를 읽고 작업 맥락에 유지한다. 원래 태그를 수정하거나 지침 파일을 복사해 기준 실행 상태를 임의로 변경하지 않는다.
일반적인 개선·업로드 요청은 새 작업 브랜치, 변경에 맞는 검증, 커밋, Push와 PR 생성까지 수행한다. 사용자가 범위를 로컬/Push만으로 제한했다면 그 범위를 따른다.
main 반영을 요청받으면 PR과 검증·팀 검토 상태를 확인한 후 요청 범위에 맞게 병합한다. 재현 가능한 버전 배포까지 요청받으면 새 태그·Release·버전 목록 등록을 수행한다.

## 보존할 기준
- 배포 기준 태그: v0.2.0-draft.1. 정본 설정 configs/baseline.json, 태풍 생성기 trend-path-intensity-3x3-v1.
- 3시간 롤링, 내부 15분, 168시간 계획, 9개 경로×강도 시나리오, mean-CVaR λ=0.5/α=0.8.
- 모형/태풍 생성 규칙 변경은 사용자가 요청한 범위에서만 한다. 개선 실험은 별도 설정 파일과 작업 브랜치에 작성한다.
- 원본 태그·baseline.lock.json·시나리오 fixture를 테스트 통과만을 위해 덮어쓰지 않는다.
- 기존 outputs를 덮어쓰지 않는다. 새 실험마다 새 출력 폴더를 사용한다.
- sources/나 사용자의 다른 프로젝트 폴더는 편집하지 않는다.

## 작업과 검증
- .venv의 Python을 사용한다. 설치는 python scripts/bootstrap.py, 검증은 python -m unittest discover -s tests -v.
- 일반 개발에서는 python -m maritime_sim baseline이 changed여도 정상이다. 이것은 배포 원본과의 차이를 보여준다.
- 새 설정은 configs/experiments/에 저장한다. 실행 결과에는 Git 커밋/변경 여부와 설정·코드 해시가 자동 기록된다.
- 변경 목적·수정 파일·검증·남은 한계를 설명하고 docs/CHANGELOG.md와 PROJECT_CONTEXT_TEAM.md를 갱신한다.
- GitHub 업로드/PR/메시지 전송은 사용자의 해당 작업 지시에 따른다. 비밀키·개인 경로·가상환경·대용량 결과는 커밋하지 않는다.
- 전체 항해는 사용자가 요청했거나 배포 검증일 때만 실행한다. 기본 검증은 단위 검증과 작은 실행/보고서 점검이다.
- 실제 실행 비용과 의사결정 목적함수(미래 위험 조정 점수)를 구분하여 보고한다.
