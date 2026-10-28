#!/bin/bash
cd -- "$(dirname -- "$0")"
/bin/bash scripts/launch.sh setup
APP_EXIT=$?
if [ "$APP_EXIT" -ne 0 ]; then echo "Setup failed. Check the message above and rerun this file."; fi
read -r -p "Press Enter to close... "
exit "$APP_EXIT"
