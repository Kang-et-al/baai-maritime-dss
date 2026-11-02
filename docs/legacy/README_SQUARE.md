# BAAI 해상운항 DSS — 팀 실험 환경

부산 → 홍콩 단일 선박의 운항을 태풍 예측과 함께 계획하는 Python 교육용 프로젝트입니다.
3시간마다 다음 도달 노드를 정하며, 시나리오별 미래 경로를 DP로 계산해 mean-CVaR로 평가합니다.
별도 솔버, 기상 API, 유료 서비스 없이 로컬에서 실행합니다.

## 처음 시작하기

**AI와 함께 처음 설치한다면 [팀원용 AI 설치·실험·업로드 안내문](docs/TEAM_AI_ONBOARDING.md)부터 확인하세요.**

1. 먼저 GitHub 저장소 초대를 수락합니다. 비공개 저장소이므로 접근 권한이 필요합니다.
2. 위 안내문을 열고 파일의 **Download raw file(원본 파일 다운로드)** 기능으로 `.md` 파일을 저장합니다. 또는 저장소를 복제한 뒤 `docs/TEAM_AI_ONBOARDING.md`를 사용합니다.
3. 안내문의 입력 표에 운영체제·작업 폴더·GitHub 아이디·팀 식별자·원하는 작업·업로드 범위를 채웁니다.
4. 파일을 AI에 첨부하고 “이 안내문에 따라 설치·검증 후 기준 설정으로 한 스텝 실행해줘”라고 요청합니다. 로컬 파일·터미널을 사용할 수 있는 AI 도구는 직접 작업할 수 있고, 일반 채팅에서는 안내받은 작업을 직접 수행합니다.

직접 설치하려면 아래 순서를 따릅니다.

1. GitHub 초대를 수락하고 이 저장소를 복제(Clone)합니다. GitHub Desktop을 사용해도 됩니다.
2. Python **3.12.x**를 설치합니다. Windows는 `setup_windows.bat`을 실행합니다.
3. Mac/Linux는 저장소 폴더에서 `python3.12 scripts/bootstrap.py`를 실행합니다.
4. 아래 명령은 Windows 기준입니다. Mac/Linux는 `.venv/Scripts/python.exe` 대신 `.venv/bin/python`을 씁니다.

```text
# 검증 (전체 항해를 실행하지 않음)
.venv/Scripts/python.exe -m unittest discover -s tests -v
# 단계별 실시간 실험: 한 스텝
.venv/Scripts/python.exe -m maritime_sim run --experiment live --steps 1 --output outputs/my_live
# 같은 실험에서 3스텝 더 진행
.venv/Scripts/python.exe -m maritime_sim run --resume --steps 3 --output outputs/my_live
# 완주 재생 실험
.venv/Scripts/python.exe -m maritime_sim run --experiment replay --output outputs/my_replay
```

결과의 `dashboard.html`을 브라우저로 열면 시간 슬라이더, KPI, 실제 항적, 예상 태풍과 미래 항로를 확인할 수 있습니다.
`archive.html`, `figures/`, `summary.csv`도 함께 생성됩니다. 완주 실험은 `run_demo.bat`으로도 실행할 수 있습니다.

## 버전과 실험 관리

**개선 모델을 올리기 전 [버전 관리·업로드 지침](docs/VERSIONING.md)을 확인하세요.** [보존 버전 목록](docs/VERSIONS.md)에서 초기 모델과 이후 배포를 찾을 수 있습니다.
Push는 변경 이력을 공유하며 새 버전 번호를 자동으로 만들지는 않습니다. 작업 브랜치에서 개선하고, 보존할 시점에 새 태그/Release로 등록합니다.

- 기준 태그 **v0.2.0-draft.1**, 설정 `configs/baseline.json`, λ=0.5, α=0.8.
- main은 팀이 받아들인 최신 코드입니다. 원래 기준 버전은 태그로 보존합니다.
- 작업마다 새 브랜치 → 수정·검증 → 커밋·Push → Pull Request(PR) 순서로 공유합니다.
- 새 설정은 `configs/experiments/`, 새 결과는 서로 다른 `outputs/이름/`에 저장합니다.
- 결과에 Git 커밋·수정 여부, 설정/코드 해시, Python·NumPy·Pillow 버전이 기록됩니다.
- 중요한 결과는 `scripts/register_result.py`로 등록하고 ZIP을 해당 코드 버전의 Release에 첨부합니다.
- 개발 중 `python -m maritime_sim baseline`의 changed는 기준 소스와 다르다는 뜻입니다. 개발을 금지하는 검사가 아닙니다.

## 문서와 AI 사용

| 문서 | 용도 |
|---|---|
| [설치](docs/SETUP.md) | 처음 설치·버전·문제 해결 |
| [팀 운영](docs/TEAM_GUIDE.md) | 브랜치·PR·Release·무료 운영 |
| [AI 작업](docs/AI_WORKFLOW.md) | ChatGPT/Claude 등에 줄 시작 요청문 |
| [팀원용 AI 전체 안내문](docs/TEAM_AI_ONBOARDING.md) | AI에 첨부할 설치·실험·수정·GitHub 공유 지침 |
| [인계](PROJECT_CONTEXT_TEAM.md) | 코드 구조와 다음 작업 |
| [확정 모형](docs/BASELINE.md) | 목적함수·시나리오 수식·파라미터 |
| [실험 관리](docs/EXPERIMENTS.md) | 결과 등록·공유·재현 |

AI 도구에는 프로젝트 폴더를 열고 AGENTS.md부터 읽도록 요청하세요. Claude용 CLAUDE.md도 같은 지침을 연결합니다.
Gemini용 GEMINI.md도 공통 지침을 연결합니다. 이미 설치한 팀원도 다음 작업 전에 최신 main의 운영 문서를 확인하세요. 과거 태그를 실행할 때는 태그 선택 전에 최신 운영 지침을 먼저 읽습니다.
이 절차는 AI와 팀원이 따르는 작업 지침입니다. 서버가 브랜치 생성·검증·PR을 자동 수행하거나 main 직접 수정을 강제로 차단하는 설정은 아닙니다.
현재 모형에 AI API 호출은 없으며, 개인 AI 도구 사용료는 선택한 서비스 정책에 따릅니다.

공유 기준 실행과 검증 범위는 [Release 설명](docs/RELEASE_NOTES.md)과 [검증 기록](docs/SHARED_VALIDATION.md)을 참고하세요.
