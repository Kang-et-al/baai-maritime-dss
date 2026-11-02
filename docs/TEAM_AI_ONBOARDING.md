# 팀원용 AI 설치·실험·개발 안내 — 현재 기본 육각 확장판

이 파일을 로컬 파일·터미널을 사용할 수 있는 AI에게 첨부하고 아래 요청을 채워 전달하세요. 비공개 저장소 초대를 먼저 수락해야 합니다. 인증정보는 채팅에 보내지 않습니다.

## AI에게 전달할 요청

첨부한 안내문에 따라 BAAI 해상운항 DSS의 현재 기본 육각 확장판을 내 PC에 구성해줘.

- 운영체제: [Windows/macOS/Linux/직접 확인]
- 새 작업 폴더: [경로]
- GitHub 아이디: [아이디]
- 팀 내 식별자: [짧은 영문 이름]
- 저장소 초대: [수락 완료/아직 미수락]
- 이번 작업: 설치·검증 후 기준 설정으로 한 스텝 실행
- 업로드 범위: 우선 로컬 작업만

기존 파일을 보존하고 필요한 정보를 중간에 물어봐줘. 완료하면 대시보드를 열고 프로젝트 구조와 실행 방법을 설명해줘.

## AI가 따라야 할 절차

1. 저장소 Kang-et-al/baai-maritime-dss의 최신 main 또는 사용자가 지정한 태그를 새 폴더에 받는다. 루트 AGENTS.md와 docs/VERSIONING.md를 읽는다.
2. 기본은 extensions/hex_v03이다. 이 폴더의 AGENTS.md, README.md, PROJECT_CONTEXT.md, docs/VERSION_SPEC.md, docs/TEAM_HEX_GUIDE.md를 읽고 **이 폴더에서 실행**한다. 기존 루트 bootstrap/maritime_sim은 사각 baseline 재현용이다.
3. Python3.12.x 가상환경을 이 폴더 안에 만들고 requirements.txt의 고정 버전을 설치한다. API키·CPLEX는 불필요하다.
4. python scripts/check_version.py, python -m unittest discover -s tests -v, python -m unittest experimental_dp.test_kernel.SelectiveTests experimental_dp.test_threaded.ThreadedTests experimental_dp.test_policy.PolicyTests -v를 실행한다.
5. python -m experimental_dp.experiment typhoon --steps 1 --output outputs/<새이름>으로 한 결정과 최대3h 실제 실행을 한다. 첫 설치 요청만으로 전체 항해를 시작하지 않는다.
6. 생성한 dashboard.html을 열고 초기 후보의 비용/장기 가치와 실제 실행 KPI를 설명한다. 고유 기상장1개는 전체DP 내부 병렬, 여러 개는 선택적DP 시나리오 병렬인 기본 정책을 임의 변경하지 않는다.
7. 이후 --resume --steps N, --complete, --state, 별도 --config 실험은 사용자 요청 범위에서 실행한다. 기존 outputs를 덮어쓰거나 코드가 바뀐 실행을 이어붙이지 않는다.
8. 개발은 feature/<식별자>/<주제> 또는 experiment/<식별자>/<주제> 브랜치에서 한다. 수정에 맞는 검증과 문서 갱신 후 커밋한다. 업로드 요청이 있으면 브랜치 Push와 PR, main 병합·태그/Release는 해당 범위의 요청을 따른다. 기존 태그를 이동하지 않는다.

자세한 상태 JSON·재개·결과 파일 설명은 [확장판 팀 안내](../extensions/hex_v03/docs/TEAM_HEX_GUIDE.md), 이전 모델 재현은 [기존 baseline](BASELINE.md)을 참조한다.
