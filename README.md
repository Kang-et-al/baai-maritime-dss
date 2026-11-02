# BAAI 해상운항 DSS — 팀 기본 환경

현재 기본은 **v0.3.0-draft.1 육각·연속 운항 확장판**입니다. 앞으로의 실험·개발은 이 모델을 출발점으로 합니다. 기존 사각 baseline v0.2.0-draft.1의 코드·설정·태그는 보존합니다.

## 처음 사용하는 팀원

[AI에게 첨부할 설치·실험 안내문](docs/TEAM_AI_ONBOARDING.md)을 다운로드해 로컬 파일·터미널에 접근할 수 있는 AI에게 전달하세요. 팀 저장소를 받은 다음 **extensions/hex_v03 폴더를 작업 루트로 사용**합니다.

| 내용 | 안내 |
|---|---|
| 설치·실행·결과 확인 | [확장판 README](extensions/hex_v03/README.md) |
| 수학적 모델 | [상태·의사결정·동역학·목적함수](extensions/hex_v03/docs/CURRENT_MATHEMATICAL_STRUCTURE_KO.md) |
| 알고리즘·정확성 | [전체/선택적 DP와 기본 계산 정책](extensions/hex_v03/docs/VERSION_SPEC.md) |
| 기존 버전과의 차이 | [변경 비교표](extensions/hex_v03/docs/BASELINE_DIFF.md) |
| 팀 실험·AI 운영 | [팀원 실행 안내](extensions/hex_v03/docs/TEAM_HEX_GUIDE.md) |
| 버전 관리 | [브랜치·PR·태그·Release 절차](docs/VERSIONING.md) · [버전 목록](docs/VERSIONS.md) |

## 빠른 시작 (Windows)

```powershell
cd extensions/hex_v03
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe scripts/check_version.py
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m unittest experimental_dp.test_kernel.SelectiveTests experimental_dp.test_threaded.ThreadedTests experimental_dp.test_policy.PolicyTests -v
.venv/Scripts/python.exe -m experimental_dp.experiment typhoon --steps 1 --output outputs/my_first
```

macOS/Linux에서는 python3.12와 .venv/bin/python을 사용합니다. 결과 dashboard.html을 열면 됩니다. 최초 구축/컴파일은 시간이 걸릴 수 있습니다. 전체 항해는 --complete를 명시했을 때만 실행합니다.

기본 계산: 고유 기상장이1개면 전체DP 내부 최대8스레드, 여러 개면 선택적DP 시나리오 간 최대9스레드. λ=0/α=.8, 3시간 롤링, 기상 API·MILP 솔버 없이 실행합니다. 계산 시간제한은 강제하지 않습니다.

## 이전 사각 baseline 재현

[기존 모델 문서](docs/BASELINE.md)와 [원본 고정 버전](https://github.com/Kang-et-al/baai-maritime-dss/tree/v0.2.0-draft.1)을 사용합니다. 루트 maritime_sim 및 configs/baseline.json은 그대로 남습니다. 루트 bootstrap은 이전 사각 환경용이며 현재 확장판은 위 별도 환경을 사용하세요.

과거 완주 결과는 당시 실행 소스의 기록입니다. 이번 통합 커밋에서 전체 항해를 다시 실행한 결과로 표시하지 않습니다. 교육용 DSS이며 연속 전역 최적성이나 실선 안전성 인증을 의미하지 않습니다.
