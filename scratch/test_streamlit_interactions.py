"""Test user interactions on Streamlit app."""

from pathlib import Path
from streamlit.testing.v1 import AppTest

app_path = str(Path(__file__).parent.parent / "app.py")
at = AppTest.from_file(app_path, default_timeout=30)
at.run()
assert not at.exception

# Test Multi-Date Section 3 Structure selector
print("Testing Multi-Date structure curve selector...")
# Find ms_struct_view_choice radio
struct_radios = [r for r in at.radio if r.key == "ms_struct_view_choice"]
assert len(struct_radios) == 1, "ms_struct_view_choice radio not found"
struct_radios[0].set_value("⚖️ Call Skew & Put Skew (vol pts)").run()
assert not at.exception
print("[OK] Call & Put Skew rendered on Multi-Date.")

struct_radios[0].set_value("📐 Skew / Risk Reversal (Call − Put vol pts)").run()
assert not at.exception
print("[OK] Risk Reversal rendered on Multi-Date.")

struct_radios[0].set_value("🌊 Smile Curvature & Kurtosis Fat-Tail Ratio").run()
assert not at.exception
print("[OK] Curvature & Kurtosis rendered on Multi-Date.")

# Switch to Consecutive Date Analysis
print("Switching to Consecutive Date Analysis...")
at.sidebar.radio[0].set_value("Consecutive Date Analysis").run()
assert not at.exception

# Test Graph 2 structure selector in Consecutive View
consec_struct_radios = [r for r in at.radio if r.key == "consec_struct_choice"]
assert len(consec_struct_radios) == 1, "consec_struct_choice radio not found"

consec_struct_radios[0].set_value("⚖️ Call Skew, Put Skew & Risk Reversal (vol pts)").run()
assert not at.exception
print("[OK] Consecutive Skew & RR rendered.")

consec_struct_radios[0].set_value("🌊 Smile Curvature & Kurtosis Fat-Tail Ratio").run()
assert not at.exception
print("[OK] Consecutive Curvature & Kurtosis rendered.")

# Test Stepper Buttons: Next Pair
print("Testing Next Pair button...")
next_buttons = [b for b in at.button if "Next Pair" in b.label]
assert len(next_buttons) == 1
next_buttons[0].click().run()
assert not at.exception
print(f"[OK] Next pair clicked, new date1: {at.session_state['consec_date1']}, date2: {at.session_state['consec_date2']}")

# Test Stepper Buttons: Prev Pair
print("Testing Prev Pair button...")
prev_buttons = [b for b in at.button if "Prev Pair" in b.label]
assert len(prev_buttons) == 1
prev_buttons[0].click().run()
assert not at.exception
print(f"[OK] Prev pair clicked, new date1: {at.session_state['consec_date1']}, date2: {at.session_state['consec_date2']}")

print("ALL USER INTERACTIONS VERIFIED SUCCESSFULLY!")
