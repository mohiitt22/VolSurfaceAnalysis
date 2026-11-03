/* Attribution acceptance tests. Run: node tools/test_spread_math.js */
const assert = require("assert");
const m = require("../docs/spread-math.js");

let passed = 0;
function check(name, fn) {
  fn();
  passed += 1;
  console.log("ok  " + name);
}

const S = 5600;
const kn = 5600;
const kf = 5700;
const T = 60 / 365;
const r = m.RATE;
const tol = 1e-8;
const igTol = 5e-4;

check("A no IV change", () => {
  const a = m.attributePair("call", S, T, r, kn, kf, 16, 18, 16, 18);
  assert.ok(Math.abs(a.levelVolPts) < tol);
  assert.ok(Math.abs(a.skewVolPts) < tol);
  assert.ok(Math.abs(a.shapleyTotal) < tol);
  assert.ok(Math.abs(a.igTotal) < tol);
  assert.ok(Math.abs(a.shapleyL) < tol && Math.abs(a.shapleyA) < tol);
  assert.ok(Math.abs(a.igL) < tol && Math.abs(a.igA) < tol);
});

check("B pure parallel shift", () => {
  const a = m.attributePair("call", S, T, r, kn, kf, 15, 17, 16.5, 18.5);
  assert.ok(Math.abs(a.skewVolPts) < 1e-9);
  assert.ok(Math.abs(a.shapleyA) < 1e-8);
  assert.ok(Math.abs(a.igA) < igTol);
  assert.ok(Math.abs(a.shapleyL - a.ivOnly) < 1e-8);
  assert.ok(Math.abs(a.igL - a.ivOnly) < igTol);
});

check("C pure local skew", () => {
  const a = m.attributePair("put", S, T, r, 5500, 5400, 18, 22, 19, 21);
  assert.ok(Math.abs(a.levelVolPts) < 1e-9);
  assert.ok(Math.abs(a.shapleyL) < 1e-8);
  assert.ok(Math.abs(a.igL) < igTol);
  assert.ok(Math.abs(a.shapleyA - a.ivOnly) < 1e-8);
  assert.ok(Math.abs(a.igA - a.ivOnly) < igTol);
});

check("D shapley reconciliation", () => {
  const a = m.attributePair("call", S, T, r, kn, kf, 14.2, 12.4, 15.8, 13.1);
  assert.ok(Math.abs(a.shapleyError) < 1e-8);
});

check("E integrated reconciliation", () => {
  const a = m.attributePair("call", S, T, r, kn, kf, 14.2, 12.4, 15.8, 13.1);
  assert.ok(Math.abs(a.igError) < igTol);
  assert.ok(a.igConvergence < igTol);
});

check("F factor reconstruction", () => {
  const a = m.attributePair("call", S, T, r, kn, kf, 14.2, 12.4, 15.8, 13.1);
  assert.ok(Math.abs(a.rebuiltNear - 15.8) < 1e-9);
  assert.ok(Math.abs(a.rebuiltFar - 13.1) < 1e-9);
});

check("G strike-wise offsets stay aligned", () => {
  const dateA = {
    spot: 5600, atm_strike: 5600, dte: 60,
    smile: [
      { strike: 5600, offset: 0, side: "call", iv: 15, prem: 80, label: "Call ATM", delta: 0.5 },
      { strike: 5700, offset: 100, side: "call", iv: 13, prem: 40, label: "Call ATM+100", delta: 0.4 },
      { strike: 5800, offset: 200, side: "call", iv: 12, prem: 20, label: "Call ATM+200", delta: 0.3 },
    ],
  };
  const dateB = {
    spot: 5650, atm_strike: 5650, dte: 60,
    smile: [
      { strike: 5650, offset: 0, side: "call", iv: 15.5, prem: 70, label: "Call ATM", delta: 0.5 },
      { strike: 5750, offset: 100, side: "call", iv: 13.5, prem: 35, label: "Call ATM+100", delta: 0.4 },
      { strike: 5850, offset: 200, side: "call", iv: 12.2, prem: 18, label: "Call ATM+200", delta: 0.3 },
    ],
  };
  const built = m.buildRows(dateA, dateB, { side: "call", mode: "strike", width: 100 });
  const row = built.rows.find((item) => item.available && item.loc === "ATM/+100");
  assert.ok(row);
  assert.strictEqual(row.kn, 5600);
  assert.strictEqual(row.knB, 5650);
  assert.ok(row.attr);
});

