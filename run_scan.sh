#!/usr/bin/env bash
# Tender Monitor - run one scan of all enabled portals (used by cron or manually)
set -e
cd "$(dirname "$0")"
exec ./.venv/bin/python main.py --scan
