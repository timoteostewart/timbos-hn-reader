#!/usr/bin/env bash

ensure-correct-file-owner() {
    # usage: ensure-correct-file-owner $file
    # example: ensure-correct-file-owner "${combined_log_file}"

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
    local cur_year=$(date -u +"%Y")
    local cur_doy=$(date -u +"%j")
    local cur_doy_zeros="00${cur_doy}"
    local cur_doy_padded="${cur_doy_zeros: -3}"
    local cur_year_and_doy="${cur_year}-${cur_doy_padded}"
    echo "${cur_year_and_doy}"
}

get-last-filename() {
    local pattern="$1"
    local last_file=""
    # Use a glob pattern without word splitting
    for file in $pattern; do
        if [ -f "$file" ]; then
            last_file="$file"
        fi
    done
    echo "$last_file"
}

get-sha1-of-current-time() {
    local current_time=$(date +%s)
    echo -n "$current_time" | sha1sum | cut -c 1-12
}

write-log-message() {
    # usage: write-log-message $log_identifier $level $message [$write_to_combined_log_flag]
    # example: write-log-message loop error "${LOG_PREFIX_LOCAL} Failed to delete ${file}"
    # example: write-log-message loop info "${LOG_PREFIX_LOCAL} ${min_pings} or more pings succeeded. Continuing."
    local cur_year_and_doy=$(get-cur-year-and-doy)
    local log_identifier="$1"
    local write_to_combined_log_flag="$4"

    if [[ -z "${write_to_combined_log_flag}" ]]; then
        write_to_combined_log_flag="true"
    fi

    local level="$2"
    local message="$3"
    local log_line=$(printf "%s           %-8s %s" "$(get-iso8601-date-milliseconds)" "${level^^}" "${message}")

    local specific_log_file="${all_logs_dir}${server_name}-${log_identifier}-${cur_year_and_doy}.log"
    ensure-correct-file-owner "${specific_log_file}"
    sudo -u "${utility_account_username}" printf -- "${log_line}\n" >> "${specific_log_file}"

    if [[ "${write_to_combined_log_flag}" == "true" ]]; then
        local combined_log_file="${all_logs_dir}${server_name}-${combined_log_identifier}-${cur_year_and_doy}.log"
        ensure-correct-file-owner "${combined_log_file}"
        sudo -u "${utility_account_username}" printf -- "${log_line}\n" >> "${combined_log_file}"
    fi

}
