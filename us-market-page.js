const indices = {
  SPX: ['S&P 500', 'SP:SPX', 'var(--s-price)'],
  IXIC: ['나스닥 종합', 'NASDAQ:IXIC', 'var(--s-spread)'],
  SOX: ['필라델피아 반도체', 'NASDAQ:SOX', 'var(--s-spread2)'],
  RUT: ['Russell 2000', 'TVC:RUT', 'var(--accent)'],
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
const chartNote = document.getElementById('chart-note');
const chartLink = document.getElementById('chart-link');
const chartSwitch = document.getElementById('chart-switch');
const legend = document.getElementById('chart-legend');
const svgNamespace = 'http://www.w3.org/2000/svg';
let archive = {};
let liveSymbol = 'SPX';

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

function renderArchiveChart(day) {
  const series = Object.keys(indices).filter(symbol => day.bars?.[symbol]?.length > 1);
  if (!series.length) return false;

  const width = Math.max(280, chart.clientWidth);
  const height = chart.clientHeight;
  const plot = {left: 54, top: 16, right: width - 22, bottom: height - 30};
  const allPoints = series.flatMap(symbol => day.bars[symbol]);
  const lastMinute = day.closeMinute || 960;
  const values = allPoints.map(([, value]) => value);
  const low = Math.min(0, ...values);
  const high = Math.max(0, ...values);
  const step = Math.max(0.25, 10 ** Math.floor(Math.log10(Math.max(high - low, 0.25) / 4)));
  const tick = Math.ceil(Math.max(high - low, step) / (step * 5)) * step;
  const min = Math.floor(low / tick) * tick;
  const max = Math.max(min + tick, Math.ceil(high / tick) * tick);
  const x = minute => plot.left + (minute - 570) / (lastMinute - 570) * (plot.right - plot.left);
  const y = value => plot.bottom - (value - min) / (max - min) * (plot.bottom - plot.top);
  const svg = svgNode('svg', {viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': `${session.value} 미국 지수 5분 추이, 전 거래일 종가 대비 등락률`});

  for (let value = min; value <= max + tick / 100; value += tick) {
    const isZero = Math.abs(value) < tick / 100;
    svg.append(svgNode('line', {x1: plot.left, x2: plot.right, y1: y(value), y2: y(value), class: isZero ? 'chart-zero' : 'chart-gridline'}));
    svg.append(svgNode('text', {x: plot.left - 7, y: y(value) + 4, 'text-anchor': 'end'}, `${isZero ? 0 : Number(value.toFixed(2))}%`));
  }
  const middleMinute = lastMinute < 960 ? 660 : 750;
  for (const minute of [570, middleMinute, lastMinute]) {
    const hour = Math.floor(minute / 60);
    const label = `${String(hour).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')}`;
    svg.append(svgNode('text', {x: x(minute), y: plot.bottom + 21, 'text-anchor': 'middle'}, label));
  }

  legend.replaceChildren();
  for (const symbol of series) {
    const color = indices[symbol][2];
    const path = day.bars[symbol].map(([minute, value], index) => `${index ? 'L' : 'M'}${x(minute).toFixed(1)},${y(value).toFixed(1)}`).join(' ');
    svg.append(svgNode('path', {d: path, fill: 'none', stroke: color, 'stroke-width': 2.3}));
    const key = element('span');
    const line = element('i');
    line.style.setProperty('--series-color', color);
    key.append(line, indices[symbol][0]);
    legend.append(key);
  }
  chart.replaceChildren(svg);
  chartNote.textContent = '전 거래일 종가 대비 · 5분 간격 · 미국 동부시간';
  chartSwitch.hidden = true;
  legend.hidden = false;
  return true;
}

function renderLiveChart() {
  chartSwitch.hidden = false;
  legend.hidden = true;
  chartNote.textContent = 'TradingView 최신 화면 · 5분 간격 · 미국 동부시간';
  const [, symbol] = indices[liveSymbol];
  const source = new URL('https://www.tradingview.com/chart/');
  source.search = new URLSearchParams({symbol, interval: '5'});
  chartLink.href = source.href;
  for (const button of chartSwitch.querySelectorAll('button')) {
    button.setAttribute('aria-pressed', String(button.dataset.symbol === liveSymbol));
  }
  const widget = element('div', '', 'tradingview-widget-container');
  widget.style.height = '100%';
  const viewport = element('div', '', 'tradingview-widget-container__widget');
  viewport.style.height = 'calc(100% - 24px)';
  const attribution = element('div', '', 'tradingview-widget-copyright');
  const link = element('a', 'TradingView', 'blue-text');
  link.href = source.href;
  link.target = '_blank';
  link.rel = 'noopener nofollow';
  attribution.append(link);
  const script = document.createElement('script');
  script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
  script.async = true;
  script.textContent = JSON.stringify({
    symbol, autosize: true, interval: '5', range: '1D', timezone: 'America/New_York', style: '2',
    theme: matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light', locale: 'kr',
    hide_top_toolbar: true, hide_side_toolbar: true, hide_volume: true, allow_symbol_change: false,
  });
  chart.replaceChildren(widget);
  widget.append(viewport, attribution, script);
}

function renderSession() {
  const day = archive[session.value] || {};
  indexCards.replaceChildren();
  breadth.replaceChildren();
  for (const [symbol, [label]] of Object.entries(indices)) {
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
  if (!renderArchiveChart(day)) {
    renderLiveChart();
    if (session.value) chartNote.textContent = `${session.value} 저장 차트 없음 · TradingView 최신 5분 차트`;
  }
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
chartSwitch.addEventListener('click', event => {
  const symbol = event.target.closest('button')?.dataset.symbol;
  if (!symbol || symbol === liveSymbol) return;
  liveSymbol = symbol;
  renderLiveChart();
  if (session.value) chartNote.textContent = `${session.value} 저장 차트 없음 · TradingView 최신 5분 차트`;
});
new ResizeObserver(() => {
  if (archive[session.value]?.bars) renderArchiveChart(archive[session.value]);
}).observe(chart);
loadArchive();
