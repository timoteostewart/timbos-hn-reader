#!/usr/bin/env bash

# TODO: also output these VPN logs to thnr-vpn...log as well as thnr-combined...log

CUR_YEAR=$(printf '%(%Y)T' -1)
CUR_DOY=$(printf '%(%j)T' -1)
CUR_DOY_ZEROS="00${CUR_DOY}"
CUR_DOY_PADDED="${CUR_DOY_ZEROS: -3}"
CUR_YEAR_AND_DOY="${CUR_YEAR}-${CUR_DOY_PADDED}"


SERVER_NAME=thnr
UTILITY_ACCOUNT_USERNAME=tim
BASE_DIR=/srv/timbos-hn-reader/
LOG_FILES_PATH="${BASE_DIR}/logs/"
VPN_LOG_FILE="${LOG_FILES_PATH}${SERVER_NAME}-vpn-${CUR_YEAR_AND_DOY}.log"

vpn_log_message() {
	LEVEL="$1"
	MESSAGE="$2"
	CUR_DATETIME=$(printf '%(%Y-%m-%d %H:%M:%S %Z)T' -1)
	LOG_LINE="${CUR_DATETIME} ${LEVEL^^} ${MESSAGE}"
    # LOG_FILE="${LOOP_LOG_PATH}${SERVER_NAME}-vpn-${CUR_YEAR_AND_DOY}.log"

    if (( ${EUID:-$(id -u)} == 0 )); then
        sudo -u ${UTILITY_ACCOUNT_USERNAME} printf -- "${LOG_LINE}\n" >> "${VPN_LOG_FILE}"
    else
        printf -- "${LOG_LINE}\n" >> "${VPN_LOG_FILE}"
    fi
}

am-root() {
    if (( ${EUID:-$(id -u)} != 0 )); then
        return 1
    else
        return 0
    fi
}

am_logged_into_vpn_client() {
    vpn_account_status=$(nordvpn account)
    if [[ "${vpn_account_status}" == *"You are not logged in."* ]]; then
        return 1
    else
        return 0
    fi
}

login_to_vpn_client() {
    login_token=$(cat /srv/timbos-hn-reader/vpn_token.txt)
    nordvpn login --token "${login_token}"
}

vpn_is_connected() {
    vpn_status=$(nordvpn status)
    if [[ "${vpn_status}" == *"Status: Disconnected"* ]]; then
        vpn_log_message info "VPN is not connected."
        return 1
    else
        vpn_log_message info "VPN is connected."
        return 0
    fi
}

try_to_connect_to_vpn() {
    nordvpn connect
}

# settings
seconds_delay_between_attempts=10

# try a few times to login (we might be already)
for i in 1 2 3 4; do
    if am_logged_into_vpn_client; then
        break
    else
        login_to_vpn_client
    fi
    sleep "${seconds_delay_between_attempts}"
    (( seconds_delay_between_attempts *= 2 ))
done

# check whether we're logged into the vpn.
# if we're not, reboot if we're sudo, exit with error otherwise
if ! am_logged_into_vpn_client; then
    if am-root; then
        vpn_log_message info "Shutting down now."
        shutdown -r now
    else
        exit 1
    fi
fi

#
# invariant now: we are logged into the vpn.
# (we are not necessarily connected to the vpn though.)
#

if vpn_is_connected; then
    vpn_log_message info "VPN is connected."
    exit 0
fi

seconds_delay_between_attempts=10

# try a few times to connect
for i in 1 2 3 4; do
    try_to_connect_to_vpn
    if vpn_is_connected; then
        exit 0
    fi
    sleep "${seconds_delay_between_attempts}"
    (( seconds_delay_between_attempts *= 2 ))
done

#
# invariant now: we are still not connected to the vpn
#

# try restarting the vpn service
seconds_delay_between_attempts=10
systemctl restart nordvpn
sleep "${seconds_delay_between_attempts}"

# try a few more times to connect
for i in 1 2 3 4; do
    try_to_connect_to_vpn
    if vpn_is_connected; then
        exit 0
    fi
    sleep "${seconds_delay_between_attempts}"
    (( seconds_delay_between_attempts *= 2 ))
done

# we've tried just about everything. let's reboot.
if am-root; then
    shutdown -r now
else
    exit 1
fi
