#!/usr/bin/env bash

# debugging switches
# set -o errexit  # abort on nonzero exit status; same as set -e
# set -o nounset  # abort on unbound variable; same as set -u
# set -o pipefail # don't hide errors within pipes
# set -o xtrace   # show commands being executed; same as set -x
# set -o verbose  # verbose mode; same as set -v

# usage: see locals below
add-deb-repo() {
    # Check for missing parameters
    [[ -z "${1}" ]] && die "add-deb-repo() requires a key_url to be specified."
    [[ -z "${2}" ]] && die "add-deb-repo() requires a repo_url to be specified."
    [[ -z "${3}" ]] && die "add-deb-repo() requires a distro to be specified."
    [[ -z "${4}" ]] && die "add-deb-repo() requires a component to be specified."
    [[ -z "${5}" ]] && die "add-deb-repo() requires a label to be specified."

    local key_url="${1}"
    local repo_url="${2}"
    local distro="${3}"
    local component="${4}"
    local label="${5}"
    local keyring="/usr/share/keyrings/${label}-keyring.gpg"
    local sources="/etc/apt/sources.list.d/${label}.list"

    curl --fail --location --silent --show-error --url "${key_url}" | gpg --dearmor | dd of="${keyring}"
    chmod 644 "${keyring}"
    printf "deb [arch=$(dpkg --print-architecture) signed-by=${keyring}] ${repo_url} ${distro} ${component}\n" | tee "${sources}" >/dev/null
}

# usage: am-root
# returns 0 if root, 1 if not root
am-root() {
    local EUID_copy="${EUID:-$(id -u)}"
    [[ -z "${EUID_copy}" ]] && die "am-root() could not determine the current user's EUID."
    ((EUID_copy == 0))
}

# usage: cd-or-die $DIRECTORY
cd-or-die() {
    [[ -z "${1}" ]] && die "cd-or-die() requires a directory to be specified."
    [[ ! -d "${1}" ]] && die "The path ${1} is not a directory."
    cd "${1}" || die "Could not cd to ${1}."
}

convert-time-in-unix-seconds-to-iso8601() {
    local unix_time="${1}"
    [[ -z "${unix_time}" ]] && die "convert-time-in-unix-seconds-to-iso8601() requires a Unix time to be specified."
    date --utc +"%Y-%m-%dT%H:%M:%SZ" --date="@${unix_time}"
}

# usage: count-network-interfaces
# returns: the number of network interfaces, excluding the loopback interface
count-network-interfaces() {
    local broadcast_interfaces=($(get-list-of-network-interfaces))
    IFS=' ' read -r -a broadcast_interfaces <<<"$(get-list-of-network-interfaces)"
    echo "${#broadcast_interfaces[@]}"
}

# usage: die "$MESSAGE" ["$EXIT_CODE"]
die() {
    local message="${1:-Unspecified Error}"
    local exit_code="${2:-1}"
    printf >&2 "Error: %s\nAn unrecoverable error has occurred. Look above for any error messages.\n" "${message}"
    exit "${exit_code}"
}

# usage: die-if-file-not-present $FILENAME_WITH_PATH ["$MESSAGE"]
die-if-file-not-present() {
    [[ -z "${1}" ]] && die "die-if-file-not-present() requires a filename to be specified."
    local filename="${1}"
    local message="${2:-File ${filename} not found.}"
    [[ -f "${filename}" ]] || die "${message}"
}

# usage: die-if-not-root
die-if-not-root() {
    am-root || die "Please run this script as root (e.g., using ‘sudo’)."
}

# usage: die-if-root
die-if-root() {
    am-root && die "Please run this script as a non-root user (e.g., not as root, not using ‘sudo’)."
}

# usage: die-if-program-not-available $PROGRAM_NAME "$MESSAGE"
die-if-program-not-available() {
    program-not-available "${1}" && die "${2}"
    return 0
}

# usage: ensure-dir-or-die "$DIRECTORY"
ensure-dir-or-die() {
    [[ -z "${1}" ]] && die "ensure-dir-or-die() requires a directory to be specified."
    local dir="${1}"
    mkdir --parents "$dir" || die "Could not create directory ${dir}."
}

# usage: ensure-file-or-die "$FILE"
ensure-file-or-die() {
    [[ -z "${1}" ]] && die "ensure-file-or-die() requires a file to be specified."
    local file="${1}"
    touch "${file}" || die "Could not create file ${file}."
}

