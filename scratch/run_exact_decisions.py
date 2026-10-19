import json
import math

with open('dashboard/data/panel.json') as f:
    panel = json.load(f)

meta = panel['meta']
test_date = meta['test_date']
all_dates = panel['dates']
post_dates = [d for d in all_dates if d >= test_date]
cols = panel['columns']

rows = [dict(zip(cols, r)) for r in panel['rows']]
by_date = {}
for r in rows:
    by_date.setdefault(r['trade_date'], []).append(r)

def finite(x):
    return x is not None and not (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))

def decision_of(row, z_gate):
    if not row:
        return {"label": "CANNOT DECIDE", "direction": ""}
    z = row.get("z_60_residual")
    res = row.get("residual")
    extrapolated = row.get("extrapolated", False)
    
    sign_conflict = False
    if finite(res) and finite(z) and res != 0 and z != 0:
        if (res > 0 and z < 0) or (res < 0 and z > 0):
            sign_conflict = True
            
    direction = "CHEAP" if finite(res) and res < 0 else "EXPENSIVE" if finite(res) and res > 0 else ""
    
    if extrapolated or not finite(z) or not finite(res) or sign_conflict:
        return {"label": "CANNOT DECIDE", "direction": direction}
    
    if abs(z) < z_gate:
        return {"label": "NO TRADE", "direction": direction}
        
    return {"label": "TRADE", "direction": direction}

print("=== EXACT STRATEGY DESK RESULTS ACROSS POST-HOLDOUT DATES (11 Sep -> 22 Sep) ===")
for g in [3.0, 2.5, 2.0, 1.5]:
    print(f"\n==================== Z-GATE: {g} ====================")
    for d in post_dates:
        day_rows = by_date.get(d, [])
        trades_cheap = []
        trades_exp = []
        no_trade = []
        cannot = []
        
        for r in day_rows:
            dec = decision_of(r, g)
            if dec["label"] == "TRADE":
                if dec["direction"] == "CHEAP":
                    trades_cheap.append(r)
                else:
                    trades_exp.append(r)
            elif dec["label"] == "NO TRADE":
                no_trade.append(r)
            else:
                cannot.append(r)
                
        trades_cheap.sort(key=lambda x: x["z_60_residual"])
        trades_exp.sort(key=lambda x: -x["z_60_residual"])
        
        tc_str = f"{trades_cheap[0]['structure']} (z={trades_cheap[0]['z_60_residual']:.2f}, res={trades_cheap[0]['residual']*10000:+.1f}bp)" if trades_cheap else "—"
        te_str = f"{trades_exp[0]['structure']} (z={trades_exp[0]['z_60_residual']:.2f}, res={trades_exp[0]['residual']*10000:+.1f}bp)" if trades_exp else "—"
        
        tot_trades = len(trades_cheap) + len(trades_exp)
        print(f"{d} | Trades: {tot_trades:2d} (Cheap: {len(trades_cheap):2d}, Exp: {len(trades_exp):2d}) | Top Cheap: {tc_str:<35} | Top Exp: {te_str}")
