# AGENTS.md — AI 작업 안내 (Codex, Claude 등 공통)

이 저장소를 수정하는 AI는 작업 전에 이 파일을 끝까지 읽어 주세요.
사람 사용자도 참고용으로 볼 수 있게 한국어로 씁니다. 사용자와의 대화도 한국어로 해 주세요.

## 이 사이트는 무엇인가

- 개인 투자 리서치 사이트. GitHub Pages로 배포: https://musicinsun.github.io/consensus-note/
- 빌드 도구·프레임워크·패키지 매니저 없음. **순수 HTML/CSS/JS 정적 파일**이며 `main` 브랜치 루트가 그대로 배포된다.
- 외부 라이브러리는 글꼴(Pretendard, jsDelivr)만 쓴다. 차트는 직접 그린 SVG.
- 사용자는 비개발자다. 변경 이유와 결과를 쉬운 말로 설명해 주세요.

## 파일 구조

| 파일 | 역할 | 손으로 수정? |
|---|---|---|
| `index.html` | 컨센서스 노트 페이지 (카드 목록, 금주의 보고서, 주간 그래프, 블로그 초안) | 가능 |
| `aluminum.html` | LME 알루미늄 팔로우 페이지 (차트 5개) | 가능 |
| `style.css` | 모든 페이지 공통: 색 토큰, 다크 모드, 사이드바 레이아웃 | 가능 (주의) |
| `data.js` | 노션 데이터 + 리포트 본문 HTML (`window.CONSENSUS`, `window.NOTES`) | **금지 — 자동 생성** |
| `lme.js` | LME 알루미늄 가격·재고 (`window.LME`) | **금지 — 자동 생성** |
| `sync_notion.py` | 노션 → `data.js`, 본문 이미지 → 이미지 저장소 | 사용자 요청 시에만 |
| `fetch_lme.py` | westmetall.com → `lme.js` | 사용자 요청 시에만 |
| `.github/workflows/sync.yml` | 노션 동기화 (3시간마다 + 수동, 날짜 지정 가능) | 사용자 요청 시에만 |
| `.github/workflows/lme.yml` | LME 갱신 (하루 4번) | 사용자 요청 시에만 |

## 절대 하지 말 것

1. **`data.js`, `lme.js`를 손으로 고치지 않는다.** 자동 동기화가 몇 시간마다 통째로 덮어쓴다.
   데이터 모양을 바꾸려면 `sync_notion.py` / `fetch_lme.py`를 고친다.
2. **이미지 저장소(`musicinsun/consensus-images-<연도>`)의 파일을 지우거나 옮기거나 이름을 바꾸지 않는다.**
   네이버 블로그 글들이 `https://musicinsun.github.io/consensus-images-<연도>/<블록ID>.jpg` 주소를 직접 불러온다. 지우면 블로그 그림이 깨진다.
3. 비밀값(`NOTION_TOKEN`, `IMAGES_TOKEN`)을 코드·로그·커밋에 넣지 않는다. 워크플로에서 `secrets.*`로만 쓴다.
4. 노션 DB 속성 이름(아래 표)을 코드에서 바꾸지 않는다. 바꾸면 동기화가 빈 값을 넣는다.
5. 빌드 도구(npm, 번들러, 프레임워크)를 들여오지 않는다. 정적 파일 그대로 배포되는 구조를 유지한다.
6. 저장소를 비공개로 바꾸거나 삭제하지 않는다 (GitHub Pages와 블로그 이미지가 멈춘다).

## 새 페이지를 추가하는 방법

1. 새 파일 `<이름>.html`을 만든다. `aluminum.html`을 뼈대로 복사하면 편하다. 필수 요소:
   ```html
   <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
   <link rel="stylesheet" href="style.css">
   ...
   <body>
   <div class="app">
   <nav class="side" aria-label="페이지"> ... </nav>
   <div class="wrap"> 페이지 내용 </div>
   </div>
   ```
