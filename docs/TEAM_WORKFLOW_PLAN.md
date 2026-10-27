# 팀 로컬 실험·버전 관리 환경 설계안

작성일: 2026-10-27. 이 문서는 실행 전 설계안의 보존본이다. 실제 운영은 TEAM_GUIDE.md, 최신 상태는 PROJECT_CONTEXT_TEAM.md를 따른다. 무료 운영을 단순화하기 위해 실제 Actions는 자동 PR 검증 대신 수동 실행으로 구성했다.

## 1. 권장 환경

- 중앙 저장소: `baai-maritime-dss`라는 이름의 GitHub 비공개 저장소 1개. 초기에는 담당자 개인 소유 + 팀원 collaborator로 시작한다. 저장소명은 제안이다.
- 팀원 실행: Python 3.12, 프로젝트별 `.venv`, `requirements-lock.txt`의 의존성 버전 사용.
- 작업 도구: 각자 사용하는 편집기와 로컬 파일을 다룰 수 있는 AI 도구. 특정 AI 제공업체를 실행 필수조건으로 두지 않는다.
- Git 작업: 명령줄 또는 GitHub Desktop. 복제, 브랜치 생성, 커밋, 푸시, PR은 같은 절차를 따른다.
- 자동검증: GitHub Actions. PR마다 단위/회귀검증과 짧은 실행·보고서 생성 검증. 완주 실행은 수동 또는 릴리스 준비 시 수행한다.
- 결과 열람: 기존 오프라인 HTML 대시보드·PNG·CSV를 유지한다. 초기에는 별도 웹 서버·데이터베이스·클라우드 실행 환경을 추가하지 않는다.

## 2. 보존할 기준과 발전할 코드

`main`은 팀이 검토하고 통합한 최신 버전이다. 최초 기준본은 `v0.2.0-draft.1` 같은 Git 태그와 Release로 보존한다. 현재 Python 패키지 버전 0.2.0과 일관된 첫 초안 태그의 예시이며 실제 발행 전 확정한다. 태그가 가리키는 기준 커밋은 이동시키지 않는다.

현재 baseline은 `busan-hongkong-mean-cvar-v1`, λ=0.5, α=0.8, 직전 태풍 교차 시나리오다. 실험 조건의 baseline ID, 코드의 버전/커밋, 실행 결과의 run ID를 별개로 기록한다. 하나의 baseline에서 조건을 바꾸거나 모델을 개발한 것은 기준본을 덮어쓰는 대신 변경 이력이 있는 변형이다.

브랜치는 과제별로 만든다. 예: `feature/scenario-editor`, `experiment/minsu/lambda-sweep`. 사람별 영구 브랜치를 기본 구조로 만들지 않는다. 검토 가능한 변경을 PR로 통합하고, 장기 보존할 독립 모델은 별도의 변형 태그와 실험 설명으로 고정한다. 모든 변형을 억지로 공통 모델에 통합할 필요는 없다.

## 3. 현재 환경에서 먼저 고칠 부분

1. **독립된 배포 폴더**: 현재 ChatGPT 프로젝트 동기화 폴더에서 필요한 파일만 새 Git 작업 폴더로 복사한다. 동기화 참조 원본은 수정하지 않는다.
2. **공유 대상 선별**: 소스, 격자, 정본 설정, 테스트·고정 fixture, 문서만 포함한다. `work/`, 임시 렌더링, node_modules 연결, 개인 참고자료, 캐시, 로컬 환경, 대량 outputs는 제외한다. provenance의 개인 절대경로는 배포판에서 출처 설명으로 바꾼다.
3. **설치 경로 독립**: Codex 내장 Python 경로를 몰라도 표준 Python과 `.venv`로 설치·실행할 수 있도록 안내와 실행 스크립트를 정리한다. 한국어 PNG용 재배포 가능한 글꼴과 라이선스를 확보해 Windows/macOS/Linux 표시를 확인한다.
4. **기준 검사와 개발 분리**: 현재 lock은 코드·시각화 전체 해시를 포함하고 테스트는 완전 일치를 요구한다. 이를 모든 개발 PR에 그대로 적용하면 정상적인 수정도 실패한다. 동결 태그의 무결성 검사와 개발 브랜치의 모델 계약/설정 검증을 분리한다. lock 자동 재생성을 일반적인 개발 절차로 삼지 않는다.
5. **실행 출처 추가**: manifest에 Git 커밋, 작업 트리 변경 여부, Python·NumPy·Pillow 버전, baseline 참조, 전체 설정/해시, 현재 소스 해시를 기록한다. 공유할 결과는 커밋한 코드로 실행하는 것을 원칙으로 한다.
6. **mean-CVaR 기준 결과 생성**: 기존 132시간 완주 예시는 평균 목적함수로 실행한 기록이다. 새 목적함수의 공식 공유 결과로 재사용하지 않는다. 배포 준비 후 mean-CVaR 설정으로 1회 완주한 기준 결과를 새로 생성하고 옛 예시는 legacy로 보존한다.

