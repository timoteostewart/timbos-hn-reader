#!/usr/bin/env bash

# debugging switches
# set -o errexit   # abort on nonzero exitstatus; same as set -e
# set -o nounset   # abort on unbound variable; same as set -u
set -o pipefail # don't hide errors within pipes
# set -o xtrace    # show commands being executed; same as set -x
# set -o verbose   # verbose mode; same as set -v

source /srv/timbos-hn-reader/functions.sh
source /srv/timbos-hn-reader/thnr-common-functions.sh

project_base_dir="/srv/timbos-hn-reader/"
all_logs_dir="${project_base_dir}logs/"
combined_log_identifier="combined"
server_name=thnr
TZ=UTC
utility_account_username=tim
log_prefix_local="connect-to-vpn.sh:"

# more settings
seconds_delay_between_login_attempts=16

am-logged-into-vpn-client() {
    vpn_account_status=$(nordvpn account)
    if [[ "${vpn_account_status}" == *"You are not logged in."* ]]; then
        return 1
    else
        return 0
    fi
}

log-in-to-vpn-client() {
    login_token=$(cat /srv/timbos-hn-reader/secret_vpn_token.txt)
    nordvpn login --token "${login_token}"
}

try-to-connect-to-vpn() {
    nordvpn connect
}

vpn-is-connected() {
    vpn_connection_status=$(nordvpn status)
    # possible results of `nordvpn status`:
    # Status: Connected
    # Status: Disconnected

    if [[ "${vpn_connection_status}" == *"Status: Connected"* ]]; then
        vpn_hostname=$(echo "${vpn_connection_status}" | grep 'Hostname:' | cut -d ' ' -f 2-)
        vpn_ip_address=$(echo "${vpn_connection_status}" | grep 'IP:' | cut -d ' ' -f 2)
        vpn_country=$(echo "${vpn_connection_status}" | grep 'Country:' | cut -d ' ' -f 2-)
        vpn_city=$(echo "${vpn_connection_status}" | grep 'City:' | cut -d ' ' -f 2-)
        vpn_technology=$(echo "${vpn_connection_status}" | grep 'Current technology:' | cut -d ' ' -f 3-)
        vpn_protocol=$(echo "${vpn_connection_status}" | grep 'Current protocol: ' | cut -d ' ' -f 3-)
        vpn_transfer=$(echo "${vpn_connection_status}" | grep 'Transfer:' | cut -d ' ' -f 2-)
        vpn_uptime=$(echo "${vpn_connection_status}" | grep 'Uptime: ' | cut -d ' ' -f 2-)

        write-log-message vpn info "${log_prefix_local} VPN is connected. Hostname: ${vpn_hostname}, IP: ${vpn_ip_address}, Country: ${vpn_country}, City: ${vpn_city}, Technology: ${vpn_technology}, Protocol: ${vpn_protocol}, Transfer: ${vpn_transfer}, Uptime: ${vpn_uptime}"

        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-text-content" \
            "elementId" "vpn-status-value" \
            "value" "connected"

        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-text-content" \
            "elementId" "vpn-uptime-seconds" \
            "value" "${vpn_uptime}"

        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-text-content" \
            "elementId" "vpn-transfer" \
            "value" "${vpn_transfer}"

        cur_ts=$(get-time-in-unix-seconds)

        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-text-content" \
            "elementId" "vpn-last-updated-timestamp" \
            "value" "${cur_ts}"

        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-text-content" \
            "elementId" "vpn-last-updated-iso8601" \
            "value" "$(convert-time-in-unix-seconds-to-iso8601 ${cur_ts})"

        return 0
    else
        write-log-message vpn info "${log_prefix_local} VPN is not connected."

        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-text-content" \
            "elementId" "vpn-status-value" \
            "value" "not connected"

        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-text-content" \
            "elementId" "vpn-uptime-seconds" \
            "value" "—"

        cur_ts=$(get-time-in-unix-seconds)

        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-text-content" \
            "elementId" "vpn-last-updated-timestamp" \
            "value" "${cur_ts}"

        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-text-content" \
            "elementId" "vpn-last-updated-iso8601" \
            "value" "$(convert-time-in-unix-seconds-to-iso8601 ${cur_ts})"

        return 1
    fi
}

# try a few times to login (we might be already)
cur_delay=${seconds_delay_between_login_attempts}
for i in 1 2 3 4 5 6 7 8; do
    if am-logged-into-vpn-client; then
        break
    else
        log-in-to-vpn-client
    fi
    write-log-message vpn info "${log_prefix_local} sleeping for ${cur_delay} seconds"
    sleep "${cur_delay}"
    ((cur_delay *= 2))
done

# check whether we're logged into the vpn account.
# if we're not, reboot if we're sudo, exit with error otherwise
if ! am-logged-into-vpn-client; then
    write-log-message vpn info "${log_prefix_local} still not logged in. sleeping 5 minutes, and then restarting host."
    sleep 300 && shutdown -r now && sleep 60
fi

#
# invariant now: we are logged into the vpn account.
# (we are not necessarily connected to the vpn though.)
#

nordvpn set autoconnect enabled
nordvpn set cybersec disabled
nordvpn set dns 192.168.1.59
nordvpn set firewall disabled
# nordvpn set killswitch disabled  # requires firewall to be enabled
nordvpn set lan-discovery disabled
# nordvpn set obfuscate disabled  # requires OpenVPN to be enabled
nordvpn set routing enabled
nordvpn set technology nordlynx
nordvpn whitelist add port 22
nordvpn whitelist add subnet 192.168.1.1/24

if vpn-is-connected; then
    exit 0
fi

# try a few times to connect
cur_delay=${seconds_delay_between_login_attempts}
for i in 1 2 3 4 5 6 7 8; do
    try-to-connect-to-vpn
    if vpn-is-connected; then
        exit 0
    fi
    write-log-message vpn info "${log_prefix_local} sleeping for ${cur_delay} seconds"
    sleep "${cur_delay}"
    ((cur_delay *= 2))
done

#
# invariant now: we are still not connected to the vpn
#

# try restarting the vpn service
cur_delay=${seconds_delay_between_login_attempts}
write-log-message vpn info "${log_prefix_local} restarting nordvpn service"
systemctl restart nordvpn
write-log-message vpn info "${log_prefix_local} sleeping for ${cur_delay} seconds"
sleep "${cur_delay}"

# try a few more times to connect
for i in 1 2 3 4 5 6 7 8; do
    try-to-connect-to-vpn
    if vpn-is-connected; then
        exit 0
    fi
    write-log-message vpn info "${log_prefix_local} sleeping for ${cur_delay} seconds"
    sleep "${cur_delay}"
    ((cur_delay *= 2))
done

# we've tried just about everything. let's wait 5 minutes and reboot.
write-log-message vpn info "${log_prefix_local} sleeping 5 minutes, and then restarting host."
sleep 300 && shutdown -r now && sleep 60
