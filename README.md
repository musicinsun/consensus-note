# 컨센서스 노트

노션 '컨센서스 프로젝트' DB를 카드로 보여주는 개인 사이트. 카드를 누르면 해당 노션 페이지가 열린다.

- `index.html`: 사이트
- `data.js`: 노션 데이터 스냅샷 (자동 생성)
- `sync_notion.py`: 노션 → `data.js` 동기화 스크립트
- `.github/workflows/sync.yml`: 3시간마다 자동 동기화

## 자동 동기화 설정 (한 번만)

1. https://www.notion.so/profile/integrations 에서 **새 내부 통합** 만들기 → 권한은 "콘텐츠 읽기"만 → 토큰 복사
2. 노션에서 '컨센서스 프로젝트' DB 페이지 → 우측 상단 `•••` → **연결** → 방금 만든 통합 추가
3. GitHub 저장소 → Settings → Secrets and variables → Actions → **New repository secret**
   이름 `NOTION_TOKEN`, 값은 1번 토큰
4. Settings → Pages → Source: `Deploy from a branch`, 브랜치 `main` / `(root)`
5. Actions 탭 → "노션 동기화" → **Run workflow** 로 첫 동기화 확인
