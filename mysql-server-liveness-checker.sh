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

mysql_server_host_ip="$(get-secret 'mysql_server_host_ip')"
mysql_server_hostname="$(get-secret 'mysql_server_hostname')"
mysql_server_liveness_check_password="$(get-secret 'mysql_server_liveness_check_password')"
mysql_server_liveness_check_username="$(get-secret 'mysql_server_liveness_check_username')"
mysql_server_port="$(get-secret 'mysql_server_port')"
thnr_scraper_host_ip="$(get-secret 'thnr_scraper_host_ip')"

# check if host mysql-server.home.arpa is reachable (using nmap)
nmap_tempfile=$(mktemp --tmpdir=/tmp nmap-output-XXXXXXXXXX.xml)

log_message="${log_prefix_local} nmap: writing to temp file ${nmap_tempfile}"
write-log-message mysql info "${log_message}" false

# echo "${nmap_tempfile}"
nmap -Pn "${mysql_server_host_ip}" -oX "${nmap_tempfile}"

hosts_down=$(xmlstarlet sel -t -v "/nmaprun/runstats/hosts/@down" "${nmap_tempfile}")
hosts_up=$(xmlstarlet sel -t -v "/nmaprun/runstats/hosts/@up" "${nmap_tempfile}")
num_ports_conn_refused=$(xmlstarlet sel -t -m "//extrareasons[@reason='conn-refused']" -v "@count" -n "${nmap_tempfile}")
num_ports_host_unreaches=$(xmlstarlet sel -t -m "//extrareasons[@reason='host-unreaches']" -v "@count" -n "${nmap_tempfile}")
num_ports_no_responses=$(xmlstarlet sel -t -m "//extrareasons[@reason='no-responses']" -v "@count" -n "${nmap_tempfile}")
num_ports_resets=$(xmlstarlet sel -t -m "//extrareasons[@reason='resets']" -v "@count" -n "${nmap_tempfile}")
mysql_server_port_state=$(xmlstarlet sel -t -v "/nmaprun/host/ports/port[@portid=${mysql_server_port}]/state/@state" "${nmap_tempfile}")

if [[ -z "${mysql_server_port_state}" ]]; then
    mysql_server_port_state="unknown"
fi

# echo "hosts_down: ${hosts_down}"
# echo "hosts_up: ${hosts_up}"
# echo "num_ports_conn_refused: ${num_ports_conn_refused}"
# echo "num_ports_host_unreaches: ${num_ports_host_unreaches}"
# echo "num_ports_no_responses: ${num_ports_no_responses}"
# echo "num_ports_resets: ${num_ports_resets}"
# echo "mysql_server_port_state: ${mysql_server_port_state}"

case "${hosts_up}" in
1)
    log_message="${log_prefix_local} nmap: host ${mysql_server_host_ip} is reachable, and its port ${mysql_server_port} is ${mysql_server_port_state}"
    echo "${log_message}"
    write-log-message mysql info "${log_message}" false

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "mysql-host-status-value" \
        "value" "up"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-color" \
        "elementId" "mysql-host-status-value" \
        "value" "green"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "mysql-host-mysql-port-status-value" \
        "value" "${mysql_server_port_state}"

    if [[ "${mysql_server_port_state}" == "open" ]]; then
        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-color" \
            "elementId" "mysql-host-mysql-port-status-value" \
            "value" "green"
    else
        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-color" \
            "elementId" "mysql-host-mysql-port-status-value" \
            "value" "red"
    fi

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "mysql-status-last-updated-iso8601" \
        "value" "$(get-iso8601-date)"

    ;;

0)
    log_message="${log_prefix_local} nmap: host ${mysql_server_host_ip} is not reachable"
    echo "${log_message}"
    write-log-message mysql error "${log_message}" false

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "mysql-host-status-value" \
        "value" "down"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-color" \
        "elementId" "mysql-host-status-value" \
        "value" "red"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "mysql-host-mysql-port-status-value" \
        "value" "—"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "mysql-status-last-updated-iso8601" \
        "value" "$(get-iso8601-date)"

    ;;

*)
    log_message="${log_prefix_local} nmap: Unexpected value for hosts_up: ${hosts_up}"
    echo "${log_message}"
    write-log-message mysql error "${log_message}" false
    ;;
esac

# check if MySQL server is up (using mysqladmin)
if [[ -z "${mysql_server_liveness_check_username}" ]]; then
    log_message="${log_prefix_local} mysqladmin: could not retrieve MySQL username from secrets file"
    echo "${log_message}"
    write-log-message mysql error "${log_message}" false
    exit 1
fi

liveness_check_output=$(mysqladmin \
    --bind-address "${thnr_scraper_host_ip}" \
    --connect-timeout 8 \
    --host "${mysql_server_host_ip}" \
    --no-beep \
    --password="${mysql_server_liveness_check_password}" \
    --port "${mysql_server_port}" \
    --user "${mysql_server_liveness_check_username}" \
    --verbose \
    ping 2>&1)

# echo ${liveness_check_output}

# success
if echo "${liveness_check_output}" | grep "mysqld is alive"; then
    log_message="${log_prefix_local} mysqladmin: MySQL server at ${mysql_server_host_ip}:${mysql_server_port} is up"
    echo "${log_message}"
    write-log-message mysql info "${log_message}" false

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "mysql-status-value" \
        "value" "up"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-color" \
        "elementId" "mysql-status-value" \
        "value" "green"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "mysql-status-last-updated-iso8601" \
        "value" "$(get-iso8601-date)"
fi

# mysqladmin can connect to host, but no MySQL server is detected
if echo "${liveness_check_output}" | grep "Can't connect to MySQL server on"; then
    log_message="${log_prefix_local} mysqladmin: could not connect to a MySQL server at ${mysql_server_host_ip}:${mysql_server_port}"
    echo "${log_message}"
    write-log-message mysql error "${log_message}" false

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "mysql-host-status-value" \
        "value" "up"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-color" \
        "elementId" "mysql-host-status-value" \
        "value" "green"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "mysql-status-value" \
        "value" "down"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-color" \
        "elementId" "mysql-status-value" \
        "value" "red"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "mysql-status-last-updated-iso8601" \
        "value" "$(get-iso8601-date)"
fi

# # mysqladmin cannot resolve the hostname
# if echo "${liveness_check_output}" | grep "Unknown MySQL server host"; then
#     log_message="${log_prefix_local} mysqladmin: host ${mysql_server_host_ip} could not be resolved"
#     echo "${log_message}"
#     write-log-message mysql error "${log_message}"
# fi

exit 0
