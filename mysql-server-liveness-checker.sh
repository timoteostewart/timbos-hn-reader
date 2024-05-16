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

log_prefix_local="mysql-server-liveness-checker.sh: "

remote_host_nickname="mysql"
remote_host_ip="$(get-secret 'mysql_server_host_ip')"
# mysql_server_hostname="$(get-secret 'mysql_server_hostname')"
remote_host_port_of_interest="$(get-secret 'mysql_server_port')"

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

    "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
        "timestamps" "$(get-time-in-unix-seconds)" "" \
        "operation" "update-text-content" \
        "elementId" "${remote_host_nickname}-host-status-value" \
        "value" "reachable"

    "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
        "operation" "update-color" \
        "elementId" "${remote_host_nickname}-host-status-value" \
        "value" "green"

    "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
        "timestamps" "$(get-time-in-unix-seconds)" "" \
        "operation" "update-text-content" \
        "elementId" "${remote_host_nickname}-host-${remote_host_nickname}-port-status-value" \
        "value" "${remote_host_port_of_interest_state}"

    if [[ "${remote_host_port_of_interest_state}" == "open" ]]; then
        "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
            "operation" "update-color" \
            "elementId" "${remote_host_nickname}-host-${remote_host_nickname}-port-status-value" \
            "value" "green"
    else
        "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
            "operation" "update-color" \
            "elementId" "${remote_host_nickname}-host-${remote_host_nickname}-port-status-value" \
            "value" "red"
    fi

elif [[ "${remote_host_is_reachable}" == "false" ]]; then
    log_message="${log_prefix_local} nmap: host ${remote_host_ip} is not reachable"
    echo "${log_message}"
    write-log-message liveness error "${log_message}" false

    "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
        "timestamps" "$(get-time-in-unix-seconds)" "" \
        "operation" "update-text-content" \
        "elementId" "${remote_host_nickname}-host-status-value" \
        "value" "not reachable"

    "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
        "operation" "update-color" \
        "elementId" "${remote_host_nickname}-host-status-value" \
        "value" "red"

    "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
        "timestamps" "$(get-time-in-unix-seconds)" "" \
        "operation" "update-text-content" \
        "elementId" "${remote_host_nickname}-host-${remote_host_nickname}-port-status-value" \
        "value" "—"
fi

# "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
#     "operation" "update-text-content" \
#     "elementId" "${remote_host_nickname}-status-last-updated-iso8601" \
#     "value" "$(get-iso8601-date)"

# check if MySQL server is up (using mysqladmin)
mysql_server_liveness_check_password="$(get-secret 'mysql_server_liveness_check_password')"
mysql_server_liveness_check_username="$(get-secret 'mysql_server_liveness_check_username')"
thnr_scraper_host_ip="$(get-secret 'thnr_scraper_host_ip')"

if [[ -z "${mysql_server_liveness_check_username}" ]]; then
    log_message="${log_prefix_local} mysqladmin: could not retrieve MySQL username from secrets file"
    echo "${log_message}"
    write-log-message liveness error "${log_message}" false
    exit 1
fi

liveness_check_output=$(mysqladmin \
    --bind-address "${thnr_scraper_host_ip}" \
    --connect-timeout 8 \
    --host "${remote_host_ip}" \
    --no-beep \
    --password="${mysql_server_liveness_check_password}" \
    --port "${remote_host_port_of_interest}" \
    --user "${mysql_server_liveness_check_username}" \
    --verbose \
    ping 2>&1)

# echo ${liveness_check_output}

# success

if [[ "${liveness_check_output}" == *"mysqld is alive"* ]]; then
    log_message="${log_prefix_local} mysqladmin: MySQL server at ${remote_host_ip}:${remote_host_port_of_interest} is up"
    echo "${log_message}"
    write-log-message liveness info "${log_message}" false

    "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
        "timestamps" "$(get-time-in-unix-seconds)" "" \
        "operation" "update-text-content" \
        "elementId" "${remote_host_nickname}-host-status-value" \
        "value" "up"

    "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
        "operation" "update-color" \
        "elementId" "my${remote_host_nickname}sql-host-status-value" \
        "value" "green"

    "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
        "timestamps" "$(get-time-in-unix-seconds)" "" \
        "operation" "update-text-content" \
        "elementId" "${remote_host_nickname}-server-status-value" \
        "value" "up"

    "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
        "operation" "update-color" \
        "elementId" "${remote_host_nickname}-server-status-value" \
        "value" "green"

    "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
        "timestamps" "$(get-time-in-unix-seconds)" "" \
        "operation" "update-text-content" \
        "elementId" "${remote_host_nickname}-status-last-updated-iso8601" \
        "value" "$(get-iso8601-date)"
fi

# mysqladmin can connect to host, but no MySQL server is detected
if [[ "${liveness_check_output}" == *"Can't connect to MySQL server on"* ]]; then
    log_message="${log_prefix_local} mysqladmin: could not connect to a MySQL server at ${remote_host_ip}:${remote_host_port_of_interest}"
    echo "${log_message}"
    write-log-message liveness error "${log_message}" false

    "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
        "timestamps" "$(get-time-in-unix-seconds)" "" \
        "operation" "update-text-content" \
        "elementId" "${remote_host_nickname}-host-status-value" \
        "value" "up"

    "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
        "operation" "update-color" \
        "elementId" "${remote_host_nickname}-host-status-value" \
        "value" "green"

    "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
        "timestamps" "$(get-time-in-unix-seconds)" "" \
        "operation" "update-text-content" \
        "elementId" "${remote_host_nickname}-server-status-value" \
        "value" "down"

    "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
        "operation" "update-color" \
        "elementId" "${remote_host_nickname}-server-status-value" \
        "value" "red"

    # "${project_base_dir}send-dashboard-event-to-kafka2.sh" \
    #     "operation" "update-text-content" \
    #     "elementId" "${remote_host_nickname}-status-last-updated-iso8601" \
    #     "value" "$(get-iso8601-date)"
fi

# # mysqladmin cannot resolve the hostname
# if echo "${liveness_check_output}" | grep "Unknown MySQL server host"; then
#     log_message="${log_prefix_local} mysqladmin: host ${remote_host_ip} could not be resolved"
#     echo "${log_message}"
#     write-log-message liveness error "${log_message}"
# fi

exit 0
