#!/usr/bin/env python3
"""Build energy-dashboard.html from dash_template.html + config.json + the dashboard_*.json data files.

Usage: python3 build_dashboard.py <data_dir> [out.html]
data_dir holds dashboard_bills.json, dashboard_line_items.json, dashboard_tesla.json, dashboard_tesla_base.json,
dashboard_car.json, dashboard_water_heater.json, dashboard_ema.json. All are required; a missing one stops the build
with a clear message instead of writing a broken page.
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
data = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "data")
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "energy-dashboard.html")
cfg_path = os.path.join(HERE, "config.json")
if not os.path.exists(cfg_path):
    cfg_path = os.path.join(HERE, "config.example.json")
t = open(os.path.join(HERE, "dash_template.html")).read()
files = {"__CONFIG__": cfg_path, "__BILLS__": "dashboard_bills.json", "__ITEMS__": "dashboard_line_items.json", "__API__": "dashboard_tesla.json",
         "__TESLA__": "dashboard_tesla_base.json", "__CAR__": "dashboard_car.json", "__WATER__": "dashboard_water_heater.json", "__EMA__": "dashboard_ema.json"}
import datetime as _dt
cfg = json.load(open(cfg_path)); cfg["built"] = _dt.datetime.now().strftime("%b %d, %Y %I:%M %p")
built_cfg = os.path.abspath(os.path.join(data, ".config_built.json")); json.dump(cfg, open(built_cfg, "w"), ensure_ascii=False)
files["__CONFIG__"] = built_cfg


def safe(js):
    # JSON is valid JS; neutralize sequences that would close or comment out the surrounding <script>
    return js.replace("</", "<\\/").replace("<!--", "<\\u0021--")


payload = {}
missing = []
for k, f in files.items():
    p = f if os.path.isabs(f) else os.path.join(data, f)
    if not os.path.exists(p):
        missing.append(os.path.basename(p)); continue
    payload[k] = safe(json.dumps(json.load(open(p)), ensure_ascii=False, separators=(",", ":")))
if missing:
    sys.exit("Missing data files in " + data + ": " + ", ".join(missing) + ". Run the matching export first.")
t = re.sub("|".join(map(re.escape, payload)), lambda m: payload[m.group(0)], t)
open(out, "w").write(t)
print("wrote", out)
