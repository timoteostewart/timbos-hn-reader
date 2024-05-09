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

local_host_ip="192.168.1.237"

mysql_hostname="mysql-server.home.arpa"
mysql_host_ip="192.168.1.233"
mysql_port="3306"

# check if host mysql-server.home.arpa is reachable (using nmap)
nmap_tempfile=$(mktemp --tmpdir=/tmp nmap-output-XXXXXXXXXX.xml)

log_message="${log_prefix_local} nmap: writing to temp file ${nmap_tempfile}"
write-log-message mysql info "${log_message}"

# echo "${nmap_tempfile}"
nmap -Pn "${mysql_host_ip}" -oX "${nmap_tempfile}"

hosts_down=$(xmlstarlet sel -t -v "/nmaprun/runstats/hosts/@down" "${nmap_tempfile}")
hosts_up=$(xmlstarlet sel -t -v "/nmaprun/runstats/hosts/@up" "${nmap_tempfile}")
num_ports_conn_refused=$(xmlstarlet sel -t -m "//extrareasons[@reason='conn-refused']" -v "@count" -n "${nmap_tempfile}")
num_ports_host_unreaches=$(xmlstarlet sel -t -m "//extrareasons[@reason='host-unreaches']" -v "@count" -n "${nmap_tempfile}")
num_ports_no_responses=$(xmlstarlet sel -t -m "//extrareasons[@reason='no-responses']" -v "@count" -n "${nmap_tempfile}")
num_ports_resets=$(xmlstarlet sel -t -m "//extrareasons[@reason='resets']" -v "@count" -n "${nmap_tempfile}")
mysql_port_state=$(xmlstarlet sel -t -v "/nmaprun/host/ports/port[@portid=${mysql_port}]/state/@state" "${nmap_tempfile}")

if [[ -z $mysql_port_state ]]; then
    mysql_port_state="unknown"
fi

# echo "hosts_down: ${hosts_down}"
# echo "hosts_up: ${hosts_up}"
# echo "num_ports_conn_refused: ${num_ports_conn_refused}"
# echo "num_ports_host_unreaches: ${num_ports_host_unreaches}"
# echo "num_ports_no_responses: ${num_ports_no_responses}"
# echo "num_ports_resets: ${num_ports_resets}"
# echo "mysql_port_state: ${mysql_port_state}"

case "$hosts_up" in
1)
    log_message="${log_prefix_local} nmap: host ${mysql_host_ip} is reachable, and its port ${mysql_port} is ${mysql_port_state}"
    echo "${log_message}"
    write-log-message mysql info "${log_message}"
    ;;

0)
    log_message="${log_prefix_local} nmap: host ${mysql_host_ip} is not reachable"
    echo "${log_message}"
    write-log-message mysql error "${log_message}"
    ;;

*)
    log_message="${log_prefix_local} nmap: Unexpected value for hosts_up: ${hosts_up}"
    echo "${log_message}"
    write-log-message mysql error "${log_message}"
    ;;
esac

# check if MySQL server is up (using mysqladmin)
# first, retrieve secrets

secrets_file="/srv/timbos-hn-reader/secrets_file.py"
mysql_user=""
mysql_pass=""

# Read each line from the secrets file
while IFS= read -r line; do
    # Extract the username
    if [[ "$line" =~ MYSQL_LIVENESS_CHECK_USERNAME[[:space:]]*=[[:space:]]*\"(.*)\" ]]; then
        mysql_user="${BASH_REMATCH[1]}"
    fi
    # Extract the password
    if [[ "$line" =~ MYSQL_LIVENESS_CHECK_PASSWORD[[:space:]]*=[[:space:]]*\"(.*)\" ]]; then
        mysql_pass="${BASH_REMATCH[1]}"
    fi
done <"${secrets_file}"

if [[ -z $mysql_user ]]; then
    log_message="${log_prefix_local} mysqladmin: could not retrieve MySQL username from secrets file"
    echo "${log_message}"
    write-log-message mysql error "${log_message}"
    exit 1
fi

liveness_check_output=$(mysqladmin \
    --bind-address "${local_host_ip}" \
    --connect-timeout 8 \
    --host "${mysql_host_ip}" \
    --no-beep \
    --password="${mysql_pass}" \
    --port "${mysql_port}" \
    --user "${mysql_user}" \
    --verbose \
    ping 2>&1)

# echo ${liveness_check_output}

# success
if echo "${liveness_check_output}" | grep "mysqld is alive"; then
    log_message="${log_prefix_local} mysqladmin: MySQL server at ${mysql_host_ip}:${mysql_port} is up"
    echo "${log_message}"
    write-log-message mysql info "${log_message}"
    "${project_base_dir}send-dashboard-event-to-kafka.sh" "operation" "update-text-content" "elementId" "mysql-status-value" "value" "up"
    "${project_base_dir}send-dashboard-event-to-kafka.sh" "operation" "update-text-content" "elementId" "mysql-status-timestamp" "value" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
fi

# mysqladmin can connect to host, but no MySQL server is detected
if echo "${liveness_check_output}" | grep "Can't connect to MySQL server on"; then
    log_message="${log_prefix_local} mysqladmin: could not connect to a MySQL server at ${mysql_host_ip}:${mysql_port}"
    echo "${log_message}"
    write-log-message mysql error "${log_message}"
    "${project_base_dir}send-dashboard-event-to-kafka.sh" "operation" "update-text-content" "elementId" "mysql-status-value" "value" "down"
    "${project_base_dir}send-dashboard-event-to-kafka.sh" "operation" "update-text-content" "elementId" "mysql-status-timestamp" "value" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
fi

# # mysqladmin cannot resolve the hostname
# if echo "${liveness_check_output}" | grep "Unknown MySQL server host"; then
#     log_message="${log_prefix_local} mysqladmin: host ${mysql_host_ip} could not be resolved"
#     echo "${log_message}"
#     write-log-message mysql error "${log_message}"
# fi

exit 0
