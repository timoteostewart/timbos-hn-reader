#!/usr/bin/env bash

if [ $(($# % 2)) -ne 0 ]; then
    echo "Please provide an even number of arguments."
    exit 1
fi

# retrieve secrets
secrets_file="/srv/timbos-hn-reader/secrets_file.py"
kafka_server_host_ip=""
kafka_server_username=""

# Read each line from the secrets file
while IFS= read -r line; do
    # Extract the username
    if [[ "$line" =~ KAFKA_SERVER_HOST_IP[[:space:]]*=[[:space:]]*\"(.*)\" ]]; then
        kafka_server_host_ip="${BASH_REMATCH[1]}"
    fi
    # Extract the password
    if [[ "$line" =~ KAFKA_SERVER_USERNAME[[:space:]]*=[[:space:]]*\"(.*)\" ]]; then
        kafka_server_username="${BASH_REMATCH[1]}"
    fi
done <"${secrets_file}"

if [ -z "${kafka_server_host_ip}" ] || [ -z "${kafka_server_username}" ]; then
    echo "Failed to retrieve Kafka server host IP or username from secrets file."
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

dashboard_kafka_topic="dashboard"
kafka_server_port="9092"
message_version="0.1.0"
timestamp_unix=$(date -u +%s)

message="{\"topic\":\"${dashboard_kafka_topic}\", ${kv_pairs}, \"timestamp_unix\":${timestamp_unix}, \"message_version\":\"${message_version}\", \"username\":\"${kafka_server_username}\"}"

# printf "${message}\n"

echo "${message}" | kafkacat -P -b "${kafka_server_host_ip}:${kafka_server_port}" -t "${dashboard_kafka_topic}"

res=$(echo $?)

if [ "${res}" -eq 0 ]; then
    printf "Message sent to Kafka successfully: ${message}\n"
else
    printf "Failed to send message to Kafka: ${message}\n"
fi
