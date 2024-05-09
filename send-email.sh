#!/usr/bin/env bash

# debugging switches
# set -o errexit   # abort on nonzero exitstatus; same as set -e
# set -o nounset   # abort on unbound variable; same as set -u
# set -o pipefail # don't hide errors within pipes
# set -o xtrace    # show commands being executed; same as set -x
# set -o verbose   # verbose mode; same as set -v

source /srv/timbos-hn-reader/functions.sh
source /srv/timbos-hn-reader/thnr-common-functions.sh

alert_email=$(get-secret "alert_email")

recipient="${alert_email}"
sender="${alert_email}"
subject="$1"
body="$2"

{
    echo "To: ${recipient}"
    echo "From: ${sender}"
    echo "Subject: ${subject}"
    echo
    echo "${body}"
} | sendmail -t
