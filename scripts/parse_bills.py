#!/usr/bin/env python3
"""Parse Pacific Power bill PDFs into dashboard JSON and CSV files.

Usage: python parse_bills.py <bills_dir> [out_dir]
Needs pypdf (pip install pypdf). If the PDFs are password protected, put the password in
tesla_api/pacific_power.txt as PDF_PASSWORD=..., or set the PP_PDF_PASSWORD environment variable.
Files must be named "YYYY-MM-DD ... .pdf" (any name works; the billing date is read from the PDF).
Every bill is checked: line items must add up to the bill's Total New Charges, or the bill is flagged.
"""
from __future__ import annotations

import csv, datetime as dt, glob, json, logging, os, re, sys
logging.getLogger("pypdf").setLevel(logging.ERROR)

HERE = os.path.dirname(os.path.abspath(__file__))
MON = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
NUM = r"-?\d[\d,]*\.\d+"


def iso(s):
    m = re.match(r"(\w{3})\w*\.? (\d{1,2}), (\d{4})", s.strip())
    return dt.date(int(m.group(3)), MON[m.group(1)[:3].title()], int(m.group(2))).isoformat() if m else None


def password():
    pw = os.environ.get("PP_PDF_PASSWORD")
    p = os.path.join(HERE, "tesla_api", "pacific_power.txt")
    if not pw and os.path.exists(p):
        for line in open(p):
            if line.startswith("PDF_PASSWORD="):
                pw = line.split("=", 1)[1].strip()
    return pw


def pdf_text(path, pw):
    from pypdf import PdfReader
    r = PdfReader(path)
    if r.is_encrypted:
        if not pw or not r.decrypt(pw):
            raise RuntimeError("encrypted; set PDF_PASSWORD")
    return "\n".join((p.extract_text() or "") for p in r.pages)


def category(name):
    n = name.lower()
    if n.startswith("basic charge"): return "basic"
    if n.startswith("delivery"): return "delivery"
    if n.startswith("supply"): return "supply"
    if "off peak" in n: return "offpeak"
    if "on peak" in n: return "onpeak"
    if "blue sky" in n: return "bluesky"
    if n.startswith("b p a") or "columbia river" in n: return "bpa"
    if "paperless" in n: return "paperless"
    if "tax" in n: return "tax"
    if any(k in n for k in ("system benefits", "energy trust", "public purpose", "low income")): return "programs"
    return "other"


RATE_KEY = {"delivery": "del", "supply": "sup", "offpeak": "off", "onpeak": "on", "bpa": "bpa", "bluesky": "blue"}
CHARGE_RE = re.compile(r"^(?P<name>[A-Za-z][A-Za-z /.&'()-]*?)?\s*(?:for (?P<days>\d+) day\(s\))?\s*"
                       r"(?:(?P<units>-?\d[\d,]*) (?P<unit>onkwh|offkwh|kwh))?\s*(?:(?P<rate>-?\d+\.\d{4,7}))?\s+(?P<charge>-?\d[\d,]*\.\d{2})$")
METER_RE = re.compile(r"^(\d+)([MS]) (\w{3} \d{1,2}, \d{4}) (\w{3} \d{1,2}, \d{4})(?: (\d+))? (\d+) (\d+) [\d.]+ (-?\d[\d,]*) (onkwh|offkwh|kwh)$")
NAME_ONLY = re.compile(r"^[A-Z][A-Za-z /.&'-]*(Charge|Usage|Assistance|Credit|Recovery|Benefits|Purpose|Tax)$")