check("G2 delta-wise uses the file nodes", () => {
  const node = (label, side, delta, strike, iv) => ({ label, side, strike, delta, iv, prem: 10 });
  const dateA = {
    spot: 5600, atm_strike: 5600, dte: 60,
    delta_nodes: [node("45 delta call", "call", 0.45, 5650, 14), node("40 delta call", "call", 0.40, 5700, 13)],
  };
  const dateB = {
    spot: 5620, atm_strike: 5620, dte: 60,
    delta_nodes: [node("45 delta call", "call", 0.45, 5680, 15), node("40 delta call", "call", 0.40, 5730, 13.5)],
  };
  const built = m.buildRows(dateA, dateB, { side: "call", mode: "delta", width: 5 });
  const row = built.rows.find((item) => item.available);
  assert.ok(row);
  assert.strictEqual(row.loc, "45Δ/40Δ");
  assert.strictEqual(row.kn, 5650);
  assert.strictEqual(row.knB, 5680);
  assert.ok(row.attr);
  assert.ok(Math.abs(row.attr.shapleyError) < 1e-6);
});

check("H price parity and finite-difference delta", () => {
  const call = m.bsPrice("call", S, 5600, T, r, 0.16);
  assert.ok(Math.abs(call - 165.94011776160642) < 5e-4);
  const put = m.bsPrice("put", S, 5600, T, r, 0.16);
  const forwardGap = S - 5600 * Math.exp(-r * T);
  assert.ok(Math.abs((call - put) - forwardGap) < 1e-6);
  const g = m.bsGreeks("call", S, 5600, T, r, 0.16);
  assert.ok(Math.abs(g.delta - 0.5582232660482468) < 1e-4);
  assert.ok(Math.abs(g.vega - 8.961257884500302) < 1e-4);
  const bump = 0.5;
  const up = m.bsPrice("call", S + bump, 5600, T, r, 0.16);
  const dn = m.bsPrice("call", S - bump, 5600, T, r, 0.16);
  assert.ok(Math.abs((up - dn) / (2 * bump) - g.delta) < 1e-4);
  const vegaBump = 0.0001;
  const vu = m.bsPrice("call", S, 5600, T, r, 0.16 + vegaBump);
  const vd = m.bsPrice("call", S, 5600, T, r, 0.16 - vegaBump);
  const vegaDec = (vu - vd) / (2 * vegaBump);
  assert.ok(Math.abs(vegaDec - g.vegaDec) < 0.05);
});

check("I shares are unclipped and sum to 100", () => {
  const a = m.attributePair("call", S, T, r, kn, kf, 14.2, 12.4, 15.8, 13.1);
  const sh = m.shares(a.shapleyL, a.shapleyA, a.ivOnly);
  assert.ok(Math.abs(sh.grossLevel + sh.grossSkew - 100) < 1e-8);
  assert.ok(sh.signedLevel === null || Number.isFinite(sh.signedLevel));
  const offsetting = m.shares(2, -3, -1);
  assert.ok(offsetting.signedLevel === -200);
  assert.ok(offsetting.signedSkew === 300);
  const none = m.shares(0, 0, 0);
  assert.strictEqual(none.grossLevel, null);
  assert.strictEqual(none.signedLevel, null);
});

check("missing strike is not filled with zero", () => {
  const look = m.ivAtStrike([{ strike: 5600, iv: 15 }, { strike: 5700, iv: 14 }], 5900);
  assert.strictEqual(look.iv, null);
  assert.strictEqual(look.how, "outside");
});

console.log(passed + " tests passed");
