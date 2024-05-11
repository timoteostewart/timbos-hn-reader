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

# usage: convert-time-in-unix-seconds-to-iso8601 $UNIX_TIME
# returns: formatted ISO8601 date string based on provided Unix time
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

create-nmap-xml() {
    program-not-available nmap && die "nmap is required but is not available"

    local network_identifier="${1}"
    local nmap_xml="${2-}"

    [[ -z "${network_identifier}" ]] && die "create-nmap-xml: not enough arguments\nUsage: create-nmap-xml <network_identifier> [nmap_xml]\n\n"

    # if we're not given an nmap XML file, we create one
    if [[ -z "${nmap_xml}" ]]; then
        nmap_xml=$(mktemp --tmpdir=/tmp nmap-output-XXXXXXXXXX.xml)
        nmap_res=$(nmap -Pn "${network_identifier}" -oX "${nmap_xml}")
    fi

    # confirm the nmap xml file exists
    [[ ! -f "${nmap_xml}" ]] && die "create-nmap-xml: nmap XML file does not exist\n"

    echo "${nmap_xml}"
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

# usage: get-ip-address-for-interface $INTERFACE
# returns: IP address for the specified network interface
get-ip-address-for-interface() {
    local interface="${1}"
    [[ -z "${interface}" ]] && die "get-ip-address-for-interface() requires an interface name to be specified."
    ip_address=$(ip -4 address show "${interface}" | grep --perl-regexp --only-matching "(?<=inet\s)\d+\.\d+\.\d+\.\d+" | head --lines=1)
    [[ -z "${ip_address}" ]] && die "get-ip-address-for-interface() could not determine the IP address for the interface ${interface}."
    printf "${ip_address}"
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

# usage: get-list-of-network-interfaces
# returns: list of active network interfaces excluding loopback
get-list-of-network-interfaces() {
    local interfaces=($(ip link show | grep -v LOOPBACK | awk '/: <BROADCAST,/{print substr($2, 1, length($2)-1)}'))
    for i in "${!interfaces[@]}"; do
        interfaces[$i]=$(echo "${interfaces[$i]}" | sed 's/@.*//')
    done
    echo ${interfaces[@]}
}

get-port-state() {
    program-not-available nmap && die "nmap is required but is not available"

    local network_identifier="${1}"
    local port_of_interest="${2}"
    local nmap_xml="${3-}"

    [[ -z "${network_identifier}" ]] && die "get-port-state: not enough arguments
    Usage: get-port-state <network_identifier> <port_of_interest> [nmap_xml]
    "
    [[ -z "${port_of_interest}" ]] && die "get-port-state: not enough arguments
    Usage: get-port-state <network_identifier> <port_of_interest> [nmap_xml]
    "

    # if we're not given an nmap XML file, we create one
    if [[ -z "${nmap_xml}" ]]; then
        nmap_xml="$(create-nmap-xml "${network_identifier}")"
    fi

    # confirm the nmap xml file exists
    [[ ! -f "${nmap_xml}" ]] && die "is-host-reachable: nmap XML file does not exist\n"

    hosts_up=$(xmlstarlet sel -t -v "/nmaprun/runstats/hosts/@up" "${nmap_xml}")
    port_state=$(xmlstarlet sel -t -v "/nmaprun/host/ports/port[@portid=${port_of_interest}]/state/@state" "${nmap_xml}")

    case "${hosts_up}" in
    1)
        port_state=$(xmlstarlet sel -t -v "/nmaprun/host/ports/port[@portid=${port_of_interest}]/state/@state" "${nmap_xml}")
        [[ -z "${port_state}" ]] && port_state="no-response"
        echo "${port_state}"
        ;;
    0)
        echo "host-not-reachable"
        ;;
    *)
        echo "failure-condition"
        ;;
    esac
}

# usage: get-time-in-unix-seconds
get-time-in-unix-seconds() {
    printf $(date --utc +%s)
}

is-host-reachable() {
    program-not-available nmap && die "nmap is required but is not available"

    local network_identifier="${1}"
    local nmap_xml="${2-}"

    [[ -z "${network_identifier}" ]] && die "is-host-reachable: not enough arguments
    Usage: is_host_reachable <network_identifier> [nmap_xml]
    "

    # if we're not given an nmap XML file, we create one
    if [[ -z "${nmap_xml}" ]]; then
        nmap_xml="$(create-nmap-xml "${network_identifier}")"
    fi

    # confirm the nmap xml file exists
    [[ ! -f "${nmap_xml}" ]] && die "is-host-reachable: nmap XML file does not exist\n"

    # hosts_down=$(xmlstarlet sel -t -v "/nmaprun/runstats/hosts/@down" "${nmap_xml}")
    hosts_up=$(xmlstarlet sel -t -v "/nmaprun/runstats/hosts/@up" "${nmap_xml}")
    # num_ports_conn_refused=$(xmlstarlet sel -t -m "//extrareasons[@reason='conn-refused']" -v "@count" -n "${nmap_xml}")
    # num_ports_host_unreaches=$(xmlstarlet sel -t -m "//extrareasons[@reason='host-unreaches']" -v "@count" -n "${nmap_xml}")
    # num_ports_no_responses=$(xmlstarlet sel -t -m "//extrareasons[@reason='no-responses']" -v "@count" -n "${nmap_xml}")
    # num_ports_resets=$(xmlstarlet sel -t -m "//extrareasons[@reason='resets']" -v "@count" -n "${nmap_xml}")
    # port_of_interest_state=$(xmlstarlet sel -t -v "/nmaprun/host/ports/port[@portid=${port_of_interest}]/state/@state" "${nmap_xml}")

    if [[ "${hosts_up}" == "1" ]]; then
        echo "true"
    elif [[ "${hosts_up}" == "0" ]]; then
        echo "false"
    else
        echo "failure-condition"
    fi

}

# usage: make-beep
make-beep() {
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

prettify-duration-seconds() {
    local total_seconds=${1}
    local weeks=$((total_seconds / 604800))
    local days=$((total_seconds % 604800 / 86400))
    local hours=$((total_seconds % 86400 / 3600))
    local minutes=$((total_seconds % 3600 / 60))
    local seconds=$((total_seconds % 60))

    local result=""
    [[ ${weeks} -gt 0 ]] && result+="${weeks} weeks "
    [[ ${days} -gt 0 ]] && result+="${days} days "
    [[ ${hours} -gt 0 ]] && result+="${hours} hours "
    [[ ${minutes} -gt 0 ]] && result+="${minutes} minutes "
    [[ ${seconds} -gt 0 ]] && result+="${seconds} seconds "

    echo ${result}
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

# usage: source-if-exists $FILE
# returns: sources the file if it exists, prints error and returns 1 if it doesn't
source-if-exists() {
    local file=$1
    if [[ -f "${file}" ]]; then
        source "${file}"
    else
        printf >&2 "Error: Could not find '%s'.\n" "$file"
        return 1
    fi
}

# usage: trim_string $STRING
# returns: trimmed string with leading and trailing whitespace removed
trim_string() {
    local input=$1
    # Remove leading whitespace
    input="${input#"${input%%[![:space:]]*}"}"
    # Remove trailing whitespace
    input="${input%"${input##*[![:space:]]}"}"
    printf "${input}"
}
