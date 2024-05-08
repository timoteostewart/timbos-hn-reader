#!/usr/bin/env bash

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

# usage: die "$MESSAGE" ["$EXIT_CODE"]
die() {
    local message="${1:-Unspecified Error}"
    local exit_code="${2:-1}"
    printf >&2 "Error: ${message}\nAn unrecoverable error has occurred. Look above for any error messages.\n"
    exit "$exit_code"
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
    mkdir -p "$dir" || die "Could not create directory ${dir}."
}

# usage: get-iso8601-date
get-iso8601-date() {
    printf $(date -u +"%Y-%m-%dT%H:%M:%SZ")
}

# usage: get-iso8601-date-microseconds
get-iso8601-date-microseconds() {
    printf $(date -u +"%Y-%m-%dT%H:%M:%S.%6NZ")
}

# usage: get-iso8601-date-milliseconds
get-iso8601-date-milliseconds() {
    printf $(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")
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
    printf '%(%s)T\n' -1
}

# usage: make-beep
make_beep() {
    printf "\a"
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

trim_string() {
    local input=$1
    # Remove leading whitespace
    input="${input#"${input%%[![:space:]]*}"}"
    # Remove trailing whitespace
    input="${input%"${input##*[![:space:]]}"}"
    echo "$input"
}
