import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from reports.health import parse_power_supplies
import json

p = r"d:\NW\2026\08-August\2026-08-05\D - Block 4D - Block 4th Floorth Floor\backup_2026-08-05_12-37-05.txt"
with open(p, 'r', encoding='utf-8') as f:
    out = f.read()
res = parse_power_supplies(out)
print(json.dumps(res, indent=2))
