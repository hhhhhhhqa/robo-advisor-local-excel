#!/bin/bash
cd -- "$(dirname -- "$0")"
/bin/bash scripts/launch.sh update
APP_EXIT=$?
if [ "$APP_EXIT" -ne 0 ]; then echo "Update failed. Your Excel inputs have been kept. Check the message above."; fi
read -r -p "Press Enter to close... "
exit "$APP_EXIT"