## 4. 권장 폴더 구조

```text
baai-maritime-dss/
  maritime_sim/                 공통 실행·최적화·시각화 모듈
  data/                        고정 격자와 지도 출처
  configs/
    baseline.json              정본 조건
    experiments/<member>/      개인별 변경 실험 설정
  tests/
    fixtures/                  이전 예측 등의 회귀 기준값
  docs/
    SETUP.md                   운영체제별 설치·실행
    BASELINE.md                기준 모델·파라미터
    EXPERIMENTS.md             실행·결과 공유 규칙
    AI_WORKFLOW.md             AI 도구에 제공할 공통 안내
    MODEL_SPEC.md              수학·실행 계약
  results/index.csv            공유 실험의 작은 목록과 결과 링크
  .github/workflows/tests.yml  자동검증
  .github/pull_request_template.md
  AGENTS.md                    AI 도구용 공통 작업 원칙
  PROJECT_CONTEXT.md           현재 구현·의사결정 맥락
  CONTRIBUTING.md              브랜치·PR·검토 절차
  CHANGELOG.md
  requirements-lock.txt
  .python-version
  outputs/                     로컬 실행 결과, 기본 Git 제외
```

위 구조 중 새 파일과 검사 방식은 구현 예정이다. 현재 이미 존재하는 파일과 앞으로 만들 파일을 혼동하지 않는다.

## 5. 팀원 작업 절차

1. 저장소를 자기 PC에 복제하고 공통 Python 환경을 만든다.
2. 기준 확인과 테스트를 실행해 설치 성공을 확인한다.
3. 공통 안내 문서를 AI 도구에 읽히고 작업 목적을 전달한다. 도구마다 자동 인식 파일이 다르므로 최초 요청에서 읽을 문서를 명시한다.
4. 새로운 작업 브랜치를 만든다.
5. 조건 실험은 별도 JSON으로, 모델 수정은 해당 소스 모듈로 구분한다.
6. 테스트 후 코드를 커밋하고, 공유할 실험은 그 커밋에서 실행한다.
7. 자기 브랜치를 GitHub에 푸시한다. 푸시는 개인 버전 공유이며 main 반영과 다르다.
8. PR에 변경 목적, baseline과의 차이, 실험 설정, 검증 결과, 결과 링크를 적는다.
9. 다른 팀원이 확인하고 통합 담당자가 main에 병합한다.
10. 중요한 통합/변형 버전은 태그와 Release로 보존한다.

Git에 익숙하지 않은 팀원은 GitHub Desktop의 같은 이름의 기능으로 진행한다. 파일만 덮어쓰는 업로드 대신 커밋/브랜치 이력을 남긴다.

## 6. 결과 관리

| 대상 | 저장 위치 |
|---|---|
| 소스·설정·문서·작은 테스트 fixture | Git 저장소 |
| 공유 실험의 설정 경로·커밋·KPI·설명·링크 | `results/index.csv` 및 실험 요약 문서 |
| 개인의 모든 실행 결과 | 자기 PC의 `outputs/` |
| 주요 기준/변형 실험 전체 결과 ZIP | 해당 코드 태그의 GitHub Release 첨부 |
| CI가 생성한 테스트 로그·임시 결과 | GitHub Actions Artifacts |

전체 결과 ZIP에는 config, manifest, state, steps, summary, dashboard와 그림을 함께 넣는다. dashboard.html만 보내면 연결된 그림·기록을 잃을 수 있다. run ID는 작성자·일시·실험명을 조합한다. 예: `20261027_minsu_lambda080_01`.

최소 결과 인덱스는 run ID, 작성자, baseline 참조, 코드 커밋, 전체 설정 해시, 목적함수 λ/α, 종료 상태, 도착시간, 연료, 실제 비용, 결과 ZIP 링크를 담는다. mean-CVaR 평가값과 실제 누적비용은 별개로 기록한다. 동일한 제약/종료조건인지도 함께 확인한다.

Actions Artifacts는 기본 보관기간이 90일이므로 장기 기준 결과의 유일한 보관소로 쓰지 않는다. 로컬 결과를 공유하기 위해 자동으로 Actions를 재실행해야 하는 구조도 만들지 않는다. 로컬에서 만든 주요 결과는 직접 Release에 첨부한다.

## 7. AI 공통 작업 규칙

AGENTS와 공통 안내에는 현재 목적함수, 시나리오 생성기, 입력/출력 스키마, 테스트 명령, 과거 결과 보존 원칙을 담는다. 실험용 파라미터와 정본을 구분하고, 의미를 바꾸면 문서와 테스트를 같이 바꾸도록 한다.

