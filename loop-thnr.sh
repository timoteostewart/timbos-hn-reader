#!/usr/bin/env bash

# debugging switches
# set -o errexit   # abort on nonzero exitstatus; same as set -e
# set -o nounset   # abort on unbound variable; same as set -u
set -o pipefail # don't hide errors within pipes
# set -o xtrace    # show commands being executed; same as set -x
# set -o verbose   # verbose mode; same as set -v

source /srv/timbos-hn-reader/functions.sh
source /srv/timbos-hn-reader/thnr-common-functions.sh

if ! am-root; then
    die "Please run as root."
fi

project_base_dir="/srv/timbos-hn-reader/"
export ONCE_FLAG="${1:-}"

"${project_base_dir}send-dashboard-event-to-kafka.sh" \
    "operation" "update-text-content" \
    "elementId" "scraper-app-current-activity" \
    "value" "Entering loop-thnr.sh"

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

trap handle_control_c INT
# trap handle_error INT

export MAGICK_HOME=/usr/local/ImageMagick-7
export WAND_MAGICK_LIBRARY_SUFFIX="-7.Q16HDRI"

all_logs_dir="${project_base_dir}logs/"
python_bin_dir="${project_base_dir}.venv/bin/"
server_name=thnr
export TZ=UTC
utility_account_username=tim

cd "${project_base_dir}" || {
    log_dump_via_email "Error: loop-thnr.sh couldn't cd to ${project_base_dir}"
    exit 1
}

if [[ -z ${utility_account_username} ]]; then
    die "The variable \$utility_account_username cannot be blank."
fi

PAUSE_BETWEEN_CYCLES_IN_MINUTES=30
MAX_AGE_OF_TEMP_FILES_IN_SLASH_TMP_IN_MINUTES=2880            # 2 days
MAX_AGE_OF_RESPONSE_OBJECT_FILES_IN_SLASH_TMP_IN_MINUTES=2160 # 1½ days
MAX_AGE_OF_OG_IMAGE_FILES_IN_SLASH_TMP_IN_MINUTES=60          # 1 hour
MAX_AGE_OF_TEMP_DIRS_IN_SLASH_TMP_IN_MINUTES=60               # 1 hour
LOOPS_BEFORE_RESTART=25
script_invocation_id=$(get-sha1-of-current-time-plus-random)
LOG_PREFIX_LOCAL="loop-thnr.sh id=${script_invocation_id}: "
combined_log_identifier="combined"
SETTINGS_FILE="${project_base_dir}settings.yaml"

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
    dump_id=$(get-sha1-of-current-time-plus-random)
    local error_msg="$1"
    send-alert-email "${error_msg} - dump id ${dump_id}" "see incoming log files for details"
    # email_mock "${error_msg} - dump id ${dump_id}" "see incoming log files for details"
    printf "${error_msg} - dump id ${dump_id}\n"

    local combined_log_file="${all_logs_dir}${server_name}-${combined_log_identifier}-${cur_year_and_doy}.log"

    ext_error_msg="${error_msg} - ${cur_log_file}"
    log_tail=$(tail -n 250 ${combined_log_file})
    send-alert-email "dump_id=${dump_id} - 'tail -n 250 of ${combined_log_file}' " "${log_tail}"
    # email_mock "dump id ${dump_id} - 'tail -n 50 of ${combined_log_file}' " "${log_tail}"
}