def parse(text):
    lines = [re.sub(r"\s+", " ", l).strip() for l in text.splitlines()]
    g = lambda pat, grp=1: next((m.group(grp) for l in lines for m in [re.search(pat, l)] if m), None)
    bill = {"d": None, "p0": None, "p1": None, "days": None, "amt": None, "imp": 0, "exp": 0, "onImp": 0, "onExp": 0,
            "net": 0, "adj": 0, "bank": None, "temp": None, "plan": None}
    for i, l in enumerate(lines):
        if l == "BILLING DATE:" and bill["d"] is None:
            bill["d"] = iso(lines[i + 1])
        if re.match(r"ITEM \d+ - ELECTRIC SERVICE", l) and bill["plan"] is None:
            bill["plan"] = lines[i + 1]
    bill["amt"] = float(g(r"^New Charges \+?(" + NUM + ")").replace(",", ""))
    t = g(r"^Avg\. Daily Temp\. (\d+)"); bill["temp"] = int(t) if t else None
    b = g(r"excess power of (\d+) KWH"); bill["bank"] = int(b) if b else None
    meters = []
    for l in lines:
        m = METER_RE.match(l)
        if m:
            kwh = int(m.group(8).replace(",", "")); kind = m.group(9); main = m.group(2) == "M"
            meters.append({"meter": "main (from grid)" if main else "subordinate (to grid)", "tou": {"onkwh": "on", "offkwh": "off"}.get(kind, "all"),
                           "prev": int(m.group(6)), "cur": int(m.group(7)), "kwh": kwh, "p0": iso(m.group(3)), "p1": iso(m.group(4)), "days": m.group(5)})
            if main:
                bill["imp"] += kwh
                if kind == "onkwh": bill["onImp"] += kwh
            else:
                bill["exp"] += -kwh
                if kind == "onkwh": bill["onExp"] += -kwh
        m = re.match(r"^Usage Adjustment (-?\d+) (off)?kwh", l)
        if m: bill["adj"] += int(m.group(1))
        m = re.match(r"^Billed Usage (-?\d+)", l)
        if m: bill["net"] = max(0, int(m.group(1)))
    if meters:
        bill["p0"], bill["p1"] = meters[0]["p0"], meters[0]["p1"]
        bill["days"] = next((int(x["days"]) for x in meters if x["days"]), None)
    if not any(re.match(r"^Billed Usage", l) for l in lines):
        # no adjustment line: billed kWh is the positive on-peak plus off-peak (or plain kWh) totals
        tots = [int(m.group(1).replace(",", "")) for l in lines for m in [re.match(r"^Total (-?\d[\d,]*) (on|off)?kwh$", l)] if m]
        bill["net"] = sum(max(0, t) for t in tots)
    # line items: first item that has charges
    items, inside, name, total = [], False, None, None
    for j, l in enumerate(lines):
        if l.startswith("NEW CHARGES -"):
            inside = True; continue
        if not inside:
            continue
        if l.startswith("Total New Charges"):
            total = float(l.split()[-1].replace(",", "")); break
        if "$" in l or not l:
            continue
        nxt = next((x for x in lines[j + 1:] if x), "")
        if not re.search(r"\d", l) and (NAME_ONLY.match(l) or nxt.startswith("for ")) and len(l) < 60:
            name = l; continue
        m = CHARGE_RE.match(l)
        if not m:
            continue
        nm = (m.group("name") or "").strip() or name
        if not nm or not re.search(r"[a-z]", nm) or nm.lower().startswith(("total", "cost per", "avg")):
            continue
        name = nm
        f = lambda k, t=float: t(m.group(k).replace(",", "")) if m.group(k) else None
        items.append([nm, f("days", int), f("units", int), m.group("unit"), f("rate"), f("charge")])
    c = {k: 0.0 for k in ("delivery", "programs", "paperless", "tax", "offpeak", "onpeak", "bluesky", "supply", "basic", "bpa", "other")}
    r = {v: None for v in RATE_KEY.values()}
    for it in items:
        k = category(it[0]); c[k] = round(c[k] + it[5], 2)
        if k in RATE_KEY and it[4] is not None:
            r[RATE_KEY[k]] = it[4]
    if not c["other"]:
        del c["other"]
    bill["c"], bill["r"] = c, r
    s = round(sum(it[5] for it in items), 2)
    ok = total is not None and abs(s - total) < 0.011 and abs(total - bill["amt"]) < 0.011
    return bill, items, meters, ok, s, total


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "."
    out = sys.argv[2] if len(sys.argv) > 2 else src
    pw = password()
    bills, items, reads, bad = [], {}, [], []
    for p in sorted(glob.glob(os.path.join(src, "*.pdf"))):
        try:
            b, it, mr, ok, s, tot = parse(pdf_text(p, pw))
        except Exception as e:
            print(f"  skip {os.path.basename(p)}: {e}"); continue
        if not b["d"] or b["d"] in items:
            continue  # duplicate download of the same bill
        bills.append(b); items[b["d"]] = it
        reads += [[b["d"], x["p0"], x["p1"], x["meter"], x["tou"], x["prev"], x["cur"], x["kwh"]] for x in mr]
        if not ok:
            bad.append(f"{b['d']}: items {s} vs total {tot} vs amount {b['amt']}")
    bills.sort(key=lambda b: b["d"])
    json.dump(bills, open(os.path.join(out, "dashboard_bills.json"), "w"))
    json.dump(dict(sorted(items.items())), open(os.path.join(out, "dashboard_line_items.json"), "w"))
    with open(os.path.join(out, "pacific_power_bills.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["bill_date", "period_start", "period_end", "days", "amount", "grid_import_kwh", "grid_export_kwh", "on_peak_import_kwh", "on_peak_export_kwh",
                                       "billed_kwh", "usage_adjustment_kwh", "banked_kwh", "avg_temp_f", "plan"] + [f"cost_{k}" for k in bills[-1]["c"]])
        for b in bills:
            w.writerow([b["d"], b["p0"], b["p1"], b["days"], b["amt"], b["imp"], b["exp"], b["onImp"], b["onExp"], b["net"], b["adj"], b["bank"], b["temp"], b["plan"]] + [b["c"].get(k, 0) for k in bills[-1]["c"]])
    with open(os.path.join(out, "pacific_power_line_items.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["bill_date", "line_item", "days", "units", "unit", "rate", "charge"])
        for d, it in sorted(items.items()):
            for x in it: w.writerow([d] + x)
    with open(os.path.join(out, "pacific_power_meter_reads.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["bill_date", "period_start", "period_end", "meter", "tou_period", "previous_read", "current_read", "kwh"]); w.writerows(reads)
    print(f"Parsed {len(bills)} bills ({bills[0]['d']} to {bills[-1]['d']}); {len(bills) - len(bad)} reconcile to the penny.")
    for x in bad:
        print("  CHECK", x)


if __name__ == "__main__":
    main()
