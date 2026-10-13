#!/usr/bin/env python3
"""Tesla vehicle snapshot + charging history (Fleet API). Reuses tesla_fleet_export's sign-in."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tesla_fleet_export as T

OUT = os.path.join(T.OUT, "vehicle")


def main():
    os.makedirs(OUT, exist_ok=True)
    c = T.creds()
    tok = T.access_token(c)
    vehicles = T.get(tok, "/api/1/vehicles") or []
    json.dump(vehicles, open(os.path.join(OUT, "vehicles.json"), "w"))
    T.log(f"Vehicles: {len(vehicles)}")
    stamp = time.strftime("%Y-%m-%dT%H%M")
    for v in vehicles:
        vin = v.get("vin")
        T.log(f"  {v.get('display_name')} state={v.get('state')}")
        eps = "charge_state;climate_state;vehicle_state;vehicle_config;gui_settings"
        data = None
        for attempt in range(4):
            code, r = T.curl("GET", f"{T.BASE}/api/1/vehicles/{vin}/vehicle_data?endpoints={eps}", token=tok)
            if code == 200:
                data = r.get("response"); break
            if code == 408 and attempt == 0:
                T.log("  car asleep, waking it once ...")
                T.curl("POST", f"{T.BASE}/api/1/vehicles/{vin}/wake_up", token=tok)
            time.sleep(20)
        if data:
            json.dump(data, open(os.path.join(OUT, f"snapshot_{stamp}.json"), "w"))
            cs, vs = data.get("charge_state", {}), data.get("vehicle_state", {})
            T.log(f"  battery {cs.get('battery_level')}%  range {cs.get('battery_range')} mi  odometer {vs.get('odometer')}")
        else:
            T.log("  could not reach the car (asleep or offline); snapshot skipped")
        svc = T.get(tok, f"/api/1/vehicles/{vin}/service_data")
        if svc is not None:
            json.dump(svc, open(os.path.join(OUT, "service_data.json"), "w"))
    # Charging history (paginated)
    hist, page = [], 1
    while True:
        r = T.get(tok, "/api/1/dx/charging/history", pageNo=page, pageSize=50, sortBy="start_datetime", sortOrder="DESC")
        if not r:
            break
        items = r.get("data") if isinstance(r, dict) else r
        if not items:
            break
        hist += items
        if len(items) < 50:
            break
        page += 1
        time.sleep(0.5)
    json.dump(hist, open(os.path.join(OUT, "charging_history.json"), "w"))
    T.log(f"Charging history sessions: {len(hist)}")
    T.log("Done.")


if __name__ == "__main__":
    main()
