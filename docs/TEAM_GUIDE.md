> **현재 팀 기본 (v0.3.0-draft.1):** 육각 확장판 extensions/hex_v03에서 별도 가상환경으로 실행한다. 그 폴더의 AGENTS.md와 README.md가 현재 모델/기본 알고리즘 지침이다. 아래 루트 실행·사각 설정 설명은 이전 v0.2.0-draft.1 재현에 적용한다. 버전관리·태그 보존 규칙은 공통이다.

# 2~3명 팀 운영

GitHub 개인 계정의 비공개 저장소 하나를 사용합니다. 공동작업자는 전체 코드를 탐색하고 브랜치를 올릴 수 있습니다.
소유자는 Settings → Collaborators에서 GitHub ID로 초대합니다. 유료 조직·서버·클라우드 개발환경은 필요 없습니다.
main은 PR로 변경한다는 팀 합의로 운영하며, 유료 강제 보호 규칙은 설정하지 않습니다.

## 작업 순서

1. main에서 최신 내용을 Pull합니다.
2. feature/주제 또는 experiment/이름/주제 브랜치를 만듭니다.
3. AI와 코드를 수정하거나 configs/experiments/에 새 설정을 작성합니다.
4. 단위 검증과 필요한 작은 실행·시각화 확인을 합니다.
5. 커밋하고 Push합니다.
6. PR에 변경 목적·검증·결과 위치를 적습니다. 다른 한 명이 읽고 main에 반영합니다.

```text
git switch main
git pull --ff-only
git switch -c experiment/member/risk-weight
# 수정 및 검증
git add configs/experiments docs results
git commit -m "Add risk-weight experiment profile"
git push -u origin experiment/member/risk-weight
```

GitHub Desktop: Current branch → New branch → Commit → Publish branch → Create Pull Request 순서입니다.
영구 개인 브랜치보다 작업 단위 브랜치를 사용합니다.

## 버전 보존

상세 절차와 AI 요청문은 [VERSIONING.md](VERSIONING.md), 배포 목록은 [VERSIONS.md](VERSIONS.md)를 따른다.

- v0.2.0-draft.1은 최초 공유 초안입니다. 태그를 이동/덮어쓰지 않습니다.
- 재현: 새 Clone 폴더 → 해당 태그 선택 → 기준 환경 설치 → 같은 설정 실행.
- main은 최신 개선 버전이며, 독립 변형은 별도 태그/Release로 남길 수 있습니다.
- 공통 기준 변경 시 새 ID·설정·회귀 검증·배포 lock·태그를 함께 만듭니다.
- 단순 개발 중 lock을 자동 재작성하지 않습니다.

## 무료 운영

계산은 각자 PC에서 합니다. GitHub Actions는 **수동 실행만** 등록했습니다.
Actions → Manual validation → Run workflow에서 계정의 남은 무료 실행량을 확인하고 실행합니다.
자동 예약·PR별 실행·클라우드 완주 실행·유료 기능은 활성화하지 않습니다. 유료 사용 예산을 추가하지 않습니다.
무료 실행량을 다 쓰면 로컬 검증으로 계속 작업합니다. 계정 전체의 사용량이므로 다른 저장소 사용량도 포함됩니다.
공식 안내: https://docs.github.com/en/get-started/learning-about-github/githubs-plans

Git에는 소스·설정·작은 데이터/fixture·문서·결과 색인만 보관합니다.
.venv, outputs, work, 비밀키·개인 참고 문서는 제외합니다. 주요 결과 ZIP은 해당 버전 Release에 첨부합니다.
대시보드는 ZIP을 풀고 로컬에서 엽니다. 비공개 Pages나 서버 배포는 필요 없습니다.
