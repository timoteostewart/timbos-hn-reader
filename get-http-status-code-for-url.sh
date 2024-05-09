#!/usr/bin/env bash

# debugging switches
# set -o errexit   # abort on nonzero exitstatus; same as set -e
# set -o nounset   # abort on unbound variable; same as set -u
# set -o pipefail  # don't hide errors within pipes
# set -o xtrace    # show commands being executed; same as set -x
# set -o verbose   # verbose mode; same as set -v

source /srv/timbos-hn-reader/functions.sh
source /srv/timbos-hn-reader/thnr-common-functions.sh

target_url="${1-}"

[[ -z "${target_url}" ]] && die "get-http-status-code-for-url.sh requires a URL to be specified."

alert_email_address="$(get-secret 'alert_email_address')"

STATUS=$(curl -o /dev/null -s -w "%{http_code}\n" --max-time 10 $URL)

# Check if the status code is not 200
if [ "$STATUS" -ne 200 ]; then
    # Send email alert
    echo "The URL $URL did not return a 200 status code. Status was $STATUS." | mail -s "URL Check Alert" $EMAIL

    # Instead of email, you could send a Slack/Teams/PagerDuty/Pushover/etc, etc alert, with something like:
    curl -X POST https://events.pagerduty.com/...
fi
