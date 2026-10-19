import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from spx_butterfly.data_loader import find_default_file, load_raw_dataset, transform_to_long_form
from spx_butterfly.multidate_model import build_multidate_flies, compute_fly_structure_metrics, get_snapshot
from spx_butterfly.multidate_charts import create_multidate_structure_chart

raw = load_raw_dataset(find_default_file())
df = transform_to_long_form(raw)
dates = ['2026-08-03', '2026-08-04']
flies = build_multidate_flies(df, dates)
print("Type of flies['2026-08-03']:", type(flies['2026-08-03']))
print("Length:", len(flies['2026-08-03']))
print("First fly item:", flies['2026-08-03'][0])

snaps = {d: get_snapshot(df, d) for d in dates}
try:
    fig = create_multidate_structure_chart(
        snapshots=snaps,
        selected_dates=dates,
        metric_category="fly_skew_rr",
        reference_date='2026-08-03',
        focus_date='2026-08-04',
        flies_by_date=flies,
    )
    print("SUCCESS: create_multidate_structure_chart fly_skew_rr created successfully!")
except Exception as e:
    print("ERROR in create_multidate_structure_chart:", e)
