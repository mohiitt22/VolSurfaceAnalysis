/* Spread Analysis pricing and attribution.
   Pricing matches the surface lab: European BSM, q = 0, sigma in decimal.
   The live lab passes r = 0.045 and T = DTE / 365. Greeks match
   spx_butterfly/greeks.py units: vega per vol point, volga per vol-point
   squared, theta per calendar day, vanna per vol point. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.SpreadMath = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  const RATE = 0.045;
  const TINY = 1e-8;

  function normCdf(x) {
    // Φ(x) = 0.5 * (1 + erf(x / sqrt(2))), Abramowitz-Stegun 7.1.26.
    // The surface lab applies the erf series to x itself, so its prices do
    // not match spx_butterfly.black_scholes. This copy does.
    const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741;
    const a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
    const sign = x < 0 ? -1 : 1;
    const z = Math.abs(x) / Math.SQRT2;
    const t = 1 / (1 + p * z);
    const erf = 1 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-z * z);
    return 0.5 * (1 + sign * erf);
  }

  function normPdf(x) {
    return Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI);
  }

  function bsPrice(side, S, K, T, r, sigma) {
    if (!(S > 0) || !(K > 0) || !(T > 0) || !(sigma > 0) || !Number.isFinite(r)) return null;
    const d1 = (Math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * Math.sqrt(T));
    const d2 = d1 - sigma * Math.sqrt(T);
    if (side === "call") return S * normCdf(d1) - K * Math.exp(-r * T) * normCdf(d2);
    if (side === "put") return K * Math.exp(-r * T) * normCdf(-d2) - S * normCdf(-d1);
    return null;
  }

  function bsGreeks(side, S, K, T, r, sigma) {
    if (!(S > 0) || !(K > 0) || !(T > 0) || !(sigma > 0) || !Number.isFinite(r)) return null;
    const sqrtT = Math.sqrt(T);
    const d1 = (Math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrtT);
    const d2 = d1 - sigma * sqrtT;
    const disc = Math.exp(-r * T);
    const pdf = normPdf(d1);
    const vegaDec = S * sqrtT * pdf;
    const call = side === "call";
    const delta = call ? normCdf(d1) : -normCdf(-d1);
    const gamma = pdf / (S * sigma * sqrtT);
    const thetaAnnual = -(S * pdf * sigma) / (2 * sqrtT)
      + (call ? -r * K * disc * normCdf(d2) : r * K * disc * normCdf(-d2));
    return {
      delta,
      gamma,
      vega: vegaDec * 0.01,
      vegaDec,
      volga: vegaDec * (d1 * d2) / sigma * 0.0001,
      theta: thetaAnnual / 365,
      vanna: (-pdf * (d2 / sigma)) * 0.01,
    };
  }

  function finite(n) {
    return typeof n === "number" && Number.isFinite(n);
  }

  function sideRows(dateObj, side) {
    const rows = (dateObj && dateObj.smile) || [];
    const want = side === "put" ? "p" : "c";
    const out = [];
    const seen = new Set();
    rows.forEach((row) => {
      const tag = String(row.side || "").toLowerCase();
      if (!tag.startsWith(want)) return;
      const strike = Number(row.strike);
      const iv = Number(row.iv);
      if (!finite(strike) || !finite(iv) || iv <= 0) return;
      const key = strike.toFixed(4);
      if (seen.has(key)) return;
      seen.add(key);
      out.push({
        strike,
        offset: finite(Number(row.offset)) ? Number(row.offset) : strike - Number(dateObj.atm_strike),
        iv,
        prem: finite(Number(row.prem)) ? Number(row.prem) : null,
        label: row.label || null,
        fileDelta: finite(Number(row.delta)) ? Number(row.delta) : null,
        fileVega: finite(Number(row.vega)) ? Number(row.vega) : null,
      });
    });
    out.sort((a, b) => a.strike - b.strike);
    return out;
  }

  function ivAtStrike(rows, strike) {
    if (!rows.length || !finite(strike)) return { iv: null, how: "missing" };
    let exact = null;
    for (let i = 0; i < rows.length; i += 1) {
      if (Math.abs(rows[i].strike - strike) < 0.02) exact = rows[i];
    }
    if (exact) return { iv: exact.iv, prem: exact.prem, how: "exact" };
    if (strike < rows[0].strike - 1e-6 || strike > rows[rows.length - 1].strike + 1e-6) {
      return { iv: null, how: "outside" };
    }
    for (let i = 0; i < rows.length - 1; i += 1) {
      const a = rows[i];
      const b = rows[i + 1];
      if (a.strike <= strike && strike <= b.strike) {
        const span = b.strike - a.strike;
        if (!(span > 0)) return { iv: null, how: "bad-grid" };
        const w = (strike - a.strike) / span;
        return { iv: a.iv + w * (b.iv - a.iv), prem: null, how: "interpolated" };
      }
    }
    return { iv: null, how: "missing" };
  }

  function widthsFrom(strikes) {
    const sorted = [...strikes].sort((a, b) => a - b);
    const steps = [];
    for (let i = 1; i < sorted.length; i += 1) {
      const step = Math.round((sorted[i] - sorted[i - 1]) * 100) / 100;
      if (step > 0 && !steps.includes(step)) steps.push(step);
    }
    const extra = [];
    if (steps.length && steps[0] > 0) {
      const base = steps[0];
      for (let n = 2; n <= 4; n += 1) {
        const w = Math.round(base * n * 100) / 100;
        if (!steps.includes(w) && !extra.includes(w)) extra.push(w);
      }
    }
    return steps.concat(extra).sort((a, b) => a - b);
  }

  function strikePairs(dateA, side, width) {
    const rows = sideRows(dateA, side);
    const atm = Number(dateA.atm_strike);
    const wing = rows.filter((row) => (side === "call" ? row.strike >= atm - 0.02 : row.strike <= atm + 0.02));
    const strikes = wing.map((row) => row.strike);
    const available = widthsFrom(strikes);
    const use = finite(width) ? width : (available[0] || null);
    const pairs = [];
    if (use) {
      strikes.forEach((kn) => {
        const kf = side === "call" ? kn + use : kn - use;
        if (strikes.some((k) => Math.abs(k - kf) < 0.02)) pairs.push({ kn, kf, width: use });
      });
    }
    return { pairs, widths: available, width: use };
  }

  function nearestByDelta(dateObj, side, rate) {
    const rows = sideRows(dateObj, side);
    const S = Number(dateObj.spot);
    const T = Number(dateObj.dte) / 365;
    const targets = [];
    for (let d = 50; d >= 10; d -= 5) targets.push(d / 100);
    const used = new Set();
    const nodes = [];
    targets.forEach((target) => {
      let best = null;
      rows.forEach((row) => {
        const g = bsGreeks(side, S, row.strike, T, rate, row.iv / 100);
        if (!g) return;
        const abs = Math.abs(g.delta);
        const err = Math.abs(abs - target);
        if (err > 0.035) return;
        if (!best || err < best.err) best = { strike: row.strike, delta: g.delta, abs, err, iv: row.iv };
      });
      if (best && !used.has(best.strike.toFixed(4))) {
        used.add(best.strike.toFixed(4));
        nodes.push(best);
      }
    });
    nodes.sort((a, b) => b.abs - a.abs);
    return nodes;
  }

  function legState(dateObj, side, strike, rate) {
    const look = ivAtStrike(sideRows(dateObj, side), strike);
    if (!finite(look.iv)) return { ok: false, how: look.how };
    const S = Number(dateObj.spot);
    const T = Number(dateObj.dte) / 365;
    const sigma = look.iv / 100;
    const price = bsPrice(side, S, strike, T, rate, sigma);
    const greeks = bsGreeks(side, S, strike, T, rate, sigma);
    if (price === null || !greeks) return { ok: false, how: "invalid-price" };
    return { ok: true, iv: look.iv, sigma, premModel: price, premRecorded: look.prem ?? null, how: look.how, greeks, S, T };
  }

  function priceFrozen(side, S, T, r, kn, kf, sigN, sigF) {
    if (!(sigN > 0) || !(sigF > 0)) return null;
    const near = bsPrice(side, S, kn, T, r, sigN);
    const far = bsPrice(side, S, kf, T, r, sigF);
    if (near === null || far === null) return null;
    return near - far;
  }

  function legendre(n, x) {
    if (n === 0) return 1;
    if (n === 1) return x;
    let p0 = 1;
    let p1 = x;
    for (let k = 2; k <= n; k += 1) {
      const p = ((2 * k - 1) * x * p1 - (k - 1) * p0) / k;
      p0 = p1;
      p1 = p;
    }
    return p1;
  }

  function gaussLegendre(n) {
    const nodes = [];
    for (let i = 0; i < n; i += 1) {
      let x = Math.cos(Math.PI * (i + 0.75) / (n + 0.5));
      for (let iter = 0; iter < 30; iter += 1) {
        const p = legendre(n, x);
        const pm = legendre(n - 1, x);
        const dp = (n / (1 - x * x)) * (pm - x * p);
        const step = p / dp;
        x -= step;
        if (Math.abs(step) < 1e-14) break;
      }
      const pm = legendre(n - 1, x);
      const dp = (n / (1 - x * x)) * (pm - x * legendre(n, x));
      const w = 2 / ((1 - x * x) * dp * dp);
      nodes.push({ u: 0.5 * (x + 1), w: 0.5 * w });
    }
    return nodes;
  }

  const GL16 = gaussLegendre(16);
  const GL8 = gaussLegendre(8);

  function integrateFactors(side, S, T, r, kn, kf, sigN0, sigF0, level, skew, nodes) {
    let pL = 0;
    let pA = 0;
    for (let i = 0; i < nodes.length; i += 1) {
      const u = nodes[i].u;
      const sn = sigN0 + u * (level + skew / 2);
      const sf = sigF0 + u * (level - skew / 2);
      const gn = bsGreeks(side, S, kn, T, r, sn);
      const gf = bsGreeks(side, S, kf, T, r, sf);
      if (!gn || !gf) return null;
      pL += nodes[i].w * (gn.vegaDec - gf.vegaDec) * level;
      pA += nodes[i].w * ((gn.vegaDec + gf.vegaDec) / 2) * skew;
    }
    return { level: pL, skew: pA, total: pL + pA };
  }

  function attributePair(side, S, T, r, kn, kf, ivN0, ivF0, ivN1, ivF1) {
    const sigN0 = ivN0 / 100;
    const sigF0 = ivF0 / 100;
    const sigN1 = ivN1 / 100;
    const sigF1 = ivF1 / 100;
    const dN = sigN1 - sigN0;
    const dF = sigF1 - sigF0;
    const level = (dN + dF) / 2;
    const skew = dN - dF;
    const rebuiltN = sigN0 + level + skew / 2;
    const rebuiltF = sigF0 + level - skew / 2;
    const gN = bsGreeks(side, S, kn, T, r, sigN0);
    const gF = bsGreeks(side, S, kf, T, r, sigF0);
    const v00 = priceFrozen(side, S, T, r, kn, kf, sigN0, sigF0);
    const v10 = priceFrozen(side, S, T, r, kn, kf, sigN0 + level, sigF0 + level);
    const v01 = priceFrozen(side, S, T, r, kn, kf, sigN0 + skew / 2, sigF0 - skew / 2);
    const v11 = priceFrozen(side, S, T, r, kn, kf, rebuiltN, rebuiltF);
    if ([v00, v10, v01, v11].some((v) => v === null) || !gN || !gF) return null;
    const shapleyL = 0.5 * ((v10 - v00) + (v11 - v01));
    const shapleyA = 0.5 * ((v01 - v00) + (v11 - v10));
    const ig16 = integrateFactors(side, S, T, r, kn, kf, sigN0, sigF0, level, skew, GL16);
    const ig8 = integrateFactors(side, S, T, r, kn, kf, sigN0, sigF0, level, skew, GL8);
    if (!ig16 || !ig8) return null;
    const target = v11 - v00;
    return {
      levelVolPts: level * 100,
      skewVolPts: skew * 100,
      rebuiltNear: rebuiltN * 100,
      rebuiltFar: rebuiltF * 100,
      firstL: (gN.vegaDec - gF.vegaDec) * level,
      firstA: ((gN.vegaDec + gF.vegaDec) / 2) * skew,
      vegaNear: gN.vega,
      vegaFar: gF.vega,
      v00, v10, v01, v11,
      shapleyL, shapleyA,
      shapleyTotal: shapleyL + shapleyA,
      shapleyError: shapleyL + shapleyA - target,
      igL: ig16.level,
      igA: ig16.skew,
      igTotal: ig16.total,
      igError: ig16.total - target,
      igConvergence: Math.abs(ig16.total - ig8.total),
      ivOnly: target,
    };
  }

  function shares(level, skew, total) {
    const gross = Math.abs(level) + Math.abs(skew);
    return {
      signedLevel: Math.abs(total) > TINY ? (100 * level) / total : null,
      signedSkew: Math.abs(total) > TINY ? (100 * skew) / total : null,
      grossLevel: gross > TINY ? (100 * Math.abs(level)) / gross : null,
      grossSkew: gross > TINY ? (100 * Math.abs(skew)) / gross : null,
    };
  }

  function fitQuadratic(rows, atm, H) {
    const pts = rows.filter((row) => finite(row.iv));
    if (pts.length < 4) return null;
    let s00 = 0, s01 = 0, s02 = 0, s03 = 0, s04 = 0;
    let t0 = 0, t1 = 0, t2 = 0;
    pts.forEach((row) => {
      const x = (row.strike - atm) / H;
      const y = row.iv;
      s00 += 1; s01 += x; s02 += x * x; s03 += x ** 3; s04 += x ** 4;
      t0 += y; t1 += y * x; t2 += y * x * x;
    });
    const A = [[s00, s01, s02], [s01, s02, s03], [s02, s03, s04]];
    const b = [t0, t1, t2];
    const coeff = solve3(A, b);
    if (!coeff) return null;
    let sse = 0;
    pts.forEach((row) => {
      const x = (row.strike - atm) / H;
      const fit = coeff[0] + coeff[1] * x + coeff[2] * x * x;
      sse += (row.iv - fit) ** 2;
    });
    return { a: coeff[0], b: coeff[1], c: coeff[2], rmse: Math.sqrt(sse / pts.length), n: pts.length, H };
  }

  function solve3(M, b) {
    const A = M.map((row, i) => row.concat(b[i]));
    for (let col = 0; col < 3; col += 1) {
      let pivot = col;
      for (let r = col + 1; r < 3; r += 1) if (Math.abs(A[r][col]) > Math.abs(A[pivot][col])) pivot = r;
      if (Math.abs(A[pivot][col]) < 1e-12) return null;
      const tmp = A[col]; A[col] = A[pivot]; A[pivot] = tmp;
      const div = A[col][col];
      for (let c = col; c < 4; c += 1) A[col][c] /= div;
      for (let r = 0; r < 3; r += 1) {
        if (r === col) continue;
        const f = A[r][col];
        for (let c = col; c < 4; c += 1) A[r][c] -= f * A[col][c];
      }
    }
    return [A[0][3], A[1][3], A[2][3]];
  }

  function netGreeks(near, far) {
    if (!near || !far) return null;
    const keys = ["delta", "gamma", "vega", "volga", "theta", "vanna"];
    const out = {};
    keys.forEach((key) => { out[key] = near[key] - far[key]; });
    return out;
  }

  function fileDeltaNodes(dateObj, side) {
    const want = side === "put" ? "p" : "c";
    const out = [];
    const seen = new Set();
    (dateObj.delta_nodes || []).forEach((row) => {
      const tag = String(row.side || "").toLowerCase();
      const label = String(row.label || "");
      const strike = Number(row.strike);
      const iv = Number(row.iv);
      const delta = Number(row.delta);
      if (!finite(strike) || !finite(iv) || iv <= 0 || !finite(delta)) return;
      if (label.toLowerCase() === "atm") {
        if (side !== "call") return;
      } else if (!tag.startsWith(want)) return;
      const key = label.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      out.push({
        strike,
        iv,
        prem: finite(Number(row.prem)) ? Number(row.prem) : null,
        label,
        delta,
        fileDelta: delta,
        fileVega: finite(Number(row.vega)) ? Number(row.vega) : null,
        offset: strike - Number(dateObj.atm_strike),
      });
    });
    out.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));
    return out;
  }

  function nodeLabel(node, mode) {
    if (mode === "delta") {
      if (String(node.label || "").toLowerCase() === "atm") return "ATM";
      return Math.round(Math.abs(node.delta) * 100) + "Δ";
    }
    const offset = Math.round(node.offset);
    if (Math.abs(offset) < 1) return "ATM";
    return (offset > 0 ? "+" : "") + offset;
  }

  function quoteNode(dateObj, side, node, rate) {
    const S = Number(dateObj.spot);
    const T = Number(dateObj.dte) / 365;
    const sigma = node.iv / 100;
    const price = bsPrice(side, S, node.strike, T, rate, sigma);
    const greeks = bsGreeks(side, S, node.strike, T, rate, sigma);
    if (price === null || !greeks || !(T > 0) || !(S > 0)) return { ok: false };
    return { ok: true, iv: node.iv, premModel: price, premRecorded: node.prem, greeks, strike: node.strike };
  }

  function buildRows(dateA, dateB, spec) {
    const side = spec.side === "put" ? "put" : "call";
    const mode = spec.mode === "delta" ? "delta" : "strike";
    const rate = finite(spec.rate) ? spec.rate : RATE;
    let widths = [];
    let width = finite(Number(spec.width)) ? Number(spec.width) : null;
    let pairs = [];
    if (mode === "delta") {
      const nodes = fileDeltaNodes(dateA, side);
      if (!nodes.length) {
        return { rows: [], widths: [5, 10, 15], width: 5, rate, missingGrid: "This workbook has no delta-wise nodes. Choose the 12 Oct or 16 Oct file." };
      }
      widths = [5, 10, 15];
      width = widths.includes(width) ? width : 5;
      const step = width / 5;
      for (let i = 0; i + step < nodes.length; i += 1) {
        pairs.push({ near: nodes[i], far: nodes[i + step], loc: nodeLabel(nodes[i], mode) + "/" + nodeLabel(nodes[i + step], mode) });
      }
    } else {
      const built = strikePairs(dateA, side, width);
      widths = built.widths;
      width = built.width;
      const byOffset = new Map(sideRows(dateA, side).map((row) => [Math.round(row.offset), row]));
      built.pairs.forEach((pair) => {
        const near = byOffset.get(Math.round(pair.kn - Number(dateA.atm_strike)));
        const far = byOffset.get(Math.round(pair.kf - Number(dateA.atm_strike)));
        if (!near || !far) return;
        pairs.push({ near, far, loc: nodeLabel(near, mode) + "/" + nodeLabel(far, mode) });
      });
    }
    const match = (node) => {
      if (mode === "delta") {
        const key = String(node.label || "").toLowerCase();
        return fileDeltaNodes(dateB, side).find((row) => String(row.label || "").toLowerCase() === key) || null;
      }
      return sideRows(dateB, side).find((row) => Math.abs(row.offset - node.offset) < 0.5) || null;
    };
    const rows = pairs.map((pair) => {
      const bNear = match(pair.near);
      const bFar = match(pair.far);
      const base = {
        side,
        mode,
        loc: pair.loc,
        kn: pair.near.strike,
        kf: pair.far.strike,
        knB: bNear ? bNear.strike : null,
        kfB: bFar ? bFar.strike : null,
        width: mode === "delta" ? width : Math.abs(pair.near.offset - pair.far.offset),
        deltaNear: pair.near.fileDelta,
        deltaFar: pair.far.fileDelta,
        howB: mode === "delta" ? "same delta node" : "same ATM offset",
      };
      if (!bNear || !bFar) {
        return Object.assign(base, { available: false, reason: "Date B has no matching " + (mode === "delta" ? "delta node" : "ATM offset") + "." });
      }
      const aN = quoteNode(dateA, side, pair.near, rate);
      const aF = quoteNode(dateA, side, pair.far, rate);
      const bN = quoteNode(dateB, side, bNear, rate);
      const bF = quoteNode(dateB, side, bFar, rate);
      if (!aN.ok || !aF.ok || !bN.ok || !bF.ok) {
        return Object.assign(base, { available: false, reason: "A required IV, spot, or maturity is missing." });
      }
      const gA = netGreeks(aN.greeks, aF.greeks);
      const gB = netGreeks(bN.greeks, bF.greeks);
      const attr = attributePair(side, Number(dateA.spot), Number(dateA.dte) / 365, rate, pair.near.strike, pair.far.strike, aN.iv, aF.iv, bN.iv, bF.iv);
      const note = mode === "delta"
        ? "Delta-wise. Same file delta on both dates. IV-only attribution holds Date A's spot, maturity, and strikes, and uses Date B's IV at that delta."
        : "Strike-wise. Same ATM offset on both dates. IV-only attribution holds Date A's spot, maturity, and strikes, and uses Date B's IV at that offset.";
      return Object.assign(base, {
        available: true,
        reason: attr ? note : "A counterfactual volatility was nonpositive, so the spread was not attributed.",
        ivnA: aN.iv, ivfA: aF.iv, gapA: aN.iv - aF.iv,
        ivnB: bN.iv, ivfB: bF.iv, gapB: bN.iv - bF.iv,
        dIvn: bN.iv - aN.iv, dIvf: bF.iv - aF.iv,
        dAvg: ((bN.iv - aN.iv) + (bF.iv - aF.iv)) / 2,
        dGap: (bN.iv - bF.iv) - (aN.iv - aF.iv),
        nearPremA: aN.premModel, farPremA: aF.premModel, spreadA: aN.premModel - aF.premModel,
        nearPremB: bN.premModel, farPremB: bF.premModel, spreadB: bN.premModel - bF.premModel,
        dNearPrem: bN.premModel - aN.premModel,
        dFarPrem: bF.premModel - aF.premModel,
        dSpread: (bN.premModel - bF.premModel) - (aN.premModel - aF.premModel),
        recordedA: aN.premRecorded !== null && aF.premRecorded !== null ? aN.premRecorded - aF.premRecorded : null,
        recordedB: bN.premRecorded !== null && bF.premRecorded !== null ? bN.premRecorded - bF.premRecorded : null,
        dRecorded: null,
        gA, gB,
        interpolated: false,
        attr,
        sharesSh: attr ? shares(attr.shapleyL, attr.shapleyA, attr.ivOnly) : null,
        sharesIg: attr ? shares(attr.igL, attr.igA, attr.ivOnly) : null,
      });
    });
    rows.forEach((row) => {
      if (row.recordedA !== null && row.recordedB !== null) row.dRecorded = row.recordedB - row.recordedA;
    });
    return { rows, widths, width, rate };
  }

  return {
    RATE, normCdf, bsPrice, bsGreeks, sideRows, ivAtStrike, widthsFrom, strikePairs,
    attributePair, shares, fitQuadratic, buildRows, gaussLegendre,
  };
});
