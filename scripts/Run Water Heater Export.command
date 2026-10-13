#!/bin/bash
# Rheem EcoNet water heater export. Double-click to run.
cd "$(dirname "$0")"
VENV="energy_data/.venv"
mkdir -p energy_data
{
  echo "== $(date)"
  [ -x "$VENV/bin/python" ] || /usr/bin/python3 -m venv "$VENV"
  "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check pyeconet 2>&1 | tail -3
  "$VENV/bin/python" -u econet_export.py 2>&1
  echo "== exit $?"
} | tee -a energy_data/water_heater_log.txt
echo; echo "You can close this window."
