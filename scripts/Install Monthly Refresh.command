#!/bin/bash
# Sets up a monthly refresh: on the 1st of each month at 8:50 am (or the next time the Mac wakes),
# macOS opens "Run Everything.command" in Terminal. To remove it later, run:
#   launchctl unload ~/Library/LaunchAgents/com.home.energy-refresh.plist && rm ~/Library/LaunchAgents/com.home.energy-refresh.plist
DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.home.energy-refresh.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.home.energy-refresh</string>
  <key>ProgramArguments</key><array><string>/usr/bin/open</string><string>$DIR/Run Everything.command</string></array>
  <key>StartCalendarInterval</key><dict><key>Day</key><integer>1</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>50</integer></dict>
</dict></plist>
PL
launchctl unload "$PLIST" 2>/dev/null
launchctl load "$PLIST" && echo "Monthly refresh installed: 1st of each month, 8:50 am." | tee -a "$DIR/energy_data/run_everything_log.txt"
launchctl list | grep energy-refresh | tee -a "$DIR/energy_data/run_everything_log.txt"
echo; echo "You can close this window."
