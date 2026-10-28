# AI 작업 지침 — BAAI Maritime DSS

먼저 README.md, PROJECT_CONTEXT_TEAM.md, docs/BASELINE.md, docs/TEAM_GUIDE.md를 읽는다.
이 저장소의 최상위 폴더에서 Python을 실행한다. 별도의 솔버·기상 API·AI API 키는 필요 없다.
모델 개선·GitHub 업로드·버전 배포 작업에서는 docs/VERSIONING.md와 docs/VERSIONS.md도 읽는다.
개선 코드는 작업 브랜치에 Push하고, main 병합과 새 태그/Release 생성은 해당 범위의 사용자 요청에 따른다.
Push만으로 새 버전이 생성되었다고 보고하지 않는다. 배포 태그는 실제 실행 소스 커밋을 가리키며 기존 태그는 이동하지 않는다.

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
