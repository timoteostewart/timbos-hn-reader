#!/usr/bin/env bash

# debugging switches
# set -o errexit   # abort on nonzero exitstatus; same as set -e
# set -o nounset   # abort on unbound variable; same as set -u
# set -o pipefail  # don't hide errors within pipes
# set -o xtrace    # show commands being executed; same as set -x
# set -o verbose   # verbose mode; same as set -v

source /srv/timbos-hn-reader/functions.sh
source /srv/timbos-hn-reader/thnr-common-functions.sh

# for write-log-message
project_base_dir="/srv/timbos-hn-reader/"
all_logs_dir="${project_base_dir}logs/"
combined_log_identifier="combined"
server_name=thnr
TZ=UTC
utility_account_username=tim

log_prefix_local="web-server-liveness-checker.sh: "

get-http-status-code-for-url() {
    local target_url="${1-}"

    [[ -z "${target_url}" ]] && die "get-http-status-code-for-url() requires a URL to be specified."

    http_status_code_curl=""
    if program-available curl; then
        http_status_code_curl=$(
            curl \
                --max-redirs 0 \
                --max-time 10 \
                --output /dev/null \
                --silent \
                --write-out "%{http_code}\n" \
                "${target_url}"
        )
    fi

    http_status_code_wget=""
    if program-available wget; then
        http_status_code_wget=$(
            wget \
                --max-redirect=0 \
                --server-response \
                --spider \
                "${target_url}" 2>&1 |
                grep "HTTP/" |
                awk '{print $2}'
        )
    fi

    # both 200: very happy path
    if [[ "${http_status_code_curl}" == "${http_status_code_wget}" && "${http_status_code_curl}" == "200" ]]; then
        echo "200"

    # both same: still pretty happy
    elif [[ "${http_status_code_curl}" == "${http_status_code_wget}" && "${http_status_code_curl}" != "" ]]; then
        echo "${http_status_code_curl}"

    # both blank
    elif [[ "${http_status_code_curl}" == "${http_status_code_wget}" && "${http_status_code_curl}" == "" ]]; then
        echo "failed to get http status code for ${target_url}"

    # wget worked, curl didn't
    elif [[ "${http_status_code_curl}" == "" ]]; then
        echo "${http_status_code_wget}"

    # curl worked, wget didn't
    elif [[ "${http_status_code_wget}" == "" ]]; then
        echo "${http_status_code_curl}"

    # invariant now: both curl and wget returned http status codes, but they're not the same code

    # one of them is 200
    elif [[ "${http_status_code_curl}" == "200" || "${http_status_code_wget}" == "200" ]]; then
        echo "200"

    # one starts with a "2" and the other starts with a "5"
    elif [[ "${http_status_code_curl:0:1}" == "2" && "${http_status_code_wget:0:1}" == "5" ]]; then
        echo "${http_status_code_curl}"
    elif [[ "${http_status_code_curl:0:1}" == "5" && "${http_status_code_wget:0:1}" == "2" ]]; then
        echo "${http_status_code_wget}"

    # both start with a "4"
    elif [[ "${http_status_code_curl:0:1}" == "4" && "${http_status_code_wget:0:1}" == "4" ]]; then
        echo "4xx"

    # both start with a "5"
    elif [[ "${http_status_code_curl:0:1}" == "5" && "${http_status_code_wget:0:1}" == "5" ]]; then
        echo "5xx"

    # indeterminate case
    else
        echo "indeterminate response from ${target_url}"
    fi

}

urls_file="/srv/timbos-hn-reader/urls-for-liveness-checks.txt"
die-if-file-not-present "${urls_file}"

while IFS= read -r url; do
    [[ "${url}" =~ ^# ]] && continue

    http_status_code=$(get-http-status-code-for-url "${url}")

    # slugify the url
    url_slug=$(echo "${url}" | sed -e 's/[^[:alnum:]]/-/g' | tr -s '-' | tr A-Z a-z)

    # send kafka event
    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "${url_slug}-http-status-code" \
        "value" "${http_status_code}"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "${url_slug}-http-status-code-last-updated-iso8601" \
        "value" "$(get-iso8601-date)"

    if [[ "${http_status_code}" == "200" ]]; then
        # green for good
        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-color" \
            "elementId" "${url_slug}-http-status-code" \
            "value" "green"
    else
        # red for bad
        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-color" \
            "elementId" "${url_slug}-http-status-code" \
            "value" "red"

        # send alert email
        send-alert-email \
            "Web server problem: http status code ${http_status_code} for ${url}" \
            "Web server problem: http status code ${http_status_code} for ${url}"
    fi

done <"${urls_file}"

exit

# Check if the status code is not 200
if [ "${http_status_code}" -ne 200 ]; then
    # Send email alert
    echo "The URL $URL did not return a 200 status code. Status was ${http_status_code}." | mail -s "URL Check Alert" $EMAIL

    # Instead of email, you could send a Slack/Teams/PagerDuty/Pushover/etc, etc alert, with something like:
    curl -X POST https://events.pagerduty.com/...
fi
