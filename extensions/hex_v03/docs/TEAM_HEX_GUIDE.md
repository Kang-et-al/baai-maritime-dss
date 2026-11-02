# 팀원·AI용 확장판 설치·실험·개발 안내

## 시작할 때 AI에게 줄 정보

- 새 작업 폴더, 운영체제, GitHub 아이디/팀 식별자, 저장소 초대 수락 여부.
- 사용할 버전: 기존 사각 baseline인지 육각 확장판인지. 확장판 태그는 아직 미게시다.
- 작업 범위: 설치·작은 검증 / 한 스텝 / 특정 상태 재계획 / 완주 / 개발.
- 업로드 범위: 로컬만 / 작업 브랜치 Push·PR까지 / 별도 배포 요청.

공유 준비 패키지에서는 `extensions/hex_v03`가 확장판의 실행 루트다. 기존 `maritime_sim`은 상위 저장소 루트에서 실행한다. 두 환경의 설정·가상환경·outputs를 섞지 않는다.

## 최초 설치

1. GitHub 초대를 수락하고 팀 저장소의 해당 브랜치 또는 이후 확정 태그를 새 폴더에 받는다. 인증 정보는 AI 대화에 붙이지 않는다.
2. 확장판 폴더를 열고 README, AGENTS, PROJECT_CONTEXT와 확정 명세를 읽게 한다.
3. Python3.12.x 가상환경을 만들고 requirements.txt를 설치한다. NumPy/Numba 버전을 임의로 올리지 않는다.
4. `python scripts/check_version.py`, 기존32개 테스트와 새 알고리즘·정책 테스트를 실행한다.
5. 요청한 경우에만 `python -m experimental_dp.experiment typhoon --steps 1 --output outputs/my_first`를 실행한다.
6. `outputs/my_first/dashboard.html`을 열고 선택 후보, 추진명령, 실제 속도, 예상 비용과 실제 비용을 구분해 설명한다.

첫 실행은 컴파일·격자·전이표 생성이 포함되어 느릴 수 있다. 캐시는 현재 컴퓨터에서 생성한다. 여러 시나리오의 밀집 가치표가 동시에 필요하므로 RAM 사용량도 확인한다.

## 실행 형식

| 요청 | 실행 |
|---|---|
| 한 결정+최대3h 실행 | `python -m experimental_dp.experiment typhoon --steps 1 --output outputs/new_001` |
| 다음 두 결정 | `python -m experimental_dp.experiment typhoon --resume --steps 2 --output outputs/new_001` |
| 태풍 완주 재생 | `python -m experimental_dp.experiment typhoon --complete --output outputs/storm_complete` |
| 무태풍 완주 재생 | `python -m experimental_dp.experiment calm --complete --output outputs/calm_complete` |
| 실험 설정 변경 | 새 JSON을 `configs/experiments/`에 저장하고 `--config` 사용 |
| 임의 상태 재계획 | `--state state.json` 사용; 격자를 다시 옮기지 않음 |

상태 JSON 예시는 다음과 같다. 좌표는 **해리 단위 LCC 투영 좌표**이며 경위도가 아니다. 시간은 출항 이후 절대시간이다.

```json
{"time_h":7.3833,"x_nm":330.2,"y_nm":411.1,"speed_kn":7.3,"heading_deg":237.4}
```

`--state`는 시작 스냅샷이며 고정 격자 원점을 바꾸는 설정이 아니다. 입력 위치·속도·방향 때문에 연결할 후보가 없으면 실패가 명시될 수 있다. 실제 선박 위치를 자동 수집하는 기능은 없다.

## 결과를 읽는 방법

| 경로 | 내용 |
|---|---|
| `config.json`, `initial_state.json`, `identity.json` | 실제 설정, 시작 상태, 코드/데이터/정책 해시 |
| `sessions/*.json` | 실행 커밋·작업상태·Python/라이브러리·세션 계측 |
| `steps/step_NNN.json` | 결정 전후 상태·모든 후보 비용·선택·9개 예측·실제 실행 |
| `work/step_NNN/solver_policy.json` | 이번 시점의 자동 선택 알고리즘·병렬 기본값 |
| `work/step_NNN/scenario*.json` | 시나리오 DP 시간·전이/적분 횟수·계산 상태수 |
| `work/step_NNN/*.npy` | 중단 재개용 가치표·파고장; 완료 스텝은 정리됨 |
| `dashboard.html` | 저장 결과의 시점별 재생; 웹 서버/API 불필요 |

`solve_seconds`는 후보 생성·DP·기록·연속 복원을 포함하고 실제 구간 실행/대시보드 렌더링은 제외한다. 시나리오 `seconds`는 해당 DP·후보 조회·수치파일 기록이며 파고장 사전 생성은 제외한다. 병렬 작업 시간을 합한 값은 실제 경과시간이 아니다. 재개된 스텝 시간에는 이전 중단 세션 시간이 전부 합산되지 않으므로 `sessions/`와 함께 해석한다.

재개 시 완료 시나리오를 재사용한다. 아직 계산 중인 시나리오는 다시 계산하며 함수 내부 DFS 스택까지 저장하지 않는다. 소스·설정·정책이 바뀌면 같은 outputs에 이어 붙일 수 없다. 실패/강제종료는 `status.json`만으로 성공 판정하지 말고 마지막 완료 step의 `arrived`를 확인한다.

## AI에게 그대로 전달할 요청

> 이 확장판 폴더의 AGENTS.md, README.md, PROJECT_CONTEXT.md와 docs/VERSION_SPEC.md를 먼저 읽어줘. 기존 사각 baseline과 과거 결과를 보존해줘. Python3.12 가상환경에 고정 의존성을 설치하고 정본 검사와 작은 문제 검증을 수행해줘. 이번 작업은 [한 스텝/상태 재계획/완주/개발]이며 출력은 [새 폴더]야. 기본 자동 계산 정책과 물리·시나리오 규칙을 임의 변경하지 마. 결과 대시보드를 열고 미래 DP 점수와 실제 비용을 구분해 설명해줘. 업로드는 [우선 로컬만]이야.

## 개선 버전 공유

팀 상위 저장소의 docs/VERSIONING.md를 읽는다. 새 작업 브랜치에서 수정·검증·문서화·커밋한다. 업로드 요청이 있으면 해당 브랜치 Push와 PR, main/태그/Release는 요청 범위에 맞춰 진행한다. 기존 태그를 이동하지 않는다. 새 실험은 깨끗한 소스에서 수행하고 실제 실행 커밋·설정 해시를 남긴다. 이번 공유 준비의 과거 완주 자료는 과거 커밋의 결과다.
