#!/usr/bin/env bash

# debugging switches
# set -o errexit   # abort on nonzero exitstatus; same as set -e
# set -o nounset   # abort on unbound variable; same as set -u
# set -o pipefail  # don't hide errors within pipes
# set -o xtrace    # show commands being executed; same as set -x
# set -o verbose   # verbose mode; same as set -v

source /srv/timbos-hn-reader/functions.sh

if ! am-root; then
    die "Please run as root."
fi

TZ=UTC

SERVER_NAME=thnr
UTILITY_ACCOUNT_USERNAME=tim

BASE_DIR=/srv/timbos-hn-reader/
ALL_LOGS_PATH="${BASE_DIR}logs/"
PYTHON_BIN_DIR="${BASE_DIR}.venv/bin/"

cd "${BASE_DIR}" || { log_dump_via_email "Error: loop-thnr.sh couldn't cd to ${BASE_DIR}"; exit 1; }

if [[ -z ${UTILITY_ACCOUNT_USERNAME} ]]; then
    die "The variable ${UTILITY_ACCOUNT_USERNAME} cannot be blank."
fi

PAUSE_BETWEEN_CYCLES_IN_MINUTES=30
LOG_PREFIX_LOCAL="loop-thnr.sh:"
COMBINED_LOG_IDENTIFIER="combined"
SETTINGS_FILE="${BASE_DIR}settings.yaml"

ONCE_FLAG="${1:-}"
ONCE_STORY_TYPE="${2:-all}"

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
    dump_id=$(get_sha1_of_current_time)
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
        cur_log_file=$(get_last_filename "${each_pattern}")
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

get_cur_year_and_doy() {
    TZ=UTC
    local CUR_YEAR=$(date -u +"%Y")
    local CUR_DOY=$(date -u +"%j")
    local CUR_DOY_ZEROS="00${CUR_DOY}"
    local CUR_DOY_PADDED="${CUR_DOY_ZEROS: -3}"
    local CUR_YEAR_AND_DOY="${CUR_YEAR}-${CUR_DOY_PADDED}"
    echo "${CUR_YEAR_AND_DOY}"
}

get_cur_datetime_iso_8601() {
    TZ=UTC
    printf $(date -u +"%Y-%m-%dT%H:%M:%SZ")
}

ensure_correct_file_owner() {
    # usage: ensure_correct_file_owner $FILE
    [[ -z "${1}" ]] && die "ensure_correct_file_owner() requires a file to be specified."
    local FILE="${1}"
    if [[ ! -f "${FILE}" ]]; then
        sudo -u ${UTILITY_ACCOUNT_USERNAME} touch "${FILE}"
    fi
    local FILE_OWNER=$(stat -c '%U' "${FILE}")
    if [[ "$FILE_OWNER" != "$UTILITY_ACCOUNT_USERNAME" ]]; then
        chown ${UTILITY_ACCOUNT_USERNAME}:${UTILITY_ACCOUNT_USERNAME} "${FILE}"
    fi
}

write_log_message() {
    # usage: write_log_message LOG_IDENTIFIER LEVEL MESSAGE
    local CUR_YEAR_AND_DOY=$(get_cur_year_and_doy)
    local LOG_IDENTIFIER="$1"

    local LOG_FILE="${ALL_LOGS_PATH}${SERVER_NAME}-${LOG_IDENTIFIER}-${CUR_YEAR_AND_DOY}.log"
    local COMBINED_LOG_FILE="${ALL_LOGS_PATH}${SERVER_NAME}-${COMBINED_LOG_IDENTIFIER}-${CUR_YEAR_AND_DOY}.log"

    ensure_correct_file_owner "${LOG_FILE}"
    ensure_correct_file_owner "${COMBINED_LOG_FILE}"

    local LEVEL="$2"
    local MESSAGE="$3"
    local LOG_LINE=$(printf "%s           %-8s %s" "$(get_cur_datetime_iso_8601)" "${LEVEL^^}" "${MESSAGE}")

    if (( ${EUID:-$(id -u)} == 0 )); then
        sudo -u "${UTILITY_ACCOUNT_USERNAME}" printf -- "${LOG_LINE}\n" >> "${LOG_FILE}"
        sudo -u "${UTILITY_ACCOUNT_USERNAME}" printf -- "${LOG_LINE}\n" >> "${COMBINED_LOG_FILE}"
    else
        printf -- "${LOG_LINE}\n" >> "${LOG_FILE}"
        printf -- "${LOG_LINE}\n" >> "${COMBINED_LOG_FILE}"
    fi
}

