#!/usr/bin/env bash

# debugging switches
# set -o errexit   # abort on nonzero exitstatus; same as set -e
# set -o nounset   # abort on unbound variable; same as set -u
# set -o pipefail  # don't hide errors within pipes
# set -o xtrace    # show commands being executed; same as set -x
# set -o verbose   # verbose mode; same as set -v

source /srv/timbos-hn-reader/functions.sh
source /srv/timbos-hn-reader/thnr-common-functions.sh

project_base_dir="/srv/timbos-hn-reader/"

uptime_seconds=$(cat /proc/uptime | awk '{print $1}')

"${project_base_dir}send-dashboard-event-to-kafka.sh" \
    "operation" "update-text-content" \
    "elementId" "scraper-host-uptime-seconds" \
    "value" "${uptime_seconds}"

exit 0
