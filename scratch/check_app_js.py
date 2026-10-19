with open('dashboard/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines in app.js: {len(lines)}")
# Check for obvious syntax breakages
import re
print("Done reading.")