cleanup_uc_temp_files() {
    # delete various stale temp files
    MINUTES_TO_KEEP_TEMP_FILES=50
    find "/tmp" -maxdepth 1 -type d -name "uc_*" -exec rm -rf {} \;
    find "/tmp" -maxdepth 1 -type f -name "tmp*" -mmin "+${MINUTES_TO_KEEP_TEMP_FILES}" -exec rm {} \;
    find "/tmp" -maxdepth 1 -type f -name ".com.google.Chrome*" -mmin "+${MINUTES_TO_KEEP_TEMP_FILES}" -exec rm {} \;
    find "/tmp" -maxdepth 1 -type d -name ".com.google.Chrome*" -mmin "+${MINUTES_TO_KEEP_TEMP_FILES}" -exec rm -r {} \;
}

cleanup_venv_temp_files() {
    TARGET_DIR="/srv/timbos-hn-reader/.venv/lib/python3.10/site-packages"
    # if [ -d "$TARGET_DIR" ]; then
    #     find "$TARGET_DIR" -type d -name '~*' -exec rm -rf {} +
    #     write_log_message loop info "tilde-prefixed directories in '$TARGET_DIR' have been removed."
    # else
    #     write_log_message loop error "Directory '$TARGET_DIR' does not exist."
    # fi
}

cleanup_tmp_dir() {
    TARGET_DIR="/tmp"
    # Find and delete files and directories older than 4 hours
    find "${TARGET_DIR}" -mindepth 1 -user "${UTILITY_ACCOUNT_USERNAME}" -mmin +240 -exec rm -rf {} +
}

CMD_INVOCATION="$0 $@"
write_log_message loop info "${LOG_PREFIX_LOCAL} Starting with this invocation: ${CMD_INVOCATION}"

cd-or-die "${BASE_DIR}"
source "${PYTHON_BIN_DIR}activate"

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

declare -a story_types=(
    "active"
    "best"
    "classic"
    "top"
    "new"
)

declare -a apt_packages=(
    # "chromium-browser-l10n"
    # "chromium-browser"
    # "chromium-chromedriver"
    # "chromium-codecs-ffmpeg-extra"
    # "google-chrome-beta"
    # "google-chrome-stable"
    "nordvpn"
)

