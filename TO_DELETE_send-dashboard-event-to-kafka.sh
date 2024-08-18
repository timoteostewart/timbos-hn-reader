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

if [ $(($# % 2)) -ne 0 ]; then
    echo "Please provide an even number of arguments."
    exit 1
fi

source /srv/timbos-hn-reader/functions.sh
source /srv/timbos-hn-reader/thnr-common-functions.sh

# retrieve secrets
kafka_dashboard_topic="$(get-secret 'kafka_dashboard_topic')"
# kafka_message_version="$(get-secret 'kafka_message_version')"
kafka_message_version="0.1.0"
kafka_server_host_ip="$(get-secret 'kafka_server_host_ip')"
kafka_server_port="$(get-secret 'kafka_server_port')"
kafka_server_username="$(get-secret 'kafka_server_username')"

if [ -z "${kafka_server_host_ip}" ] || [ -z "${kafka_server_username}" ]; then
    echo "Failed to retrieve Kafka server host IP or username from secrets."
    exit 1
fi

kv_pairs=""

while [ $# -gt 0 ]; do
    key="$1"
    value="$2"

    pair="\"$key\":\"$value\""
    if [ -z "$kv_pairs" ]; then
        kv_pairs=$pair
    else
        kv_pairs="$kv_pairs, $pair"
    fi

    shift 2
done

timestamp_unix="$(get-time-in-unix-seconds)"

message="{\"topic\":\"${kafka_dashboard_topic}\", ${kv_pairs}, \"timestamp_unix\":${timestamp_unix}, \"kafka_message_version\":\"${kafka_message_version}\", \"username\":\"${kafka_server_username}\"}"

# printf "${message}\n"

echo "${message}" | kafkacat -P -b "${kafka_server_host_ip}:${kafka_server_port}" -t "${kafka_dashboard_topic}"

res=$?

if [[ "${res}" != 0 ]]; then
    printf "Failed to send message to Kafka: ${message}\n"
fi
