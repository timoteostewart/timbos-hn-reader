#!/usr/bin/env bash

# debugging switches
# set -o errexit   # abort on nonzero exitstatus; same as set -e
# set -o nounset   # abort on unbound variable; same as set -u
set -o pipefail  # don't hide errors within pipes
# set -o xtrace    # show commands being executed; same as set -x
# set -o verbose   # verbose mode; same as set -v

source /srv/timbos-hn-reader/functions.sh
source /srv/timbos-hn-reader/thnr-common-functions.sh

RECENT_LOGFILE=$(get-last-filename '/srv/timbos-hn-reader/logs/thnr-combined-*.log')

if [[ -n "$RECENT_LOGFILE" ]]; then
    echo "$RECENT_LOGFILE"
else
    echo "No recent logfile found matching the criteria."
fi
