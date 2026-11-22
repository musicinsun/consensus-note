(() => {
  const models = {
    h100: "H100 (Hopper)", h200: "H200 (Hopper)", b200: "B200 (Blackwell)",
    a100: "A100", l40s: "L40S",
  };
  // A list preserves the chosen order even for all-numeric model keys.
  const gpuModels = [...Object.entries(models), ["4090", "RTX 4090"], ["5090", "RTX 5090 (Blackwell)"]];
  const day = 86400000;
  const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 });
  const axisNumber = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
  const dollar = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 4 });
  const priceText = value => Number.isFinite(value) ? number.format(value) : "—";
  const el = id => document.getElementById(id);
  const localKey = "consensus-note:nand-prices:v1";
  const sourcePrefix = "window.MARKET_PRICES = ";
  const state = { data: window.MARKET_PRICES || { gpu: {}, nand: [] }, local: [], series: [] };
  // Quarter-ending month quotes cited in TEAMGROUP's Nov 2, 2026 IR, slide 18.
  const contractReference = new Map([
    ["2025-12-31", 12.16], ["2026-03-31", 23.69],
    ["2026-06-30", 25.76], ["2026-09-30", 26.43],
  ]);
  const isContract = row => row.kind === "contract";
  const time = date => Date.parse(date + "T00:00:00Z");
  const iso = stamp => new Date(stamp).toISOString().slice(0, 10);

  function html(tag, text, className) {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function svg(tag, attrs, text) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    if (text != null) node.textContent = text;
    return node;
  }

  function changeFrom(now, previous) {
    return Number.isFinite(now) && previous > 0 ? Math.round((now / previous - 1) * 1000) / 10 : null;
  }

  function changeText(change) {
    return (change > 0 ? "+" : "") + change.toFixed(1) + "%";
  }

  function changeCell(now, previous) {
    const change = changeFrom(now, previous);
    return html("td", change == null ? "—" : changeText(change),
      change > 0 ? "market-up" : change < 0 ? "market-down" : "");
  }

  function insertRow(body, label, note, cells) {
    const row = html("tr");
    const name = html("th", label);
    name.scope = "row";
    if (note) name.append(html("small", note));
    row.append(name, ...cells);
    body.append(row);
  }

  function chart(box, points, lines, unit, empty, options = {}) {
    box.replaceChildren();
    const values = points.flatMap(row => lines.flatMap(line =>
      (line.range || [line.key]).map(key => row[key]))).filter(Number.isFinite);
    if (!values.length) {
      box.append(html("p", empty, "chart-empty"));
      return;
    }
    const width = Math.max(240, box.clientWidth);
    const height = width < 420 ? 218 : (width >= 680 && options.daily ? 350 : 285);
    const padding = { top: 16, right: 12, bottom: 30, left: 50 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;
    const first = time(points[0].date), last = time(points.at(-1).date);
    const low = Math.min(...values), high = Math.max(...values);
    const cushion = (high - low) * .12 || Math.abs(low) * .08 || 1;
    const requestedTicks = options.ticks || [];
    const min = Math.min(low < 0 ? low - cushion : Math.max(0, low - cushion), ...requestedTicks);
    const max = Math.max(high + cushion, ...requestedTicks);
    const x = stamp => padding.left + (last === first ? plotWidth / 2 : (stamp - first) * plotWidth / (last - first));
    const y = value => padding.top + (max - value) * plotHeight / (max - min);
    const graph = svg("svg", {
      viewBox: "0 0 " + width + " " + height,
      height, role: "img", "aria-label": lines.map(line => line.label).join(" / ") + " · " + unit,
    });
    const yTicks = options.ticks || Array.from({ length: 5 }, (_, i) => min + (max - min) * i / 4);
    for (const value of yTicks) {
      const py = y(value);
      const style = options.suffix && value === 0 ? "guide guide-zero" : "guide";
      graph.append(svg("line", { x1: padding.left, x2: width - padding.right, y1: py, y2: py, class: style }));
      graph.append(svg("text", { x: padding.left - 6, y: py + 4, "text-anchor": "end" },
        (max - min < .04 ? priceText(value) : axisNumber.format(value)) + (options.suffix || "")));
    }
    const tickCount = first === last ? 1 : Math.min(width < 420 ? 3 : 5, points.length, (last - first) / day + 1);
    const xTicks = options.quarters ? points.map(point => [time(point.date), point.label])
      : Array.from({ length: tickCount }, (_, i) => {
      const stamp = tickCount === 1 ? first : first + Math.round((last - first) / day * i / (tickCount - 1)) * day;
      return [stamp, iso(stamp)];
    });
    xTicks.forEach(([stamp, label], i) => {
      const anchor = xTicks.length === 1 || options.quarters ? "middle" : i === 0 ? "start" : i === xTicks.length - 1 ? "end" : "middle";
      const px = options.quarters ? Math.min(width - 19, x(stamp)) : x(stamp);
      graph.append(svg("text", { x: px, y: height - 8, "text-anchor": anchor }, label));
    });
    let hasGaps = false;
    for (const line of lines) {
      if (line.range) {
        const marks = [];
        const midpoints = [];
        for (const point of points) {
          const [lower, upper] = line.range.map(key => point[key]);
          if (!Number.isFinite(lower) || !Number.isFinite(upper)) continue;
          const cx = x(time(point.date)) + line.offset;
          const cy = y((lower + upper) / 2);
          const span = svg("line", { x1: cx, x2: cx, y1: y(upper), y2: y(lower),
            stroke: line.color, "stroke-width": 5, "stroke-linecap": "round" });
          span.append(svg("title", {}, point.label + " · " + line.label + " " + lower + "% ~ " + upper + "%"));
          marks.push(span, svg("circle", { cx, cy, r: 3.8, fill: line.color }));
          midpoints.push(cx + "," + cy);
        }
        if (line.connect) graph.append(svg("polyline", { points: midpoints.join(" "),
          fill: "none", stroke: line.color, "stroke-width": 1.6, "stroke-opacity": .55 }));
        graph.append(...marks);
        continue;
      }
      let path = "", gaps = "", previous = null;
      const dots = [];
      for (const point of points) {
        const value = point[line.key], stamp = time(point.date);
        if (Number.isFinite(value)) {
          const cx = x(stamp), cy = y(value);
          const coordinate = cx + "," + cy;
          const hasGap = previous && options.daily && stamp - previous.stamp > day;
          if (hasGap) gaps += "M" + previous.coordinate + "L" + coordinate;
          path += (!previous || hasGap ? "M" : "L") + coordinate;
          const dot = svg("circle", { cx, cy, r: points.length > 100 ? 1.6 : 3, fill: line.color });
          dot.append(svg("title", {}, point.date + " · " + line.label + " " + priceText(value) + " " + unit));
          dots.push(dot);
          if (options.valueLabels) {
            dots.push(svg("text", { x: cx, y: cy - 9, "text-anchor": "middle", class: "plot-value" }, dollar.format(value)));
          }
          previous = { stamp, coordinate };
        } else if (!options.daily) {
          previous = null;
        }
      }
      if (gaps) {
        hasGaps = true;
        graph.append(svg("path", { d: gaps, fill: "none", stroke: line.color, "stroke-width": 1.5,
          "stroke-dasharray": "4 5", "stroke-opacity": .65 }));
      }
      graph.append(svg("path", { d: path, fill: "none", stroke: line.color, "stroke-width": 2, "stroke-linejoin": "round" }), ...dots);
    }
    const figure = html("figure");
    const key = html("div", null, "chart-key");
    for (const line of lines) {
      const item = html("span", line.label);
      item.style.setProperty("--series", line.color);
      key.append(item);
    }
    const caption = points.length === 1 ? "기록 1건 · 데이터가 쌓이면 추세선을 표시합니다."
      : unit + (hasGaps ? " · 점선 사이에는 가격 기록이 없습니다." : "");
    figure.append(key, graph, html("figcaption", caption));
    box.append(figure);
  }

  function drawGpu() {
    const key = el("gpu-model").value;
    const all = state.data.gpu[key] || [];
    const range = Number(el("gpu-range").value);
    const cutoff = all.length && range ? time(all.at(-1).date) - (range - 1) * day : -Infinity;
    chart(el("gpu-chart"), all.filter(row => time(row.date) >= cutoff), [
      { key: "low", label: "최저가", color: "var(--s-price)" },
      { key: "p25", label: "하위 25% 가격", color: "var(--s-spread)" },
    ], "USD/GPU·시간", "이 모델의 가격 기록이 없습니다.", { daily: true });
  }

  const forecasts = new Map();
  for (const row of el("outlook-history").rows) {
    const { quarter, low, high } = row.dataset;
    const publication = row.querySelector("time").dateTime;
    if (!forecasts.has(quarter)) forecasts.set(quarter, []);
    forecasts.get(quarter).push({ label: row.cells[0].textContent, publication, low: Number(low), high: Number(high) });
  }

  function drawOutlook() {
    const quarters = [...forecasts.keys()].sort().map(date => {
      const versions = forecasts.get(date).sort((a, b) => a.publication.localeCompare(b.publication));
      const latest = versions.at(-1);
      const prior = versions.at(-2);
      return { date, label: latest.label, price: contractReference.get(date),
        priorLow: prior?.low, priorHigh: prior?.high, low: latest.low, high: latest.high };
    });
    const latestActual = quarters.findLast(point => Number.isFinite(point.price));
    if (latestActual) {
      const [year, month] = latestActual.date.split("-");
      el("contract-value").textContent = dollar.format(latestActual.price);
      el("contract-detail").textContent = year + "년 " + Number(month) + "월 · 공개 IR";
    }
    chart(el("contract-chart"), quarters, [
      { key: "price", label: "분기 말 계약가", color: "var(--s-price)" },
    ], "USD", "공개 계약가 기록이 없습니다.", { quarters: true, valueLabels: true, ticks: [10, 15, 20, 25, 30] });
    chart(el("outlook-chart"), quarters, [
      { range: ["priorLow", "priorHigh"], label: "이전 전망", color: "var(--s-stock)", offset: -5 },
      { range: ["low", "high"], label: "최근 전망", color: "var(--s-spread)", offset: 5, connect: true },
    ], "전분기 대비 (%)", "공개 전망 기록이 없습니다.",
    { quarters: true, suffix: "%", ticks: [-10, 0, 20, 40, 60, 80] });
  }

  function renderGpu() {
    const body = el("gpu-table");
    body.replaceChildren();
    const recent = [];
    for (const [key, label] of gpuModels) {
      const history = state.data.gpu[key] || [];
      const last = history.at(-1);
      const before = last && history.find(row => row.date === iso(time(last.date) - day));
      if (key === "h100" || key === "5090") {
        const change = changeFrom(last?.low, before?.low);
        el(key + "-value").textContent = Number.isFinite(last?.low) ? dollar.format(last.low) : "—";
        el(key + "-detail").textContent = change == null ? (last?.date || "가격 기록 없음")
          : "전일 대비 " + changeText(change) + " · " + last.date;
      }
      if (last) recent.push(last.date);
      insertRow(body, label, last?.date, [
        html("td", priceText(last?.low)), changeCell(last?.low, before?.low),
        html("td", priceText(last?.p25)), html("td", last?.n ?? "—"),
      ]);
    }
    const latest = recent.sort().at(-1);
    el("gpu-status").textContent = latest
      ? "최근 공개 기록 " + latest + " · 전일 기록이 있으면 최저가 변동률을 표시합니다."
      : "공급자 가격을 불러오지 못했습니다.";
    drawGpu();
  }

  const correlation = JSON.parse(el("corr-data").textContent);
  el("corr-period").textContent = correlation.from + " ~ " + correlation.through + " 분석";

  function renderCorrelation() {
    const results = correlation[el("corr-frequency").value][el("corr-metric").value];
    const body = el("corr-body");
    body.replaceChildren();
    for (const [key, label] of gpuModels) {
      const cells = results[key].map(([coefficient, count]) => {
        const rounded = coefficient == null ? null : Math.round(coefficient * 100) / 100;
        const value = rounded == null ? "—" : (rounded > 0 ? "+" : "") + rounded.toFixed(2);
        const cell = html("td", value);
        if (coefficient) {
          cell.className = coefficient > 0 ? "corr-positive" : "corr-negative";
          cell.style.setProperty("--corr-strength", Math.round(Math.abs(coefficient) * 28) + "%");
        }
        if (coefficient == null) cell.title = "비교 구간의 렌탈가 변화율이 일정합니다.";
        cell.append(html("small", count + "쌍"));
        return cell;
      });
      insertRow(body, label.split(" (")[0], "", cells);
    }
  }

  function mergeNand(rows) {
    const groups = new Map();
    for (const row of rows) {
      const key = JSON.stringify([row.kind, row.item, row.unit]);
      if (!groups.has(key)) groups.set(key, new Map());
      groups.get(key).set(row.date, row);
    }
    return [...groups.values()].map(dates => [...dates.values()].sort((a, b) => a.date.localeCompare(b.date)))
      .sort((a, b) => a[0].item.localeCompare(b[0].item));
  }

  function drawNand() {
    const rows = state.series[Number(el("nand-series").value)] || [];
    chart(el("nand-chart"), rows, [
      { key: "price", label: rows[0]?.item || "낸드 계약가", color: "var(--s-price)" },
    ], rows[0]?.unit || "", "계약가 기록이 없습니다.");
  }

  function renderNand() {
    const selection = el("nand-series"), oldLabel = selection.selectedOptions[0]?.textContent;
    const body = el("nand-table");
    body.replaceChildren();
    const localContracts = state.local.filter(isContract);
    state.series = mergeNand(state.data.nand.filter(isContract).concat(localContracts));
    selection.replaceChildren();
    el("nand-records").hidden = !state.series.length;
    el("nand-reset").hidden = !localContracts.length;
    if (!state.series.length) return;
    state.series.forEach((rows, index) => {
      const last = rows.at(-1), prior = rows.at(-2);
      const name = last.item + " (" + last.unit + ")";
      selection.add(new Option(name, index, false, name === oldLabel));
      const amount = html("td", priceText(last.price));
      amount.append(html("small", last.unit));
      insertRow(body, last.item, "", [
        amount, changeCell(last.price, prior?.price), html("td", last.date),
      ]);
    });
    el("nand-status").textContent = localContracts.length ? "내 파일 포함" : "";
    drawNand();
  }

  function parseNandCsv(raw) {
    const rows = raw.replace(/^\uFEFF/, "").trim().split(/\r?\n/).filter(line => line.trim());
    const split = line => line.split(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/)
      .map(x => x.trim().replace(/^"(.*)"$/, "$1").replaceAll('""', '"'));
    if (!rows.length || split(rows.shift()).join(",") !== "date,kind,item,price,unit" || !rows.length || rows.length > 10000) {
      throw new Error("CSV의 첫 줄과 가격 기록을 확인해 주세요.");
    }
    return rows.map((line, index) => {
      const fields = split(line);
      const [date, kind, item, amount, unit] = fields;
      const price = Number(amount), stamp = time(date);
      if (fields.length !== 5 || !/^\d{4}-\d{2}-\d{2}$/.test(date)
          || !Number.isFinite(stamp) || iso(stamp) !== date || stamp > Date.now() + day
          || (kind !== "contract" && kind !== "spot") || !item || item.length > 100
          || !unit || unit.length > 30 || !Number.isFinite(price) || price <= 0) {
        throw new Error((index + 2) + "번째 줄의 날짜, 구분, 품목, 가격, 단위를 확인해 주세요.");
      }
      return { date, kind, item, price, unit };
    });
  }

  el("nand-file").addEventListener("change", async event => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      if (file.size > 2_000_000) throw new Error("CSV 파일은 2MB 이하로 저장해 주세요.");
      const rows = parseNandCsv(await file.text()).filter(isContract);
      if (!rows.length) throw new Error("CSV에 계약가(contract) 행이 없습니다.");
      const merged = mergeNand([...state.local, ...rows]).flat();
      localStorage.setItem(localKey, JSON.stringify(merged));
      state.local = merged;
      el("import-status").textContent = "계약가 기록 " + rows.length + "개를 불러왔습니다.";
    } catch (error) {
      el("import-status").textContent = error.message;
    } finally {
      event.target.value = "";
      renderNand();
    }
  });
  el("nand-reset").addEventListener("click", () => {
    state.local = state.local.filter(row => !isContract(row));
    if (state.local.length) localStorage.setItem(localKey, JSON.stringify(state.local));
    else localStorage.removeItem(localKey);
    el("import-status").textContent = "이 브라우저에 저장한 계약가 기록을 지웠습니다.";
    renderNand();
  });
  for (const [key, label] of gpuModels) el("gpu-model").add(new Option(label, key));
  el("gpu-model").addEventListener("change", drawGpu);
  el("gpu-range").addEventListener("change", drawGpu);
  el("corr-frequency").addEventListener("change", renderCorrelation);
  el("corr-metric").addEventListener("change", renderCorrelation);
  el("nand-series").addEventListener("change", drawNand);
  try {
    const saved = JSON.parse(localStorage.getItem(localKey));
    if (Array.isArray(saved)) state.local = saved;
  } catch {
    state.local = [];
  }
  renderGpu();
  renderCorrelation();
  renderNand();
  drawOutlook();
  let pending;
  window.addEventListener("resize", () => {
    clearTimeout(pending);
    pending = setTimeout(() => { drawGpu(); if (state.series.length) drawNand(); drawOutlook(); }, 100);
  });

  // Scheduled commits made by GITHUB_TOKEN need not trigger a Pages rebuild.
  if (location.hostname === "musicinsun.github.io" && location.pathname.startsWith("/consensus-note/")) {
    const url = "https://raw.githubusercontent.com/musicinsun/consensus-note/main/market-data.js";
    fetch(url, { cache: "no-cache" }).then(response => {
      if (!response.ok) throw new Error("Price update unavailable");
      return response.text();
    }).then(text => {
      const source = text.trim();
      if (!source.startsWith(sourcePrefix) || !source.endsWith(";")) return;
      const data = JSON.parse(source.slice(sourcePrefix.length, -1));
      if (data.version !== 1 || data.gpuSource !== "gpurentalprices" || !Array.isArray(data.nand)) return;
      state.data = data;
      renderGpu();
      renderNand();
    }).catch(() => { /* The published snapshot remains available. */ });
  }
})();
