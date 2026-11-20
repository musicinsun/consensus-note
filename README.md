# 시장 리서치 (컨센서스 노트)

개인 투자 리서치 사이트: https://musicinsun.github.io/consensus-note/

- **컨센서스 노트** (`index.html`): 노션 '컨센서스 프로젝트' DB를 카드로 보여줌. 금주의/오늘의 보고서, 주간 그래프, 네이버 블로그용 글 초안 만들기
- **LME 알루미늄 팔로우** (`aluminum.html`): 현물가·재고·스프레드 차트 (삼아알미늄 판가 구조)

AI(Codex, Claude 등)로 수정할 때는 먼저 [AGENTS.md](AGENTS.md)를 읽게 하세요.

## 자동으로 돌아가는 것

| 작업 | 주기 | 파일 |
|---|---|---|
| 노션 동기화 (본문·이미지 포함) | 3시간마다 | `.github/workflows/sync.yml` → `sync_notion.py` → `data.js` |
| LME 알루미늄 갱신 | 하루 4번 | `.github/workflows/lme.yml` → `fetch_lme.py` → `lme.js` |

바로 반영하려면: Actions → **노션 동기화** → **Run workflow** (날짜 칸에 `261120`처럼 넣으면 그날만 빠르게)

## 저장소와 비밀값

- 블로그 이미지는 연도별 저장소 `musicinsun/consensus-images-<연도>`에 저장됨. **지우면 네이버 블로그 그림이 깨지니 지우지 말 것.**
- Settings → Secrets and variables → Actions
  - `NOTION_TOKEN`: 노션 내부 통합 토큰 (콘텐츠 읽기만)
  - `IMAGES_TOKEN`: 이미지 저장소에 쓰는 GitHub 토큰 (해당 저장소 Contents 읽기·쓰기)
- 새해가 오기 전에: `consensus-images-<다음 연도>` 저장소를 만들고 Pages를 켠 뒤, `IMAGES_TOKEN` 토큰 설정에 그 저장소를 추가