처음 전달할 요청 예시:

> 이 폴더의 README, AGENTS.md, PROJECT_CONTEXT.md, docs/SETUP.md, docs/BASELINE.md를 먼저 읽어줘. 기준 버전과 현재 브랜치를 확인한 뒤 로컬 환경 설치와 테스트를 진행해줘. 이번 작업은 별도 실험 설정으로 수행하고, 변경 내용과 재현 명령을 정리해줘.

파일을 직접 다룰 수 없는 채팅 도구를 쓰는 경우에는 이 안내와 관련 파일을 제공하고 변경 내용을 로컬 편집기에 반영한다. 공통 실험에 특정 AI 서비스 계정이나 API 키가 필요하지 않도록 유지한다.

## 8. 검토·자동검증

초기 운영은 main 직접 수정을 피하고 PR 검토 후 담당자가 병합하는 규칙으로 시작한다. GitHub Free 비공개 저장소에서는 강제 branch protection을 사용할 수 없는 경우가 있으므로 운영 합의와 기술적 강제를 구분한다. 강제가 필요하면 개인 소유는 Pro, 조직 소유는 Team 등 저장소 소유 형태에 맞는 플랜을 확인한다.

PR 자동검증은 표준 설치, 단위검증, 기존 태풍 예측 회귀검증, 위험평가, 최소 실행·보고서 스키마를 확인한다. 최초에는 Python 3.12 Windows와 Linux에서 확인하고, 팀에 Mac 사용자가 있으면 설치·한글 보고서 확인을 추가한다. OS가 다르면 미세한 부동소수·렌더링 차이가 있을 수 있으므로 수치 허용오차와 구조 검사를 사용하고 PNG 전체 픽셀 일치를 강제하지 않는다.

기준 태그의 검증은 별도로 고정 lock의 전체 해시 일치를 확인한다. 개발 브랜치에서는 의도한 코드 변경을 무조건 baseline 오류로 취급하지 않고, baseline 참조와 변경 모델의 유효성 검증 결과를 함께 표시한다.

## 9. 단계별 실행 계획과 완료 기준

| 단계 | 작업 | 완료 기준 |
|---|---|---|
| 1. 배포본 정리 | 독립 Git 폴더에 공유할 코드·격자·문서만 복사, ignore·개인 경로 정리 | 새 폴더에서 기존 테스트 통과 |
| 2. 로컬 설치 표준화 | Python 3.12, 고정 의존성, OS별 설치/글꼴, 실행 스크립트 | 깨끗한 가상환경에서 설치·짧은 실행·보고서 생성 |
| 3. 기준/개발 검사 분리 | 태그 기준 무결성과 작업 버전 검사를 분리, Git 출처를 manifest에 추가 | 정상 개발 변경은 테스트 가능하고 정본 변경은 추적 가능 |
| 4. 협업 문서·CI 작성 | 공통 AI 안내, PR 템플릿, 실험 인덱스, 자동검증 | 샘플 PR에서 테스트와 변경 설명 확인 |
| 5. GitHub 개설 | 비공개 저장소, 팀원 초대, 첫 초안 태그/Release | 팀원 계정으로 clone·push·PR 확인 |
| 6. 기준 결과 생성 | 확정 mean-CVaR 설정으로 1회 완주, 결과 묶음과 요약 보관 | 커밋·설정·결과가 연결된 기준 실험 등록 |
| 7. 팀원 온보딩 시험 | 다른 PC에서 AI 안내에 따라 설치·기준 검증·조건 변경 실험·업로드 | 작성자 외 1명이 전체 절차 성공 |
| 8. 공동 운영 | 각자 브랜치에서 실험/개발, PR 검토, 주요 버전 Release | 변경 이유·실행 조건·결과를 버전별로 추적 |

초기 구현 범위는 이 흐름이 실제 팀원 PC에서 한 번 성공하는 데 둔다. Docker, 브라우저 기반 공동 실행 서버, 별도 실험 추적 서비스는 필요성이 생긴 뒤 추가한다.

## 10. 실행 착수 시 필요한 정보

- 저장소를 소유할 GitHub 계정(또는 조직)과 사용할 이름.
- 초대할 팀원의 GitHub ID와 운영체제.
- main 통합 담당자 및 검토 방식. 초기 권장값은 사용자 1명 통합 담당, 다른 팀원 1명 검토다.

## 확인한 공식 문서

- GitHub Desktop 시작: https://docs.github.com/en/desktop/overview/getting-started-with-github-desktop
- 브랜치 작업: https://docs.github.com/en/desktop/making-changes-in-a-branch/managing-branches-in-github-desktop
- 보호 브랜치 제공 범위: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches
- Release와 태그: https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
- Artifacts 보관: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts
