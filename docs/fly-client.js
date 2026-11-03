/* Browser-side SNP parquet folder → Fly / Spread / Smile payloads. */
(function () {
  const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
  const REQUIRED = [
    "contract", "time", "expiry", "strike", "underlying", "rate",
    "call_price", "put_price", "call_iv", "put_iv", "call_delta", "put_delta", "atm", "dte",
  ];

  let parquetReadObjects = null;
  let compressors = null;

  async function ensureParquet() {
    if (parquetReadObjects && compressors) return;
    const hp = await import("https://cdn.jsdelivr.net/npm/hyparquet@1.32.0/+esm");
    const hc = await import("https://cdn.jsdelivr.net/npm/hyparquet-compressors@1.1.3/+esm");
    parquetReadObjects = hp.parquetReadObjects;
    compressors = hc.compressors;
  }

  function round(value, digits) {
    if (value === null || value === undefined) return null;
    const n = Number(value);
    if (!Number.isFinite(n)) return null;
    const f = 10 ** digits;
    return Math.round(n * f) / f;
  }

  function toDate(value) {
    if (value instanceof Date) return value;
    if (typeof value === "number" && Number.isFinite(value)) {
      // ns / us / ms heuristics
      if (value > 1e18) return new Date(value / 1e6);
      if (value > 1e15) return new Date(value / 1e3);
      if (value > 1e12) return new Date(value);
      return new Date(value * 1000);
    }
    const s = String(value).trim().replace(" ", "T");
    const d = new Date(s);
    if (!Number.isNaN(d.getTime())) return d;
    const d2 = new Date(String(value));
    return Number.isNaN(d2.getTime()) ? null : d2;
  }

  function ymd(value) {
    if (typeof value === "string") {
      const m = value.trim().match(/^(\d{4}-\d{2}-\d{2})/);
      if (m) return m[1];
    }
    const d = toDate(value);
    if (!d) return null;
    // Parquet timestamps are wall-clock market times — prefer UTC fields to avoid TZ shifts.
    const y = d.getUTCFullYear();
    const m = String(d.getUTCMonth() + 1).padStart(2, "0");
    const day = String(d.getUTCDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function hourLabel(value) {
    if (typeof value === "string") {
      const m = value.trim().match(/\b(\d{2}):(\d{2})(?::\d{2})?\b/);
      if (m) return `${m[1]}:${m[2]}`;
    }
    const d = toDate(value);
    if (!d) return null;
    return `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
  }

  function num(value) {
    if (value === null || value === undefined || value === "") return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function catalogFiles(fileList) {
    const byDate = new Map();
    const files = Array.from(fileList || []);
    for (const file of files) {
      const base = (file.name || "").split(/[/\\]/).pop();
      if (!/\.parquet$/i.test(base)) continue;
      const stem = base.replace(/\.parquet$/i, "");
      if (!DATE_RE.test(stem)) continue;
      byDate.set(stem, file);
    }
    const dates = [...byDate.keys()].sort();
    return { dates, byDate, count: dates.length };
  }

  async function readParquet(file) {
    await ensureParquet();
    const buffer = await file.arrayBuffer();
    const rows = await parquetReadObjects({ file: buffer, compressors });
    if (!rows || !rows.length) throw new Error(file.name + " has no rows.");
    const sample = rows[0];
    const keys = Object.keys(sample);
    if ("contact" in sample && !("contract" in sample)) {
      rows.forEach((r) => { r.contract = r.contact; });
    }
    const missing = REQUIRED.filter((c) => !(c in rows[0]) && !(c === "contract" && "contact" in sample));
    if (missing.length) throw new Error(file.name + " missing columns: " + missing.join(", "));
    return rows.map((r) => ({
      ...r,
      strike: num(r.strike),
      underlying: num(r.underlying),
      rate: num(r.rate),
      call_price: num(r.call_price),
      put_price: num(r.put_price),
      call_iv: num(r.call_iv),
      put_iv: num(r.put_iv),
      call_delta: num(r.call_delta),
      put_delta: num(r.put_delta),
      call_gamma: num(r.call_gamma),
      put_gamma: num(r.put_gamma),
      call_vega: num(r.call_vega),
      put_vega: num(r.put_vega),
      call_theta: num(r.call_theta),
      put_theta: num(r.put_theta),
      atm: num(r.atm),
      dte: num(r.dte),
      _time: toDate(r.time),
      _expiry: toDate(r.expiry),
      _hour: hourLabel(r.time),
      _expiryDay: ymd(r.expiry),
    })).filter((r) => r.strike != null && r.underlying != null && r._time && r._expiryDay);
  }

  function listHours(rows) {
    return [...new Set(rows.map((r) => r._hour).filter(Boolean))].sort();
  }

  function filterHour(rows, hour) {
    const wanted = String(hour);
    let out = rows.filter((r) => r._hour === wanted);
    if (out.length) return out;
    const wantH = Number(String(hour).split(":")[0]);
    const hours = listHours(rows);
    if (!hours.length) throw new Error("No timestamps in file.");
    const nearest = hours.reduce((best, h) =>
      Math.abs(Number(h.split(":")[0]) - wantH) < Math.abs(Number(best.split(":")[0]) - wantH) ? h : best
    , hours[0]);
    return rows.filter((r) => r._hour === nearest);
  }

  function listExpiries(rows) {
    const map = new Map();
    rows.forEach((r) => {
      if (!map.has(r._expiryDay)) {
        map.set(r._expiryDay, { expiry: r._expiryDay, dte: r.dte, strikes: new Set() });
      }
      map.get(r._expiryDay).strikes.add(r.strike);
      if (r.dte != null) map.get(r._expiryDay).dte = r.dte;
    });
    return [...map.values()].map((e) => ({
      expiry: e.expiry,
      dte: round(e.dte, 0),
      strikes: e.strikes.size,
    })).sort((a, b) => Math.abs((a.dte ?? 999) - 60) - Math.abs((b.dte ?? 999) - 60) || a.expiry.localeCompare(b.expiry));
  }

  function pickExpiry(expiries, targetDte, chosen) {
    if (!expiries.length) throw new Error("No expiries in this hour slice.");
    if (chosen) {
      const hit = expiries.find((e) => e.expiry === chosen);
      if (!hit) throw new Error("Expiry " + chosen + " not in this hour slice.");
      return hit;
    }
    const t = Number(targetDte) || 60;
    return expiries.reduce((best, e) =>
      Math.abs((e.dte ?? 1e9) - t) < Math.abs((best.dte ?? 1e9) - t) ? e : best
    , expiries[0]);
  }

  function dayMetaFromRows(day, rows, targetDte) {
    const hours = listHours(rows);
    const byHour = {};
    hours.forEach((hour) => {
      const slice = filterHour(rows, hour);
      const expiries = listExpiries(slice);
      const def = pickExpiry(expiries, targetDte);
      byHour[hour] = {
        expiries,
        default_expiry: def.expiry,
        default_dte: def.dte,
        spot: round(slice[0].underlying, 2),
      };
    });
    return {
      ok: true,
      date: day,
      hours,
      default_hour: hours[hours.length - 1] || null,
      by_hour: byHour,
      rows: rows.length,
    };
  }

  function atmStrike(rows) {
    const zero = rows.find((r) => r.atm != null && Math.abs(r.atm) < 1e-9);
    if (zero) return zero.strike;
    const spot = rows[0].underlying;
    return rows.reduce((best, r) =>
      Math.abs(r.strike - spot) < Math.abs(best - spot) ? r.strike : best
    , rows[0].strike);
  }

  function toLong(chain) {
    const atm = atmStrike(chain);
    const spot = chain[0].underlying;
    const dte = chain.find((r) => r.dte != null)?.dte ?? null;
    const rate = chain.find((r) => r.rate != null)?.rate ?? 0;
    const tradeDate = ymd(chain[0]._time);
    const expiry = chain[0]._expiryDay;
    const hour = chain[0]._hour;
    const out = [];
    chain.forEach((r) => {
      const base = {
        date: tradeDate,
        hour,
        expiry,
        underlying: spot,
        atm_strike: atm,
        target_dte: dte,
        rate,
        strike: r.strike,
        atm_offset: r.strike - atm,
      };
      if (r.call_iv != null && r.call_price != null) {
        out.push({
          ...base,
          option_side: "call",
          iv_decimal: r.call_iv,
          premium: r.call_price,
          delta: r.call_delta,
          gamma: r.call_gamma,
          vega: r.call_vega,
          theta: r.call_theta,
        });
      }
      if (r.put_iv != null && r.put_price != null) {
        out.push({
          ...base,
          option_side: "put",
          iv_decimal: r.put_iv,
          premium: r.put_price,
          delta: r.put_delta == null ? null : -Math.abs(r.put_delta),
          gamma: r.put_gamma,
          vega: r.put_vega,
          theta: r.put_theta,
        });
      }
    });
    return out;
  }

  function buildSmile(longRows) {
    const puts = longRows.filter((r) => r.option_side === "put" && r.atm_offset < 0);
    const calls = longRows.filter((r) => r.option_side === "call" && r.atm_offset > 0);
    let atm = longRows.filter((r) => Math.abs(r.atm_offset) < 1e-6);
    let atmRow = atm.find((r) => r.option_side === "call") || atm[0] || null;
    const smile = [...puts, ...(atmRow ? [atmRow] : []), ...calls]
      .sort((a, b) => a.atm_offset - b.atm_offset);
    const seen = new Set();
    const out = [];
    smile.forEach((r) => {
      const key = round(r.atm_offset, 4);
      if (seen.has(key)) return;
      seen.add(key);
      out.push({
        strike: round(r.strike, 2),
        offset: round(r.atm_offset, 2),
        side: r.option_side,
        iv: round(r.iv_decimal * 100, 4),
        prem: round(r.premium, 4),
        delta: round(r.delta, 4),
        vega: round(r.vega, 4),
      });
    });
    return out;
  }

  function sideMap(longRows, side) {
    const map = new Map();
    longRows.filter((r) => r.option_side === side).forEach((r) => {
      map.set(Math.round(r.strike * 10000) / 10000, {
        strike: r.strike,
        premium: r.premium,
        iv_decimal: r.iv_decimal,
        delta: r.delta,
        vega: r.vega,
      });
    });
    return map;
  }

  function lookup(map, strike) {
    const key = Math.round(Number(strike) * 10000) / 10000;
    if (map.has(key)) return map.get(key);
    for (const [cand, row] of map.entries()) {
      if (Math.abs(cand - Number(strike)) < 1e-6) return row;
    }
    return null;
  }

  function buildFlies(longRows, wing) {
    const atm = longRows[0].atm_strike;
    const calls = [];
    const puts = [];
    [["call", calls], ["put", puts]].forEach(([side, bucket]) => {
      const map = sideMap(longRows, side);
      [...map.keys()].sort((a, b) => a - b).forEach((centre) => {
        const lower = lookup(map, centre - wing);
        const mid = lookup(map, centre);
        const upper = lookup(map, centre + wing);
        if (!lower || !mid || !upper) return;
        const offset = centre - atm;
        if (side === "call" && offset < -1e-6) return;
        if (side === "put" && offset > 1e-6) return;
        const prem = lower.premium - 2 * mid.premium + upper.premium;
        const ivFly = (lower.iv_decimal - 2 * mid.iv_decimal + upper.iv_decimal) * 100;
        bucket.push({
          centre: round(centre, 2),
          offset: round(offset, 2),
          lower: round(centre - wing, 2),
          upper: round(centre + wing, 2),
          prem: round(prem, 4),
          iv_fly: round(ivFly, 4),
          delta: round((lower.delta || 0) - 2 * (mid.delta || 0) + (upper.delta || 0), 4),
          vega: round((lower.vega || 0) - 2 * (mid.vega || 0) + (upper.vega || 0), 4),
          lower_iv: round(lower.iv_decimal * 100, 4),
          mid_iv: round(mid.iv_decimal * 100, 4),
          upper_iv: round(upper.iv_decimal * 100, 4),
          lower_prem: round(lower.premium, 4),
          mid_prem: round(mid.premium, 4),
          upper_prem: round(upper.premium, 4),
        });
      });
    });
    return [calls, puts];
  }

  function buildSpreads(longRows, width) {
    const atm = longRows[0].atm_strike;
    const calls = [];
    const puts = [];
    [["call", calls, 1], ["put", puts, -1]].forEach(([side, bucket, direction]) => {
      const map = sideMap(longRows, side);
      [...map.keys()].sort((a, b) => a - b).forEach((near) => {
        const far = near + direction * width;
        const nearRow = lookup(map, near);
        const farRow = lookup(map, far);
        if (!nearRow || !farRow) return;
        const offset = near - atm;
        if (side === "call" && offset < -1e-6) return;
        if (side === "put" && offset > 1e-6) return;
        bucket.push({
          near: round(near, 2),
          far: round(far, 2),
          offset: round(offset, 2),
          prem: round(nearRow.premium - farRow.premium, 4),
          iv_near: round(nearRow.iv_decimal * 100, 4),
          iv_far: round(farRow.iv_decimal * 100, 4),
          iv_gap: round((nearRow.iv_decimal - farRow.iv_decimal) * 100, 4),
          delta: round((nearRow.delta || 0) - (farRow.delta || 0), 4),
          vega: round((nearRow.vega || 0) - (farRow.vega || 0), 4),
        });
      });
    });
    return [calls, puts];
  }

  function factorsFromSmile(smile, h) {
    const byOff = new Map(smile.filter((r) => r.iv != null).map((r) => [r.offset, r]));
    function ivAt(offset) {
      if (byOff.has(offset)) return byOff.get(offset).iv;
      const offs = [...byOff.keys()].sort((a, b) => a - b);
      if (!offs.length || offset < offs[0] || offset > offs[offs.length - 1]) return null;
      for (let i = 0; i < offs.length - 1; i += 1) {
        const a = offs[i];
        const b = offs[i + 1];
        if (a <= offset && offset <= b) {
          const w = b === a ? 1 : (b - offset) / (b - a);
          return w * byOff.get(a).iv + (1 - w) * byOff.get(b).iv;
        }
      }
      return null;
    }
    const atm = ivAt(0);
    const up = ivAt(h);
    const down = ivAt(-h);
    return {
      level: round(atm, 4),
      skew: up == null || down == null ? null : round(up - down, 4),
      curvature: atm == null || up == null || down == null ? null : round(0.5 * (up + down) - atm, 4),
    };
  }

  function buildDayFromRows(day, rows, opts) {
    const hourWanted = opts.hour || null;
    const hours = listHours(rows);
    if (!hours.length) throw new Error(day + " has no timestamps.");
    let chosenHour = hourWanted && hours.includes(hourWanted) ? hourWanted : (hourWanted || hours[hours.length - 1]);
    if (!hours.includes(chosenHour)) {
      const wantH = Number(String(chosenHour).split(":")[0]);
      chosenHour = hours.reduce((best, h) =>
        Math.abs(Number(h.split(":")[0]) - wantH) < Math.abs(Number(best.split(":")[0]) - wantH) ? h : best
      , hours[0]);
    }
    const slice = filterHour(rows, chosenHour);
    const expiries = listExpiries(slice);
    const picked = pickExpiry(expiries, opts.targetDte || 60, opts.expiry || null);
    const chain = slice.filter((r) => r._expiryDay === picked.expiry);
    if (!chain.length) throw new Error(`No chain for ${picked.expiry} at ${chosenHour} on ${day}.`);
    const longRows = toLong(chain);
    const smile = buildSmile(longRows);
    const wing = Number(opts.wing) || 100;
    const spreadWidth = Number(opts.spreadWidth != null ? opts.spreadWidth : wing);
    const [callFlies, putFlies] = buildFlies(longRows, wing);
    const [callSpreads, putSpreads] = buildSpreads(longRows, spreadWidth);
    const facts = factorsFromSmile(smile, 500);
    return {
      date: day,
      hour: chosenHour,
      expiry: picked.expiry,
      dte: picked.dte,
      spot: round(longRows[0].underlying, 2),
      atm_strike: round(longRows[0].atm_strike, 2),
      rate: round(longRows[0].rate, 6),
      wing,
      spread_width: spreadWidth,
      level: facts.level,
      skew: facts.skew,
      curvature: facts.curvature,
      smile,
      call_flies: callFlies,
      put_flies: putFlies,
      call_spreads: callSpreads,
      put_spreads: putSpreads,
      hours,
      expiries,
      n_strikes: new Set(chain.map((r) => r.strike)).size,
    };
  }

  async function compareFiles(fileA, dateA, fileB, dateB, opts) {
    const [rowsA, rowsB] = await Promise.all([readParquet(fileA), readParquet(fileB)]);
    const aFinal = buildDayFromRows(dateA, rowsA, {
      ...opts,
      expiry: opts.expiryA != null ? opts.expiryA : opts.expiry,
    });
    const bFinal = buildDayFromRows(dateB, rowsB, {
      ...opts,
      hour: opts.hour || aFinal.hour,
      expiry: opts.expiryB != null ? opts.expiryB : opts.expiry,
    });
    const spotMove = aFinal.spot == null || bFinal.spot == null ? null : round(bFinal.spot - aFinal.spot, 2);
    const spotPct = aFinal.spot ? round(100 * (bFinal.spot - aFinal.spot) / aFinal.spot, 4) : null;
    return {
      ok: true,
      source: "browser-upload",
      target_dte: opts.targetDte || 60,
      wing: opts.wing || 100,
      spread_width: opts.spreadWidth || opts.wing || 100,
      date_a: aFinal,
      date_b: bFinal,
      spot_move: spotMove,
      spot_move_pct: spotPct,
    };
  }

  /**
   * Same-contract hold path: lock the expiry chosen on the start day (~target DTE),
   * then walk the next 1..10 trading sessions with that same expiry (DTE falls naturally).
   * getRows(date) -> Promise<rows>
   */
  async function buildHoldPath(dateList, getRows, startDate, opts) {
    const holdDays = Math.max(1, Math.min(10, Number(opts.holdDays) || 10));
    const i0 = dateList.indexOf(startDate);
    if (i0 < 0) throw new Error("Start date " + startDate + " is not in the loaded folder.");
    const pathDates = [];
    for (let k = 0; k <= holdDays; k += 1) {
      if (i0 + k >= dateList.length) break;
      pathDates.push(dateList[i0 + k]);
    }
    if (!pathDates.length) throw new Error("No dates available for the hold path.");

    const rows0 = await getRows(pathDates[0]);
    const day0 = buildDayFromRows(pathDates[0], rows0, {
      hour: opts.hour,
      targetDte: opts.targetDte || 60,
      expiry: opts.expiry || null,
      wing: opts.wing || 100,
      spreadWidth: opts.spreadWidth,
    });
    const lockedExpiry = day0.expiry;
    const hour = opts.hour || day0.hour;
    const days = [{ hold_day: 0, ...day0 }];
    const warnings = [];

    for (let k = 1; k < pathDates.length; k += 1) {
      try {
        const rows = await getRows(pathDates[k]);
        const built = buildDayFromRows(pathDates[k], rows, {
          hour,
          expiry: lockedExpiry,
          targetDte: opts.targetDte || 60,
          wing: opts.wing || 100,
          spreadWidth: opts.spreadWidth,
        });
        days.push({ hold_day: k, ...built });
      } catch (err) {
        warnings.push(pathDates[k] + ": " + (err && err.message ? err.message : err));
      }
    }

    const first = days[0];
    const last = days[days.length - 1];
    return {
      ok: true,
      source: "browser-upload",
      mode: "hold",
      start_date: startDate,
      locked_expiry: lockedExpiry,
      hold_days_requested: holdDays,
      hold_days_available: days.length - 1,
      hour,
      wing: opts.wing || 100,
      spread_width: opts.spreadWidth || opts.wing || 100,
      days,
      spot_move: first && last ? round(last.spot - first.spot, 2) : null,
      spot_move_pct: first && last && first.spot
        ? round(100 * (last.spot - first.spot) / first.spot, 4)
        : null,
      dte_start: first ? first.dte : null,
      dte_end: last ? last.dte : null,
      warnings,
    };
  }

  window.FlyClient = {
    catalogFiles,
    readParquet,
    dayMetaFromRows,
    buildDayFromRows,
    compareFiles,
    buildHoldPath,
    listHours,
    listExpiries,
    pickExpiry,
  };
})();
