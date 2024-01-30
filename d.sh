#!/usr/bin/env bash

# debugging switches
# set -o errexit   # abort on nonzero exitstatus; same as set -e
# set -o nounset   # abort on unbound variable; same as set -u
# set -o pipefail  # don't hide errors within pipes
# set -o xtrace    # show commands being executed; same as set -x
# set -o verbose   # verbose mode; same as set -v

TZ=UTC

get_last_filename() {
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

get_sha1_of_current_time() {
    local current_time=$(date +%s)
    echo -n "$current_time" | sha1sum | cut -c 1-12
}

email_mock() {
    local subject="$1"
    local body="$2"
    echo -e ""
    echo -e "┌────────────────────────────────────────────────────"
    echo -e "│"
    echo -e "New email:\nSubject: $subject\nBody:\n$body\n"
    echo -e "│"
    echo -e "└────────────────────────────────────────────────────"
    echo -e ""
}

log_dump_via_email() {
    dump_id=$(get_sha1_of_current_time)
    local error_msg="$1"
    # /srv/timbos-hn-reader/send-email.sh "${error_msg} - dump id ${dump_id}" "see incoming log files for details"
    email_mock "${error_msg} - dump id ${dump_id}" "see incoming log files for details"


    printf "${error_msg} - dump id ${dump_id}\n"

    declare -a log_files_patterns=(
        '/srv/timbos-hn-reader/logs/thnr-combined-*.log'
        '/srv/timbos-hn-reader/logs/thnr-loop-*.log'
        '/srv/timbos-hn-reader/logs/thnr-main-py-*.log'
        '/srv/timbos-hn-reader/logs/thnr-thnr-*.log'
        '/srv/timbos-hn-reader/logs/thnr-vpn-*.log'
    )

    for each_pattern in "${log_files_patterns[@]}"; do
        cur_log_file=$(get_last_filename "${each_pattern}")
        if [[ -z ${cur_log_file} ]]; then
            # /srv/timbos-hn-reader/send-email.sh "no matches for log file pattern ${each_pattern} - dump id ${dump_id}" "."
            email_mock "dump id ${dump_id} - warning: no matches for log file pattern ${each_pattern}" "."
            continue
        fi
        ext_error_msg="${error_msg} - ${cur_log_file}"
        log_tail=$(tail -n 50 ${cur_log_file})
        # /srv/timbos-hn-reader/send-email.sh "${ext_error_msg} - dump id ${dump_id}" "${log_tail}"
        email_mock "dump id ${dump_id} - 'tail -n 50 of ${cur_log_file}' " "${log_tail}"
    done
}

# THNR's base directory
BASE_DIR=/srv/timbos-hn-readerx/

if ! cd "${BASE_DIR}"; then
    log_dump_via_email "Error: loop-thnr.sh couldn't cd to ${BASE_DIR}"
    exit 1
fi
