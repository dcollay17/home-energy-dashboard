#!/bin/bash
# Tesla car snapshot + charging history. Double-click to run.
cd "$(dirname "$0")"
mkdir -p energy_data
{ echo "== $(date)"; /usr/bin/python3 -u tesla_vehicle_export.py 2>&1; echo "== exit $?"; } | tee -a energy_data/car_log.txt
echo; echo "You can close this window."
