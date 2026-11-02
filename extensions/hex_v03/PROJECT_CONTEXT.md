# 버전 인계: 육각·연속 운항 DSS

## 정본과 현재 범위

2026-11-02, 팀 기본 확장판 v0.3.0-draft.1, 패키지0.3.0.dev1. 먼저 README, docs/CURRENT_MATHEMATICAL_STRUCTURE_KO.md, docs/VERSION_SPEC.md, docs/BASELINE_DIFF.md, docs/TEAM_HEX_GUIDE.md를 읽는다. 이전 개발 기록보다 이 문서와 확정 명세가 우선한다.

- 모델: hex-propulsion-response-v2. 육각18nm, 연속 실제 위치/속도/방향, 추진명령과 파고저항, 가감속/선회, 임의 상태 재계획.
- 시나리오: observed-trend-path-intensity-3x3-v2. 현재까지 관측만으로9개 예측 생성. 파고만 반영, 전복·파향·해류·선박 특성 제외.
- 기준: λ=0/α=.8, 최대3h 재계획. 표준 완주 실험은3h고정. DP15분, 실제/연결30초, 미래 적분fallback5분, 계획168h, 전이12h.
- 정책: effective-scenarios-full-or-selective-v1. 매 시점 고유 기상장1개면 전체DP/상태 내부 최대8스레드, 여러 개면 선택적DP/시나리오 간 최대9스레드(각 내부 직렬).
- 기본 실행: python -m experimental_dp.experiment. 기본1스텝, --complete 완주, --resume 명시. 계산 시간제한 없음. --state는 시작 스냅샷만 바꾸며 격자 원점을 바꾸지 않는다.

## 보존 범위와 검증

이번 확정 작업에서 hex_dss/config/data와 기존 experimental_dp/voyage.py, 두 커널은 수정하지 않았다. 기존 사각 공유 baseline도 별도 보존한다. 과거 outputs를 덮어쓰거나 해시를 새 소스로 바꾸지 않았다. 기존32+알고리즘/정책 고유11개=43개 작은 문제 검증 통과. 새 자동 실행기의 실제 전체 항해 재실행은 하지 않았다.

과거 실측: 선택적전용 태풍36결정/107.0267h/70.2181t/$95,644.22, 무태풍37결정/109.5912h/51.3847t/$85,626.45. 무태풍은 기존 전체DP와 최종 상태가 같지만 선택적 내부직렬이 약9.9배 느렸고 이것이 자동정책의 근거다. t=3h 동일 병렬조건 선택적38.9% 단축, 후보/시나리오 유한값 최대차이7.28e-11달러. 상세는 docs/RELEASE_VALIDATION.md와 examples/reference.

DP값 일치와 연속 경로/실제 최적성을 구분한다. 초기 후보는 최대12h 연결을 평가하고 실제로는3h까지만 실행한다. 중앙 시나리오 참고경로와 대기 유지 규칙은 기존 실행기대로다. 선택적DP는 모든 요청값 확정 방식으로 후보단위epsilon 조기종료를 사용하지 않는다.

## 공유 상태

사용자가 브랜치 업로드·검증·PR·main 병합·새 태그/Release를 승인했다. 배포 이력은 팀 저장소 docs/VERSIONS.md를 확인한다. 팀 저장소 반영은 최신main 기반 새 브랜치에서 extensions/hex_v03에 추가할 계획이다. 독립 로컬 저장소 이력을 팀main에 강제Push하지 않는다. docs/UPLOAD_PREPARATION.md 및 sharing의 PR/README 추가안을 사용한다. 기존 v0.2.0-draft.1 및 baseline lock은 유지한다.

과거 실행기는 hex_dss(속도상한), hex_dss.propulsion(추진 전체DP), experimental_dp.voyage(선택적전용 완주)로 보존된다. 원본 로컬 개발 일지는 docs/archive에 별도 보존했으며 공유 패키지에는 현재 인계만 포함한다.
