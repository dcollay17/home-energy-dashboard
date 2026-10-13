#!/usr/bin/env python3
"""Build dashboard_water_heater.json from energy_data/water_heater (Rheem EcoNet export). Read-only data."""
import datetime as dt, glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(HERE, "energy_data", "water_heater")
out = sys.argv[1]
SKIP = set()  # add dates to ignore here
daily = []
for p in sorted(glob.glob(os.path.join(W, "*_energy.json"))):
    day = os.path.basename(p)[:10]
    d = json.load(open(p)); hr = [(d.get("hourly") or {}).get(str(i)) or 0 for i in range(24)]
    if day in SKIP or sum(hr) > 100 or (not daily and sum(hr) == 0):  # >100 kWh in a day = counter reset
        continue
    daily.append([day, round(sum(hr), 2), hr])
end = dt.date.today() - dt.timedelta(days=1); start = (end - dt.timedelta(days=364)).isoformat()
last = [r for r in daily if r[0] >= start]
prof = [round(sum(r[2][h] for r in last) / max(len(last), 1), 3) for h in range(24)]
snap = json.load(open(os.path.join(W, "snapshot.json")))
res = {"daily": [r[:2] for r in daily], "profile": prof, "days12": len(last), "kwh12": round(sum(r[1] for r in last), 1),
       "snapshot": {k: snap.get(k) for k in ("name", "set_point", "mode", "tank_health", "compressor_health", "hot_water_pct", "taken")}}
json.dump(res, open(out, "w"))
print(f"water heater: {len(daily)} days, {res['kwh12']} kWh last 12 months")
