#!/usr/bin/env python3
"""Build dashboard_car.json from the newest car snapshot and the Supercharger history."""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.join(HERE, "energy_data", "vehicle")
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "dashboard_car.json")
snaps = sorted(glob.glob(os.path.join(V, "snapshot_*.json")))
prev = json.load(open(out)) if os.path.exists(out) else {}
car = dict(prev)
if snaps:
    s = json.load(open(snaps[-1])); cs, vs, vc, cl, gs = (s.get(k, {}) for k in ("charge_state", "vehicle_state", "vehicle_config", "climate_state", "gui_settings"))
    car.update({"snap_time": os.path.basename(snaps[-1])[9:24], "battery": cs.get("battery_level"), "range": cs.get("battery_range"), "limit": cs.get("charge_limit_soc"),
                "max_amps": cs.get("charge_current_request_max"), "sched_mode": cs.get("scheduled_charging_mode"), "odometer": round(vs.get("odometer") or 0, 1),
                "version": (vs.get("car_version") or "").split(" ")[0], "tpms": [vs.get("tpms_pressure_fl"), vs.get("tpms_pressure_fr"), vs.get("tpms_pressure_rl"), vs.get("tpms_pressure_rr")],
                "car_type": vc.get("car_type"), "trim": vc.get("trim_badging"), "color": vc.get("exterior_color"), "wheel": vc.get("wheel_type"),
                "inside_temp": cl.get("inside_temp"), "outside_temp": cl.get("outside_temp"), "dist_units": gs.get("gui_distance_units")})
    # odometer log across snapshots, for miles driven per month
    log = {}
    for p in snaps:
        try:
            o = json.load(open(p)).get("vehicle_state", {}).get("odometer")
        except Exception:
            o = None
        if o:
            log[os.path.basename(p)[9:19]] = round(o, 1)
    car["odo_log"] = sorted(log.items())
hp = os.path.join(V, "charging_history.json")
if os.path.exists(hp):
    sess = []
    for h in json.load(open(hp)):
        fees = h.get("fees") or []
        kwh = sum(sum(f.get(k) or 0 for k in ("usageBase", "usageTier1", "usageTier2", "usageTier3", "usageTier4")) for f in fees if f.get("feeType") == "CHARGING" and f.get("uom") == "kwh")
        cost = sum(f.get("netDue") or f.get("totalDue") or 0 for f in fees)
        sess.append([(h.get("chargeStartDateTime") or "")[:16], h.get("siteLocationName"), round(kwh, 1), round(cost, 2)])
    car["sessions"] = sorted(sess, reverse=True)
car.setdefault("service", {})
json.dump(car, open(out, "w"))
print(f"car: snapshot {car.get('snap_time')}, odometer {car.get('odometer')}, {len(car.get('sessions', []))} Supercharger sessions")
