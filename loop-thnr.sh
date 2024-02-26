#!/usr/bin/env bash

# debugging switches
# set -o errexit   # abort on nonzero exitstatus; same as set -e
# set -o nounset   # abort on unbound variable; same as set -u
set -o pipefail  # don't hide errors within pipes
# set -o xtrace    # show commands being executed; same as set -x
# set -o verbose   # verbose mode; same as set -v

source /srv/timbos-hn-reader/functions.sh
source /srv/timbos-hn-reader/thnr_common_functions.sh

if ! am-root; then
    die "Please run as root."
fi

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

trap handle_control_c INT
# trap handle_error INT

project_base_dir=/srv/timbos-hn-reader/
all_logs_dir="${project_base_dir}logs/"
python_bin_dir="${project_base_dir}.venv/bin/"
server_name=thnr
TZ=UTC
utility_account_username=tim

cd "${project_base_dir}" || { log_dump_via_email "Error: loop-thnr.sh couldn't cd to ${project_base_dir}"; exit 1; }

if [[ -z ${utility_account_username} ]]; then
    die "The variable \$utility_account_username cannot be blank."
fi

PAUSE_BETWEEN_CYCLES_IN_MINUTES=30
MAX_AGE_OF_TEMP_FILES_IN_SLASH_TMP_IN_MINUTES=180
LOOPS_BEFORE_RESTART=25
LOG_PREFIX_LOCAL="loop-thnr.sh:"
combined_log_identifier="combined"
SETTINGS_FILE="${project_base_dir}settings.yaml"

ONCE_FLAG="${1:-}"
ONCE_STORY_TYPE="${2:-all}"

handle_control_c() {
    write-log-message loop info "${LOG_PREFIX_LOCAL} Control-C received. Exiting."
    exit 0
}

handle_error() {
    write-log-message loop info "${LOG_PREFIX_LOCAL} Error. Exiting."
    exit 1
}

# email_mock() {
#     local subject="$1"
#     local body="$2"
#     echo -e ""
#     echo -e "┌────────────────────────────────────────────────────"
#     echo -e "│"
#     echo -e "New email:\nSubject: $subject\nBody:\n$body\n"
#     echo -e "│"
#     echo -e "└────────────────────────────────────────────────────"
#     echo -e ""
# }

log_dump_via_email() {
    dump_id=$(get-sha1-of-current-time)
    local error_msg="$1"
    /srv/timbos-hn-reader/send-email.sh "${error_msg} - dump id ${dump_id}" "see incoming log files for details"
    # email_mock "${error_msg} - dump id ${dump_id}" "see incoming log files for details"
    printf "${error_msg} - dump id ${dump_id}\n"

    declare -a log_files_patterns=(
        '/srv/timbos-hn-reader/logs/thnr-combined-*.log'
        '/srv/timbos-hn-reader/logs/thnr-loop-*.log'
        '/srv/timbos-hn-reader/logs/thnr-main-py-*.log'
        '/srv/timbos-hn-reader/logs/thnr-thnr-*.log'
        '/srv/timbos-hn-reader/logs/thnr-vpn-*.log'
    )

    for each_pattern in "${log_files_patterns[@]}"; do
        cur_log_file=$(get-last-filename "${each_pattern}")
        if [[ -z ${cur_log_file} ]]; then
            /srv/timbos-hn-reader/send-email.sh "dump id ${dump_id} - warning: no matches for log file pattern ${each_pattern}" "(body intentionally left blank)"
            # email_mock "dump id ${dump_id} - warning: no matches for log file pattern ${each_pattern}" "(body intentionally left blank)"
            continue
        fi
        ext_error_msg="${error_msg} - ${cur_log_file}"
        log_tail=$(tail -n 50 ${cur_log_file})
        /srv/timbos-hn-reader/send-email.sh "dump id ${dump_id} - 'tail -n 50 of ${cur_log_file}' " "${log_tail}"
        # email_mock "dump id ${dump_id} - 'tail -n 50 of ${cur_log_file}' " "${log_tail}"
    done
}

