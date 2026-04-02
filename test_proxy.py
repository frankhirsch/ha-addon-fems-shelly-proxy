#!/usr/bin/env python3
"""
Schnelltest: Prüft ob der Proxy korrekte Shelly Plug S Gen3 Antworten liefert.
Aufruf: python test_proxy.py [port]
"""

import json
import sys
import urllib.request

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
BASE = f"http://localhost:{PORT}"

TESTS = [
    ("Device Info", "/shelly", ["app", "gen", "mac", "model"]),
    ("GetDeviceInfo", "/rpc/Shelly.GetDeviceInfo", ["app", "gen"]),
    ("GetStatus", "/rpc/Shelly.GetStatus", ["switch:0", "sys", "wifi"]),
    ("Switch.GetStatus", "/rpc/Switch.GetStatus?id=0", ["apower", "voltage", "aenergy"]),
]

print(f"Teste Proxy auf {BASE}...\n")
ok = 0
for name, path, required_keys in TESTS:
    url = BASE + path
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
            missing = [k for k in required_keys if k not in data]
            if missing:
                print(f"  ✗ {name}: Fehlende Keys: {missing}")
            else:
                print(f"  ✓ {name}")
                ok += 1

                # Spezialcheck: app muss PlugSG3 sein
                if "app" in data and data["app"] != "PlugSG3":
                    print(f"    ⚠ app='{data['app']}' (erwartet 'PlugSG3')")

                # Spezialcheck: switch:0 muss apower haben
                if "switch:0" in data:
                    sw = data["switch:0"]
                    print(f"    Power: {sw.get('apower', '?')} W, "
                          f"Voltage: {sw.get('voltage', '?')} V, "
                          f"Current: {sw.get('current', '?')} A")
    except Exception as e:
        print(f"  ✗ {name}: {e}")

print(f"\n{ok}/{len(TESTS)} Tests bestanden.")
if ok == len(TESTS):
    print("→ Proxy bereit für FEMS Shelly DIY App!")
else:
    print("→ Bitte Proxy und config.json prüfen.")
