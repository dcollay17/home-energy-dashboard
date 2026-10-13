#!/bin/bash
# Tesla Fleet API Export. Double-click to run.
cd "$(dirname "$0")"
mkdir -p energy_data
{ echo "== $(date)"; /usr/bin/python3 -u tesla_fleet_export.py 2>&1; echo "== exit $?"; } | tee -a energy_data/api_log.txt
echo; echo "You can close this window."
