"""Deep interaction test verifying new Fly Premium Structure features."""

from pathlib import Path
from streamlit.testing.v1 import AppTest

app_path = str(Path(__file__).parent.parent / "app.py")
print("Initializing AppTest...")
at = AppTest.from_file(app_path, default_timeout=30)
at.run()
assert not at.exception, f"Initial run failed: {at.exception}"

# Switch to Consecutive Date Analysis
at.sidebar.radio[0].set_value("Consecutive Date Analysis").run()
assert not at.exception, f"Failed to switch to Consecutive Date Analysis: {at.exception}"
print("[OK] Switched to Consecutive Date Analysis")

# Find struct choice radio
struct_radio = None
for r in at.radio:
    if r.key == "consec_struct_choice":
        struct_radio = r
        break

assert struct_radio is not None, "consec_struct_choice radio not found"
print(f"Found radio options: {struct_radio.options}")

# Test every structure option
for opt in struct_radio.options:
    print(f"Testing radio option: {opt}...")
    struct_radio.set_value(opt).run()
    assert not at.exception, f"Failed on option {opt}: {at.exception}"
    print(f"  [PASS] {opt} rendered cleanly with {len(at.plotly_chart)} plotly charts")

print("ALL FLY STRUCTURE OPTIONS VERIFIED SUCCESSFULLY!")
