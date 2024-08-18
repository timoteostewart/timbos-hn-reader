#!/usr/bin/env bash

# debugging switches
# set -o errexit   # abort on nonzero exitstatus; same as set -e
# set -o nounset   # abort on unbound variable; same as set -u
# set -o pipefail # don't hide errors within pipes
# set -o xtrace    # show commands being executed; same as set -x
# set -o verbose   # verbose mode; same as set -v

# exit immediately if $ONCE_FLAG exists and has a non-empty value
# so we avoid spurious logging during "ONCE" runs of loop-thnr.sh
if [ -n "$ONCE_FLAG" ]; then
    exit 0
fi

source /srv/timbos-hn-reader/functions.sh
source /srv/timbos-hn-reader/thnr-common-functions.sh

alias kafkacat='kcat'

# retrieve secrets
kafka_dashboard_topic="$(get-secret 'kafka_dashboard_topic')"
# kafka_message_version="$(get-secret 'kafka_message_version')"
kafka_message_version="0.1.2"
kafka_server_host_ip="$(get-secret 'kafka_server_host_ip')"
kafka_server_port="$(get-secret 'kafka_server_port')"
kafka_server_username="$(get-secret 'kafka_server_username')"

if [[ -z "${kafka_server_host_ip}" ]]; then
    die "Failed to retrieve Kafka server host IP from secrets."
fi

kv_pairs=""

add_kv_pair() {
    local pair="\"${1}\": \"${2}\""

    if [[ -z "${kv_pairs}" ]]; then
        kv_pairs="${pair}"
    else
        kv_pairs="${kv_pairs}, ${pair}"
    fi
}

# if "timestamps" is first argument, extract next two arguments as unix timestamp and iso8601 timestamp
if [[ "${1}" == "timestamps" ]]; then
    add_kv_pair "timestamp_unix" "${2}"
    add_kv_pair "timestamp_iso8601" "${3}"
    shift 3
fi

# ensure we have an even number of remaining arguments
if [ $(($# % 2)) -ne 0 ]; then
    die "incorrect number of arguments"
fi

# extract remaining arguments as key-value pairs
while [ $# -gt 0 ]; do
    add_kv_pair "${1}" "${2}"
    shift 2
done

add_kv_pair "kafka_message_version" "${kafka_message_version}"

message="{${kv_pairs}}"

# printf "${message}\n"

echo "${message}" | kafkacat -P -b "${kafka_server_host_ip}:${kafka_server_port}" -t "${kafka_dashboard_topic}"

res=$?

[[ "${res}" != 0 ]] && die "Failed to send message to Kafka: ${message}"