2. **사이드바 메뉴를 모든 페이지에 똑같이 추가한다.** 현재 메뉴 (각 파일의 `<nav class="side">` 안):
   ```html
   <div class="brand">시장 리서치</div>
   <a href="index.html">컨센서스 노트<small>증권사 리포트 기록</small></a>
   <a href="aluminum.html">LME 알루미늄 팔로우<small>삼아알미늄 판가</small></a>
   ```
   - 새 `<a>`를 `index.html`, `aluminum.html`, 새 파일 **세 곳 모두**에 넣는다.
   - 지금 보고 있는 페이지의 링크에만 `aria-current="page"`를 붙인다.
3. 색은 `style.css`의 CSS 변수(`--bg`, `--surface`, `--text`, `--muted`, `--line`, `--accent` 등)만 쓴다. 다크 모드는 변수로 자동 처리된다. 차트 선 색은 `--s-price`, `--s-stock`, `--s-spread`, `--s-spread2`.
4. 휴대폰(폭 860px 이하)에서는 사이드바가 위쪽 가로 탭으로 바뀐다. 새 페이지도 좁은 화면에서 가로 스크롤이 생기지 않게 만든다.
5. 새 페이지에 매일 바뀌는 데이터가 필요하면: `fetch_<이름>.py`로 `<이름>.js`(`window.<이름> = {...}`)를 만들고, `.github/workflows/`에 워크플로를 새로 추가한다. 기존 워크플로와 같은 `concurrency: group: data-push`를 쓰고, 커밋 전에 `git pull --rebase`를 한다 (`lme.yml` 참고).

## 데이터 형식 (읽기 전용 참고)

`data.js`
- `window.CONSENSUS.rows`: `[페이지ID, 날짜(YYMMDD), 기업명, 증권사, 투자의견코드, UPSIDE, 추가공부, 선정, 선정이유]`
  - 투자의견코드: `C`=CONVICTION BUY, `B`=BUY, `H`=HOLD, `S`=SELL, `N`=NR, `J`=수주 코멘트 (여러 개면 `|`로 구분)
  - 추가공부: `1`=공부하자, `0`=NO, `null`=미정 / 선정: `1`=오늘의, `2`=금주의, `null`=없음
  - 예전 기록은 기업명이 `하이브(SK)`처럼 증권사를 괄호에 담고 있어 `index.html`이 분리해서 보여준다.
- `window.NOTES`: `{페이지ID: {t: 노션 수정시각, h: 본문 HTML}}`. 이미지는 이미지 저장소의 절대 주소.
- 노션 페이지 주소: `https://www.notion.so/<페이지ID>`

`lme.js`
- `window.LME.rows`: `[날짜(YYYY-MM-DD), 현물가 Cash-Settlement USD/t, 3개월물 USD/t, 재고 t]`

노션 DB('컨센서스 프로젝트') 속성 이름: `기업명`(제목), `증권사`, `투자 의견`, `UPSIDE`, `날짜별 묶음`(선택 또는 다중 선택, 여러 개면 가장 마지막(최근) 날짜를 씀), `추가 공부`, `선정`, `선정 이유`

## 작업 방식

- 작업은 브랜치 + Pull Request로 올려서 사용자가 GitHub에서 확인 후 Merge하게 한다.
- 다른 AI가 같은 파일을 동시에 고치고 있을 수 있다. 시작 전에 최신 `main`을 받는다.
- 자동 동기화 봇(`notion-sync`, `lme-sync`)이 `data.js`/`lme.js`를 자주 커밋한다. 이 두 파일에서 충돌이 나면 **원격(main) 쪽 내용을 그대로 채택**한다.
- 바꾼 화면은 데스크톱과 휴대폰 폭 모두에서 확인하고, 사용자에게 무엇이 바뀌었는지 쉬운 말로 알려 준다.
