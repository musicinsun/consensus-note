# 시장 리서치 (컨센서스 노트)

개인 투자 리서치 사이트: https://musicinsun.github.io/consensus-note/

- **컨센서스 노트** (`index.html`): 노션 '컨센서스 프로젝트' DB를 카드로 보여줌. 금주의/오늘의 보고서, 주간 그래프, 네이버 블로그용 글 초안 만들기
- **LME 알루미늄 팔로우** (`aluminum.html`): 현물가·재고·스프레드 차트 (삼아알미늄 판가 구조)
- **낸드·GPU 가격** (`market.html`): 낸드 현물·계약 가격과 GPU 7종 렌탈가 표·차트

AI(Codex, Claude 등)로 수정할 때는 먼저 [AGENTS.md](AGENTS.md)를 읽게 하세요.

## 자동으로 돌아가는 것

| 작업 | 주기 | 파일 |
|---|---|---|
| 노션 동기화 (본문·이미지 포함) | 3시간마다 | `.github/workflows/sync.yml` → `sync_notion.py` → `data.js` |
| LME 알루미늄 갱신 | 하루 4번 | `.github/workflows/lme.yml` → `fetch_lme.py` → `lme.js` |
| 낸드·GPU 가격 갱신 | 하루 4번 확인 | `.github/workflows/market.yml` → `fetch_market.py` → `market-data.js` |

바로 반영하려면: Actions → **노션 동기화** → **Run workflow** (날짜 칸에 `261120`처럼 넣으면 그날만 빠르게)

## 낸드·GPU 가격

- GPU는 [GPU Rental Prices](https://gpurentalprices.com/data)의 일별 공개 데이터(CC BY 4.0)를 집계합니다. 당일 확인된 온디맨드 요금만 사용하며 같은 모델의 공급자별 최저가를 기준으로 최저가, 하위 25% 가격, 공급자 수를 계산합니다. 전일 데이터가 빠진 날은 전일 대비를 공란으로 표시합니다.
- 낸드 가격 파일은 페이지에서 직접 불러올 수 있습니다. CSV 머리글은 `date,kind,item,price,unit`입니다. `kind`는 `spot`(현물) 또는 `contract`(계약)입니다. 입력한 기록은 해당 브라우저에 저장됩니다.
- 자동 갱신에는 공개 게시가 허용된 가격 피드가 필요합니다. 해당 피드의 HTTPS 주소를 Actions 비밀값 `NAND_FEED_URL`에 등록합니다. 접속 토큰이 필요한 경우 `NAND_FEED_TOKEN`도 등록합니다. 피드 응답은 CSV와 같은 필드의 JSON 배열이며 `price`는 숫자입니다. 수집된 가격은 공개 파일 `market-data.js`에 함께 저장됩니다.

## 저장소와 비밀값

- 블로그 이미지는 연도별 저장소 `musicinsun/consensus-images-<연도>`에 저장됨. **지우면 네이버 블로그 그림이 깨지니 지우지 말 것.**
- Settings → Secrets and variables → Actions
  - `NOTION_TOKEN`: 노션 내부 통합 토큰 (콘텐츠 읽기만)
  - `IMAGES_TOKEN`: 이미지 저장소에 쓰는 GitHub 토큰 (해당 저장소 Contents 읽기·쓰기)
- 새해가 오기 전에: `consensus-images-<다음 연도>` 저장소를 만들고 Pages를 켠 뒤, `IMAGES_TOKEN` 토큰 설정에 그 저장소를 추가
