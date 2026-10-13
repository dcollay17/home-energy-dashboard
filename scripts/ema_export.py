#!/usr/bin/env python3
"""APsystems EMA OpenAPI export. Budget-aware: free tier is 1,000 calls/month.

Reads tesla_api/ema_credentials.txt (APP_ID, APP_SECRET, SID). Uses the Mac's built-in python3 + curl.
Saves raw JSON in energy_data/ema/. Skips anything already downloaded so reruns are cheap.
"""
import base64, datetime as dt, hashlib, hmac, json, os, subprocess, sys, time, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "energy_data", "ema")
BASE = "https://api.apsystemsema.com:9282"
BUDGET = int(os.environ.get("EMA_BUDGET", "400"))  # max calls this run
calls = 0


def creds():
    c = {}
    for line in open(os.path.join(HERE, "tesla_api", "ema_credentials.txt")):
        if "=" in line:
            k, v = line.strip().split("=", 1); c[k] = v.strip()
    if not c.get("SID"):
        sys.exit("Add your System ID (EMA app > Settings > Account Details) as SID= in tesla_api/ema_credentials.txt.")
    return c


def get(c, path, **params):
    global calls
    if calls >= BUDGET:
        raise RuntimeError("budget reached")
    ts = str(int(time.time() * 1000)); nonce = uuid.uuid4().hex
    last = path.rstrip("/").split("/")[-1]
    sts = f"{ts}/{nonce}/{c['APP_ID']}/{last}/GET/HmacSHA256"
    sig = base64.b64encode(hmac.new(c["APP_SECRET"].encode(), sts.encode(), hashlib.sha256).digest()).decode()
    q = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE}{path}" + (f"?{q}" if q else "")
    cmd = ["curl", "-sS", "--max-time", "60", url, "-H", f"X-CA-AppId: {c['APP_ID']}", "-H", f"X-CA-Timestamp: {ts}", "-H", f"X-CA-Nonce: {nonce}",
           "-H", "X-CA-Signature-Method: HmacSHA256", "-H", f"X-CA-Signature: {sig}"]
    r = subprocess.run(cmd, capture_output=True, text=True); calls += 1
    try:
        d = json.loads(r.stdout)
    except ValueError:
        d = {"raw": r.stdout[:300], "err": r.stderr[:300]}
    time.sleep(0.4)
    return d


def save(name, d):
    json.dump(d, open(os.path.join(OUT, name), "w"))


def have(name):
    return os.path.exists(os.path.join(OUT, name))


def main():
    os.makedirs(OUT, exist_ok=True)
    c = creds(); sid = c["SID"]
    det = get(c, f"/user/api/v2/systems/details/{sid}"); save("details.json", det)
    print("details:", json.dumps(det)[:400], flush=True)
    if det.get("code") not in (0, "0", None) and "data" not in det:
        sys.exit("API rejected the request; check APP_ID / APP_SECRET / SID.")
    inv = get(c, f"/user/api/v2/systems/inverters/{sid}"); save("inverters.json", inv)
    ecus = inv.get("data") or []
    uids = [i.get("uid") for e in ecus for i in (e.get("inverter") or [])]
    print(f"ECUs: {len(ecus)}  inverters: {len(uids)}", flush=True)
    save("summary.json", get(c, f"/user/api/v2/systems/summary/{sid}"))
    for u in uids:  # lifetime/year/month/today per panel channel
        save(f"inv_{u}_summary.json", get(c, f"/user/api/v2/systems/{sid}/devices/inverter/summary/{u}"))
    # System daily energy by month since Apr 2025
    m = dt.date(2025, 4, 1); today = dt.date.today()
    while m <= today:
        key = m.strftime("%Y-%m"); f = f"sys_daily_{key}.json"
        if not have(f) or key == today.strftime("%Y-%m"):
            save(f, get(c, f"/user/api/v2/systems/energy/{sid}", energy_level="daily", date_range=key))
        m = (m.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    # Per-inverter daily energy, last 12 months
    m = (today.replace(day=1) - dt.timedelta(days=330)).replace(day=1)
    while m <= today:
        key = m.strftime("%Y-%m")
        for u in uids:
            f = f"inv_{u}_daily_{key}.json"
            if not have(f) or key == today.strftime("%Y-%m"):
                try:
                    save(f, get(c, f"/user/api/v2/systems/{sid}/devices/inverter/energy/{u}", energy_level="daily", date_range=key))
                except RuntimeError:
                    print("Stopped at call budget; rerun later to continue.", flush=True); print(f"Calls used: {calls}"); return
        m = (m.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    print(f"Calls used this run: {calls}", flush=True)
    print("Done.", flush=True)


if __name__ == "__main__":
    main()