cleanup_tmp_dir() {
    TARGET_DIR="/tmp"
    num_tmp_files=0
    while IFS= read -r file; do
        if ! rm "${file}"; then
            write-log-message loop error "${LOG_PREFIX_LOCAL} Failed to delete ${file}"
        else
            (( num_tmp_files += 1 ))
        fi
    done < <(find "${TARGET_DIR}" -mindepth 1 -user "${utility_account_username}" -name "*" -type f -mmin "+${MAX_AGE_OF_TEMP_FILES_IN_SLASH_TMP_IN_MINUTES}")

    num_tmp_dirs=0
    while IFS= read -r dir; do
        if ! rm -rf "${dir}"; then
            write-log-message loop error "${LOG_PREFIX_LOCAL} Failed to delete ${dir}"
        else
            (( num_tmp_dirs += 1 ))
        fi
    done < <(find "${TARGET_DIR}" -mindepth 1 -user "${utility_account_username}" -name "*" -type d -mmin "+${MAX_AGE_OF_TEMP_FILES_IN_SLASH_TMP_IN_MINUTES}")

    write-log-message loop info "${LOG_PREFIX_LOCAL} Deleted ${num_tmp_files} files and ${num_tmp_dirs} dirs in ${TARGET_DIR}"
}

CMD_INVOCATION="$0 $@"
write-log-message loop info "${LOG_PREFIX_LOCAL} Starting with this invocation: ${CMD_INVOCATION}"

cd-or-die "${project_base_dir}"
source "${python_bin_dir}activate"

story_types=(
    "active"
    "best"
    "classic"
    "top"
    "new"
)

apt_packages=(
    # "chromium-browser-l10n"
    # "chromium-browser"
    # "chromium-chromedriver"
    # "chromium-codecs-ffmpeg-extra"
    # "google-chrome-beta"
    # "google-chrome-stable"
    "nordvpn"
)

pip_packages=(
    "pip"
    "wheel"
    # "boto3"
    # "botocore"
    # "hrequests[all]"
    # "playwright"
    # "requests"
    # "selenium"
    # "undetected-chromedriver"
    # "urllib3"
)

# check for internet connectivity
websites_to_ping=(
    "1.1.1.1"
    "8.8.8.8"
    "icanhazip.com"
    "www.amazon.com"
    "www.facebook.com"
    "www.google.com"
)

LOOP_NUMBER=1

