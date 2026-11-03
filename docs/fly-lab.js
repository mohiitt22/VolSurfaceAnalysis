/* Fly Analysis tab — hourly parquet folders, day A/B smile / fly / spread compare. */
(function () {
  const READY = "hold-v2";
  const state = {
    folder: "",
    folders: [],
    dates: [],
    filesByDate: new Map(),
    rowCache: new Map(),
    source: "upload",
    view: "compare", // compare | hold
    dateA: null,
    dateB: null,
    hour: null,
    targetDte: 60,
    expiryMode: "target",
    expiryA: "",
    expiryB: "",
    metaA: null,
    metaB: null,
    wing: 100,
    spreadWidth: 100,
    side: "call",
    align: "offset",
    focusStrike: null,
    compare: null,
    // Same-contract hold path
    holdDate: null,
    holdDays: 10,
    holdHour: null,
    holdTargetDte: 60,
    holdExpiryMode: "target",
    holdExpiry: "",
    holdMeta: null,
    holdFocusStrike: "all", // "all" or numeric K/offset
    holdPath: null,
    busy: false,
    error: "",
    holdError: "",
    note: "Choose your SNP data folder from this computer (files named YYYY-MM-DD.parquet).",
  };

  function el(id) {
    return document.getElementById(id);
  }

  function fmt(n, d) {
    if (n === null || n === undefined || !Number.isFinite(Number(n))) return "—";
    return Number(n).toLocaleString(undefined, {
      minimumFractionDigits: d,
      maximumFractionDigits: d,
    });
  }

  function layout(title, x, y) {
    return {
      title: { text: title, font: { size: 14, color: "#e6edf3" } },
      paper_bgcolor: "#0d1117",
      plot_bgcolor: "#0d1117",
      font: { color: "#c9d1d9", size: 11 },
      margin: { l: 64, r: 24, t: 48, b: 72 },
      legend: { orientation: "h", y: -0.28, yanchor: "top" },
      xaxis: { title: { text: x }, gridcolor: "#21262d", zerolinecolor: "#30363d" },
      yaxis: { title: { text: y }, gridcolor: "#21262d", zerolinecolor: "#30363d" },
      hovermode: "closest",
    };
  }

  function plot(id, traces, title, x, y) {
    const node = el(id);
    if (!node || !window.Plotly) return;
    Plotly.react(node, traces, layout(title, x, y), { responsive: true, displayModeBar: false });
  }

  function barPlot(id, xs, ys, title, xlab, ylab, texts) {
    const colors = (ys || []).map((v) => (Number(v) >= 0 ? "#3dba7a" : "#f85149"));
    plot(id, [{
      type: "bar",
      x: xs,
      y: ys,
      text: texts || ys.map((v) => fmt(v, 3)),
      textposition: "outside",
      marker: { color: colors },
      name: "Δ",
      hovertemplate: "%{x}<br>%{y:.4f}<extra></extra>",
    }], title, xlab, ylab);
  }

  function xLabel() {
    return state.align === "strike" ? "Strike" : "ATM offset";
  }

  function xOf(row, kind) {
    if (state.align === "strike") {
      if (kind === "fly") return Number(row.centre);
      if (kind === "spread") return Number(row.near);
      return Number(row.strike);
    }
    return Number(row.offset);
  }

  function matchKey(row, kind) {
    const side = row.side || "";
    if (state.align === "strike") {
      const k = kind === "fly" ? row.centre : kind === "spread" ? row.near : row.strike;
      return `${side}:${Number(k)}`;
    }
    return `${side}:${Number(row.offset)}`;
  }

  function matchPairs(rowsA, rowsB, kind) {
    const mapB = new Map();
    (rowsB || []).forEach((row) => mapB.set(matchKey(row, kind), row));
    return (rowsA || []).map((row) => {
      const other = mapB.get(matchKey(row, kind));
      return {
        x: xOf(row, kind),
        offsetA: row.offset,
        offsetB: other ? other.offset : null,
        strike: state.align === "strike"
          ? (kind === "fly" ? row.centre : kind === "spread" ? row.near : row.strike)
          : null,
        a: row,
        b: other || null,
      };
    }).filter((row) => row.b);
  }

  function shell() {
    return `
      <section class="sa-block">
        <h2>Upload data folder</h2>
        <p class="sa-note">Select the folder on your computer that contains hourly chain files named <code>YYYY-MM-DD.parquet</code> (columns: contract, time, expiry, strike, underlying, IVs, premiums, Greeks, atm, dte). Files are read in the browser — nothing is uploaded to a remote server. Only the dates you compare are parsed.</p>
        <div class="sa-controls">
          <label>Choose folder from this computer
            <input id="faUpload" type="file" webkitdirectory multiple />
          </label>
        </div>
        <div class="sa-nav">
          <button type="button" id="faLoadFolder">Load selected folder</button>
        </div>
        <details class="sa-note" style="margin-top:8px">
          <summary style="cursor:pointer;color:#58a6ff">Optional: use local desk path (developer)</summary>
          <div class="sa-controls" style="margin-top:8px">
            <label>Detected folders <select id="faFolder"></select></label>
            <label>Or folder path <input id="faPath" type="text" placeholder="SNP data" /></label>
          </div>
          <div class="sa-nav">
            <button type="button" id="faUseFolder">Use local path</button>
            <button type="button" id="faRefreshFolders">Refresh local folders</button>
          </div>
        </details>
        <div id="faFolderNote" class="sa-summary"></div>
      </section>
      <section class="sa-block">
        <h2>Analysis mode</h2>
        <div class="sa-nav">
          <button type="button" id="faModeCompare" class="fa-mode-btn active">Day vs day compare</button>
          <button type="button" id="faModeHold" class="fa-mode-btn">Same-contract hold path</button>
        </div>
        <p class="sa-note" id="faModeNote">Day vs day: pick two sessions and compare smiles / flies / spreads.</p>
      </section>
      <div id="faPanelCompare">
      <section class="sa-block">
        <h2>Day vs day — date, hour, expiry</h2>
        <div class="sa-controls">
          <label>Reference date A <select id="faDateA"></select></label>
          <label>Comparison date B <select id="faDateB"></select></label>
          <label>Hour snapshot <select id="faHour"></select></label>
          <label>Target DTE
            <input id="faTargetDte" type="number" min="1" max="365" step="1" value="60" />
          </label>
          <label>Expiry mode
            <select id="faExpiryMode">
              <option value="target">Closest to target DTE (default)</option>
              <option value="manual">Pick expiry per date</option>
            </select>
          </label>
          <label>Expiry A <select id="faExpiryA"></select></label>
          <label>Expiry B <select id="faExpiryB"></select></label>
          <label>Fly wing
            <select id="faWing">
              <option value="50">50</option>
              <option value="100" selected>100</option>
              <option value="150">150</option>
              <option value="200">200</option>
            </select>
          </label>
          <label>Spread width
            <select id="faSpreadWidth">
              <option value="50">50</option>
              <option value="100" selected>100</option>
              <option value="150">150</option>
              <option value="200">200</option>
            </select>
          </label>
          <label>Side
            <select id="faSide">
              <option value="call">Calls</option>
              <option value="put">Puts</option>
              <option value="both">Both</option>
            </select>
          </label>
          <label>Align structures
            <select id="faAlign">
              <option value="offset">ATM-offset wise (sticky delta)</option>
              <option value="strike">Strike-wise (fixed K, e.g. 7800)</option>
            </select>
          </label>
          <label>Focus strike
            <select id="faFocusStrike"></select>
          </label>
        </div>
        <div class="sa-nav">
          <button type="button" id="faPrevA">Previous A</button>
          <button type="button" id="faNextA">Next A</button>
          <button type="button" id="faPrevB">Previous B</button>
          <button type="button" id="faNextB">Next B</button>
          <button type="button" id="faPrevWin">Previous window</button>
          <button type="button" id="faNextWin">Next window</button>
          <button type="button" id="faBNext">B = next after A</button>
          <button type="button" id="faSwap">Swap dates</button>
          <button type="button" id="faRun">Run comparison</button>
        </div>
        <div id="faSummary" class="sa-summary"></div>
        <p id="faWarn" class="sa-warn"></p>
      </section>
      <section class="sa-block">
        <h2>Spot move</h2>
        <div id="faSpot" class="sa-summary"></div>
      </section>
      <section class="sa-block" id="faFocusBlock">
        <h2>Fixed-strike drilldown</h2>
        <p class="sa-note" id="faFocusNote">Pick Align = strike-wise and a focus strike (e.g. 7800). Same absolute fly / spread / smile node is tracked as spot moves.</p>
        <div id="faFocusCards" class="sa-summary"></div>
        <div id="faFocusDetail" class="sa-scroll" style="margin-top:10px"></div>
      </section>
      <section class="sa-block">
        <h2>IV smile comparison</h2>
        <p class="sa-note" id="faSmileNote">OTM smile: puts below ATM, calls above ATM. IVs in vol points.</p>
        <div id="faSmile" class="sa-chart"></div>
        <div id="faSmileChg" class="sa-chart"></div>
      </section>
      <section class="sa-block">
        <h2 id="faFlyTitle">Fly premium</h2>
        <p class="sa-note" id="faFlyNote">Fly = P(K−h) − 2P(K) + P(K+h) from file premiums.</p>
        <div id="faFlyPrem" class="sa-chart"></div>
        <div id="faFlyChg" class="sa-chart"></div>
        <div id="faFlyIv" class="sa-chart"></div>
      </section>
      <section class="sa-block">
        <h2 id="faSpreadTitle">Vertical spread premium</h2>
        <p class="sa-note" id="faSpreadNote">Call debit: long near / short near+width. Put debit: long near / short near−width. File premiums.</p>
        <div id="faSpreadPrem" class="sa-chart"></div>
        <div id="faSpreadChg" class="sa-chart"></div>
        <div id="faSpreadGap" class="sa-chart"></div>
      </section>
      <section class="sa-block">
        <h2>Detail tables</h2>
        <div class="sa-scroll"><table id="faFlyTable"></table></div>
        <div class="sa-scroll" style="margin-top:12px"><table id="faSpreadTable"></table></div>
      </section>
      </div>

      <div id="faPanelHold" style="display:none">
      <section class="sa-block">
        <h2>Same-contract hold path</h2>
        <p class="sa-note">Pick <b>one</b> entry day and a ~60 DTE expiry. That calendar expiry is locked. The next 1–10 trading sessions reuse the <b>same contract</b> (DTE falls by about one each session). Track how spot, smile, fly and spread values evolve while you hold it.</p>
        <div class="sa-controls">
          <label>Entry date <select id="fhDate"></select></label>
          <label>Hold days ahead
            <select id="fhHoldDays">
              ${[1,2,3,4,5,6,7,8,9,10].map((n) => `<option value="${n}" ${n === 10 ? "selected" : ""}>${n}</option>`).join("")}
            </select>
          </label>
          <label>Hour snapshot <select id="fhHour"></select></label>
          <label>Target DTE
            <input id="fhTargetDte" type="number" min="1" max="365" step="1" value="60" />
          </label>
          <label>Expiry mode
            <select id="fhExpiryMode">
              <option value="target">Closest to target DTE on entry day</option>
              <option value="manual">Pick expiry on entry day</option>
            </select>
          </label>
          <label>Locked expiry <select id="fhExpiry"></select></label>
          <label>Fly wing
            <select id="fhWing">
              <option value="50">50</option>
              <option value="100" selected>100</option>
              <option value="150">150</option>
              <option value="200">200</option>
            </select>
          </label>
          <label>Spread width
            <select id="fhSpreadWidth">
              <option value="50">50</option>
              <option value="100" selected>100</option>
              <option value="150">150</option>
              <option value="200">200</option>
            </select>
          </label>
          <label>Side
            <select id="fhSide">
              <option value="call">Calls</option>
              <option value="put">Puts</option>
            </select>
          </label>
          <label>Align structures
            <select id="fhAlign">
              <option value="offset">ATM-offset wise</option>
              <option value="strike">Strike-wise (fixed K)</option>
            </select>
          </label>
          <label>Strike scope
            <select id="fhFocusStrike"></select>
          </label>
        </div>
        <div class="sa-nav">
          <button type="button" id="fhPrev">Previous entry day</button>
          <button type="button" id="fhNext">Next entry day</button>
          <button type="button" id="fhRun">Run hold path</button>
        </div>
        <div id="fhSummary" class="sa-summary"></div>
        <p id="fhWarn" class="sa-warn"></p>
      </section>
      <section class="sa-block">
        <h2>Hold path — spot &amp; DTE</h2>
        <div id="fhSpot" class="sa-summary"></div>
        <div id="fhSpotChart" class="sa-chart"></div>
        <div id="fhDteChart" class="sa-chart"></div>
        <div id="fhLevelChart" class="sa-chart"></div>
      </section>
      <section class="sa-block">
        <h2>Hold path — smile (entry vs last hold day)</h2>
        <div id="fhSmile" class="sa-chart"></div>
        <div id="fhSmileChg" class="sa-chart"></div>
        <div id="fhSmileBar" class="sa-chart"></div>
      </section>
      <section class="sa-block" id="fhAllBlock">
        <h2>Hold path — all-strike premium analysis</h2>
        <p class="sa-note">Every available fly / spread on the locked expiry. Curves show entry vs last hold day; bars show premium change (last − entry) across all strikes.</p>
        <div id="fhAllCards" class="sa-summary"></div>
        <div id="fhFlyCurve" class="sa-chart"></div>
        <div id="fhFlyBar" class="sa-chart"></div>
        <div id="fhIvFlyBar" class="sa-chart"></div>
        <div id="fhSpreadCurve" class="sa-chart"></div>
        <div id="fhSpreadBar" class="sa-chart"></div>
        <div class="sa-scroll"><table id="fhAllTable"></table></div>
      </section>
      <section class="sa-block" id="fhOneBlock">
        <h2>Hold path — individual strike path</h2>
        <p class="sa-note">Track one absolute strike (strike-wise) or one ATM offset (offset-wise) across the hold window.</p>
        <div id="fhFocusCards" class="sa-summary"></div>
        <div id="fhFlyPath" class="sa-chart"></div>
        <div id="fhFlyPathBar" class="sa-chart"></div>
        <div id="fhIvFlyPath" class="sa-chart"></div>
        <div id="fhSpreadPath" class="sa-chart"></div>
        <div id="fhSpreadPathBar" class="sa-chart"></div>
        <div class="sa-scroll"><table id="fhFocusTable"></table></div>
      </section>
      <section class="sa-block">
        <h2>Hold path — session table</h2>
        <div class="sa-scroll"><table id="fhDaysTable"></table></div>
      </section>
      </div>`;
  }

  function ensureStyle() {
    if (document.getElementById("fa-style")) return;
    const style = document.createElement("style");
    style.id = "fa-style";
    style.textContent = `
      .sa-block{margin:18px 0;padding:14px;border:1px solid #30363d;border-radius:10px;background:#0d1117}
      .sa-block h2{margin:0 0 10px;font-size:18px}
      .sa-controls,.sa-nav{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}
      .sa-controls label,.sa-block label{display:flex;flex-direction:column;gap:4px;font-size:12px;color:#8b949e}
      .sa-controls select,.sa-controls input,.sa-nav button{background:#161b22;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:6px 8px}
      .sa-nav button:disabled{opacity:.4}
      .sa-summary{display:flex;flex-wrap:wrap;gap:8px}
      .sa-summary span{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:4px 8px}
      .sa-summary em{color:#8b949e;font-style:normal;margin-right:4px}
      .sa-warn{color:#d29922;min-height:1.2em}
      .sa-note{color:#8b949e;font-size:13px}
      .sa-chart{height:360px;margin:8px 0}
      .sa-scroll{overflow:auto;max-height:420px}
      .sa-scroll table{border-collapse:collapse;font-size:12px;min-width:900px;width:100%}
      .sa-scroll th,.sa-scroll td{border-bottom:1px solid #21262d;padding:6px 8px;text-align:right;white-space:nowrap}
      .sa-scroll th:first-child,.sa-scroll td:first-child{text-align:left}
      .fa-focus-row{background:rgba(88,166,255,0.08)}
      .fa-mode-btn.active{border-color:#58a6ff;color:#fff;background:#1f6feb33}
      #viewFly{padding:0 24px 32px;max-width:1400px;margin:0 auto}
      #faPath{min-width:280px}
    `;
    document.head.appendChild(style);
  }

  async function api(url, options) {
    let res;
    try {
      res = await fetch(url, options);
    } catch (err) {
      throw new Error("Local desk API unreachable: " + (err && err.message ? err.message : err));
    }
    const text = await res.text();
    let payload;
    try {
      payload = JSON.parse(text);
    } catch (err) {
      throw new Error("Local desk API is not available on this host. Use Choose folder from this computer instead.");
    }
    if (!payload.ok) throw new Error(payload.error || "Request failed");
    return payload;
  }

  async function rowsFor(day) {
    if (state.rowCache.has(day)) return state.rowCache.get(day);
    const file = state.filesByDate.get(day);
    if (!file) throw new Error("No uploaded file for " + day);
    if (!window.FlyClient) throw new Error("fly-client.js failed to load.");
    const rows = await window.FlyClient.readParquet(file);
    state.rowCache.set(day, rows);
    return rows;
  }

  function applyUploadedCatalog(fileList, label) {
    if (!window.FlyClient) throw new Error("fly-client.js failed to load.");
    const catalog = window.FlyClient.catalogFiles(fileList);
    if (!catalog.count) {
      throw new Error("No YYYY-MM-DD.parquet files found in that folder.");
    }
    state.source = "upload";
    state.folder = label || "Uploaded folder";
    state.filesByDate = catalog.byDate;
    state.rowCache = new Map();
    state.dates = catalog.dates;
    state.metaA = null;
    state.metaB = null;
    state.compare = null;
    state.holdMeta = null;
    state.holdPath = null;
  }

  function shiftDate(iso, step) {
    const i = state.dates.indexOf(iso);
    const j = i + step;
    return j >= 0 && j < state.dates.length ? state.dates[j] : null;
  }

  function fillFolders() {
    const select = el("faFolder");
    if (select) {
      select.innerHTML = `<option value="">Choose folder</option>` + state.folders.map((f) =>
        `<option value="${f.path}">${f.label} · ${f.first} → ${f.last}</option>`
      ).join("");
      if (state.source === "local" && state.folder) select.value = state.folder;
    }
    if (el("faPath") && state.source === "local") el("faPath").value = state.folder || "";
    el("faFolderNote").innerHTML = state.dates.length
      ? `<span><em>Source</em>${state.source === "upload" ? "Browser folder" : "Local desk"}</span>` +
        `<span><em>Active</em>${state.folder}</span>` +
        `<span><em>Days</em>${state.dates.length}</span>` +
        `<span><em>Range</em>${state.dates[0]} → ${state.dates[state.dates.length - 1]}</span>`
      : `<span>${state.note}</span>`;
  }

  function fillDates() {
    for (const id of ["faDateA", "faDateB", "fhDate"]) {
      const node = el(id);
      if (!node) continue;
      node.innerHTML = state.dates.map((d) => `<option value="${d}">${d}</option>`).join("");
    }
    if (!state.dateA || !state.dates.includes(state.dateA)) {
      state.dateA = state.dates[Math.max(0, state.dates.length - 2)] || state.dates[0] || null;
    }
    if (!state.dateB || !state.dates.includes(state.dateB)) {
      state.dateB = state.dates[state.dates.length - 1] || null;
    }
    if (!state.holdDate || !state.dates.includes(state.holdDate)) {
      state.holdDate = state.dates[Math.max(0, state.dates.length - 11)] || state.dates[0] || null;
    }
    if (el("faDateA")) el("faDateA").value = state.dateA || "";
    if (el("faDateB")) el("faDateB").value = state.dateB || "";
    if (el("fhDate")) el("fhDate").value = state.holdDate || "";
  }

  function setView(view) {
    state.view = view;
    const compareOn = view === "compare";
    if (el("faPanelCompare")) el("faPanelCompare").style.display = compareOn ? "" : "none";
    if (el("faPanelHold")) el("faPanelHold").style.display = compareOn ? "none" : "";
    if (el("faModeCompare")) el("faModeCompare").classList.toggle("active", compareOn);
    if (el("faModeHold")) el("faModeHold").classList.toggle("active", !compareOn);
    if (el("faModeNote")) {
      el("faModeNote").textContent = compareOn
        ? "Day vs day: pick two sessions and compare smiles / flies / spreads."
        : "Same-contract hold: pick one entry day and a ~60 DTE expiry, then track that locked expiry over the next 1–10 trading sessions.";
    }
  }

  function commonHours() {
    const ha = (state.metaA && state.metaA.hours) || [];
    const hb = (state.metaB && state.metaB.hours) || [];
    if (!ha.length) return hb;
    if (!hb.length) return ha;
    const setB = new Set(hb);
    const both = ha.filter((h) => setB.has(h));
    return both.length ? both : ha;
  }

  function fillHours() {
    const hours = commonHours();
    el("faHour").innerHTML = hours.map((h) => `<option value="${h}">${h}</option>`).join("");
    if (!state.hour || !hours.includes(state.hour)) {
      state.hour = hours[hours.length - 1] || null;
    }
    if (state.hour) el("faHour").value = state.hour;
  }

  function fillExpiries() {
    const hour = state.hour;
    const packA = hour && state.metaA && state.metaA.by_hour ? state.metaA.by_hour[hour] : null;
    const packB = hour && state.metaB && state.metaB.by_hour ? state.metaB.by_hour[hour] : null;
    const exA = (packA && packA.expiries) || [];
    const exB = (packB && packB.expiries) || [];
    el("faExpiryA").innerHTML = exA.map((e) =>
      `<option value="${e.expiry}">${e.expiry} (${e.dte} DTE)</option>`
    ).join("");
    el("faExpiryB").innerHTML = exB.map((e) =>
      `<option value="${e.expiry}">${e.expiry} (${e.dte} DTE)</option>`
    ).join("");
    if (state.expiryMode === "target") {
      state.expiryA = (packA && packA.default_expiry) || (exA[0] && exA[0].expiry) || "";
      state.expiryB = (packB && packB.default_expiry) || (exB[0] && exB[0].expiry) || "";
    }
    if (state.expiryA) el("faExpiryA").value = state.expiryA;
    if (state.expiryB) el("faExpiryB").value = state.expiryB;
    el("faExpiryA").disabled = state.expiryMode === "target";
    el("faExpiryB").disabled = state.expiryMode === "target";
  }

  function availableFocusStrikes() {
    const c = state.compare;
    if (!c) return [];
    const set = new Set();
    sideRows(c.date_a, "flies").forEach((r) => set.add(Number(r.centre)));
    sideRows(c.date_b, "flies").forEach((r) => set.add(Number(r.centre)));
    sideRows(c.date_a, "spreads").forEach((r) => set.add(Number(r.near)));
    sideRows(c.date_b, "spreads").forEach((r) => set.add(Number(r.near)));
    (c.date_a.smile || []).forEach((r) => set.add(Number(r.strike)));
    (c.date_b.smile || []).forEach((r) => set.add(Number(r.strike)));
    return [...set].filter((n) => Number.isFinite(n)).sort((a, b) => a - b);
  }

  function fillFocusStrikes() {
    const strikes = availableFocusStrikes();
    const node = el("faFocusStrike");
    if (!node) return;
    const atmA = state.compare && state.compare.date_a ? Number(state.compare.date_a.atm_strike) : null;
    node.innerHTML = `<option value="">Auto (ATM A)</option>` + strikes.map((k) =>
      `<option value="${k}">${k}</option>`
    ).join("");
    if (state.focusStrike != null && strikes.includes(Number(state.focusStrike))) {
      node.value = String(state.focusStrike);
    } else if (atmA != null) {
      const nearest = strikes.reduce((best, k) =>
        best == null || Math.abs(k - atmA) < Math.abs(best - atmA) ? k : best, null);
      state.focusStrike = nearest;
      if (nearest != null) node.value = String(nearest);
    } else {
      state.focusStrike = null;
      node.value = "";
    }
  }

  async function refreshFolders() {
    // Optional local-desk discovery only. Browser folder upload is the main path.
    try {
      const payload = await api("/api/fly/folders");
      state.folders = payload.folders || [];
      fillFolders();
    } catch (err) {
      state.folders = [];
      fillFolders();
    }
  }

  async function useFolder(path) {
    state.busy = true;
    state.error = "";
    paintWarn();
    try {
      const payload = await api("/api/fly/set_folder?path=" + encodeURIComponent(path));
      state.source = "local";
      state.folder = path;
      state.filesByDate = new Map();
      state.rowCache = new Map();
      state.dates = payload.dates || [];
      fillFolders();
      fillDates();
      await loadMeta();
      await loadHoldMeta();
      if (state.view === "hold") await runHoldPath();
      else await runCompare();
    } catch (err) {
      state.error = String(err.message || err);
    } finally {
      state.busy = false;
      paintWarn();
    }
  }

  async function loadUploadedFolder() {
    const input = el("faUpload");
    if (!input.files || !input.files.length) {
      state.error = "Choose a folder of YYYY-MM-DD.parquet files first.";
      paintWarn();
      return;
    }
    state.busy = true;
    state.error = "";
    state.holdError = "";
    paintWarn();
    try {
      const first = input.files[0];
      const label = (first.webkitRelativePath || first.name || "folder").split(/[/\\]/)[0] || "Uploaded folder";
      applyUploadedCatalog(input.files, label);
      fillFolders();
      fillDates();
      await loadMeta();
      await loadHoldMeta();
      if (state.view === "hold") await runHoldPath();
      else await runCompare();
    } catch (err) {
      state.error = String(err.message || err);
      state.holdError = state.error;
    } finally {
      state.busy = false;
      paintWarn();
    }
  }

  async function loadMeta() {
    if (!state.dateA || !state.dateB) return;
    const target = state.targetDte;
    if (state.source === "upload") {
      const [rowsA, rowsB] = await Promise.all([rowsFor(state.dateA), rowsFor(state.dateB)]);
      state.metaA = window.FlyClient.dayMetaFromRows(state.dateA, rowsA, target);
      state.metaB = window.FlyClient.dayMetaFromRows(state.dateB, rowsB, target);
    } else {
      const [metaA, metaB] = await Promise.all([
        api(`/api/fly/meta?date=${encodeURIComponent(state.dateA)}&target_dte=${target}`),
        api(`/api/fly/meta?date=${encodeURIComponent(state.dateB)}&target_dte=${target}`),
      ]);
      state.metaA = metaA;
      state.metaB = metaB;
    }
    fillHours();
    fillExpiries();
  }

  async function runCompare() {
    if (!state.dateA || !state.dateB) return;
    if (!state.hour && state.metaA) state.hour = state.metaA.default_hour;
    if (!state.hour) return;
    state.busy = true;
    state.error = "";
    paintWarn();
    try {
      if (state.source === "upload") {
        const fileA = state.filesByDate.get(state.dateA);
        const fileB = state.filesByDate.get(state.dateB);
        if (!fileA || !fileB) throw new Error("Missing uploaded parquet for one of the dates.");
        const opts = {
          hour: state.hour,
          targetDte: state.targetDte,
          wing: state.wing,
          spreadWidth: state.spreadWidth,
        };
        if (state.expiryMode === "manual") {
          opts.expiryA = state.expiryA || null;
          opts.expiryB = state.expiryB || null;
        }
        state.compare = await window.FlyClient.compareFiles(fileA, state.dateA, fileB, state.dateB, opts);
      } else {
        const params = new URLSearchParams({
          date_a: state.dateA,
          date_b: state.dateB,
          hour: state.hour,
          target_dte: String(state.targetDte),
          wing: String(state.wing),
          spread_width: String(state.spreadWidth),
        });
        if (state.expiryMode === "manual") {
          if (state.expiryA) params.set("expiry_a", state.expiryA);
          if (state.expiryB) params.set("expiry_b", state.expiryB);
        }
        state.compare = await api("/api/fly/compare?" + params.toString());
      }
      fillFocusStrikes();
      paintAll();
    } catch (err) {
      state.error = String(err.message || err);
      state.compare = null;
    } finally {
      state.busy = false;
      paintWarn();
    }
  }

  function paintWarn() {
    if (el("faWarn")) el("faWarn").textContent = state.error || (state.busy && state.view === "compare" ? "Working…" : "");
    if (el("fhWarn")) el("fhWarn").textContent = state.holdError || (state.busy && state.view === "hold" ? "Working…" : "");
  }

  async function loadHoldMeta() {
    if (!state.holdDate) return;
    const target = state.holdTargetDte;
    if (state.source === "upload") {
      const rows = await rowsFor(state.holdDate);
      state.holdMeta = window.FlyClient.dayMetaFromRows(state.holdDate, rows, target);
    } else {
      state.holdMeta = await api(`/api/fly/meta?date=${encodeURIComponent(state.holdDate)}&target_dte=${target}`);
    }
    fillHoldHours();
    fillHoldExpiries();
  }

  function fillHoldHours() {
    const hours = (state.holdMeta && state.holdMeta.hours) || [];
    if (!el("fhHour")) return;
    el("fhHour").innerHTML = hours.map((h) => `<option value="${h}">${h}</option>`).join("");
    if (!state.holdHour || !hours.includes(state.holdHour)) {
      state.holdHour = hours[hours.length - 1] || null;
    }
    if (state.holdHour) el("fhHour").value = state.holdHour;
  }

  function fillHoldExpiries() {
    if (!el("fhExpiry")) return;
    const hour = state.holdHour;
    const pack = hour && state.holdMeta && state.holdMeta.by_hour ? state.holdMeta.by_hour[hour] : null;
    const ex = (pack && pack.expiries) || [];
    el("fhExpiry").innerHTML = ex.map((e) =>
      `<option value="${e.expiry}">${e.expiry} (${e.dte} DTE)</option>`
    ).join("");
    if (state.holdExpiryMode === "target") {
      state.holdExpiry = (pack && pack.default_expiry) || (ex[0] && ex[0].expiry) || "";
    }
    if (state.holdExpiry) el("fhExpiry").value = state.holdExpiry;
    el("fhExpiry").disabled = state.holdExpiryMode === "target";
  }

  function holdSideRows(dayPack, key) {
    const side = state.side === "both" ? "call" : state.side;
    // hold panel uses fhSide; mirror into a local side if present
    const holdSide = el("fhSide") ? el("fhSide").value : side;
    return (dayPack[holdSide + "_" + key] || []).map((r) => ({ ...r, side: holdSide }));
  }

  function holdAlign() {
    return el("fhAlign") ? el("fhAlign").value : state.align;
  }

  function findHoldStructure(dayPack, kind, focus) {
    const rows = holdSideRows(dayPack, kind === "fly" ? "flies" : "spreads");
    if (!rows.length) return null;
    const align = holdAlign();
    if (focus == null) return rows[0];
    if (align === "strike") {
      const field = kind === "fly" ? "centre" : "near";
      return rows.find((r) => Number(r[field]) === Number(focus)) || null;
    }
    return rows.find((r) => Number(r.offset) === Number(focus)) || null;
  }

  function availableHoldFocus() {
    const path = state.holdPath;
    if (!path || !path.days || !path.days.length) return [];
    const align = holdAlign();
    const set = new Set();
    path.days.forEach((day) => {
      holdSideRows(day, "flies").forEach((r) => set.add(align === "strike" ? Number(r.centre) : Number(r.offset)));
      holdSideRows(day, "spreads").forEach((r) => set.add(align === "strike" ? Number(r.near) : Number(r.offset)));
    });
    return [...set].filter((n) => Number.isFinite(n)).sort((a, b) => a - b);
  }

  function fillHoldFocus() {
    const node = el("fhFocusStrike");
    if (!node) return;
    const values = availableHoldFocus();
    const label = holdAlign() === "strike" ? "K" : "offset";
    node.innerHTML = `<option value="all">All strikes</option>` + values.map((v) =>
      `<option value="${v}">${label} ${v}</option>`
    ).join("");
    if (state.holdFocusStrike === "all" || state.holdFocusStrike == null || state.holdFocusStrike === "") {
      state.holdFocusStrike = "all";
      node.value = "all";
    } else if (values.includes(Number(state.holdFocusStrike))) {
      node.value = String(state.holdFocusStrike);
    } else {
      state.holdFocusStrike = "all";
      node.value = "all";
    }
  }

  function holdKeyField(kind) {
    if (holdAlign() === "strike") return kind === "fly" ? "centre" : "near";
    return "offset";
  }

  function matchHoldStructures(dayA, dayB, kind) {
    const field = holdKeyField(kind);
    const rowsA = holdSideRows(dayA, kind === "fly" ? "flies" : "spreads");
    const mapB = new Map();
    holdSideRows(dayB, kind === "fly" ? "flies" : "spreads").forEach((r) => mapB.set(Number(r[field]), r));
    return rowsA.map((r) => {
      const key = Number(r[field]);
      const other = mapB.get(key);
      return other ? { key, a: r, b: other } : null;
    }).filter(Boolean).sort((x, y) => x.key - y.key);
  }

  function isAllStrikes() {
    return state.holdFocusStrike === "all" || state.holdFocusStrike === "" || state.holdFocusStrike == null;
  }

  async function runHoldPath() {
    if (!state.holdDate) return;
    state.busy = true;
    state.holdError = "";
    paintWarn();
    try {
      const opts = {
        holdDays: state.holdDays,
        hour: state.holdHour,
        targetDte: state.holdTargetDte,
        wing: Number(el("fhWing") ? el("fhWing").value : state.wing),
        spreadWidth: Number(el("fhSpreadWidth") ? el("fhSpreadWidth").value : state.spreadWidth),
        expiry: state.holdExpiryMode === "manual" ? state.holdExpiry : null,
      };
      if (state.source === "upload") {
        state.holdPath = await window.FlyClient.buildHoldPath(
          state.dates,
          (day) => rowsFor(day),
          state.holdDate,
          opts,
        );
      } else {
        const params = new URLSearchParams({
          start_date: state.holdDate,
          hold_days: String(state.holdDays),
          target_dte: String(state.holdTargetDte),
          wing: String(opts.wing),
          spread_width: String(opts.spreadWidth),
        });
        if (state.holdHour) params.set("hour", state.holdHour);
        if (state.holdExpiryMode === "manual" && state.holdExpiry) params.set("expiry", state.holdExpiry);
        state.holdPath = await api("/api/fly/hold?" + params.toString());
      }
      if (state.holdPath.warnings && state.holdPath.warnings.length) {
        state.holdError = state.holdPath.warnings.slice(0, 3).join(" · ");
      }
      fillHoldFocus();
      paintHoldAll();
    } catch (err) {
      state.holdError = String(err.message || err);
      state.holdPath = null;
    } finally {
      state.busy = false;
      paintWarn();
    }
  }

  function paintHoldAll() {
    const path = state.holdPath;
    if (!path || !el("fhSummary")) return;
    const days = path.days || [];
    const first = days[0];
    const last = days[days.length - 1];
    const align = holdAlign();
    const xLabelHold = align === "strike" ? "Strike" : "ATM offset";
    const allMode = isAllStrikes();

    if (el("fhAllBlock")) el("fhAllBlock").style.display = allMode ? "" : "none";
    if (el("fhOneBlock")) el("fhOneBlock").style.display = allMode ? "none" : "";

    el("fhSummary").innerHTML = [
      ["Entry", path.start_date],
      ["Locked expiry", path.locked_expiry],
      ["Hour", path.hour],
      ["Hold days", `${path.hold_days_available} / ${path.hold_days_requested}`],
      ["DTE path", `${fmt(path.dte_start, 0)} → ${fmt(path.dte_end, 0)}`],
      ["Strike scope", allMode ? "All strikes" : String(state.holdFocusStrike)],
      ["Sessions", days.length],
    ].map(([k, v]) => `<span><em>${k}</em>${v}</span>`).join("");

    el("fhSpot").innerHTML = [
      ["Spot entry", first ? fmt(first.spot, 2) : "—"],
      ["Spot last", last ? fmt(last.spot, 2) : "—"],
      ["Δ Spot", fmt(path.spot_move, 2)],
      ["Δ Spot %", path.spot_move_pct == null ? "—" : fmt(path.spot_move_pct, 3) + "%"],
      ["Level entry", first ? fmt(first.level, 3) : "—"],
      ["Level last", last ? fmt(last.level, 3) : "—"],
    ].map(([k, v]) => `<span><em>${k}</em>${v}</span>`).join("");

    const xs = days.map((d) => d.hold_day);
    const xDates = days.map((d) => `${d.hold_day}: ${d.date}`);
    plot("fhSpotChart", [{
      x: xs, y: days.map((d) => d.spot), text: xDates, mode: "lines+markers", name: "Spot",
      line: { color: "#58a6ff" },
    }], "Spot along hold path", "Hold day", "Spot");
    plot("fhDteChart", [{
      x: xs, y: days.map((d) => d.dte), text: xDates, mode: "lines+markers", name: "DTE",
      line: { color: "#3dba7a" },
    }], "DTE of locked expiry", "Hold day", "DTE");
    plot("fhLevelChart", [{
      x: xs, y: days.map((d) => d.level), text: xDates, mode: "lines+markers", name: "ATM IV",
      line: { color: "#d29922" },
    }], "ATM IV (level) along hold path", "Hold day", "IV (vol pts)");

    if (first && last) {
      const smileA = first.smile || [];
      const smileB = last.smile || [];
      const xOfSmile = (r) => align === "strike" ? r.strike : r.offset;
      plot("fhSmile", [
        { x: smileA.map(xOfSmile), y: smileA.map((r) => r.iv), mode: "lines+markers", name: `Entry ${first.date}`, line: { color: "#58a6ff" } },
        { x: smileB.map(xOfSmile), y: smileB.map((r) => r.iv), mode: "lines+markers", name: `Hold+${last.hold_day} ${last.date}`, line: { color: "#3dba7a" } },
      ], "Smile: entry vs last hold day", xLabelHold, "IV");
      const mapB = new Map(smileB.map((r) => [String(xOfSmile(r)), r]));
      const matched = smileA.map((r) => {
        const b = mapB.get(String(xOfSmile(r)));
        return b ? { x: xOfSmile(r), a: r, b } : null;
      }).filter(Boolean);
      const smileDx = matched.map((r) => r.b.iv - r.a.iv);
      plot("fhSmileChg", [{
        x: matched.map((r) => r.x),
        y: smileDx,
        mode: "lines+markers",
        name: "Last − entry",
        line: { color: "#d29922" },
      }], "Smile change over hold (line)", xLabelHold, "Δ IV");
      barPlot("fhSmileBar", matched.map((r) => r.x), smileDx,
        "Smile IV change bar (last − entry)", xLabelHold, "Δ IV");
    }

    if (allMode && first && last) {
      const flies = matchHoldStructures(first, last, "fly");
      const spreads = matchHoldStructures(first, last, "spread");
      const flyDx = flies.map((r) => r.b.prem - r.a.prem);
      const ivDx = flies.map((r) => r.b.iv_fly - r.a.iv_fly);
      const sprDx = spreads.map((r) => r.b.prem - r.a.prem);
      el("fhAllCards").innerHTML = [
        ["Fly nodes", flies.length],
        ["Spread nodes", spreads.length],
        ["Mean Δ fly prem", flies.length ? fmt(flyDx.reduce((s, v) => s + v, 0) / flies.length, 3) : "—"],
        ["Mean Δ IV fly", flies.length ? fmt(ivDx.reduce((s, v) => s + v, 0) / ivDx.length, 3) : "—"],
        ["Mean Δ spread prem", spreads.length ? fmt(sprDx.reduce((s, v) => s + v, 0) / spreads.length, 3) : "—"],
      ].map(([k, v]) => `<span><em>${k}</em>${v}</span>`).join("");

      plot("fhFlyCurve", [
        { x: flies.map((r) => r.key), y: flies.map((r) => r.a.prem), mode: "lines+markers", name: "Entry fly prem", line: { color: "#58a6ff" } },
        { x: flies.map((r) => r.key), y: flies.map((r) => r.b.prem), mode: "lines+markers", name: "Last fly prem", line: { color: "#3dba7a" } },
      ], "Fly premium: all strikes (entry vs last)", xLabelHold, "Premium");
      barPlot("fhFlyBar", flies.map((r) => r.key), flyDx,
        "Fly premium change bar (last − entry)", xLabelHold, "Δ Premium");
      barPlot("fhIvFlyBar", flies.map((r) => r.key), ivDx,
        "IV fly change bar (last − entry)", xLabelHold, "Δ IV fly");

      plot("fhSpreadCurve", [
        { x: spreads.map((r) => r.key), y: spreads.map((r) => r.a.prem), mode: "lines+markers", name: "Entry spread prem", line: { color: "#58a6ff" } },
        { x: spreads.map((r) => r.key), y: spreads.map((r) => r.b.prem), mode: "lines+markers", name: "Last spread prem", line: { color: "#3dba7a" } },
      ], "Spread premium: all strikes (entry vs last)", xLabelHold, "Premium");
      barPlot("fhSpreadBar", spreads.map((r) => r.key), sprDx,
        "Spread premium change bar (last − entry)", xLabelHold, "Δ Premium");

      el("fhAllTable").innerHTML = `
        <thead><tr>
          <th>${xLabelHold}</th>
          <th>Fly prem entry</th><th>Fly prem last</th><th>Δ Fly prem</th>
          <th>IV fly entry</th><th>IV fly last</th><th>Δ IV fly</th>
          <th>Spread prem entry</th><th>Spread prem last</th><th>Δ Spread prem</th>
          <th>Δ IV gap</th>
        </tr></thead>
        <tbody>${flies.map((fly) => {
          const spr = spreads.find((s) => s.key === fly.key);
          return `<tr>
            <td>${fmt(fly.key, 0)}</td>
            <td>${fmt(fly.a.prem, 3)}</td>
            <td>${fmt(fly.b.prem, 3)}</td>
            <td>${fmt(fly.b.prem - fly.a.prem, 3)}</td>
            <td>${fmt(fly.a.iv_fly, 3)}</td>
            <td>${fmt(fly.b.iv_fly, 3)}</td>
            <td>${fmt(fly.b.iv_fly - fly.a.iv_fly, 3)}</td>
            <td>${spr ? fmt(spr.a.prem, 3) : "—"}</td>
            <td>${spr ? fmt(spr.b.prem, 3) : "—"}</td>
            <td>${spr ? fmt(spr.b.prem - spr.a.prem, 3) : "—"}</td>
            <td>${spr ? fmt(spr.b.iv_gap - spr.a.iv_gap, 3) : "—"}</td>
          </tr>`;
        }).join("")}</tbody>`;
    }

    if (!allMode) {
      const focus = Number(state.holdFocusStrike);
      const flySeries = days.map((d) => ({ day: d, row: findHoldStructure(d, "fly", focus) }));
      const sprSeries = days.map((d) => ({ day: d, row: findHoldStructure(d, "spread", focus) }));
      const flyOk = flySeries.filter((x) => x.row);
      const sprOk = sprSeries.filter((x) => x.row);
      const firstFly = flyOk[0] && flyOk[0].row;
      const lastFly = flyOk[flyOk.length - 1] && flyOk[flyOk.length - 1].row;
      const firstSpr = sprOk[0] && sprOk[0].row;
      const lastSpr = sprOk[sprOk.length - 1] && sprOk[sprOk.length - 1].row;

      el("fhFocusCards").innerHTML = [
        ["Focus", focus],
        ["Align", holdAlign()],
        ["Fly prem entry", firstFly ? fmt(firstFly.prem, 3) : "—"],
        ["Fly prem last", lastFly ? fmt(lastFly.prem, 3) : "—"],
        ["Δ Fly prem", firstFly && lastFly ? fmt(lastFly.prem - firstFly.prem, 3) : "—"],
        ["Δ IV fly", firstFly && lastFly ? fmt(lastFly.iv_fly - firstFly.iv_fly, 3) : "—"],
        ["Δ Spread prem", firstSpr && lastSpr ? fmt(lastSpr.prem - firstSpr.prem, 3) : "—"],
      ].map(([k, v]) => `<span><em>${k}</em>${v}</span>`).join("");

      plot("fhFlyPath", [{
        x: flyOk.map((x) => x.day.hold_day),
        y: flyOk.map((x) => x.row.prem),
        text: flyOk.map((x) => x.day.date),
        mode: "lines+markers",
        name: "Fly premium",
        line: { color: "#58a6ff" },
      }], "Focused fly premium along hold", "Hold day", "Premium");

      const flyVsEntry = flyOk.map((x) => x.row.prem - (firstFly ? firstFly.prem : x.row.prem));
      barPlot("fhFlyPathBar", flyOk.map((x) => x.day.hold_day), flyVsEntry,
        "Focused fly premium change vs entry (bar)", "Hold day", "Δ Premium",
        flyOk.map((x) => x.day.date));

      plot("fhIvFlyPath", [{
        x: flyOk.map((x) => x.day.hold_day),
        y: flyOk.map((x) => x.row.iv_fly),
        text: flyOk.map((x) => x.day.date),
        mode: "lines+markers",
        name: "IV fly",
        line: { color: "#a371f7" },
      }], "Focused IV fly along hold", "Hold day", "IV fly");

      plot("fhSpreadPath", [{
        x: sprOk.map((x) => x.day.hold_day),
        y: sprOk.map((x) => x.row.prem),
        text: sprOk.map((x) => x.day.date),
        mode: "lines+markers",
        name: "Spread premium",
        line: { color: "#3dba7a" },
      }], "Focused spread premium along hold", "Hold day", "Premium");

      const sprVsEntry = sprOk.map((x) => x.row.prem - (firstSpr ? firstSpr.prem : x.row.prem));
      barPlot("fhSpreadPathBar", sprOk.map((x) => x.day.hold_day), sprVsEntry,
        "Focused spread premium change vs entry (bar)", "Hold day", "Δ Premium",
        sprOk.map((x) => x.day.date));

      el("fhFocusTable").innerHTML = `
        <thead><tr>
          <th>Hold day</th><th>Date</th><th>DTE</th><th>Spot</th>
          <th>Fly prem</th><th>Δ fly vs entry</th><th>IV fly</th>
          <th>Spread prem</th><th>Δ spr vs entry</th><th>IV gap</th>
          <th>Centre/Near</th><th>Offset</th>
        </tr></thead>
        <tbody>${days.map((d) => {
          const fly = findHoldStructure(d, "fly", focus);
          const spr = findHoldStructure(d, "spread", focus);
          return `<tr>
            <td>${d.hold_day}</td>
            <td>${d.date}</td>
            <td>${fmt(d.dte, 0)}</td>
            <td>${fmt(d.spot, 2)}</td>
            <td>${fly ? fmt(fly.prem, 3) : "—"}</td>
            <td>${fly && firstFly ? fmt(fly.prem - firstFly.prem, 3) : "—"}</td>
            <td>${fly ? fmt(fly.iv_fly, 3) : "—"}</td>
            <td>${spr ? fmt(spr.prem, 3) : "—"}</td>
            <td>${spr && firstSpr ? fmt(spr.prem - firstSpr.prem, 3) : "—"}</td>
            <td>${spr ? fmt(spr.iv_gap, 3) : "—"}</td>
            <td>${fly ? fmt(fly.centre, 0) : (spr ? fmt(spr.near, 0) : "—")}</td>
            <td>${fly ? fmt(fly.offset, 0) : (spr ? fmt(spr.offset, 0) : "—")}</td>
          </tr>`;
        }).join("")}</tbody>`;
    }

    el("fhDaysTable").innerHTML = `
      <thead><tr>
        <th>Hold day</th><th>Date</th><th>Hour</th><th>Expiry</th><th>DTE</th>
        <th>Spot</th><th>ATM</th><th>Level</th><th>Skew</th><th>Curvature</th>
        <th>Call flies</th><th>Put flies</th>
      </tr></thead>
      <tbody>${days.map((d) => `
        <tr>
          <td>${d.hold_day}</td>
          <td>${d.date}</td>
          <td>${d.hour || ""}</td>
          <td>${d.expiry || ""}</td>
          <td>${fmt(d.dte, 0)}</td>
          <td>${fmt(d.spot, 2)}</td>
          <td>${fmt(d.atm_strike, 0)}</td>
          <td>${fmt(d.level, 3)}</td>
          <td>${fmt(d.skew, 3)}</td>
          <td>${fmt(d.curvature, 3)}</td>
          <td>${(d.call_flies || []).length}</td>
          <td>${(d.put_flies || []).length}</td>
        </tr>`).join("")}</tbody>`;
  }

  function paintModeNotes() {
    const strike = state.align === "strike";
    el("faSmileNote").textContent = strike
      ? "Strike-wise smile: same absolute K matched across dates. Spot move changes moneyness of each strike."
      : "OTM smile vs ATM offset: puts below ATM, calls above ATM. IVs in vol points.";
    el("faFlyTitle").textContent = strike ? "Fly premium by fixed strike" : "Fly premium by ATM offset";
    el("faFlyNote").textContent = strike
      ? "Same centre strike K on both dates (e.g. 7800 fly). When spot moves, that fixed fly’s premium, IV fly and Greeks change."
      : "Fly = P(K−h) − 2P(K) + P(K+h). Matched across dates by ATM offset.";
    el("faSpreadTitle").textContent = strike ? "Vertical spread by fixed near strike" : "Vertical spread by ATM offset";
    el("faSpreadNote").textContent = strike
      ? "Same near strike on both dates. Call: long near / short near+width. Put: long near / short near−width."
      : "Call debit: long near / short near+width. Put debit: long near / short near−width. Matched by ATM offset.";
    el("faFocusNote").textContent = strike
      ? `Focus strike tracks one absolute K across A→B: moneyness, smile IV, fly premium / IV fly, and the vertical at that near strike.`
      : "Switch Align to “Strike-wise” to lock one absolute K (e.g. 7800) and see how that fly/spread changes when spot moves.";
  }

  function paintSummary() {
    const c = state.compare;
    if (!c) {
      el("faSummary").innerHTML = "";
      el("faSpot").innerHTML = "";
      return;
    }
    const a = c.date_a;
    const b = c.date_b;
    el("faSummary").innerHTML = [
      ["A", `${a.date} ${a.hour}`],
      ["B", `${b.date} ${b.hour}`],
      ["Expiry A", `${a.expiry} (${a.dte} DTE)`],
      ["Expiry B", `${b.expiry} (${b.dte} DTE)`],
      ["ATM A", a.atm_strike],
      ["ATM B", b.atm_strike],
      ["Align", state.align === "strike" ? "Fixed strike" : "ATM offset"],
      ["Focus K", state.focusStrike != null ? state.focusStrike : "—"],
    ].map(([k, v]) => `<span><em>${k}</em>${v}</span>`).join("");
    el("faSpot").innerHTML = [
      ["Spot A", fmt(a.spot, 2)],
      ["Spot B", fmt(b.spot, 2)],
      ["Δ Spot", fmt(c.spot_move, 2)],
      ["Δ Spot %", c.spot_move_pct == null ? "—" : fmt(c.spot_move_pct, 3) + "%"],
      ["Δ Level", a.level != null && b.level != null ? fmt(b.level - a.level, 3) : "—"],
      ["Δ Skew", a.skew != null && b.skew != null ? fmt(b.skew - a.skew, 3) : "—"],
      ["Δ Curvature", a.curvature != null && b.curvature != null ? fmt(b.curvature - a.curvature, 3) : "—"],
    ].map(([k, v]) => `<span><em>${k}</em>${v}</span>`).join("");
  }

  function findByStrike(rows, field, strike, side) {
    const k = Number(strike);
    return (rows || []).find((r) => Number(r[field]) === k && (!side || r.side === side || !r.side)) || null;
  }

  function smileAtStrike(smile, strike) {
    const k = Number(strike);
    const exact = (smile || []).find((r) => Number(r.strike) === k);
    if (exact) return exact;
    const sorted = [...(smile || [])].sort((a, b) => a.strike - b.strike);
    for (let i = 0; i < sorted.length - 1; i += 1) {
      const a = sorted[i];
      const b = sorted[i + 1];
      if (a.strike <= k && k <= b.strike) {
        const w = (b.strike - a.strike) ? (k - a.strike) / (b.strike - a.strike) : 0;
        return {
          strike: k,
          offset: a.offset + w * (b.offset - a.offset),
          iv: a.iv + w * (b.iv - a.iv),
          prem: a.prem + w * (b.prem - a.prem),
          side: k >= 0 ? "interp" : "interp",
          interpolated: true,
        };
      }
    }
    return null;
  }

  function paintFocus() {
    const box = el("faFocusCards");
    const detail = el("faFocusDetail");
    if (!box || !detail) return;
    const c = state.compare;
    if (!c || state.focusStrike == null) {
      box.innerHTML = "";
      detail.innerHTML = "";
      return;
    }
    const k = Number(state.focusStrike);
    const side = state.side === "both" ? "call" : state.side;
    const fliesA = sideRows(c.date_a, "flies");
    const fliesB = sideRows(c.date_b, "flies");
    const spreadsA = sideRows(c.date_a, "spreads");
    const spreadsB = sideRows(c.date_b, "spreads");
    const flyA = findByStrike(fliesA, "centre", k, side) || findByStrike(fliesA, "centre", k);
    const flyB = findByStrike(fliesB, "centre", k, flyA ? flyA.side : side) || findByStrike(fliesB, "centre", k);
    const sprA = findByStrike(spreadsA, "near", k, side) || findByStrike(spreadsA, "near", k);
    const sprB = findByStrike(spreadsB, "near", k, sprA ? sprA.side : side) || findByStrike(spreadsB, "near", k);
    const smA = smileAtStrike(c.date_a.smile, k);
    const smB = smileAtStrike(c.date_b.smile, k);
    const spotA = c.date_a.spot;
    const spotB = c.date_b.spot;
    const atmA = c.date_a.atm_strike;
    const atmB = c.date_b.atm_strike;

    box.innerHTML = [
      ["Focus K", k],
      ["Side", (flyA && flyA.side) || (sprA && sprA.side) || side],
      ["Moneyness A (K−spot)", fmt(k - spotA, 2)],
      ["Moneyness B (K−spot)", fmt(k - spotB, 2)],
      ["Δ moneyness", fmt((k - spotB) - (k - spotA), 2)],
      ["Offset vs ATM A", fmt(k - atmA, 0)],
      ["Offset vs ATM B", fmt(k - atmB, 0)],
    ].map(([label, value]) => `<span><em>${label}</em>${value}</span>`).join("");

    const rows = [];
    rows.push(["Smile IV", smA ? smA.iv : null, smB ? smB.iv : null, "vol pts"]);
    rows.push(["Smile premium", smA ? smA.prem : null, smB ? smB.prem : null, ""]);
    rows.push(["Fly premium", flyA ? flyA.prem : null, flyB ? flyB.prem : null, ""]);
    rows.push(["IV fly", flyA ? flyA.iv_fly : null, flyB ? flyB.iv_fly : null, "vol pts"]);
    rows.push(["Fly delta", flyA ? flyA.delta : null, flyB ? flyB.delta : null, ""]);
    rows.push(["Fly vega", flyA ? flyA.vega : null, flyB ? flyB.vega : null, ""]);
    rows.push(["Fly lower IV", flyA ? flyA.lower_iv : null, flyB ? flyB.lower_iv : null, ""]);
    rows.push(["Fly mid IV", flyA ? flyA.mid_iv : null, flyB ? flyB.mid_iv : null, ""]);
    rows.push(["Fly upper IV", flyA ? flyA.upper_iv : null, flyB ? flyB.upper_iv : null, ""]);
    rows.push(["Spread premium", sprA ? sprA.prem : null, sprB ? sprB.prem : null, ""]);
    rows.push(["Spread IV gap", sprA ? sprA.iv_gap : null, sprB ? sprB.iv_gap : null, "vol pts"]);
    rows.push(["Spread near IV", sprA ? sprA.iv_near : null, sprB ? sprB.iv_near : null, ""]);
    rows.push(["Spread far IV", sprA ? sprA.iv_far : null, sprB ? sprB.iv_far : null, ""]);
    rows.push(["Spread delta", sprA ? sprA.delta : null, sprB ? sprB.delta : null, ""]);
    rows.push(["Spread vega", sprA ? sprA.vega : null, sprB ? sprB.vega : null, ""]);

    detail.innerHTML = `
      <table>
        <thead><tr>
          <th>Metric</th><th>Date A</th><th>Date B</th><th>B − A</th><th></th>
        </tr></thead>
        <tbody>
          ${rows.map(([name, va, vb, unit]) => {
            const da = va == null ? null : Number(va);
            const db = vb == null ? null : Number(vb);
            const diff = da == null || db == null ? null : db - da;
            return `<tr>
              <td>${name}</td>
              <td>${fmt(da, 4)}</td>
              <td>${fmt(db, 4)}</td>
              <td>${fmt(diff, 4)}</td>
              <td>${unit || ""}</td>
            </tr>`;
          }).join("")}
          <tr>
            <td>Fly legs</td>
            <td>${flyA ? `${flyA.lower} / ${flyA.centre} / ${flyA.upper}` : "—"}</td>
            <td>${flyB ? `${flyB.lower} / ${flyB.centre} / ${flyB.upper}` : "—"}</td>
            <td></td><td></td>
          </tr>
          <tr>
            <td>Spread legs</td>
            <td>${sprA ? `${sprA.near} / ${sprA.far}` : "—"}</td>
            <td>${sprB ? `${sprB.near} / ${sprB.far}` : "—"}</td>
            <td></td><td></td>
          </tr>
        </tbody>
      </table>`;
  }

  function paintSmile() {
    const c = state.compare;
    if (!c) return;
    const a = c.date_a.smile || [];
    const b = c.date_b.smile || [];
    const xa = a.map((r) => xOf(r, "smile"));
    const xb = b.map((r) => xOf(r, "smile"));
    plot("faSmile", [
      { x: xa, y: a.map((r) => r.iv), mode: "lines+markers", name: "A " + c.date_a.date, line: { color: "#58a6ff" } },
      { x: xb, y: b.map((r) => r.iv), mode: "lines+markers", name: "B " + c.date_b.date, line: { color: "#3dba7a" } },
    ], state.align === "strike" ? "IV smile vs strike" : "IV smile vs ATM offset", xLabel(), "IV (vol pts)");
    const matched = matchPairs(a, b, "smile");
    plot("faSmileChg", [{
      x: matched.map((r) => r.x),
      y: matched.map((r) => r.b.iv - r.a.iv),
      mode: "lines+markers",
      name: "B − A",
      line: { color: "#d29922" },
    }], "Smile change (B − A)", xLabel(), "Δ IV");
  }

  function sideRows(pack, key) {
    if (state.side === "both") {
      return []
        .concat((pack["call_" + key] || []).map((r) => ({ ...r, side: "call" })))
        .concat((pack["put_" + key] || []).map((r) => ({ ...r, side: "put" })));
    }
    return (pack[state.side + "_" + key] || []).map((r) => ({ ...r, side: state.side }));
  }

  function paintFlies() {
    const c = state.compare;
    if (!c) return;
    const a = sideRows(c.date_a, "flies");
    const b = sideRows(c.date_b, "flies");
    const tracesPrem = [];
    const tracesChg = [];
    const tracesIv = [];
    const sides = state.side === "both" ? ["call", "put"] : [state.side];
    const focus = state.focusStrike != null ? Number(state.focusStrike) : null;
    sides.forEach((side, idx) => {
      const colorA = idx === 0 ? "#58a6ff" : "#a371f7";
      const colorB = idx === 0 ? "#3dba7a" : "#f0883e";
      const aa = a.filter((r) => r.side === side);
      const bb = b.filter((r) => r.side === side);
      tracesPrem.push(
        { x: aa.map((r) => xOf(r, "fly")), y: aa.map((r) => r.prem), mode: "lines+markers", name: `A ${side}`, line: { color: colorA } },
        { x: bb.map((r) => xOf(r, "fly")), y: bb.map((r) => r.prem), mode: "lines+markers", name: `B ${side}`, line: { color: colorB } },
      );
      const matched = matchPairs(aa, bb, "fly");
      tracesChg.push({
        x: matched.map((r) => r.x),
        y: matched.map((r) => r.b.prem - r.a.prem),
        mode: "lines+markers",
        name: `${side} B−A`,
      });
      tracesIv.push(
        { x: aa.map((r) => xOf(r, "fly")), y: aa.map((r) => r.iv_fly), mode: "lines+markers", name: `A ${side} IV fly`, line: { color: colorA } },
        { x: bb.map((r) => xOf(r, "fly")), y: bb.map((r) => r.iv_fly), mode: "lines+markers", name: `B ${side} IV fly`, line: { color: colorB } },
      );
    });
    plot("faFlyPrem", tracesPrem, "Fly premium", xLabel(), "Premium");
    plot("faFlyChg", tracesChg, "Fly premium change (B − A)", xLabel(), "Δ Premium");
    plot("faFlyIv", tracesIv, "IV fly", xLabel(), "IV fly (vol pts)");

    const matched = matchPairs(a, b, "fly");
    el("faFlyTable").innerHTML = `
      <thead><tr>
        <th>Side</th><th>${state.align === "strike" ? "Strike" : "Offset"}</th>
        <th>Centre</th><th>Off A</th><th>Off B</th>
        <th>Prem A</th><th>Prem B</th><th>Δ Prem</th>
        <th>IV fly A</th><th>IV fly B</th><th>Δ IV fly</th>
        <th>Δ Delta</th><th>Δ Vega</th>
      </tr></thead>
      <tbody>${matched.map((row) => {
        const focused = focus != null && Number(row.a.centre) === focus;
        return `
        <tr class="${focused ? "fa-focus-row" : ""}">
          <td>${row.a.side || state.side}</td>
          <td>${fmt(row.x, 0)}</td>
          <td>${fmt(row.a.centre, 0)}</td>
          <td>${fmt(row.a.offset, 0)}</td>
          <td>${fmt(row.b.offset, 0)}</td>
          <td>${fmt(row.a.prem, 3)}</td>
          <td>${fmt(row.b.prem, 3)}</td>
          <td>${fmt(row.b.prem - row.a.prem, 3)}</td>
          <td>${fmt(row.a.iv_fly, 3)}</td>
          <td>${fmt(row.b.iv_fly, 3)}</td>
          <td>${fmt(row.b.iv_fly - row.a.iv_fly, 3)}</td>
          <td>${fmt((row.b.delta || 0) - (row.a.delta || 0), 4)}</td>
          <td>${fmt((row.b.vega || 0) - (row.a.vega || 0), 4)}</td>
        </tr>`;
      }).join("")}</tbody>`;
  }

  function paintSpreads() {
    const c = state.compare;
    if (!c) return;
    const a = sideRows(c.date_a, "spreads");
    const b = sideRows(c.date_b, "spreads");
    const tracesPrem = [];
    const tracesChg = [];
    const tracesGap = [];
    const sides = state.side === "both" ? ["call", "put"] : [state.side];
    const focus = state.focusStrike != null ? Number(state.focusStrike) : null;
    sides.forEach((side, idx) => {
      const colorA = idx === 0 ? "#58a6ff" : "#a371f7";
      const colorB = idx === 0 ? "#3dba7a" : "#f0883e";
      const aa = a.filter((r) => r.side === side);
      const bb = b.filter((r) => r.side === side);
      tracesPrem.push(
        { x: aa.map((r) => xOf(r, "spread")), y: aa.map((r) => r.prem), mode: "lines+markers", name: `A ${side}`, line: { color: colorA } },
        { x: bb.map((r) => xOf(r, "spread")), y: bb.map((r) => r.prem), mode: "lines+markers", name: `B ${side}`, line: { color: colorB } },
      );
      const matched = matchPairs(aa, bb, "spread");
      tracesChg.push({
        x: matched.map((r) => r.x),
        y: matched.map((r) => r.b.prem - r.a.prem),
        mode: "lines+markers",
        name: `${side} B−A`,
      });
      tracesGap.push(
        { x: aa.map((r) => xOf(r, "spread")), y: aa.map((r) => r.iv_gap), mode: "lines+markers", name: `A ${side} IV gap`, line: { color: colorA } },
        { x: bb.map((r) => xOf(r, "spread")), y: bb.map((r) => r.iv_gap), mode: "lines+markers", name: `B ${side} IV gap`, line: { color: colorB } },
      );
    });
    plot("faSpreadPrem", tracesPrem, "Spread premium", xLabel(), "Premium");
    plot("faSpreadChg", tracesChg, "Spread premium change (B − A)", xLabel(), "Δ Premium");
    plot("faSpreadGap", tracesGap, "Spread IV gap (near − far)", xLabel(), "IV gap");

    const matched = matchPairs(a, b, "spread");
    el("faSpreadTable").innerHTML = `
      <thead><tr>
        <th>Side</th><th>${state.align === "strike" ? "Near K" : "Offset"}</th>
        <th>Near</th><th>Far</th><th>Off A</th><th>Off B</th>
        <th>Prem A</th><th>Prem B</th><th>Δ Prem</th>
        <th>IV gap A</th><th>IV gap B</th><th>Δ IV gap</th>
      </tr></thead>
      <tbody>${matched.map((row) => {
        const focused = focus != null && Number(row.a.near) === focus;
        return `
        <tr class="${focused ? "fa-focus-row" : ""}">
          <td>${row.a.side || state.side}</td>
          <td>${fmt(row.x, 0)}</td>
          <td>${fmt(row.a.near, 0)}</td>
          <td>${fmt(row.a.far, 0)}</td>
          <td>${fmt(row.a.offset, 0)}</td>
          <td>${fmt(row.b.offset, 0)}</td>
          <td>${fmt(row.a.prem, 3)}</td>
          <td>${fmt(row.b.prem, 3)}</td>
          <td>${fmt(row.b.prem - row.a.prem, 3)}</td>
          <td>${fmt(row.a.iv_gap, 3)}</td>
          <td>${fmt(row.b.iv_gap, 3)}</td>
          <td>${fmt(row.b.iv_gap - row.a.iv_gap, 3)}</td>
        </tr>`;
      }).join("")}</tbody>`;
  }

  function paintAll() {
    paintModeNotes();
    paintSummary();
    paintFocus();
    paintSmile();
    paintFlies();
    paintSpreads();
  }

  function bind() {
    el("faLoadFolder").onclick = () => loadUploadedFolder();
    el("faUpload").addEventListener("change", () => {
      if (el("faUpload").files && el("faUpload").files.length) loadUploadedFolder();
    });
    el("faModeCompare").onclick = () => {
      setView("compare");
      if (state.dates.length && !state.compare) runCompare();
    };
    el("faModeHold").onclick = async () => {
      setView("hold");
      if (state.dates.length) {
        try {
          await loadHoldMeta();
          await runHoldPath();
        } catch (err) {
          state.holdError = String(err.message || err);
          paintWarn();
        }
      }
    };
    el("faRefreshFolders").onclick = () => refreshFolders();
    el("faUseFolder").onclick = () => {
      const path = el("faPath").value.trim() || el("faFolder").value;
      if (path) useFolder(path);
    };
    el("faFolder").onchange = () => {
      el("faPath").value = el("faFolder").value;
    };
    el("fhDate").onchange = async () => {
      state.holdDate = el("fhDate").value;
      await loadHoldMeta();
      await runHoldPath();
    };
    el("fhHoldDays").onchange = async () => {
      state.holdDays = Number(el("fhHoldDays").value) || 10;
      await runHoldPath();
    };
    el("fhHour").onchange = async () => {
      state.holdHour = el("fhHour").value;
      fillHoldExpiries();
      await runHoldPath();
    };
    el("fhTargetDte").onchange = async () => {
      state.holdTargetDte = Number(el("fhTargetDte").value) || 60;
      await loadHoldMeta();
      await runHoldPath();
    };
    el("fhExpiryMode").onchange = async () => {
      state.holdExpiryMode = el("fhExpiryMode").value;
      fillHoldExpiries();
      await runHoldPath();
    };
    el("fhExpiry").onchange = async () => {
      state.holdExpiry = el("fhExpiry").value;
      await runHoldPath();
    };
    el("fhWing").onchange = () => runHoldPath();
    el("fhSpreadWidth").onchange = () => runHoldPath();
    el("fhSide").onchange = () => { fillHoldFocus(); paintHoldAll(); };
    el("fhAlign").onchange = () => { fillHoldFocus(); paintHoldAll(); };
    el("fhFocusStrike").onchange = () => {
      const raw = el("fhFocusStrike").value;
      state.holdFocusStrike = raw === "all" || raw === "" ? "all" : Number(raw);
      paintHoldAll();
    };
    el("fhPrev").onclick = async () => {
      const next = shiftDate(state.holdDate, -1);
      if (!next) return;
      state.holdDate = next;
      el("fhDate").value = next;
      await loadHoldMeta();
      await runHoldPath();
    };
    el("fhNext").onclick = async () => {
      const next = shiftDate(state.holdDate, 1);
      if (!next) return;
      state.holdDate = next;
      el("fhDate").value = next;
      await loadHoldMeta();
      await runHoldPath();
    };
    el("fhRun").onclick = () => runHoldPath();
    el("faDateA").onchange = async () => {
      state.dateA = el("faDateA").value;
      await loadMeta();
      await runCompare();
    };
    el("faDateB").onchange = async () => {
      state.dateB = el("faDateB").value;
      await loadMeta();
      await runCompare();
    };
    el("faHour").onchange = async () => {
      state.hour = el("faHour").value;
      fillExpiries();
      await runCompare();
    };
    el("faTargetDte").onchange = async () => {
      state.targetDte = Number(el("faTargetDte").value) || 60;
      await loadMeta();
      await runCompare();
    };
    el("faExpiryMode").onchange = async () => {
      state.expiryMode = el("faExpiryMode").value;
      fillExpiries();
      await runCompare();
    };
    el("faExpiryA").onchange = async () => {
      state.expiryA = el("faExpiryA").value;
      await runCompare();
    };
    el("faExpiryB").onchange = async () => {
      state.expiryB = el("faExpiryB").value;
      await runCompare();
    };
    el("faWing").onchange = async () => {
      state.wing = Number(el("faWing").value);
      await runCompare();
    };
    el("faSpreadWidth").onchange = async () => {
      state.spreadWidth = Number(el("faSpreadWidth").value);
      await runCompare();
    };
    el("faSide").onchange = () => {
      state.side = el("faSide").value;
      fillFocusStrikes();
      paintAll();
    };
    el("faAlign").onchange = () => {
      state.align = el("faAlign").value;
      paintAll();
    };
    el("faFocusStrike").onchange = () => {
      const raw = el("faFocusStrike").value;
      state.focusStrike = raw === "" ? null : Number(raw);
      paintAll();
    };
    el("faPrevA").onclick = async () => {
      const next = shiftDate(state.dateA, -1);
      if (!next) return;
      state.dateA = next;
      el("faDateA").value = next;
      await loadMeta();
      await runCompare();
    };
    el("faNextA").onclick = async () => {
      const next = shiftDate(state.dateA, 1);
      if (!next) return;
      state.dateA = next;
      el("faDateA").value = next;
      await loadMeta();
      await runCompare();
    };
    el("faPrevB").onclick = async () => {
      const next = shiftDate(state.dateB, -1);
      if (!next) return;
      state.dateB = next;
      el("faDateB").value = next;
      await loadMeta();
      await runCompare();
    };
    el("faNextB").onclick = async () => {
      const next = shiftDate(state.dateB, 1);
      if (!next) return;
      state.dateB = next;
      el("faDateB").value = next;
      await loadMeta();
      await runCompare();
    };
    el("faPrevWin").onclick = async () => {
      const a = shiftDate(state.dateA, -1);
      const b = shiftDate(state.dateB, -1);
      if (!a || !b) return;
      state.dateA = a;
      state.dateB = b;
      el("faDateA").value = a;
      el("faDateB").value = b;
      await loadMeta();
      await runCompare();
    };
    el("faNextWin").onclick = async () => {
      const a = shiftDate(state.dateA, 1);
      const b = shiftDate(state.dateB, 1);
      if (!a || !b) return;
      state.dateA = a;
      state.dateB = b;
      el("faDateA").value = a;
      el("faDateB").value = b;
      await loadMeta();
      await runCompare();
    };
    el("faBNext").onclick = async () => {
      const next = shiftDate(state.dateA, 1);
      if (!next) return;
      state.dateB = next;
      el("faDateB").value = next;
      await loadMeta();
      await runCompare();
    };
    el("faSwap").onclick = async () => {
      const t = state.dateA;
      state.dateA = state.dateB;
      state.dateB = t;
      el("faDateA").value = state.dateA;
      el("faDateB").value = state.dateB;
      await loadMeta();
      await runCompare();
    };
    el("faRun").onclick = () => runCompare();
  }

  async function mount(root) {
    ensureStyle();
    if (root.dataset.ready !== READY) {
      root.innerHTML = shell();
      bind();
      root.dataset.ready = READY;
    }
    if (el("faAlign")) el("faAlign").value = state.align;
    setView(state.view);
    fillFolders();
    // Soft-discover local desk folders if available; do not auto-load them.
    refreshFolders();
    if (state.dates.length) {
      fillDates();
      try {
        await loadMeta();
        await loadHoldMeta();
        if (state.view === "hold") await runHoldPath();
        else await runCompare();
      } catch (err) {
        state.error = String(err.message || err);
        state.holdError = state.error;
        paintWarn();
      }
    }
  }

  window.FlyLab = { mount };
})();
