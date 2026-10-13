#!/usr/bin/env python3
"""Monthly Tesla totals for the dashboard: [month, house kWh, car kWh, battery discharge, solar, grid import, grid export].

Months already in dashboard_tesla_base.json from the Tesla app export are kept as they are. Later months
(and the partial month the export was taken in) are computed from the Fleet API daily history, with car
charging from the Wall Connector sessions. A month is only added once Wall Connector data exists for it.
"""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
data = sys.argv[1]
base_p, api_p = os.path.join(data, "dashboard_tesla_base.json"), os.path.join(data, "dashboard_tesla.json")
base = json.load(open(base_p)) if os.path.exists(base_p) else []
meta_p = os.path.join(data, "dashboard_tesla_base_meta.json")
meta = json.load(open(meta_p)) if os.path.exists(meta_p) else {"app_export_full_through": base[-2][0] if len(base) > 1 else ""}
keep = [r for r in base if r[0] <= meta["app_export_full_through"]]
api = json.load(open(api_p)); F = {k: i + 1 for i, k in enumerate(api["fields"])}
M = {}
for r in api["daily"]:
    a = M.setdefault(r[0][:7], {k: 0.0 for k in F})
    for k in F:
        a[k] += r[F[k]]
# Wall Connector sessions; month files overlap at the edges, so de-duplicate by start time
import datetime as dt
sess = {}
for p in glob.glob(os.path.join(HERE, "energy_data", "home_charging", "*.json")):
    for h in (json.load(open(p)) or {}).get("charge_history") or []:
        t = (h.get("charge_start_time") or {}).get("seconds")
        if t:
            sess[t] = h.get("energy_added_wh") or 0
car, fetched = {}, {os.path.basename(p)[:7] for p in glob.glob(os.path.join(HERE, "energy_data", "home_charging", "*.json"))}
for t, wh in sess.items():
    m = dt.datetime.fromtimestamp(t).strftime("%Y-%m")
    car[m] = car.get(m, 0) + wh / 1000
for m in fetched:
    car.setdefault(m, 0.0)
rows = list(keep); have = {r[0] for r in keep}
for m in sorted(M):
    if m in have or m not in car:
        continue
    a = M[m]; use = a["hs"] + a["hb"] + a["hg"]
    rows.append([m, round(use - car[m], 1), round(car[m], 1), round(a["bd"], 1), round(a["sol"]), round(a["gi"], 1), round(a["gxs"] + a["gxb"], 1)])
rows.sort()
json.dump(rows, open(base_p, "w")); json.dump(meta, open(meta_p, "w"))
# accuracy check where both sources overlap
chk = [(r[0], r[2], round(car[r[0]], 1)) for r in keep if r[0] in car]
print(f"tesla base: {len(keep)} months from the app export, {len(rows) - len(keep)} from the API (through {rows[-1][0] if rows else '-'})")
if chk:
    print("  car kWh, app export vs Wall Connector:", ", ".join(f"{m} {a} vs {b}" for m, a, b in chk[-4:]))
