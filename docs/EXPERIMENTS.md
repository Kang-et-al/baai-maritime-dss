# 실험·결과 관리

완주 재생(replay)은 항해 종료 후 시간 슬라이더로 탐색합니다. 단계별 실시간(live)은 요청한 스텝만 진행합니다.
둘 다 기존 KPI·실제 항적·태풍 예측·시나리오 항로·속도 색상·PNG/CSV를 유지합니다.
아래 python은 .venv의 실행 파일을 사용합니다.

```text
python -m maritime_sim run --config configs/baseline.json --experiment replay --output outputs/baseline_reference
python -m maritime_sim run --experiment live --steps 1 --output outputs/member_live
python -m maritime_sim run --resume --steps 2 --output outputs/member_live
python scripts/register_result.py --run outputs/baseline_reference --id baseline-mean-cvar-v1
```

새 조건은 별도 JSON에서 재정의합니다. config.json에 병합된 전체 설정이 저장됩니다.
state.json의 status가 arrived여야 도착입니다. infeasible/time_limit도 기록하되 성공 도착으로 해석하지 않습니다.
manifest.json에는 Git 커밋·수정 여부·코드/데이터/설정 해시·라이브러리 버전이 있습니다.
steps/에는 매 시점의 관측·예측·후보 평가·실행 결과가 있습니다.

register_result.py는 실행 당시 manifest 기준으로 색인과 ZIP을 만듭니다.
개발 중 수정된 코드의 실행은 허용하지만, 공유 색인 등록은 기본적으로 거부합니다.
의도적인 개발 결과만 --allow-dirty로 등록하며 설명에 표시합니다.
등록 후 results/index.csv를 커밋하고 dist/실험ID.zip을 해당 코드 태그 Release에 첨부합니다.
index.csv의 artifact_url에는 Release 링크를 적습니다. 실제 비용과 목적함수 점수를 구분해 비교합니다.

## 기준 원본 확인

```text
python -m maritime_sim baseline
python scripts/verify_release.py --ref v0.2.0-draft.1
```

첫 명령은 현재 폴더와 배포 lock의 해시를 비교합니다. 개발 중 changed는 정상입니다.
두 번째는 Git에 보관된 기준 태그 자체를 검증하므로 작업 폴더가 달라도 원본 보존을 확인할 수 있습니다.
과거 버전 실행은 새 Clone 폴더에서 진행합니다. 작업 중인 폴더를 강제 되돌리지 않습니다.
