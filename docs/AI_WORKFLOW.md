# AI 작업 요청 예시

로컬 폴더 접근이 가능한 도구에는 이 저장소를 열어 줍니다. 특정 AI 서비스에 종속되지 않습니다.
파일 접근이 없는 채팅에서는 필요한 소스와 오류를 첨부하고 제안받은 변경을 직접 적용해야 합니다.

## 처음 설치

> AGENTS.md, README.md, PROJECT_CONTEXT_TEAM.md를 읽고 Python 3.12 가상환경을 구성해줘.
> requirements-lock.txt를 설치하고 단위 검증을 실행한 뒤 한 스텝의 실시간 실험을 새 outputs 폴더에 실행해줘.
> dashboard.html을 열어줘. 기준 모형과 태풍 생성 규칙은 변경하지 마.

## 실험

> v0.2.0-draft.1을 기준으로 새 브랜치를 만들고 risk.lambda만 0.0인 설정을
> configs/experiments/mean_only.json에 작성해줘. baseline.json은 유지해줘.
> 완주 재생 실험을 새 폴더에서 실행하고 실제 비용·시간·연료와 위험 평가 점수를 구분해서 설명해줘.
> register_result.py로 결과를 등록하고 업로드할 변경 사항을 보여줘.

## 개발

> AGENTS.md와 PROJECT_CONTEXT_TEAM.md를 읽고 현재 커밋·작업 상태를 확인해줘.
> [원하는 변경]을 별도 작업 브랜치에서 구현하고 필요한 검증을 수행해줘.
> 기존 결과와 배포 lock은 덮어쓰지 말고 변경 이력과 인계 문서를 갱신해줘.
> GitHub 업로드·PR은 내가 요청한 경우에 진행해줘.

AI가 테스트를 통과시키려고 lock/fixture를 덮어쓰지 않도록 합니다.
평균 기준의 과거 결과를 mean-CVaR 결과로 표기하거나 실행하지 않은 실험을 완료했다고 보고하지 않습니다.
