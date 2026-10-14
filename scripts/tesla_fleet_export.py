#!/usr/bin/env python3
"""
Tesla Fleet API Export (official API)

Pulls Powerwall / solar history from Tesla's official Fleet API and saves CSVs
for the energy dashboard. Uses only the Mac's built-in python3 and curl.

Files (next to this script, in tesla_api/):
  credentials.txt   CLIENT_ID / CLIENT_SECRET from developer.tesla.com
  tokens.json       saved sign-in (refreshes automatically)
Outputs (in energy_data/):
  raw/YYYY-MM-DD_energy.json, raw/YYYY-MM-DD_power.json   untouched API responses
  tesla_daily.csv   one row per day, every energy field summed (kWh)
  tesla_power.csv   every power reading (kW)

Rerun any time; days already downloaded are skipped.
"""
import csv, datetime as dt, glob, http.server, json, os, secrets, subprocess, sys, threading, time, urllib.parse, webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
API_DIR = os.path.join(HERE, "tesla_api")
OUT = os.path.join(HERE, "energy_data")
RAW = os.path.join(OUT, "raw")
TOKENS = os.path.join(API_DIR, "tokens.json")
AUTH = "https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token"
AUTHORIZE = "https://auth.tesla.com/oauth2/v3/authorize"
BASE = "https://fleet-api.prd.na.vn.cloud.tesla.com"
DOMAIN = None  # read from credentials.txt (DOMAIN=yourname.github.io)
REDIRECT = "http://localhost:8765/callback"
SCOPES = "openid offline_access energy_device_data vehicle_device_data"  # read-only: no command scopes
TZ = "America/Los_Angeles"
START = dt.date(2025, 3, 1)  # Powerwall online March 2025
PAUSE = 0.4


def log(*a):
    print(*a, flush=True)


def creds():
    c = {}
    for line in open(os.path.join(API_DIR, "credentials.txt")):
        if "=" in line:
            k, v = line.strip().split("=", 1)
            c[k] = v
    if "paste-" in c.get("CLIENT_ID", "paste-"):
        sys.exit("Add your Client ID and Secret to tesla_api/credentials.txt first.")
    return c


def curl(method, url, form=None, token=None, body=None):
    cmd = ["curl", "-sS", "-X", method, url, "-w", "\n%{http_code}", "--max-time", "60"]
    if token:
        cmd += ["-H", f"Authorization: Bearer {token}"]
    if form:
        for k, v in form.items():
            cmd += ["--data-urlencode", f"{k}={v}"]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "--data", json.dumps(body)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    text, _, code = r.stdout.rpartition("\n")
    try:
        data = json.loads(text) if text.strip() else {}
    except ValueError:
        data = {"raw": text[:300]}
    return int(code or 0), data


