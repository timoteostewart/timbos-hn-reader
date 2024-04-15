#!/bin/bash

count-network-interfaces() {
    local broadcast_interfaces=($(get-list-of-network-interfaces))
    IFS=' ' read -r -a broadcast_interfaces <<<"$(get-list-of-network-interfaces)"
    echo "${#broadcast_interfaces[@]}"
}

get-list-of-network-interfaces() {
    local interfaces=($(ip link show | grep -v LOOPBACK | awk '/: <BROADCAST,/{print substr($2, 1, length($2)-1)}'))

    for i in "${!interfaces[@]}"; do
        interfaces[$i]=$(echo "${interfaces[$i]}" | sed 's/@.*//')
    done

    echo ${interfaces[@]}
}

interfaces=$(get-list-of-network-interfaces)

if [[ ${interfaces} == *"eth0"* ]] && [[ ${interfaces} == *"eth1"* ]]; then
    echo "both eth0 and eth1 given"
fi
