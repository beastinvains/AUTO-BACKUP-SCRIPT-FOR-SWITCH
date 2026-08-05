import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import json
from pathlib import Path
from reports.health import parse_power_supplies

p = Path(r"d:\NW\2026\08-August\2026-08-05\daily_report.json")
report = json.loads(p.read_text(encoding='utf-8'))

for dev in report.get('devices', []):
    hostname = dev.get('hostname')
    cmds = dev.get('commands', [])
    text = '\n'.join([(c.get('command','')+'\n'+c.get('output','')+'\n'+c.get('error','')) for c in cmds])
    # parsed from text
    parsed = parse_power_supplies(text)
    meta = dev.get('metadata', {}).get('power_supplies')
    meta_items = len(meta.get('items', [])) if meta and isinstance(meta.get('items'), list) else 0
    # decide which to use (match JS logic)
    if meta and parsed:
        power = meta if (meta_items and meta_items >= parsed['total']) else parsed
    else:
        power = meta or parsed or {}
    print(hostname)
    print('  parsed total:', parsed.get('total'))
    if meta:
        print('  meta total:', meta.get('total'), 'items:', meta_items)
    print('  chosen total:', power.get('total'), 'ok:', power.get('ok'), 'failed:', power.get('failed'), 'warning:', power.get('warning'))
    print('')
