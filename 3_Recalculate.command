#!/bin/bash
cd -- "$(dirname -- "$0")"
/bin/bash scripts/launch.sh recalculate
APP_EXIT=$?
read -r -p "Press Enter to close... "
exit "$APP_EXIT"
