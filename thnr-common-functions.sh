#!/usr/bin/env bash

# debugging switches
# set -o errexit   # abort on nonzero exitstatus; same as set -e
# set -o nounset   # abort on unbound variable; same as set -u
# set -o pipefail  # don't hide errors within pipes
# set -o xtrace    # show commands being executed; same as set -x
# set -o verbose   # verbose mode; same as set -v

source /srv/timbos-hn-reader/functions.sh

# usage: ensure-correct-file-owner $file
# ensures the specified file is owned by the utility account user; requires root privileges
# returns: 0 if operation successful, 1 otherwise
ensure-correct-file-owner() {
    if ! am-root; then
        return 1
    fi

    local file="${1}"
    [[ -z "${file}" ]] && die "ensure-correct-file-owner() requires a file to be specified."

    if [[ ! -f "${file}" ]]; then
        sudo -u ${utility_account_username} touch "${file}"
    fi

    local CUR_file_OWNER=$(stat -c '%U' "${file}")
    if [[ "${CUR_file_OWNER}" != "${utility_account_username}" ]]; then
        chown ${utility_account_username}:${utility_account_username} "${file}"
    fi
}

get-cur-year-and-doy() {
    TZ=UTC
    local cur_year=$(date --utc +"%Y")
    local cur_doy=$(date --utc +"%j")
    local cur_doy_zeros="00${cur_doy}"
    local cur_doy_padded="${cur_doy_zeros: -3}"
    local cur_year_and_doy="${cur_year}-${cur_doy_padded}"
    echo "${cur_year_and_doy}"
}

# usage: get-last-filename $pattern
# returns: the last filename matched by the specified glob pattern
get-last-filename() {
    local pattern="${1}"
    local last_file=""
    for file in $pattern; do
        if [ -f "$file" ]; then
            last_file="$file"
        fi
    done
    echo "$last_file"
}

# usage: get-secret $KEY
# This function retrieves a secret value associated with the given key from a secrets file. The key must match exactly
# and the expected format in the secrets file is 'key = "value"'. If the key is not provided or not found, the function
# logs an error message and exits with a status of 1.
# returns: Outputs the value associated with the key. Exits with status 1 if the key is not provided or not found.
get-secret() {
    secrets_file="/srv/timbos-hn-reader/secrets_file.py"
    local key_provided="${1-}"
    if [[ -z "${key_provided}" ]]; then
        log_message="${log_prefix_local} get-secret.sh: no key provided"
        write-log-message get-secret error "${log_message}" false
        exit 1
    fi

    local pattern="^${key_provided}[[:space:]]*=[[:space:]]*\"(.*)\""
    local value_returned=$(grep -oP "${pattern}" "${secrets_file}" | cut -d'"' -f2)

    if [[ -z "${value_returned}" ]]; then
        exit 1
    fi

    echo "${value_returned}"

}

# usage: get-sha1-of-current-time
# returns: SHA1 hash of the current Unix timestamp, truncated to 12 characters
get-sha1-of-current-time() {
    local current_time=$(date --utc +%s)
    echo -n "$current_time" | sha1sum | cut -c 1-12
}

# usage: get-sha1-of-current-time-plus-random
# returns: SHA1 hash of the current Unix timestamp plus a random salt, truncated to 12 characters
get-sha1-of-current-time-plus-random() {
    local cur_time=$(date --utc +%s)
    local salt=$(($RANDOM * 32768 + $RANDOM))
    ((value_to_hash = cur_time + salt))
    echo -n "${value_to_hash}" | sha1sum | cut -c 1-12
}

# usage: write-log-message $log_identifier $level $message [$write_to_combined_log_flag]
# writes a log message to a specific log file and optionally to a combined log file
# example: write-log-message loop error "${LOG_PREFIX_LOCAL} Failed to delete ${file}"
# example: write-log-message loop info "${LOG_PREFIX_LOCAL} ${min_pings} or more pings succeeded. Continuing."
write-log-message() {
    local cur_year_and_doy=$(get-cur-year-and-doy)
    local log_identifier="${1}"
    local write_to_combined_log_flag="${4}"

    if [[ -z "${write_to_combined_log_flag}" ]]; then
        write_to_combined_log_flag="true"
    fi

    local level="$2"
    local message="$3"
    local log_line=$(printf "%s           %-8s %s" "$(get-iso8601-date-milliseconds)" "${level^^}" "${message}")

    local specific_log_file="${all_logs_dir}${server_name}-${log_identifier}-${cur_year_and_doy}.log"
    ensure-correct-file-owner "${specific_log_file}"
    sudo -u "${utility_account_username}" printf -- "${log_line}\n" >>"${specific_log_file}"

    if [[ "${write_to_combined_log_flag}" == "true" ]]; then
        local combined_log_file="${all_logs_dir}${server_name}-${combined_log_identifier}-${cur_year_and_doy}.log"
        ensure-correct-file-owner "${combined_log_file}"
        sudo -u "${utility_account_username}" printf -- "${log_line}\n" >>"${combined_log_file}"
    fi
}
