# BAAI Maritime DSS — 육각·연속 운항 확장판

**공개 기본 확장판: v0.3.0-draft.1 / Python 패키지 0.3.0.dev1.** 기존 공유 기준 `v0.2.0-draft.1`과 별도로 보존하는 확장 모델이다.

육각 해상망, 연속적인 실제 위치·속도·방향, 추진 명령과 파고 저항, 가감속·선회, 임의 상태 재계획을 결합한다. 현재 관측에서 9개 태풍 예측을 생성하고, 국소 후보의 초기비용과 시나리오별 장기 DP 비용을 합친 mean–CVaR로 선택한다. 기본 λ=0, α=0.8이며 기상 API·AI API·CPLEX는 필요 없다.

## 확정 문서

| 목적 | 문서 |
|---|---|
| 전체 수학적 모델: 상태·후보·동역학·목적함수·시나리오 | [수학적 구조](docs/CURRENT_MATHEMATICAL_STRUCTURE_KO.md) |
| 알고리즘 수식·하한 증명·최적성 범위·문제별 기본값 | [확정 알고리즘 명세](docs/VERSION_SPEC.md) |
| 기존 사각 baseline과의 차이, 중간 육각 엔진과의 구분 | [변경 비교표](docs/BASELINE_DIFF.md) |
| 설치·실험·결과·재개·AI 인계 | [사용자 실행 안내](docs/TEAM_HEX_GUIDE.md) |
| 보존한 실험 실측과 현재 검증 범위 | [검증 기록](docs/RELEASE_VALIDATION.md) |
| GitHub에 합치는 경로·검토·PR 초안·배포 주의 | [업로드 준비](docs/UPLOAD_PREPARATION.md) |

공개 저장소의 로컬 설치·실험에는 GitHub 계정·로그인·초대가 필요 없습니다. 공통 [AI 설치 안내](../../docs/AI_ONBOARDING.md)와 [기여 안내](../../CONTRIBUTING.md)를 참고하세요.

## 설치 및 검증

Python **3.12.x**, `requirements.txt`의 정확한 라이브러리 버전을 기준으로 한다. 저장소/확장 모듈 폴더 최상위에서 실행한다. 데이터와 설정도 함께 사용하는 checkout 방식이며 wheel 단독 설치는 배포 형식으로 지원하지 않는다.

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe scripts/check_version.py
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m unittest experimental_dp.test_kernel experimental_dp.test_threaded experimental_dp.test_policy.PolicyTests -v
```

macOS/Linux에서는 `.venv/bin/python`을 사용한다. 검증은 작은 문제를 사용하며 전체 항해를 자동 실행하지 않는다.

## 기본 실행: 문제 유형별 알고리즘 자동 선택

```powershell
# 새 폴더에 한 번 결정하고 실제 환경에서 최대 3시간 실행
.venv/Scripts/python.exe -m experimental_dp.experiment typhoon --steps 1 --output outputs/my_typhoon
# 같은 코드·설정·데이터·정책일 때 다음 1회
.venv/Scripts/python.exe -m experimental_dp.experiment typhoon --resume --steps 1 --output outputs/my_typhoon
# 전체 항해 (사용자가 요청했을 때만)
.venv/Scripts/python.exe -m experimental_dp.experiment calm --complete --output outputs/my_calm_voyage
# 임의 시각·좌표·속도·방향의 스냅샷에서 재계획
.venv/Scripts/python.exe -m experimental_dp.experiment typhoon --state state.json --output outputs/emergency_001
```

각 결정 시 **실제 생성된 예측**을 검사한다. 고유 기상장이 1개면 **기존 전체 DP + 상태 내부 최대 8스레드**, 2개 이상이면 **새 선택적 DP + 시나리오 간 최대 9스레드**를 사용한다. 선택적 DP 내부 병렬화는 하지 않는다. 무태풍의 동일한 9개 예측은 한 번 계산하고 확률질량은 그대로 유지한다. 태풍 실험도 해당 시점의 예측이 전부 같으면 전체 DP를 사용한다.

현재 기본 실행기는 계산 시간제한을 강제하지 않는다. 물리 전이의 12시간 제한, 계획기간 168시간, 시뮬레이션 336시간 상한은 유지된다. 오래 걸리면 완료된 시나리오부터 재개할 수 있다. 첫 실행의 컴파일·격자/전이표 구축은 재사용 실행보다 오래 걸릴 수 있다.

결과 `dashboard.html`은 시점 슬라이더·재생, 실제 항적의 속도 색상, 미래 시나리오 경로, 실제/예상 태풍 영향 경계와 후보별 비용을 제공한다. `steps/`에는 결정·실제 실행, `work/`에는 시나리오 계측, `sessions/`에는 실행 커밋·환경·해시가 기록된다.

## 보존되는 과거 실행 경로

- `python -m hex_dss`: **이전 파고 속도상한 육각 엔진**. 현재 기본이 아니다.
- `python -m hex_dss.propulsion`: 추진 모형의 **기존 전체 DP 명시 실행기**. 기존 CLI 규칙·시간제한을 유지한다.
- `python -m experimental_dp.voyage`: **선택적 DP만** 사용한 과거 완주 실행기. 그때의 실험 재현용이다.
- `python -m experimental_dp.experiment`: **이번 확정 기본 실행기**. 문제 유형별 자동 선택, 기본 한 스텝, 명시적 재개.

이전 결과를 새 실행기의 성능 측정으로 바꾸어 표시하지 않는다. [완주 결과](docs/SELECTIVE_VOYAGE_RESULTS.md)와 [거동 해석](docs/VOYAGE_DECISION_AUDIT.md)은 과거 실행 소스와 함께 읽는다. 원래 사각 baseline은 기존 공유 저장소/태그에 보존한다.

**모형 범위:** 교육용 합성 기상과 유한 후보·보간 DP의 DSS다. 실선 안전성, 연속 공간 전역 최적성, 실시간 선박 제어를 보장하지 않는다. AI를 통한 비정형 기상자료 해석은 향후 모듈이며 현재 시나리오는 수식으로 생성한다.
