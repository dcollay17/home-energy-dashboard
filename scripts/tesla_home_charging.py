#!/usr/bin/env python3
"""Home (Wall Connector) charging sessions from the Tesla Fleet API energy site.

Saves energy_data/home_charging/YYYY-MM.json for each month since the Powerwall went in.
Past months are fetched once; the current and previous month are refreshed every run.
"""
import datetime as dt, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tesla_fleet_export as T

OUT = os.path.join(T.OUT, "home_charging")


def main():
    os.makedirs(OUT, exist_ok=True)
    c = T.creds(); tok = T.access_token(c)
    prods = T.get(tok, "/api/1/products") or []
    sites = [p for p in prods if "energy_site_id" in p]
    if not sites:
        sys.exit("No energy site found.")
    sid = sites[0]["energy_site_id"]
    info = json.load(open(os.path.join(T.RAW, "site_info.json"))) if os.path.exists(os.path.join(T.RAW, "site_info.json")) else {}
    first = dt.date.fromisoformat((info.get("installation_date") or "2025-04-01")[:10]).replace(day=1)
    today = dt.date.today(); this_m = today.replace(day=1); prev_m = (this_m - dt.timedelta(days=1)).replace(day=1)
    m, n_ok, n_sess, missed = first, 0, 0, 0
    while m <= this_m:
        nxt = (m.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        p = os.path.join(OUT, f"{m:%Y-%m}.json")
        if not os.path.exists(p) or m >= prev_m:
            s = dt.datetime.combine(m, dt.time(0, 0)).astimezone().isoformat()
            e = dt.datetime.combine(min(nxt - dt.timedelta(days=1), today), dt.time(23, 59, 59)).astimezone().isoformat()
            r = T.get(tok, f"/api/1/energy_sites/{sid}/telemetry_history", kind="charge", start_date=s, end_date=e, time_zone=T.TZ)
            if r is None:
                T.log(f"  {m:%Y-%m}: no response"); missed += 1; m = nxt; continue
            json.dump(r, open(p, "w")); time.sleep(T.PAUSE)
        d = json.load(open(p)); hist = (d or {}).get("charge_history") or []
        n_ok += 1; n_sess += len(hist)
        m = nxt
    T.log(f"Home charging: {n_ok} months, {n_sess} sessions. Done.")
    if missed:
        sys.exit(1)


if __name__ == "__main__":
    main()
