#!/usr/bin/env bash

# debugging switches
# set -o errexit   # abort on nonzero exitstatus; same as set -e
# set -o nounset   # abort on unbound variable; same as set -u
# set -o pipefail  # don't hide errors within pipes
# set -o xtrace    # show commands being executed; same as set -x
# set -o verbose   # verbose mode; same as set -v

source /srv/timbos-hn-reader/functions.sh
source /srv/timbos-hn-reader/thnr-common-functions.sh

get-http-status-code-for-url() {}

target_url="${1-}"

[[ -z "${target_url}" ]] && die "get-http-status-code-for-url.sh requires a URL to be specified."

http_status_code_curl=$(
    curl \
        --max-redirs 0 \
        --max-time 10 \
        --output /dev/null \
        --silent \
        --write-out "%{http_code}\n" \
        "${target_url}"
)

http_status_code_wget=$(
    wget \
        --max-redirect=0 \
        --server-response \
        --spider \
        "${target_url}" 2>&1 |
        grep "HTTP/" |
        awk '{print $2}'
)

echo "${http_status_code1}"
echo "${http_status_code2}"
