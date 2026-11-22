(() => {
  const models = {
    h100: "H100 (Hopper)", h200: "H200 (Hopper)", b200: "B200 (Blackwell)",
    a100: "A100", l40s: "L40S",
  };
  // A list preserves the chosen order even for all-numeric model keys.
  const gpuModels = [...Object.entries(models), ["4090", "RTX 4090"], ["5090", "RTX 5090 (Blackwell)"]];
  const labels = { spot: "현물", contract: "계약" };
  const day = 86400000;
  const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 });
  const axisNumber = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
  const priceText = value => Number.isFinite(value) ? number.format(value) : "—";
  const el = id => document.getElementById(id);
  const localKey = "consensus-note:nand-prices:v1";
  const sourcePrefix = "window.MARKET_PRICES = ";
  const state = { data: window.MARKET_PRICES || { gpu: {}, nand: [] }, local: [], series: [] };
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

  function changeCell(now, previous) {
    if (!Number.isFinite(now) || !(previous > 0)) return html("td", "—");
    const change = Math.round((now / previous - 1) * 1000) / 10;
    return html("td", (change > 0 ? "+" : "") + change.toFixed(1) + "%",
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

  function chart(box, points, lines, unit, empty, daily = false) {
    box.replaceChildren();
    const values = points.flatMap(row => lines.map(line => row[line.key])).filter(Number.isFinite);
    if (!values.length) {
      box.append(html("p", empty, "chart-empty"));
      return;
    }
    const width = Math.max(240, box.clientWidth);
    const height = width < 500 ? 192 : 225;
    const padding = { top: 16, right: 12, bottom: 28, left: 48 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;
    const first = time(points[0].date), last = time(points.at(-1).date);
    const low = Math.min(...values), high = Math.max(...values);
    const cushion = (high - low) * .12 || low * .08 || 1;
    const min = Math.max(0, low - cushion), max = high + cushion;
    const x = stamp => padding.left + (last === first ? plotWidth / 2 : (stamp - first) * plotWidth / (last - first));
    const y = value => padding.top + (max - value) * plotHeight / (max - min);
    const graph = svg("svg", {
      viewBox: "0 0 " + width + " " + height,
      height, role: "img", "aria-label": lines.map(line => line.label).join(" / ") + " 가격 추이 · " + unit,
    });
    for (let i = 0; i <= 4; i++) {
      const value = min + (max - min) * i / 4, py = y(value);
      graph.append(svg("line", { x1: padding.left, x2: width - padding.right, y1: py, y2: py, class: "guide" }));
      graph.append(svg("text", { x: padding.left - 6, y: py + 4, "text-anchor": "end" },
        max - min < .04 ? priceText(value) : axisNumber.format(value)));
    }
    const indices = [...new Set([0, Math.floor((points.length - 1) / 2), points.length - 1])];
    indices.forEach((index, indexInList) => {
      const anchor = indices.length === 1 ? "middle" : indexInList === 0 ? "start" : indexInList === indices.length - 1 ? "end" : "middle";
      graph.append(svg("text", { x: x(time(points[index].date)), y: height - 8, "text-anchor": anchor }, points[index].date));
    });
    for (const line of lines) {
      let path = "", previous = null;
      const dots = [];
      for (const point of points) {
        const value = point[line.key], stamp = time(point.date);
        if (Number.isFinite(value)) {
          const cx = x(stamp), cy = y(value);
          path += (previous == null || (daily && stamp - previous > day) ? "M" : "L") + cx + "," + cy;
          const dot = svg("circle", { cx, cy, r: points.length > 100 ? 1.6 : 3, fill: line.color });
          dot.append(svg("title", {}, point.date + " · " + line.label + " " + priceText(value) + " " + unit));
          dots.push(dot);
          previous = stamp;
        } else previous = null;
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
    const caption = points.length === 1 ? "기록 1건 · 데이터가 쌓이면 추세선을 표시합니다." : unit;
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
    ], "USD/GPU·시간", "이 모델의 가격 기록이 없습니다.", true);
  }

  function renderGpu() {
    const body = el("gpu-table");
    body.replaceChildren();
    const recent = [];
    for (const [key, label] of gpuModels) {
      const history = state.data.gpu[key] || [];
      const last = history.at(-1);
      const before = last && history.find(row => row.date === iso(time(last.date) - day));
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

  function mergeNand(rows) {
    const groups = new Map();
    for (const row of rows) {
      const key = JSON.stringify([row.kind, row.item, row.unit]);
      if (!groups.has(key)) groups.set(key, new Map());
      groups.get(key).set(row.date, row);
    }
    return [...groups.values()].map(dates => [...dates.values()].sort((a, b) => a.date.localeCompare(b.date)))
      .sort((a, b) => b[0].kind.localeCompare(a[0].kind) || a[0].item.localeCompare(b[0].item));
  }

  function drawNand() {
    const rows = state.series[Number(el("nand-series").value)] || [];
    chart(el("nand-chart"), rows, [
      { key: "price", label: rows.length ? labels[rows[0].kind] + " · " + rows[0].item : "낸드 가격", color: "var(--s-price)" },
    ], rows[0]?.unit || "", "가격 파일을 불러오거나 공개 게시가 허용된 공급 데이터를 연결하면 차트가 표시됩니다.");
  }

  function renderNand() {
    const selection = el("nand-series"), oldLabel = selection.selectedOptions[0]?.textContent;
    const body = el("nand-table");
    body.replaceChildren();
    state.series = mergeNand([...state.data.nand, ...state.local]);
    selection.replaceChildren();
    el("nand-reset").hidden = !state.local.length;
    if (!state.series.length) {
      const row = html("tr"), message = html("td", "연결된 현물·계약 가격 기록이 없습니다.");
      message.colSpan = 4;
      row.append(message);
      body.append(row);
      selection.add(new Option("품목 없음", ""));
      selection.disabled = true;
    } else {
      selection.disabled = false;
      state.series.forEach((rows, index) => {
        const last = rows.at(-1), prior = rows.at(-2);
        const name = labels[last.kind] + " · " + last.item + " (" + last.unit + ")";
        selection.add(new Option(name, index, false, name === oldLabel));
        const amount = html("td", priceText(last.price));
        amount.append(html("small", last.unit));
        insertRow(body, last.item, labels[last.kind], [
          amount, changeCell(last.price, prior?.price), html("td", last.date),
        ]);
      });
    }
    el("nand-status").textContent = state.local.length ? "내 파일 포함" : "";
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
          || !Object.hasOwn(labels, kind) || !item || item.length > 100
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
      const rows = parseNandCsv(await file.text());
      const merged = mergeNand([...state.local, ...rows]).flat();
      localStorage.setItem(localKey, JSON.stringify(merged));
      state.local = merged;
      el("import-status").textContent = "가격 기록 " + rows.length + "개를 불러왔습니다.";
    } catch (error) {
      el("import-status").textContent = error.message;
    } finally {
      event.target.value = "";
      renderNand();
    }
  });
  el("nand-reset").addEventListener("click", () => {
    state.local = [];
    localStorage.removeItem(localKey);
    el("import-status").textContent = "이 브라우저에 저장한 가격 기록을 지웠습니다.";
    renderNand();
  });
  for (const [key, label] of gpuModels) el("gpu-model").add(new Option(label, key));
  el("gpu-model").addEventListener("change", drawGpu);
  el("gpu-range").addEventListener("change", drawGpu);
  el("nand-series").addEventListener("change", drawNand);
  try {
    const saved = JSON.parse(localStorage.getItem(localKey));
    if (Array.isArray(saved)) state.local = saved;
  } catch {
    state.local = [];
  }
  renderGpu();
  renderNand();
  let pending;
  window.addEventListener("resize", () => {
    clearTimeout(pending);
    pending = setTimeout(() => { drawGpu(); drawNand(); }, 100);
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
