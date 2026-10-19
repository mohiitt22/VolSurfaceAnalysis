"""Verification script testing Streamlit rendering for all 3 workspaces and all structure views."""

import sys
from pathlib import Path
from streamlit.testing.v1 import AppTest

app_path = str(Path(__file__).parent.parent / "app.py")
print("Initializing Streamlit AppTest on app.py...")
at = AppTest.from_file(app_path, default_timeout=30)
at.run()
assert not at.exception, f"Multi-Date workspace threw exception: {at.exception}"
print("[OK] Multi-Date workspace default rendered cleanly with 0 exceptions.")

# Test Multi-Date structure views
print("Testing Multi-Date structure views...")
for r in at.radio:
    if hasattr(r, "key") and r.key == "ms_struct_view_choice":
        for i, opt in enumerate(r.options):
            print(f"  Testing Multi-Date view idx {i}...")
            r.set_value(opt).run()
            assert not at.exception, f"Multi-Date view idx {i} threw: {at.exception}"
            print(f"  [OK] Multi-Date view idx {i} passed.")

# Switch to Consecutive Date Analysis
print("Switching to Consecutive Date Analysis workspace...")
at.sidebar.radio[0].set_value("Consecutive Date Analysis").run()
assert not at.exception, f"Consecutive Date workspace threw exception: {at.exception}"
print("[OK] Consecutive Date Analysis workspace rendered cleanly with 0 exceptions.")

# Test Consecutive Date structure views
print("Testing Consecutive Date structure views...")
for r in at.radio:
    if hasattr(r, "key") and r.key == "consec_struct_choice":
        for i, opt in enumerate(r.options):
            print(f"  Testing Consecutive Date view idx {i}...")
            r.set_value(opt).run()
            assert not at.exception, f"Consecutive Date view idx {i} threw: {at.exception}"
            print(f"  [OK] Consecutive Date view idx {i} passed.")

# Switch to Single-Date Volatility Lab
print("Switching to Single-Date Volatility Lab workspace...")
at.sidebar.radio[0].set_value("Single-Date Volatility Lab").run()
assert not at.exception, f"Single-Date Volatility Lab threw exception: {at.exception}"
print("[OK] Single-Date Volatility Lab workspace rendered cleanly with 0 exceptions.")

print("ALL WORKSPACES AND STRUCTURE VIEWS RENDERED WITH 0 EXCEPTIONS!")
