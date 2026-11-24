# 시장 리서치 (컨센서스 노트)

개인 투자 리서치 사이트: https://musicinsun.github.io/consensus-note/

- **컨센서스 노트** (`index.html`): 노션 '컨센서스 프로젝트' DB를 카드로 보여줌. 금주의/오늘의 보고서, 주간 그래프, 네이버 블로그용 글 초안 만들기
- **LME 알루미늄 팔로우** (`aluminum.html`): 현물가·재고·스프레드 차트 (삼아알미늄 판가 구조)
- **미국장 마감** (`us-market.html`): Finviz S&P 500 히트맵, 미국 지수 4종, NYSE·NASDAQ 등락 및 52주 신고가·신저가

AI(Codex, Claude 등)로 수정할 때는 먼저 [AGENTS.md](AGENTS.md)를 읽게 하세요.

## 자동으로 돌아가는 것

| 작업 | 주기 | 파일 |
|---|---|---|
| 노션 동기화 (본문·이미지 포함) | 3시간마다 | `.github/workflows/sync.yml` → `sync_notion.py` → `data.js` |
| LME 알루미늄 갱신 | 하루 4번 | `.github/workflows/lme.yml` → `fetch_lme.py` → `lme.js` |
| 미국장 마감 갱신 | 매일 오전 9시 (한국시간) | `.github/workflows/us-market.yml` → `fetch_us_market.py` → `us-market.js` |

바로 반영하려면: Actions → **노션 동기화** → **Run workflow** (날짜 칸에 `261120`처럼 넣으면 그날만 빠르게)

## 저장소와 비밀값

- 블로그 이미지는 연도별 저장소 `musicinsun/consensus-images-<연도>`에 저장됨. **지우면 네이버 블로그 그림이 깨지니 지우지 말 것.**
- Settings → Secrets and variables → Actions
  - `NOTION_TOKEN`: 노션 내부 통합 토큰 (콘텐츠 읽기만)
  - `IMAGES_TOKEN`: 이미지 저장소에 쓰는 GitHub 토큰 (해당 저장소 Contents 읽기·쓰기)
- 새해가 오기 전에: `consensus-images-<다음 연도>` 저장소를 만들고 Pages를 켠 뒤, `IMAGES_TOKEN` 토큰 설정에 그 저장소를 추가

## 미국장 마감 갱신 설정

- 공개 웹사이트 표시와 저장이 허용된 [Barchart OnDemand](https://www.barchart.com/ondemand/api) 키를 GitHub **Settings → Secrets and variables → Actions**에서 `BARCHART_API_KEY`로 등록합니다. 키에는 지수 시세와 거래소 집계 심볼에 대한 접근이 필요합니다. S&P 500 장중 그래프를 추가하려면 해당 지수의 분봉 조회도 필요합니다.
- 처음에는 **Actions → 미국장 마감 갱신 → Run workflow**에서 확인합니다. 휴장일에는 이전 거래일 기록을 계속 표시합니다. 실행이 지연되거나 수집에 실패하면 마지막 저장 기록과 해당 날짜가 표시됩니다.
- 히트맵은 Finviz 최신 위젯으로 표시하고 TradingView 히트맵으로 전환할 수 있습니다. 날짜별로 지수 종가와 등락률, S&P 500의 개장·장중 범위·마감 요약, 거래소 집계를 저장합니다. S&P 500 장중 그래프는 데이터가 있는 날짜에 펼쳐서 볼 수 있습니다.
- GitHub Actions의 데이터 커밋이 배포를 기다리지 않도록 미국장 페이지는 공개 저장소의 `main`에서 최신 기록을 읽습니다. Pages에 배포된 기록을 예비로 사용합니다.
