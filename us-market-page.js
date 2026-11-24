const indices = {
  SPX: 'S&P 500',
  IXIC: '나스닥 종합',
  SOX: '필라델피아 반도체',
  RUT: 'Russell 2000',
};
const breadthMetrics = [
  ['up', '상승', 'positive'], ['down', '하락', 'negative'], ['flat', '보합', ''],
  ['high', '52주 신고가', 'positive'], ['low', '52주 신저가', 'negative'], ['ratio', '상승/하락', ''],
];
const session = document.getElementById('session');
const status = document.getElementById('status');
const indexCards = document.getElementById('index-cards');
const breadth = document.getElementById('breadth');
const breadthNote = document.getElementById('breadth-note');
const chart = document.getElementById('chart');
const marketFlow = document.getElementById('market-flow');
const chartDetails = document.getElementById('chart-details');
const heatmapSwitch = document.getElementById('heatmap-switch');
const heatmapNote = document.getElementById('heatmap-note');
const finvizMap = document.getElementById('finviz-map');
const tradingViewMap = document.getElementById('tradingview-map');
const svgNamespace = 'http://www.w3.org/2000/svg';
let archive = {};

const integer = new Intl.NumberFormat('ko-KR');
const decimal = new Intl.NumberFormat('ko-KR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
const signedPercent = value => `${value > 0 ? '+' : ''}${decimal.format(value)}%`;
const signedClass = value => value > 0 ? 'positive' : value < 0 ? 'negative' : '';
const finiteText = (value, format) => Number.isFinite(value) ? format(value) : '–';

function element(tag, value = '', className = '') {
  const node = document.createElement(tag);
  node.textContent = value;
  if (className) node.className = className;
  return node;
}

function svgNode(tag, attributes, text = '') {
  const node = document.createElementNS(svgNamespace, tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
  if (text) node.textContent = text;
  return node;
}

function flowText(day) {
  const close = day.indices?.SPX?.change;
  if (!Number.isFinite(close)) return '저장된 마감 기록이 없습니다.';
  const {open, low, high} = day.flow || {};
  if (![open, low, high].every(Number.isFinite)) {
    return `S&P 500은 ${signedPercent(close)}로 마감했습니다. 개장과 장중 범위는 원본 차트에서 확인할 수 있습니다.`;
  }
  return `${signedPercent(open)}로 출발해 장중 ${signedPercent(low)}~${signedPercent(high)} 사이를 움직인 뒤 ${signedPercent(close)}로 마감했습니다.`;
}

function renderArchiveChart(day) {
  const points = day.bars?.SPX;
  if (!points?.length || !chart.clientWidth || !chart.clientHeight) return;

  const width = chart.clientWidth;
  const height = chart.clientHeight;
  const plot = {left: 54, top: 16, right: width - 22, bottom: height - 30};
  const lastMinute = day.closeMinute || 960;
  const values = points.map(([, value]) => value);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const step = Math.max(0.25, 10 ** Math.floor(Math.log10(Math.max(high - low, 0.25) / 4)));
  const tick = Math.ceil(Math.max(high - low, step) / (step * 5)) * step;
  const min = Math.floor(low / tick) * tick;
  const max = Math.max(min + tick, Math.ceil(high / tick) * tick);
  const x = minute => plot.left + (minute - 570) / (lastMinute - 570) * (plot.right - plot.left);
  const y = value => plot.bottom - (value - min) / (max - min) * (plot.bottom - plot.top);
  const svg = svgNode('svg', {viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': `${session.value} S&P 500 장중 흐름, 전 거래일 종가 대비 등락률`});

  for (let value = min; value <= max + tick / 100; value += tick) {
    const isZero = Math.abs(value) < tick / 100;
    svg.append(svgNode('line', {x1: plot.left, x2: plot.right, y1: y(value), y2: y(value), class: isZero ? 'chart-zero' : 'chart-gridline'}));
    svg.append(svgNode('text', {x: plot.left - 7, y: y(value) + 4, 'text-anchor': 'end'}, `${isZero ? 0 : Number(value.toFixed(2))}%`));
  }
  for (const minute of [570, lastMinute < 960 ? 675 : 750, lastMinute]) {
    const hour = Math.floor(minute / 60);
    const label = `${String(hour).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')}`;
    svg.append(svgNode('text', {x: x(minute), y: plot.bottom + 21, 'text-anchor': 'middle'}, label));
  }

  const path = points.map(([minute, value], index) => `${index ? 'L' : 'M'}${x(minute).toFixed(1)},${y(value).toFixed(1)}`).join(' ');
  svg.append(svgNode('path', {d: path, fill: 'none', stroke: 'var(--s-price)', 'stroke-width': 2.3}));
  chart.replaceChildren(svg);
}

function renderSession() {
  const day = archive[session.value] || {};
  indexCards.replaceChildren();
  breadth.replaceChildren();
  for (const [symbol, label] of Object.entries(indices)) {
    const quote = day.indices?.[symbol] || {};
    const card = element('div', '', 'index-card');
    card.append(element('span', label), element('strong', finiteText(quote.close, decimal.format)), element('b', finiteText(quote.change, signedPercent), signedClass(quote.change)));
    indexCards.append(card);
  }
  for (const exchange of ['NYSE', 'NASDAQ']) {
    const counts = day.breadth?.[exchange] || {};
    const summary = element('article', '', 'breadth-card');
    const list = element('dl');
    for (const [key, label, color] of breadthMetrics) {
      const ratio = key === 'ratio';
      const value = ratio ? counts.up / counts.down : counts[key];
      const formatted = finiteText(value, ratio ? decimal.format : integer.format);
      const group = element('div');
      group.append(element('dt', label), element('dd', value === Infinity ? '∞' : formatted, color));
      list.append(group);
    }
    summary.append(element('h3', exchange), list);
    breadth.append(summary);
  }
  breadthNote.textContent = day.breadth ? `${session.value} 미국장 마감 · Barchart 집계` : '저장된 집계가 없습니다. 최신 수치는 Barchart에서 확인할 수 있습니다.';
  status.textContent = day.seed ? '2026-11-23 마감 기록을 먼저 넣었습니다. 이후 마감 기록 저장에는 Barchart API 키가 필요합니다.' : '';
  status.hidden = !status.textContent;
  marketFlow.textContent = flowText(day);
  chartDetails.hidden = !(day.bars?.SPX?.length > 1);
  chart.replaceChildren();
  if (chartDetails.open && !chartDetails.hidden) renderArchiveChart(day);
}

async function readArchive(url) {
  const response = await fetch(url, {cache: 'no-cache', signal: AbortSignal.timeout(5000)});
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = (await response.text()).match(/^window\.US_MARKET\s*=\s*(\{[\s\S]*\});\s*$/);
  if (!data) throw new Error('US market archive format');
  return JSON.parse(data[1]).sessions;
}

async function loadArchive() {
  const urls = ['us-market.js'];
  if (location.hostname === 'musicinsun.github.io') {
    urls.push('https://raw.githubusercontent.com/musicinsun/consensus-note/main/us-market.js');
  }
  const files = await Promise.allSettled(urls.map(readArchive));
  archive = Object.assign({}, ...files.filter(record => record.status === 'fulfilled').map(record => record.value));
  const dates = Object.keys(archive).sort().reverse();
  if (dates.length) session.replaceChildren(...dates.map(date => new Option(date, date)));
  else session.replaceChildren(new Option('저장된 기록 없음', ''));
  session.disabled = dates.length < 2;
  renderSession();
}

session.addEventListener('change', renderSession);
heatmapSwitch.addEventListener('click', () => {
  const showTradingView = tradingViewMap.hidden;
  if (showTradingView && !tradingViewMap.hasChildNodes()) {
    const heatmap = element('tv-heatmap');
    for (const [key, value] of Object.entries({'heatmap-type': 'stock', 'data-source': 'SPX500', grouping: 'sector', 'block-size': 'market_cap_basic', 'block-color': 'change'})) {
      heatmap.setAttribute(key, value);
    }
    const script = document.createElement('script');
    script.type = 'module';
    script.src = 'https://widgets.tradingview-widget.com/w/en/tv-heatmap.js';
    tradingViewMap.append(heatmap, script);
  }
  finvizMap.hidden = showTradingView;
  tradingViewMap.hidden = !showTradingView;
  heatmapSwitch.setAttribute('aria-pressed', String(showTradingView));
  heatmapSwitch.textContent = showTradingView ? 'Finviz 히트맵' : 'TradingView 히트맵';
  heatmapNote.textContent = `시가총액으로 크기 표시 · 1일 등락률 · ${showTradingView ? 'TradingView' : 'Finviz'} 최신 화면`;
});
new ResizeObserver(() => {
  if (chartDetails.open && !chartDetails.hidden) renderArchiveChart(archive[session.value]);
}).observe(chart);
loadArchive();
