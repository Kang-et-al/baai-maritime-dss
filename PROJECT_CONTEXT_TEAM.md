# 팀 공유 초안 — 다음 작업 인계

이 문서가 최신 인계 기준이다. PROJECT_CONTEXT.md는 복사해 온 개인 실험 단계의 역사적 기록이다.
기준 태그 v0.2.0-draft.1, 저장소 Kang-et-al/baai-maritime-dss (비공개).

## 모형

- 교과목용 DSS 구현이 목적. 기존 모형·태풍 생성·격자를 보존했다.
- 정본 configs/baseline.json, baseline ID busan-hongkong-mean-cvar-v1, schema 2.
- 2286개 해상 노드 / 8600개 방향 아크 / 아크 18해리, 부산 3181 → 홍콩 642.
- 3시간 롤링 / 내부 0.25시간 / 미래 168시간 / 일반 12kn / 쾌속 18kn.
- 후보 노드까지 최소 실행비용 + 미래 mean-CVaR, λ=0.5 / α=0.8.
- 1단계 내부 forward DP, 2단계 시나리오별 backward DP, 바깥 의사결정은 다음 도달 노드 선택.
- 태풍 생성기 trend-path-intensity-3x3-v1, 경로 3×강도 3, 확률 각 1/9. 수식/fixture 보존.
- 실제 태풍 경로는 고정되어 시간에 따라 실현, 예측은 관측 기준으로 재생성. 영향 반경은 강도에 비례.
- 과거 crossing_replay의 132시간 결과는 평균만 사용한 실험이다. 새 공유 기준 결과와 구분한다.

## 파일 구조

| 경로 | 역할 |
|---|---|
| config.py / network.py | 설정 병합·검증 / 기존 CSV 격자·투영 |
| weather.py | 실제 세계·관측·9개 예측·파고/속도 제약 |
| planner.py / risk.py | DP·경로 복원 / 평균·이산 CVaR 후보 평가 |
| simulation.py | 실제 상태·실행·체크포인트·이어하기 |
| runtime.py | Git 커밋·변경 여부·실행 환경 |
| report.py / replay.py / assets/replay.html | PNG·CSV·시간 탐색 대시보드 |
| baseline.py / configs/baseline.lock.json | 배포 원본 소스 확인 |
| tests/ | 독립 열거·정보 누출·실행/재개·위험 평가·생성 회귀·보고서 |
| scripts/ | 설치·실험 등록·기준 태그 검증 |

위 Python 파일은 maritime_sim/ 아래에 있다. data/에는 격자와 지도, configs/에는 정본/별도 실험 설정을 둔다.
이번 공유 구성은 이식 가능한 설치·글꼴·Git 메타데이터·문서·개발 검증 분리만 변경했다.
개발 중 소스 해시 변경은 정상이다. lock을 자동 재작성하지 않는다.
이어하기는 실험 생성 당시 코드/데이터/설정 해시가 유지되어야 한다. 버전을 바꾸면 새 실험을 만든다.
운영은 docs/TEAM_GUIDE.md, 실행은 README.md, 수학/생성 규칙은 docs/BASELINE.md를 따른다.

## 공유 검증 결과

Windows 새 가상환경 및 GitHub 복제본 설치/21개 검증 통과. 복제본 첫 3시간 실행과 기준 첫 스텝이 일치한다.
최종 기준 실험은 outputs/baseline_reference_final, 소스 커밋 69fc1a63214ec837427cdb8ab2191d7dce215f76.
44스텝·132시간에 홍콩 도착, 76.2057095톤·실제 111,723.4257달러·대기 2시간.
results/index.csv에 등록했으며 Release에 baseline-mean-cvar-v1.zip을 첨부한다.
검증 상세는 docs/SHARED_VALIDATION.md. 팀원 GitHub ID와 초대 수락 후 각자의 PC 설치/Push 확인이 남아 있다.
