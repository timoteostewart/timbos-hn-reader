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
uptime_seconds_whole="${uptime_seconds%%.*}"
uptime_pretty=$(prettify-duration-seconds ${uptime_seconds_whole})

cur_timestamp=$(get-time-in-unix-seconds)
cur_iso8601=$(convert-time-in-unix-seconds-to-iso8601 "${cur_timestamp}")

"${project_base_dir}send-dashboard-event-to-kafka2.sh" \
    "timestamps" "${cur_timestamp}" "${cur_iso8601}" \
    "operation" "update-text-content" \
    "elementId" "scraper-host-uptime-pretty" \
    "value" "${uptime_pretty}"

# "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
#     "operation" "update-text-content" \
#     "elementId" "scraper-host-stats-last-updated-iso8601" \
#     "value" "$(get-iso8601-date)"

exit 0
