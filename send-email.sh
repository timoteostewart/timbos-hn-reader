#!/usr/bin/env bash

# DEPRECATED

# debugging switches
# set -o errexit   # abort on nonzero exitstatus; same as set -e
# set -o nounset   # abort on unbound variable; same as set -u
# set -o pipefail # don't hide errors within pipes
# set -o xtrace    # show commands being executed; same as set -x
# set -o verbose   # verbose mode; same as set -v

source /srv/timbos-hn-reader/functions.sh
source /srv/timbos-hn-reader/thnr-common-functions.sh

alert_email_address="$(get-secret 'alert_email_address')"

recipient="${alert_email_address}"
sender="${alert_email_address}"
subject="$1"
body="$2"

{
    echo "To: ${recipient}"
    echo "From: ${sender}"
    echo "Subject: ${subject}"
    echo
    echo "${body}"
} | sendmail -t