# usage: get-iso8601-date
get-iso8601-date() {
    printf $(date --utc +"%Y-%m-%dT%H:%M:%SZ")
}

# usage: get-iso8601-date-microseconds
get-iso8601-date-microseconds() {
    printf $(date --utc +"%Y-%m-%dT%H:%M:%S.%6NZ")
}

# usage: get-iso8601-date-milliseconds
get-iso8601-date-milliseconds() {
    printf $(date --utc +"%Y-%m-%dT%H:%M:%S.%3NZ")
}

get-list-of-network-interfaces() {
    local interfaces=($(ip link show | grep -v LOOPBACK | awk '/: <BROADCAST,/{print substr($2, 1, length($2)-1)}'))
    for i in "${!interfaces[@]}"; do
        interfaces[$i]=$(echo "${interfaces[$i]}" | sed 's/@.*//')
    done
    echo ${interfaces[@]}
}

# usage: get-time-in-unix-seconds
get-time-in-unix-seconds() {
    printf $(date --utc +%s)
}

# usage: make-beep
make_beep() {
    printf "\a"
}

# usage: prefer $INTERFACE_NAME
# example: prefer eth0
# returns 0 if successful, 1 if not successful
prefer() {

    die-if-not-root

    preferred_network_name="${1}"

    if [[ -z "${preferred_network_name}" ]]; then
        printf "Argument must be eth0 or eth1.\n"
        exit 1
    fi

    if [[ "$1" != "eth0" ]] && [[ "$1" != "eth1" ]]; then
        printf "Argument must be eth0 or eth1.\n"
        exit 1
    fi

    is-ip-address-reachable() {
        local ip_address="${1}"
        if ping -c 4 -q "${ip_address}" >/dev/null; then
            return 0
        else
            return 1
        fi
    }

    update-metric-for-interface() {
        local gateway_address="${1}"
        local interface_name="${2}"
        local metric="${3}"
        ip route del default via "${gateway_address}" dev "${interface_name}"
        ip route add default via "${gateway_address}" dev "${interface_name}" metric "${metric}"
    }

    make_preferred() {
        local primary_interface="${1}"

        if [[ "${primary_interface}" == "eth0" ]]; then
            local primary_gateway="192.168.1.1"
            local secondary_interface="eth1"
            local secondary_gateway="192.168.2.254"
        fi
        if [[ "${primary_interface}" == "eth1" ]]; then
            local primary_gateway="192.168.2.254"
            local secondary_interface="eth0"
            local secondary_gateway="192.168.1.1"
        fi

        update-metric-for-interface "${primary_gateway}" "${primary_interface}" 1000
        # higher number means lower priority
        update-metric-for-interface "${secondary_gateway}" "${secondary_interface}" 1024

    }

    # Define an array of IP addresses
    ip_addresses=("192.168.1.1" "192.168.2.254")

    # Loop through each IP address in the array
    for ip in "${ip_addresses[@]}"; do
        if ! is-ip-address-reachable "${ip}"; then
            printf "%s not reachable!\n" "${ip}"
            exit 1
        fi
    done

    sleep 4

    make_preferred "${preferred_network_name}"

    wan_ip=$(curl --silent icanhazip.com)
    printf "preferred interface: ${preferred_network_name}\n"
    printf "wan_ip=${wan_ip}\n"
}

# usage: program-not-available $PROGRAM_NAME
# returns 0 if program isn't available, 1 if program is available
program-not-available() {
    [[ -z "${1}" ]] && die "program-not-available() requires a program to be specified."
    program-available "${1}" && return 1
    return 0
}

# usage: program-available $PROGRAM_NAME
# returns 0 if the program is available, 1 otherwise.
program-available() {
    [[ -z "${1}" ]] && die "program-available() requires a program to be specified."
    command -v "${1}" >/dev/null 2>&1 || return 1
    return 0
}

source-if-exists() {
    local file=$1
    if [[ -f "${file}" ]]; then
        source "${file}"
    else
        printf >&2 "Error: Could not find '%s'.\n" "$file"
        return 1
    fi
}

trim_string() {
    local input=$1
    # Remove leading whitespace
    input="${input#"${input%%[![:space:]]*}"}"
    # Remove trailing whitespace
    input="${input%"${input##*[![:space:]]}"}"
    printf "${input}"
}
