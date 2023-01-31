#!/usr/bin/env bash

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
        return 1
    else
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
done

# we failed 4 times to login, so try rebooting, if we are sudo;
# otherwise exit with error
if ! am_logged_into_vpn_client; then
    if am-root; then
        shutdown -r now
    else
        exit 1
    fi
fi

#
# invariant now: we are logged in
#

if vpn_is_connected; then
    exit 0
fi

# try a few times to connect
for i in 1 2 3 4; do
    try_to_connect_to_vpn
    if vpn_is_connected; then
        exit 0
    fi
    sleep "${seconds_delay_between_attempts}"
done

# try restarting the vpn service
systemctl restart nordvpn
sleep "${seconds_delay_between_attempts}"

# try a few more times to connect
for i in 1 2 3 4; do
    try_to_connect_to_vpn
    if vpn_is_connected; then
        exit 0
    fi
    sleep "${seconds_delay_between_attempts}"
done

# try rebooting, if we are sudo; otherwise exit with error
if am-root; then
    shutdown -r now
else
    exit 1
fi

