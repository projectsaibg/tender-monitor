#!/usr/bin/env bash
# Tender Monitor - schedule a daily scan with cron (macOS / Linux).
# Runs run_scan.sh every day even when the dashboard is closed.
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"
MARK="# Tender Monitor scheduled scan"

printf "Enter daily scan time as HH:MM (default 07:00): "
read -r RUNTIME
RUNTIME="${RUNTIME:-07:00}"
HH="${RUNTIME%%:*}"
MM="${RUNTIME##*:}"
# Force base-10 so values like 08/09 do not fail as octal.
HH=$((10#$HH))
MM=$((10#$MM))

LINE="$MM $HH * * * cd \"$DIR\" && ./.venv/bin/python main.py --scan >> \"$DIR/data/logs/cron.log\" 2>&1 $MARK"

# Replace any previous Tender Monitor cron entry, then add the new one.
( crontab -l 2>/dev/null | grep -v "Tender Monitor scheduled scan" ; echo "$LINE" ) | crontab -

echo "Installed daily cron job at $(printf '%02d:%02d' "$HH" "$MM"):"
echo "  $LINE"
echo
echo "To view it:   crontab -l"
echo "To remove it: crontab -l | grep -v 'Tender Monitor scheduled scan' | crontab -"