while true
do
    CUR_LOOP_START_TS=$(get-time-in-unix-seconds)

    ping_successes=0
    ping_failures=0
    min_pings=3
    for cur_website in "${websites_to_ping[@]}"; do
        if ping -c 1 ${cur_website} >/dev/null &2>1; then
            (( ping_successes += 1 ))
        else
            (( ping_failures += 1 ))
        fi
    done

    if (( ping_successes == 0 )); then
            write-log-message loop error "${LOG_PREFIX_LOCAL} Internet connectivity check: All pings failed. No Internet connectivity. Exiting."
            printf "${LOG_PREFIX_LOCAL} Internet connectivity check: No Internet connectivity. Exiting.\n"
            exit 2
    else
        if (( ping_successes >= min_pings )); then
            write-log-message loop info "${LOG_PREFIX_LOCAL} Internet connectivity check: ${min_pings} or more pings succeeded. Continuing."
        else
            write-log-message loop error "${LOG_PREFIX_LOCAL} Internet connectivity check: ${ping_failures} pings failed, ${ping_successes} pings succeeded. Unstable Internet connectivity. Exiting."
            printf "${LOG_PREFIX_LOCAL} Internet connectivity check: Unstable Internet connectivity. Exiting.\n"
            exit 2
        fi
    fi

    if ! "${project_base_dir}connect_to_vpn.sh"; then
        exit 1
    fi

    cleanup_tmp_dir
    sleep 10

    # update APT packages
    for cur_package in ${apt_packages[@]}; do
        apt-get -y install "${cur_package}"
    done

    # update pip packages
    for cur_package in ${pip_packages[@]}; do
        "${python_bin_dir}pip3" install --upgrade "${cur_package}"
    done

    # "${python_bin_dir}playwright" install
    # "${python_bin_dir}playwright" install-deps

    for cur_story_type in ${story_types[@]}; do

        MAIN_PY_START_TS=$(get-time-in-unix-seconds)

        if [[ ${ONCE_FLAG} == "once" ]]; then
            if [[ "${ONCE_STORY_TYPE}" == "all" ]]; then
                write-log-message loop info "${LOG_PREFIX_LOCAL} ONCE_STORY_TYPE is ${ONCE_STORY_TYPE}"
            else
                if [[ "${cur_story_type}" == "${ONCE_STORY_TYPE}" ]]; then
                    write-log-message loop info "${LOG_PREFIX_LOCAL} ONCE_STORY_TYPE is ${ONCE_STORY_TYPE}"
                else
                    continue
                fi
            fi
        fi

        MAIN_PY_CMD="sudo -u \"${utility_account_username}\" \"${python_bin_dir}python\" \"${project_base_dir}main.py\" \"${cur_story_type}\" \"${server_name}\" \"${SETTINGS_FILE}\""

        write-log-message loop info "${LOG_PREFIX_LOCAL} Loop number ${LOOP_NUMBER}. Starting main.py for ${cur_story_type} with this invocation: ${MAIN_PY_CMD}"

        CUR_YEAR_AND_DOY=$(get-cur-year-and-doy)
        COMBINED_LOG_FILE="${all_logs_dir}${server_name}-${combined_log_identifier}-${CUR_YEAR_AND_DOY}.log"
        MAIN_PY_LOG_FILE="${all_logs_dir}${server_name}-main-py-${CUR_YEAR_AND_DOY}.log"

        # sudo -u "${utility_account_username}" "${python_bin_dir}python" main.py "${cur_story_type}" "${server_name}" "${SETTINGS_FILE}" 2>&1 | tee -a "${MAIN_PY_LOG_FILE}" >> "${COMBINED_LOG_FILE}"

        write-log-message main-py info "${LOG_PREFIX_LOCAL} Loop number ${LOOP_NUMBER}. Starting main.py for ${cur_story_type}" "false"

        set -o pipefail
        {
            sudo -u "${utility_account_username}" "${python_bin_dir}python" "${project_base_dir}main.py" "${cur_story_type}" "${server_name}" "${SETTINGS_FILE}" 2>&1
        } | tee -a "${MAIN_PY_LOG_FILE}" | tee -a "${COMBINED_LOG_FILE}"
        MAIN_PY_ERROR_CODE=$?
        set +o pipefail

        write-log-message main-py info "${LOG_PREFIX_LOCAL} left main.py" "false"

        MAIN_PY_END_TS=$(get-time-in-unix-seconds)
        # TODO: also write MAIN_PY_START_TS and MAIN_PY_END_TS to disk as tempfiles (mktemp command?), in case their values disappear for some reason
        SECONDS_SPENT=$((MAIN_PY_END_TS - MAIN_PY_START_TS))
        DURATION=$(date -d@${SECONDS_SPENT} -u +"%Hh:%Mm:%Ss")

        write-log-message loop info "${LOG_PREFIX_LOCAL} MAIN_PY_START_TS=${MAIN_PY_START_TS}, MAIN_PY_END_TS=${MAIN_PY_END_TS}, SECONDS_SPENT=${SECONDS_SPENT}, DURATION=${DURATION}"

        if (( MAIN_PY_ERROR_CODE == 0 )); then
            write-log-message loop info "${LOG_PREFIX_LOCAL} Exited main.py for ${cur_story_type} after ${DURATION}"
        else
            write-log-message loop error "${LOG_PREFIX_LOCAL} Exited main.py for ${cur_story_type} with error code ${MAIN_PY_ERROR_CODE} after ${DURATION}"
            /srv/timbos-hn-reader/send-email.sh "THNR main.py exited with error ${MAIN_PY_ERROR_CODE} after ${DURATION}" "$(tail -n 50 ${MAIN_PY_LOG_FILE})"
        fi

        # short pause between story types
        sleep 10

    done

    CUR_LOOP_END_TS=$(get-time-in-unix-seconds)
    SECONDS_SPENT=$((CUR_LOOP_END_TS - CUR_LOOP_START_TS))
    DURATION=$(date -d@${SECONDS_SPENT} -u +"%Hh:%Mm:%Ss")

    write-log-message loop info "${LOG_PREFIX_LOCAL} LOOP_NUMBER=${LOOP_NUMBER}, CUR_LOOP_START_TS=${CUR_LOOP_START_TS}, CUR_LOOP_END_TS=${CUR_LOOP_END_TS}, SECONDS_SPENT=${SECONDS_SPENT}, DURATION=${DURATION}"

    if [[ ${ONCE_FLAG} == "once" ]]; then
        exit 0
    fi

    # longer pause between cycles
    write-log-message loop info "${LOG_PREFIX_LOCAL} Starting pause for ${PAUSE_BETWEEN_CYCLES_IN_MINUTES} minutes"
	sleep $((PAUSE_BETWEEN_CYCLES_IN_MINUTES * 60))
	# then increment loop number and resume loop
	(( LOOP_NUMBER += 1 ))

    # periodically restart the host as a stability measure, if we're root
    if (( LOOP_NUMBER > LOOPS_BEFORE_RESTART )); then
        write-log-message loop info "${LOG_PREFIX_LOCAL} restarting host for stability after ${LOOPS_BEFORE_RESTART} loops"
        shutdown -r now
    fi

done
