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

print("=== SCANNER ACROSS POST-HOLDOUT DATES (11 Sep -> 22 Sep) ===")
for g in [3.0, 2.5, 2.0]:
    print(f"\n--- Z-Gate: {g} ---")
    for d in post_dates:
        day_rows = by_date.get(d, [])
        cheap = []
        expensive = []
        no_trade = []
        cannot = []
        for r in day_rows:
            z = r.get('z_60_residual')
            c_conv = r.get('cond_convergence')
            c_struc = r.get('cond_structural')
            c_conf = r.get('cond_confidence')
            
            if z is None or math.isnan(z) or c_conv is None or c_struc is None or c_conf is None:
                cannot.append(r)
            elif abs(z) >= g and c_conv and c_struc and c_conf:
                if z < 0:
                    cheap.append(r)
                else:
                    expensive.append(r)
            else:
                no_trade.append(r)
        
        cheap_sorted = sorted(cheap, key=lambda x: x['z_60_residual'])
        exp_sorted = sorted(expensive, key=lambda x: -x['z_60_residual'])
        
        c_str = f"{cheap_sorted[0]['structure']} (z={cheap_sorted[0]['z_60_residual']:.2f}, res={cheap_sorted[0]['residual']*10000:+.1f}bp)" if cheap_sorted else "None"
        e_str = f"{exp_sorted[0]['structure']} (z={exp_sorted[0]['z_60_residual']:.2f}, res={exp_sorted[0]['residual']*10000:+.1f}bp)" if exp_sorted else "None"
        
        print(f"{d} | Trades: {len(cheap)+len(expensive):2d} (Cheap: {len(cheap):2d}, Exp: {len(expensive):2d}) | Top Cheap: {c_str:<38} | Top Exp: {e_str}")
