# 육각 확장판 AI 작업 지침

1. 먼저 README.md, PROJECT_CONTEXT.md, docs/CURRENT_MATHEMATICAL_STRUCTURE_KO.md, docs/VERSION_SPEC.md, docs/TEAM_HEX_GUIDE.md를 읽는다. 과거 MODEL.md는 속도상한 엔진 설명이며 현재 모형이 아니다.
2. 원래 팀 저장소와 v0.2.0-draft.1, 기존 실험 outputs 및 과거 실행기를 보존한다. 공유 시 확장은 extensions/hex_v03 아래 추가하고 기존 baseline lock·설정·태그를 덮어쓰지 않는다.
3. 사용자가 지정한 범위에서 로컬 수정·브랜치 Push·PR·병합·태그/Release를 수행한다. 일반 개선 요청은 브랜치와 PR을 사용하며 main 병합·배포는 사용자 요청 범위를 확인한다. 부모 저장소 AGENTS.md와 docs/VERSIONING.md도 확인한다.
4. 기본 실행은 python -m experimental_dp.experiment. 고유 기상장이1개면 전체DP/상태 내부 최대8스레드, 여러 개면 선택적DP/시나리오 간 최대9스레드, 선택적DP 내부 직렬이다. 매 시점 자동 판정하며 명시적 요청 없이 변경하지 않는다.
5. 기준 λ=0, α=.8, 고정3h 롤링, DP15분, 실제/연결 적분30초·미래 fallback5분이다. 물리 모델·시나리오 생성·제약을 속도 개선 명목으로 변경하지 않는다. 변경 실험은 별도 설정과 새 outputs를 사용한다.
6. 기본 검증은 venv Python으로 tests와 experimental_dp의 작은 문제 테스트. 전체 항해·대형 성능 비교는 요청되었을 때만 한다. 모델/알고리즘 변경 시 docs/CHANGELOG.md와 PROJECT_CONTEXT.md를 갱신한다.
7. 기존 출력은 덮어쓰지 않는다. 새 기본 실행기는 기본1스텝이고 재개는 --resume을 명시한다. 코드·설정·데이터·정책·초기 상태 해시가 같아야 재개한다. 진행 중 시나리오의 DFS 스택은 저장하지 않는다.
8. 실제 미래는 World 내부에만 둔다. 이산DP 최적값과 연속 복원 비용, 미래 점수와 실제 누적비용, 오프라인 시뮬레이션과 실제 선박제어를 구분한다. 모든 계수는 프로젝트 가정이며 실선 인증값이 아니다.
9. 작업 브랜치는 feature/<식별자>/<주제> 또는 experiment/<식별자>/<주제>. 강제Push·기존 태그 이동 금지. Push/PR/배포는 각각 사용자 요청 범위를 따른다. 기존 결과를 새로운 소스에서 실행한 결과로 재라벨링하지 않는다.
10. 버전 정본 체크는 python scripts/check_version.py. 의도한 개선으로 changed가 나면 이를 기록하고 새 버전에서 lock을 갱신한다. 테스트를 통과시키기 위해 기준 lock을 임의로 바꾸지 않는다.
