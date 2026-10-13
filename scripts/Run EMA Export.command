#!/bin/bash
# APsystems EMA export. Double-click to run.
cd "$(dirname "$0")"
mkdir -p energy_data
{ echo "== $(date)"; /usr/bin/python3 -u ema_export.py 2>&1; echo "== exit $?"; } | tee -a energy_data/ema_log.txt
echo; echo "You can close this window."
