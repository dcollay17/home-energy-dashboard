#!/bin/bash
# Refresh all energy data and rebuild the dashboard. Double-click to run.
# Safe to rerun: every step only fetches what's new. Read-only: nothing changes any device settings.
cd "$(dirname "$0")"
mkdir -p energy_data
VENV="energy_data/.venv"; PY=/usr/bin/python3; BILLS="bills"  # folder holding your bill PDFs; dashboard data files are written here too
LOG="energy_data/run_everything_log.txt"
set -o pipefail
FAILS=0
step() { echo; echo "---- $1"; }
chk() { local rc=$?; if [ $rc -ne 0 ]; then FAILS=$((FAILS+1)); echo "  !! step failed (exit $rc)"; fi; }
{
echo "== $(date)"
[ -x "$VENV/bin/python" ] || $PY -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check pyeconet pypdf 2>&1 | tail -2
step "Tesla: Powerwall, solar, grid (new days only)";  $PY -u tesla_fleet_export.py 2>&1 | tail -4; chk
step "Tesla: home charging (Wall Connector)";          $PY -u tesla_home_charging.py 2>&1 | tail -4; chk
step "Tesla: car snapshot and Supercharging";           $PY -u tesla_vehicle_export.py 2>&1 | tail -4; chk
step "Rheem water heater (read-only)";                  "$VENV/bin/python" -u econet_export.py 2>&1 | grep -v "^ *{" | tail -3; chk
step "APsystems solar panels";                          $PY -u ema_export.py 2>&1 | tail -3; chk
step "Pacific Power bills";                             "$VENV/bin/python" -u parse_bills.py "$BILLS" "$BILLS" 2>&1 | tail -5; chk
step "Build dashboard data"
$PY build_tesla_dash_data.py energy_data/raw "$BILLS/dashboard_tesla.json"; chk
$PY build_tesla_base.py "$BILLS"; chk
$PY build_car_dash_data.py "$BILLS/dashboard_car.json"; chk
$PY build_water_dash_data.py "$BILLS/dashboard_water_heater.json"; chk
$PY build_ema_dash_data.py "$BILLS/dashboard_ema.json"; chk
$PY ../dashboard/build_dashboard.py "$BILLS" energy-dashboard.html; chk
if [ $FAILS -eq 0 ]; then date "+%Y-%m-%d %H:%M" > energy_data/last_refresh.txt; echo "== done $(date), all steps OK"; else echo "== done $(date) with $FAILS failed step(s); see above"; fi
echo $FAILS > energy_data/last_run_failures.txt
} 2>&1 | tee -a "$LOG"
[ "$1" = "--quiet" ] || { open energy-dashboard.html; echo; echo "Done. The dashboard opened in your browser. You can close this window."; }
