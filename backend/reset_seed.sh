#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
rm -f app.db
python dev_seed.py --reset
echo "Reset + seed complete."
