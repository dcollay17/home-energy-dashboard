#!/usr/bin/env python3
"""Build dashboard_ema.json from energy_data/ema (APsystems OpenAPI export)."""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
E = os.path.join(HERE, "energy_data", "ema")
out = sys.argv[1]
inv = json.load(open(os.path.join(E, "inverters.json")))["data"][0]["inverter"]
months = sorted({os.path.basename(f)[-12:-5] for f in glob.glob(os.path.join(E, "inv_*_daily_*.json"))})[-12:]
panels = []
for i in inv:
    u = i["uid"]; s = json.load(open(os.path.join(E, f"inv_{u}_summary.json")))["data"]
    n = 4 if i["type"] == "QS1" else 2 if i["type"] in ("YC600", "DS3", "DS3-S", "DS3-L") else len([k for k in s if k.startswith("t")])
    for c in range(1, n + 1):
        mo = []
        for m in months:
            p = os.path.join(E, f"inv_{u}_daily_{m}.json")
            d = (json.load(open(p)).get("data") or {}) if os.path.exists(p) else {}
            mo.append(round(sum(float(v or 0) for v in d.get(f"e{c}") or []), 2))
        panels.append({"name": f"{i['type']} {u[-4:]} ch{c}", "inv": u, "type": i["type"], "ch": c,
                       "life": float(s.get(f"t{c}") or 0), "year": float(s.get(f"y{c}") or 0), "months": mo})
daily = []
for f in sorted(glob.glob(os.path.join(E, "sys_daily_*.json"))):
    m = os.path.basename(f)[-12:-5]
    for k, v in enumerate(json.load(open(f)).get("data") or []):
        daily.append([f"{m}-{k + 1:02d}", float(v or 0)])
res = {"panels": panels, "months": months, "daily": daily, "details": json.load(open(os.path.join(E, "details.json")))["data"],
       "summary": json.load(open(os.path.join(E, "summary.json")))["data"]}
json.dump(res, open(out, "w"))
print(f"solar panels: {len(panels)} panels, {len(daily)} days, months {months[0]} to {months[-1]}")