def save_tokens(t):
    t["saved_at"] = time.time()
    fd = os.open(TOKENS, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(t, f)
    os.chmod(TOKENS, 0o600)  # also tighten a file created by an older version


def partner_setup(c):
    code, t = curl("POST", AUTH, form={"grant_type": "client_credentials", "client_id": c["CLIENT_ID"],
                                        "client_secret": c["CLIENT_SECRET"], "scope": "openid energy_device_data vehicle_device_data",
                                        "audience": BASE})
    if code != 200:
        sys.exit(f"Partner token failed ({code}): {t}")
    code, r = curl("POST", f"{BASE}/api/1/partner_accounts", token=t["access_token"], body={"domain": DOMAIN or creds().get("DOMAIN", "")})
    log(f"Partner registration: {code}", "" if code == 200 else r)


def user_login(c):
    state = secrets.token_urlsafe(16)
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in q and q.get("state", [""])[0] == state:
                got["code"] = q["code"][0]
                msg = "Signed in. You can close this tab and go back to Claude."
            else:
                msg = "Sign-in did not complete: " + ", ".join(f"{k}={v[0]}" for k, v in q.items() if k != "code")
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(f"<p style='font:16px sans-serif'>{msg}</p>".encode())

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("localhost", 8765), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = AUTHORIZE + "?" + urllib.parse.urlencode({"response_type": "code", "client_id": c["CLIENT_ID"], "redirect_uri": REDIRECT,
                                                     "scope": SCOPES, "state": state, "prompt_missing_scopes": "true"})
    with open(os.path.join(API_DIR, "login_url.txt"), "w") as f:
        f.write(url)
    log("Opening Tesla sign-in in your browser ...")
    subprocess.run(["open", url])
    deadline = time.time() + 1800
    while "code" not in got and time.time() < deadline:
        time.sleep(1)
    srv.shutdown()
    if "code" not in got:
        sys.exit("Timed out waiting for Tesla sign-in.")
    code, t = curl("POST", AUTH, form={"grant_type": "authorization_code", "client_id": c["CLIENT_ID"], "client_secret": c["CLIENT_SECRET"],
                                        "code": got["code"], "audience": BASE, "redirect_uri": REDIRECT})
    if code != 200:
        sys.exit(f"Token exchange failed ({code}): {t}")
    save_tokens(t)
    log("Signed in.")
    return t


def access_token(c):
    if os.path.exists(TOKENS):
        t = json.load(open(TOKENS))
        if time.time() - t.get("saved_at", 0) < t.get("expires_in", 0) - 300:
            return t["access_token"]
        code, n = curl("POST", AUTH, form={"grant_type": "refresh_token", "client_id": c["CLIENT_ID"], "refresh_token": t["refresh_token"]})
        if code == 200:
            save_tokens(n)
            return n["access_token"]
        log(f"Refresh failed ({code}); signing in again.")
    partner_setup(c)
    return user_login(c)["access_token"]


def get(tok, path, **params):
    url = f"{BASE}{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in range(5):
        code, r = curl("GET", url, token=tok)
        if code == 200:
            return r.get("response", r)
        if code in (429, 500, 502, 503, 504):
            time.sleep(5 * (attempt + 1)); continue
        log(f"GET {path} -> {code}: {r}")
        return None
    return None


def rebuild_csvs():
    days = sorted({os.path.basename(p)[:10] for p in glob.glob(os.path.join(RAW, "*_energy.json"))})
    dcols, drows = set(), []
    for d in days:
        e = json.load(open(os.path.join(RAW, f"{d}_energy.json")))
        tot = {}
        for r in (e or {}).get("time_series", []):
            for k, v in r.items():
                if isinstance(v, (int, float)):
                    tot[k] = tot.get(k, 0) + v
        dcols |= tot.keys()
        drows.append({"date": d, **{k: round(v / 1000, 3) for k, v in tot.items()}})
    with open(os.path.join(OUT, "tesla_daily.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date"] + sorted(dcols), restval=0); w.writeheader(); w.writerows(drows)
    pcols, prows = set(), []
    for d in days:
        p = os.path.join(RAW, f"{d}_power.json")
        if not os.path.exists(p):
            continue
        for r in (json.load(open(p)) or {}).get("time_series", []):
            row = {"timestamp": r.get("timestamp")}
            for k, v in r.items():
                if isinstance(v, (int, float)):
                    row[k] = round(v / 1000, 3); pcols.add(k)
            prows.append(row)
    with open(os.path.join(OUT, "tesla_power.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["timestamp"] + sorted(pcols), restval=0); w.writeheader(); w.writerows(prows)
    log(f"CSV: {len(drows)} days, {len(prows)} power readings")


def main():
    os.makedirs(RAW, exist_ok=True)
    c = creds()
    tok = access_token(c)
    prods = get(tok, "/api/1/products") or []
    sites = [p for p in prods if "energy_site_id" in p]
    if not sites:
        sys.exit(f"No energy site found. Products: {[p.get('display_name') or p.get('resource_type') for p in prods]}")
    sid = sites[0]["energy_site_id"]
    with open(os.path.join(RAW, "products.json"), "w") as f:
        json.dump(prods, f)
    info = get(tok, f"/api/1/energy_sites/{sid}/site_info") or {}
    with open(os.path.join(RAW, "site_info.json"), "w") as f:
        json.dump(info, f)
    inst = (info.get("installation_date") or "")[:10]
    first = max(START, dt.date.fromisoformat(inst)) if inst else START
    last = dt.date.today() - dt.timedelta(days=1)
    todo = [first + dt.timedelta(days=i) for i in range((last - first).days + 1)]
    todo = [d for d in todo if not os.path.exists(os.path.join(RAW, f"{d}_power.json"))]
    log(f"Site {info.get('site_name', sid)} | {len(todo)} days to fetch")
    skipped = 0
    for n, d in enumerate(todo, 1):
        if n % 50 == 0:
            tok = access_token(c)
        s = dt.datetime.combine(d, dt.time(0, 0)).astimezone().isoformat()
        e = dt.datetime.combine(d, dt.time(23, 59, 59)).astimezone().isoformat()
        en = get(tok, f"/api/1/energy_sites/{sid}/calendar_history", kind="energy", period="day", start_date=s, end_date=e, time_zone=TZ)
        time.sleep(PAUSE)
        pw = get(tok, f"/api/1/energy_sites/{sid}/calendar_history", kind="power", period="day", start_date=s, end_date=e, time_zone=TZ)
        time.sleep(PAUSE)
        if en is None or pw is None:
            log(f"  skipped {d}, will retry next run"); skipped += 1; continue
        json.dump(en, open(os.path.join(RAW, f"{d}_energy.json"), "w"))
        json.dump(pw, open(os.path.join(RAW, f"{d}_power.json"), "w"))
        if n % 25 == 0 or n == len(todo):
            log(f"  {n}/{len(todo)} days (through {d})")
    rebuild_csvs()
    if skipped:
        log(f"Finished with {skipped} day(s) skipped; rerun to fill them in.")
        sys.exit(1)
    open(os.path.join(OUT, "DONE.txt"), "w").write(dt.datetime.now().isoformat())
    log("Done.")


if __name__ == "__main__":
    main()
