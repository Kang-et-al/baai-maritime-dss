# BAAI Maritime DSS — 해상운항 의사결정지원시스템

현재 공개 기본 모델은 **v0.3.0-draft.1 육각·연속 운항 확장판**입니다. 앞으로의 실험·개발은 이 모델을 출발점으로 합니다. 기존 사각 baseline v0.2.0-draft.1의 코드·설정·태그는 보존합니다.

## 처음 사용하는 분께

**공개 저장소이므로 로컬 다운로드·설치·실험에 GitHub 계정·로그인·초대가 필요 없습니다.** Git과 Python은 설치되어 있어야 합니다.

AI와 설치하려면 [공통 안내문](docs/AI_ONBOARDING.md)을 다운로드해 [설치 요청문](docs/INSTALL_PROMPT.md)과 함께 전달하세요. 최신 main에서 현재 기본 모델을 찾도록 되어 있어 이후 버전에도 같은 안내를 사용할 수 있습니다.

공개 HTTPS 주소로 받습니다.

```text
git clone https://github.com/Kang-et-al/baai-maritime-dss.git
cd baai-maritime-dss
```

| 내용 | 안내 |
|---|---|
| 설치·실행·결과 확인 | [확장판 README](extensions/hex_v03/README.md) |
| 수학적 모델 | [상태·의사결정·동역학·목적함수](extensions/hex_v03/docs/CURRENT_MATHEMATICAL_STRUCTURE_KO.md) |
| 알고리즘·정확성 | [전체/선택적 DP와 기본 계산 정책](extensions/hex_v03/docs/VERSION_SPEC.md) |
| 기존 버전과의 차이 | [변경 비교표](extensions/hex_v03/docs/BASELINE_DIFF.md) |
| 실험·AI 운영 | [사용자 실행 안내](extensions/hex_v03/docs/TEAM_HEX_GUIDE.md) |
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

## 기여와 이용 조건

로컬 사용은 계정 없이 가능하며, GitHub에 Issue·Fork·PR을 제출할 때만 계정이 필요합니다. [기여 안내](CONTRIBUTING.md)를 참고하세요. 공개 사용자가 원본 main에 직접 수정할 수 있는 것은 아닙니다.

자체 소스의 오픈소스 라이선스는 현재 선택 중입니다. 공개 열람과 재사용·배포 허락은 구분하며, LICENSE 확정 전 포괄적인 재사용 허락을 가정하지 마세요. [외부 자산 고지](THIRD_PARTY_NOTICES.md)도 확인하세요. 과거 태그는 당시 배포된 상태로 보존됩니다.
