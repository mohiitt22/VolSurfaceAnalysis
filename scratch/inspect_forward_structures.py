import json

with open('dashboard/data/panel.json') as f:
    p = json.load(f)

cols = p['columns']
rows = [dict(zip(cols, r)) for r in p['rows']]

def inspect_structure(struct_name, start_date='2026-09-11'):
    struct_rows = [r for r in rows if r['structure'] == struct_name and r['trade_date'] >= start_date]
    struct_rows.sort(key=lambda x: x['trade_date'])
    
    print(f"\n==================== FORWARD PATH FOR {struct_name} (from {start_date}) ====================")
    if not struct_rows:
        print("No rows found!")
        return
        
    base = struct_rows[0]
    base_res = base['residual'] * 10000
    base_z = base.get('z_60_residual', 0)
    print(f"Base on {start_date}: Market={base['market_value']:.4f}, Fair={base['fair_value']:.4f}, Residual={base_res:+.2f} bp, z_60={base_z:.2f}")
    print("-" * 115)
    print(f"{'Date':<12} | {'Mkt Val':<8} | {'Fair Val':<8} | {'Resid (bp)':<10} | {'Fade (bp)':<10} | {'Fade (%)':<10} | {'z_60':<8} | {'Decision @ 2.5':<15} | {'Behavior'}")
    print("-" * 115)
    
    for i, r in enumerate(struct_rows):
        cur_res = r['residual'] * 10000
        z = r.get('z_60_residual')
        z_str = f"{z:.2f}" if z is not None else "—"
        
        # Convergence/fade towards 0
        fade_bp = (base_res - cur_res) if base_res > 0 else (cur_res - base_res)
        fade_pct = (fade_bp / abs(base_res) * 100) if abs(base_res) > 1e-4 else 0.0
        
        # Decision at gate 2.5
        dec = "NO TRADE"
        if z is not None and abs(z) >= 2.5:
            dec = f"TRADE ({'EXP' if z > 0 else 'CHEAP'})"
        elif z is not None and abs(z) >= 2.0:
            dec = f"NEAR TRADE ({'EXP' if z > 0 else 'CHEAP'})"
            
        behavior = "Base Date" if i == 0 else ""
        if i > 0:
            if abs(cur_res) <= 1.0 or fade_pct >= 80:
                behavior = "Fully Corrected to Fair Value"
            elif fade_pct >= 50:
                behavior = "Substantial Fade (Mean-Reverting)"
            elif fade_pct < 0:
                behavior = "Dislocation Widened"
            else:
                behavior = "Partial Fade"
                
        print(f"{r['trade_date']:<12} | {r['market_value']:<8.4f} | {r['fair_value']:<8.4f} | {cur_res:<+10.2f} | {fade_bp:<+10.2f} | {fade_pct:<9.1f}% | {z_str:<8} | {dec:<15} | {behavior}")

inspect_structure("RR_25D", "2026-09-11")
inspect_structure("STRIKE_6900", "2026-09-11")
inspect_structure("STRIKE_7150", "2026-09-11")
inspect_structure("BF_45D", "2026-09-11")
