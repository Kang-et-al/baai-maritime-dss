> **공개 설치 기준:** 최신 안내는 [공통 AI 설치 안내](AI_ONBOARDING.md)를 사용한다. 로컬 사용에는 GitHub 계정·초대가 불필요하며, 아래 과거 팀/사각 환경 설명과 구분한다.

# 설치와 실행 환경

기준 환경은 Python 3.12.x, NumPy 2.3.5, Pillow 12.3.0입니다. Python 패치 버전까지 강제하지 않습니다.
표준 Python 설치와 프로젝트별 `.venv`를 사용합니다. 개인 PC의 Codex 내장 경로에 의존하지 않습니다.
저장소 폴더에서 실행하며 wheel 배포는 제공하지 않습니다. 설정과 데이터가 코드 옆에 있어야 합니다.

- Windows: Python 3.12와 launcher 설치 → setup_windows.bat 실행.
- Mac/Linux: Python 3.12 설치 → `python3.12 scripts/bootstrap.py` 실행.
- 처음 패키지를 받을 때 인터넷이 필요합니다. 실험 중 지도·기상 API는 사용하지 않습니다.

직접 설치:

```text
python -m venv .venv
# Windows
.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
.venv/Scripts/python.exe -m unittest discover -s tests -v
# Mac/Linux
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m unittest discover -s tests -v
```

개발 중 다른 버전을 사용하는 것도 가능합니다. requirements.txt는 허용 범위입니다.
공유 기준과 비교할 결과는 기준 환경에서 다시 확인하고 manifest 버전을 함께 기록합니다.
운영체제 사이의 비트/픽셀 단위 동일성은 보장하지 않으며 수치 허용오차와 동작을 검증합니다.

## 문제 해결

- py -3.12를 찾지 못함: Python 3.12를 설치하거나 실제 3.12 실행 파일로 bootstrap.py를 실행합니다.
- Windows Store 바로가기가 실행됨: Python 실제 설치 여부를 확인합니다.
- 출력 폴더가 비어 있지 않음: 새 이름을 쓰거나 기존 실험에 --resume을 사용합니다.
- 코드 변경으로 이어하기 거부: 새 실험을 만들거나 당시 커밋을 별도 폴더에 복제합니다.
- 한글 그림은 포함된 NanumGothic을 사용합니다. OFL 라이선스도 함께 배포합니다.
