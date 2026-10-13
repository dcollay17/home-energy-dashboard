#!/usr/bin/env python3
"""Turn raw Fleet API day files into compact JSON for the dashboard."""
import glob, json, os, sys
RAW = sys.argv[1]
OUT = sys.argv[2]
F = {  # short keys -> API energy fields (Wh per 5-min interval)
    "hs": "consumer_energy_imported_from_solar", "hb": "consumer_energy_imported_from_battery", "hg": "consumer_energy_imported_from_grid",
    "sol": "solar_energy_exported", "gi": "grid_energy_imported", "gxs": "grid_energy_exported_from_solar", "gxb": "grid_energy_exported_from_battery",
    "bcs": "battery_energy_imported_from_solar", "bcg": "battery_energy_imported_from_grid", "bd": "battery_energy_exported",
}
daily, prof, peak = [], {}, {}
for p in sorted(glob.glob(os.path.join(RAW, "*_energy.json"))):
    d = os.path.basename(p)[:10]
    ts = (json.load(open(p)) or {}).get("time_series", [])
    if not ts:
        continue
    tot = {k: 0.0 for k in F}
    for r in ts:
        h = int(r["timestamp"][11:13]); m = d[:7]
        hrs = prof.setdefault(m, [[0.0] * 6 for _ in range(24)])  # hs, hb, hg, sol, gx, bc  (kWh summed)
        v = {k: float(r.get(f) or 0) for k, f in F.items()}
        for k in F:
            tot[k] += v[k]
        row = hrs[h]
        row[0] += v["hs"]; row[1] += v["hb"]; row[2] += v["hg"]; row[3] += v["sol"]; row[4] += v["gxs"] + v["gxb"]; row[5] += v["bcs"] + v["bcg"]
        # on-peak window used by Pacific Power TOU (weekday 5-9pm assumed for display only)
    daily.append([d] + [round(tot[k] / 1000, 2) for k in F])
days_in = {}
for r in daily:
    days_in[r[0][:7]] = days_in.get(r[0][:7], 0) + 1
profile = {m: [[round(x / 1000 / days_in[m], 3) for x in hr] for hr in hrs] for m, hrs in prof.items()}
json.dump({"fields": list(F), "daily": daily, "profile": profile}, open(OUT, "w"), separators=(",", ":"))
print(len(daily), "days;", len(profile), "months; first", daily[0][0], "last", daily[-1][0])
