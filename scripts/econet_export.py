#!/usr/bin/env python3
"""Rheem EcoNet water heater export (unofficial EcoNet cloud API via pyeconet).

Reads tesla_api/econet_credentials.txt (EMAIL=, PASSWORD=), pulls a status snapshot
and daily energy-usage reports, saves raw JSON to energy_data/water_heater/.
"""
import asyncio, datetime as dt, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "energy_data", "water_heater")
START = dt.date(2025, 4, 1)


def creds():
    c = {}
    for line in open(os.path.join(HERE, "tesla_api", "econet_credentials.txt")):
        if "=" in line:
            k, v = line.strip().split("=", 1); c[k] = v
    if not c.get("PASSWORD") or "paste" in c.get("PASSWORD", "paste"):
        sys.exit("Fill in tesla_api/econet_credentials.txt with your EcoNet (Rheem app) email and password first.")
    return c


async def main():
    from pyeconet import EcoNetApiInterface
    from pyeconet.equipment import EquipmentType
    os.makedirs(OUT, exist_ok=True)
    c = creds()
    api = await EcoNetApiInterface.login(c["EMAIL"], password=c["PASSWORD"])
    eq = await api.get_equipment_by_type([EquipmentType.WATER_HEATER])
    whs = eq.get(EquipmentType.WATER_HEATER, [])
    print(f"Water heaters: {len(whs)}", flush=True)
    for wh in whs:
        snap = {"name": wh.device_name, "set_point": wh.set_point, "mode": str(wh.mode), "running": wh.running, "running_state": wh.running_state,
                "hot_water_pct": wh.tank_hot_water_availability, "tank_health": wh.tank_health, "compressor_health": wh.compressor_health,
                "modes": [str(m) for m in wh.modes], "taken": dt.datetime.now().isoformat()}
        json.dump(snap, open(os.path.join(OUT, "snapshot.json"), "w"), indent=1)
        print("  ", snap, flush=True)
        day = START; last = dt.date.today() - dt.timedelta(days=1); n = 0; fails = 0
        while day <= last:
            p = os.path.join(OUT, f"{day}_energy.json")
            if not os.path.exists(p):
                s = dt.datetime.combine(day, dt.time(0, 0)).astimezone(); e = dt.datetime.combine(day, dt.time(23, 59, 59)).astimezone()
                try:
                    await wh.get_energy_usage(start=s, end=e)
                    json.dump({"hourly": wh.energy_usage, "history": wh.historical_energy_usage, "unit": wh.energy_type}, open(p, "w"))
                    n += 1; fails = 0
                except Exception as ex:
                    fails += 1; print(f"   {day}: {ex}", flush=True)
                    if fails >= 5:
                        print("   stopping after repeated errors", flush=True); break
                await asyncio.sleep(1.0)
                if n and n % 30 == 0:
                    print(f"   {n} days (through {day})", flush=True)
            day += dt.timedelta(days=1)
        print(f"   saved {n} new days", flush=True)
    api.unsubscribe() if hasattr(api, "unsubscribe") else None
    print("Done.", flush=True)

asyncio.run(main())