cleanup_tmp_dir() {
    TARGET_DIR="/tmp"

    num_tmp_files=0

    # MAX_AGE_OF_TEMP_FILES_IN_SLASH_TMP_IN_MINUTES
    while IFS= read -r file; do
        if ! rm "${file}"; then
            write-log-message loop error "${LOG_PREFIX_LOCAL} Failed to delete ${file}"
        else
            ((num_tmp_files += 1))
        fi
    done < <(find "${TARGET_DIR}" -mindepth 1 -user "${utility_account_username}" -name "*" -type f -mmin "+${MAX_AGE_OF_TEMP_FILES_IN_SLASH_TMP_IN_MINUTES}")

    # MAX_AGE_OF_OG_IMAGE_FILES_IN_SLASH_TMP_IN_MINUTES
    while IFS= read -r file; do
        if ! rm "${file}"; then
            write-log-message loop error "${LOG_PREFIX_LOCAL} Failed to delete ${file}"
        else
            ((num_tmp_files += 1))
        fi
    done < <(find "${TARGET_DIR}" -mindepth 1 -user "${utility_account_username}" -name "*-og-image" -type f -mmin "+${MAX_AGE_OF_OG_IMAGE_FILES_IN_SLASH_TMP_IN_MINUTES}")

    # "*-get_response_object_via_hrequests"
    while IFS= read -r file; do
        if ! rm "${file}"; then
            write-log-message loop error "${LOG_PREFIX_LOCAL} Failed to delete ${file}"
        else
            ((num_tmp_files += 1))
        fi
    done < <(find "${TARGET_DIR}" -mindepth 1 -user "${utility_account_username}" -name "*-response_object_via_hrequests" -type f -mmin "+${MAX_AGE_OF_RESPONSE_OBJECT_FILES_IN_SLASH_TMP_IN_MINUTES}")

    # "*-get_response_object_via_requests"
    while IFS= read -r file; do
        if ! rm "${file}"; then
            write-log-message loop error "${LOG_PREFIX_LOCAL} Failed to delete ${file}"
        else
            ((num_tmp_files += 1))
        fi
    done < <(find "${TARGET_DIR}" -mindepth 1 -user "${utility_account_username}" -name "*-response_object_via_requests" -type f -mmin "+${MAX_AGE_OF_RESPONSE_OBJECT_FILES_IN_SLASH_TMP_IN_MINUTES}")

    # delete old temporary directories
    num_tmp_dirs=0
    while IFS= read -r dir; do
        if ! rm -rf "${dir}"; then
            write-log-message loop error "${LOG_PREFIX_LOCAL} Failed to delete ${dir}"
        else
            ((num_tmp_dirs += 1))
        fi
    done < <(find "${TARGET_DIR}" -mindepth 1 -user "${utility_account_username}" -name "*" -type d -mmin "+${MAX_AGE_OF_TEMP_DIRS_IN_SLASH_TMP_IN_MINUTES}")

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

# apt_packages=(
#     # "chromium-browser-l10n"
#     # "chromium-browser"
#     # "chromium-chromedriver"
#     # "chromium-codecs-ffmpeg-extra"
#     # "google-chrome-beta"
#     # "google-chrome-stable"
#     "nordvpn"
# )

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

# log session start time
session_start_ts=$(get-time-in-unix-seconds)
session_start_iso8601=$(convert-time-in-unix-seconds-to-iso8601 "${session_start_ts}")

write-log-message loop info "${LOG_PREFIX_LOCAL} Session started at ${session_start_ts}"

# "${project_base_dir}send-dashboard-event-to-kafka.sh" \
#     "operation" "update-text-content" \
#     "elementId" "scraper-app-session-start-timestamp" \
#     "value" "${session_start_ts}"

"${project_base_dir}send-dashboard-event-to-kafka.sh" \
    "operation" "update-text-content" \
    "elementId" "scraper-app-session-start-iso8601" \
    "value" "$(get-iso8601-date)"

"${project_base_dir}send-dashboard-event-to-kafka.sh" \
    "operation" "update-text-content" \
    "elementId" "scraper-app-session-start-timestamp" \
    "value" ""

"${project_base_dir}send-dashboard-event-to-kafka.sh" \
    "operation" "update-text-content" \
    "elementId" "scraper-app-session-end-iso8601" \
    "value" "—"

# sudo -u "${utility_account_username}" printf "${session_start_iso8601}\n" >>"${project_base_dir}session-starts-iso8601.txt"
# sudo -u "${utility_account_username}" printf "${session_start_ts}\n" >>"${project_base_dir}session-starts-unix-time.txt"

LOOP_NUMBER=0

"${project_base_dir}send-dashboard-event-to-kafka.sh" \
    "operation" "update-text-content" \
    "elementId" "scraper-app-loops-completed" \
    "value" "${LOOP_NUMBER}"

"${project_base_dir}send-dashboard-event-to-kafka.sh" \
    "operation" "update-text-content" \
    "elementId" "scraper-app-loops-per-session" \
    "value" "${LOOPS_BEFORE_RESTART}"

while true; do
    CUR_LOOP_START_TS=$(get-time-in-unix-seconds)

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "scraper-app-current-activity" \
        "value" "Connecting to VPN..."

    # connect to VPN
    if ! "${project_base_dir}connect-to-vpn.sh"; then
        msg="Could not connect to VPN. Will restart host in 10 minutes."
        write-log-message loop error "${LOG_PREFIX_LOCAL} ${msg}"
        printf "${LOG_PREFIX_LOCAL} ${msg}\n"

        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-text-content" \
            "elementId" "scraper-app-current-activity" \
            "value" "${msg}"

        sleep 600 && shutdown -r now && sleep 60
    fi

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "scraper-app-current-activity" \
        "value" "Checking for Internet connectivity..."

    # check for Internet connectivity
    websites_to_ping=(
        "1.1.1.1"
        "icanhazip.com"
        "www.amazon.com"
        "www.facebook.com"
        "www.google.com"
    )

    ping_successes=0
    ping_failures=0
    min_pings=2
    for cur_website in "${websites_to_ping[@]}"; do
        if curl --head --interface eth0 ${cur_website} >/dev/null 2>&1; then
            ((ping_successes += 1))
        else
            ((ping_failures += 1))
        fi
    done

    if ((ping_successes == 0)); then
        write-log-message loop error "${LOG_PREFIX_LOCAL} Internet connectivity check: ${ping_successes}/${#websites_to_ping[@]} pings succeeded. No Internet connectivity. No Internet connectivity. Will restart in 10 minutes."
        printf "${LOG_PREFIX_LOCAL} Internet connectivity check: ${ping_successes}/${#websites_to_ping[@]} pings succeeded. No Internet connectivity. No Internet connectivity. Will restart host in 10 minutes.\n"
        sleep 600 && shutdown -r now && sleep 60
    fi
    if ((ping_successes >= min_pings)); then
        write-log-message loop info "${LOG_PREFIX_LOCAL} Internet connectivity check: ${ping_successes}/${#websites_to_ping[@]} pings succeeded. Continuing."
    else
        write-log-message loop error "${LOG_PREFIX_LOCAL} Internet connectivity check: ${ping_successes}/${#websites_to_ping[@]} pings succeeded. Unstable Internet connectivity. Will restart host in 10 minutes."
        printf "${LOG_PREFIX_LOCAL} Internet connectivity check: ${ping_successes}/${#websites_to_ping[@]} pings succeeded. Unstable Internet connectivity. Will restart in 10 minutes.\n"
        sleep 600 && shutdown -r now && sleep 60
    fi

    cleanup_tmp_dir
    sleep 10

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "scraper-app-current-activity" \
        "value" "Updating select APT and pip packages..."

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

        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-text-content" \
            "elementId" "scraper-app-current-activity" \
            "value" "Entering main.py for ${cur_story_type}"

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

        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-text-content" \
            "elementId" "scraper-app-current-activity" \
            "value" "Exiting main.py for ${cur_story_type}"

        MAIN_PY_END_TS=$(get-time-in-unix-seconds)
        # TODO: also write MAIN_PY_START_TS and MAIN_PY_END_TS to disk as tempfiles (mktemp command?), in case their values disappear for some reason
        SECONDS_SPENT=$((MAIN_PY_END_TS - MAIN_PY_START_TS))
        DURATION=$(date -d@${SECONDS_SPENT} -u +"%Hh:%Mm:%Ss")

        write-log-message loop info "${LOG_PREFIX_LOCAL} MAIN_PY_START_TS=${MAIN_PY_START_TS}, MAIN_PY_END_TS=${MAIN_PY_END_TS}, SECONDS_SPENT=${SECONDS_SPENT}, DURATION=${DURATION}"

        if ((MAIN_PY_ERROR_CODE == 0)); then
            write-log-message loop info "${LOG_PREFIX_LOCAL} Exited main.py for ${cur_story_type} after ${DURATION}"
        else
            write-log-message loop error "${LOG_PREFIX_LOCAL} Exited main.py for ${cur_story_type} with error code ${MAIN_PY_ERROR_CODE} after ${DURATION}"
            send-alert-email "THNR main.py exited with error ${MAIN_PY_ERROR_CODE} after ${DURATION}" "$(tail -n 50 ${MAIN_PY_LOG_FILE})"
        fi

        # short pause between story types
        sleep 10

    done

    CUR_LOOP_END_TS=$(get-time-in-unix-seconds)
    SECONDS_SPENT=$((CUR_LOOP_END_TS - CUR_LOOP_START_TS))
    DURATION=$(date -d@${SECONDS_SPENT} -u +"%Hh:%Mm:%Ss")

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "scraper-app-recent-loop-duration-seconds" \
        "value" "${SECONDS_SPENT}"

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "scraper-app-recent-loop-duration-pretty" \
        "value" "$(prettify-duration-seconds ${SECONDS_SPENT})"

    write-log-message loop info "${LOG_PREFIX_LOCAL} LOOP_NUMBER=${LOOP_NUMBER}, CUR_LOOP_START_TS=${CUR_LOOP_START_TS}, CUR_LOOP_END_TS=${CUR_LOOP_END_TS}, SECONDS_SPENT=${SECONDS_SPENT}, DURATION=${DURATION}"

    if [[ ${ONCE_FLAG} == "once" ]]; then
        exit 0
    fi

    # then increment loop number and resume loop
    ((LOOP_NUMBER += 1))

    "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        "operation" "update-text-content" \
        "elementId" "scraper-app-loops-completed" \
        "value" "${LOOP_NUMBER}"

    if ((LOOP_NUMBER > LOOPS_BEFORE_RESTART)); then

        session_end_ts=$(get-time-in-unix-seconds)

        # "${project_base_dir}send-dashboard-event-to-kafka.sh" \
        #     "operation" "update-text-content" \
        #     "elementId" "scraper-app-session-end-timestamp" \
        #     "value" "${session_end_ts}"

        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-text-content" \
            "elementId" "scraper-app-session-end-iso8601" \
            "value" "$(get-iso8601-date)"

        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-text-content" \
            "elementId" "scraper-app-current-activity" \
            "value" "Pausing for ${PAUSE_BETWEEN_CYCLES_IN_MINUTES} minutes before restarting host"

    else

        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-text-content" \
            "elementId" "scraper-app-current-activity" \
            "value" "Pausing for ${PAUSE_BETWEEN_CYCLES_IN_MINUTES} minutes before next loop"

    fi

    write-log-message loop info "${LOG_PREFIX_LOCAL} Pausing for ${PAUSE_BETWEEN_CYCLES_IN_MINUTES} minutes"

    sleep $((PAUSE_BETWEEN_CYCLES_IN_MINUTES * 60))

    # periodically restart the host as a stability measure, if we're root
    if ((LOOP_NUMBER > LOOPS_BEFORE_RESTART)); then

        write-log-message loop info "${LOG_PREFIX_LOCAL} restarting scraper host for stability after ${LOOPS_BEFORE_RESTART} loops"

        "${project_base_dir}send-dashboard-event-to-kafka.sh" \
            "operation" "update-text-content" \
            "elementId" "scraper-app-current-activity" \
            "value" "Restarting scraper host for stability"

        shutdown -r now
    fi

done
