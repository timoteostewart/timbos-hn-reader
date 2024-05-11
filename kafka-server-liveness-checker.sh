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

log_prefix_local="kafka-server-liveness-checker.sh: "

remote_host_nickname="kafka"
remote_host_ip="$(get-secret 'kafka_server_host_ip')"
kafka_server_hostname="$(get-secret 'kafka_server_hostname')"
remote_host_port_of_interest="$(get-secret 'kafka_server_port')"

nmap_xml="$(create-nmap-xml "${remote_host_ip}")"
remote_host_is_reachable="$(is-host-reachable "${remote_host_ip}" "${nmap_tempfile}")"
remote_host_port_of_interest_state="$(get-port-state "${remote_host_ip}" "${remote_host_port_of_interest}" "${nmap_tempfile}")"

if [[ -z "${remote_host_port_of_interest_state}" ]]; then
    remote_host_port_of_interest_state="no-response"
fi

if [[ "${remote_host_is_reachable}" == "true" ]]; then
    log_message="${log_prefix_local} nmap: host ${remote_host_ip} is reachable, and its port ${remote_host_port_of_interest} is ${remote_host_port_of_interest_state}"
    echo "${log_message}"
    write-log-message liveness info "${log_message}" false

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "${remote_host_nickname}-host-status-value" \
        "value" "reachable"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-color" \
        "elementId" "${remote_host_nickname}-host-status-value" \
        "value" "green"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "${remote_host_nickname}-host-${remote_host_nickname}-port-status-value" \
        "value" "${remote_host_port_of_interest_state}"

    if [[ "${remote_host_port_of_interest_state}" == "open" ]]; then
        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-color" \
            "elementId" "${remote_host_nickname}-host-${remote_host_nickname}-port-status-value" \
            "value" "green"
    else
        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-color" \
            "elementId" "${remote_host_nickname}-host-${remote_host_nickname}-port-status-value" \
            "value" "green"
    fi

elif [[ "${remote_host_is_reachable}" == "false" ]]; then
    log_message="${log_prefix_local} nmap: host ${remote_host_ip} is not reachable"
    echo "${log_message}"
    write-log-message liveness error "${log_message}" false

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "${remote_host_nickname}-host-status-value" \
        "value" "not reachable"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-color" \
        "elementId" "${remote_host_nickname}-host-status-value" \
        "value" "red"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "${remote_host_nickname}-host-${remote_host_nickname}-port-status-value" \
        "value" "—"
fi

"${project_base_dir}send-dashboard-event-to-kafka.sh" \
    "operation" "update-text-content" \
    "elementId" "${remote_host_nickname}-status-last-updated-iso8601" \
    "value" "$(get-iso8601-date)"

# Check if Kafka is operating normally
topic_name="thnr-dashboard"
liveness_check_output="$(kafkacat -b "${remote_host_ip}:${remote_host_port_of_interest}" -L 2>&1)"

if [[ "${liveness_check_output}" == *"Metadata for all topics"* ]]; then
    log_message="${log_prefix_local} kcat: Kafka server at ${remote_host_ip}:${remote_host_port_of_interest} is up"
    echo "${log_message}"
    write-log-message liveness info "${log_message}" false

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "${remote_host_nickname}-server-status-value" \
        "value" "up"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-color" \
        "elementId" "${remote_host_nickname}-server-status-value" \
        "value" "green"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "${remote_host_nickname}-status-last-updated-iso8601" \
        "value" "$(get-iso8601-date)"

# elif [[ "${liveness_check_output}" == *"Failed to acquire metadata:"* ]] || [[ "${liveness_check_output}" == *"Broker transport failure"* ]]; then
else
    log_message="${log_prefix_local} kcat: No Kafka server detected at ${kafka_server_hostname}:${remote_host_port_of_interest}"
    echo "${log_message}"
    write-log-message liveness info "${log_message}" false

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "${remote_host_nickname}-server-status-value" \
        "value" "down"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-color" \
        "elementId" "${remote_host_nickname}-server-status-value" \
        "value" "red"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "${remote_host_nickname}-status-last-updated-iso8601" \
        "value" "$(get-iso8601-date)"
fi

exit 0