declare -a pip_packages=(
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

LOOP_NUMBER=1

while true
do
    CUR_LOOP_START_TS=$(get-time-in-unix-seconds)

    if ! "${BASE_DIR}connect_to_vpn.sh"; then
        exit 1
    fi

    cleanup_venv_temp_files
    sleep 10
    cleanup_tmp_dir
    sleep 10

    # update APT packages
    for cur_package in ${apt_packages[@]}; do
        apt-get -y install "${cur_package}"
    done

    # update pip packages
    for cur_package in ${pip_packages[@]}; do
        "${PYTHON_BIN_DIR}pip3" install --upgrade "${cur_package}"
    done

    # "${PYTHON_BIN_DIR}playwright" install
    # "${PYTHON_BIN_DIR}playwright" install-deps

    for cur_story_type in ${story_types[@]}; do

        MAIN_PY_START_TS=$(get-time-in-unix-seconds)

        if [[ ${ONCE_FLAG} == "once" ]]; then
            if [[ "${ONCE_STORY_TYPE}" == "all" ]]; then
                write_log_message loop info "${LOG_PREFIX_LOCAL} ONCE_STORY_TYPE is ${ONCE_STORY_TYPE}"
            else
                if [[ "${cur_story_type}" == "${ONCE_STORY_TYPE}" ]]; then
                    write_log_message loop info "${LOG_PREFIX_LOCAL} ONCE_STORY_TYPE is ${ONCE_STORY_TYPE}"
                else
                    continue
                fi
            fi
        fi

        MAIN_PY_CMD="sudo -u \"${UTILITY_ACCOUNT_USERNAME}\" \"${PYTHON_BIN_DIR}python\" \"${BASE_DIR}main.py\" \"${cur_story_type}\" \"${SERVER_NAME}\" \"${SETTINGS_FILE}\""

        write_log_message loop info "${LOG_PREFIX_LOCAL} Loop number ${LOOP_NUMBER}. Starting main.py for ${cur_story_type} with this invocation: ${MAIN_PY_CMD}"

        CUR_YEAR_AND_DOY=$(get_cur_year_and_doy)
        COMBINED_LOG_FILE="${ALL_LOGS_PATH}${SERVER_NAME}-${COMBINED_LOG_IDENTIFIER}-${CUR_YEAR_AND_DOY}.log"
        MAIN_PY_LOG_FILE="${ALL_LOGS_PATH}${SERVER_NAME}-main-py-${CUR_YEAR_AND_DOY}.log"
        ensure_correct_file_owner "${COMBINED_LOG_FILE}"
        ensure_correct_file_owner "${MAIN_PY_LOG_FILE}"

        if (( ${EUID:-$(id -u)} == 0 )); then
            # sudo -u "${UTILITY_ACCOUNT_USERNAME}" "${PYTHON_BIN_DIR}python" main.py "${cur_story_type}" "${SERVER_NAME}" "${SETTINGS_FILE}" 2>&1 | tee -a "${MAIN_PY_LOG_FILE}" >> "${COMBINED_LOG_FILE}"
            set -o pipefail
            {
                sudo -u "${UTILITY_ACCOUNT_USERNAME}" "${PYTHON_BIN_DIR}python" "${BASE_DIR}main.py" "${cur_story_type}" "${SERVER_NAME}" "${SETTINGS_FILE}" 2>&1
            } | tee -a "${MAIN_PY_LOG_FILE}" | tee -a "${COMBINED_LOG_FILE}"
            MAIN_PY_ERROR_CODE=$?
            set +o pipefail
        else
            # "${PYTHON_BIN_DIR}python" main.py "${cur_story_type}" "${SERVER_NAME}" "${SETTINGS_FILE}" 2>&1 | tee -a "${MAIN_PY_LOG_FILE}" >> "${COMBINED_LOG_FILE}"
            printf "Error: you should be root!\n"
            exit 1
        fi

        MAIN_PY_END_TS=$(get-time-in-unix-seconds)
        # TODO: also write MAIN_PY_START_TS and MAIN_PY_END_TS to disk as tempfiles (mktemp command?), in case their values disappear for some reason
        SECONDS_SPENT=$((MAIN_PY_END_TS - MAIN_PY_START_TS))
        DURATION=$(date -d@${SECONDS_SPENT} -u +"%Hh:%Mm:%Ss")

        write_log_message loop info "${LOG_PREFIX_LOCAL} MAIN_PY_START_TS=${MAIN_PY_START_TS}, MAIN_PY_END_TS=${MAIN_PY_END_TS}, SECONDS_SPENT=${SECONDS_SPENT}, DURATION=${DURATION}"

        if (( MAIN_PY_ERROR_CODE == 0 )); then
            write_log_message loop info "${LOG_PREFIX_LOCAL} Exiting main.py for ${cur_story_type} after ${DURATION}"
        else
            write_log_message loop error "${LOG_PREFIX_LOCAL} Exiting main.py for ${cur_story_type} with error code ${MAIN_PY_ERROR_CODE} after ${DURATION}"
            /srv/timbos-hn-reader/send-email.sh "THNR exited with error ${MAIN_PY_ERROR_CODE} after ${DURATION}" "$(tail -n 50 ${MAIN_PY_LOG_FILE})"
        fi

        # short pause between story types
        sleep 10

        # remove any leftover chromedriver binaries
        cleanup_uc_temp_files

    done

    CUR_LOOP_END_TS=$(get-time-in-unix-seconds)
    SECONDS_SPENT=$((CUR_LOOP_END_TS - CUR_LOOP_START_TS))
    DURATION=$(date -d@${SECONDS_SPENT} -u +"%Hh:%Mm:%Ss")

    write_log_message loop info "${LOG_PREFIX_LOCAL} LOOP_NUMBER=${LOOP_NUMBER}, CUR_LOOP_START_TS=${CUR_LOOP_START_TS}, CUR_LOOP_END_TS=${CUR_LOOP_END_TS}, SECONDS_SPENT=${SECONDS_SPENT}, DURATION=${DURATION}"

    if [[ ${ONCE_FLAG} == "once" ]]; then
        exit 0
    fi

    # longer pause between cycles
    write_log_message loop info "${LOG_PREFIX_LOCAL} Starting pause for ${PAUSE_BETWEEN_CYCLES_IN_MINUTES} minutes"
	sleep $((PAUSE_BETWEEN_CYCLES_IN_MINUTES * 60))
	# then increment loop number and resume loop
	(( LOOP_NUMBER += 1 ))

    # periodically restart the host as a stability measure, if we're root
    if (( LOOP_NUMBER == 25 )); then
        shutdown -r now
    fi

done
