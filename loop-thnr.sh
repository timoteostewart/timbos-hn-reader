#!/usr/bin/env bash

# debugging switches
# set -o errexit   # abort on nonzero exitstatus; same as set -e
# set -o nounset   # abort on unbound variable; same as set -u
# set -o pipefail  # don't hide errors within pipes
# set -o xtrace    # show commands being executed; same as set -x
# set -o verbose   # verbose mode; same as set -v

source ./functions.sh

if ! am-root; then
    die "Please run as root."
fi

ONCE_FLAG=$1
if [[ ! ${ONCE_FLAG} =~ ^(once)$ ]]; then
    die "Usage: ${BASH_SOURCE##*/} [once [all|active|best|classic|new|top]]"
fi
ONCE_STORY_TYPE="${2:-new}"

# handle of the server THNR is running on
SERVER_NAME=thnr

# THNR's base directory
BASE_DIR=/srv/timbos-hn-reader/

# .venv bin dir
PYTHON_BIN_DIR="${BASE_DIR}.venv/bin/"

# settings yaml file
SETTINGS_FILE="${BASE_DIR}settings.yaml"

# non-root username to run THNR program
UTILITY_ACCOUNT_USERNAME=tim

if [[ -z ${UTILITY_ACCOUNT_USERNAME} ]]; then
    die "The variable ${UTILITY_ACCOUNT_USERNAME} cannot be blank."
fi

# looping settings
PAUSE_BETWEEN_CYCLES_IN_MINUTES=30

# logging setup
ALL_LOGS_PATH="${BASE_DIR}logs/"
LOOP_LOG_PREFIX="loop-thnr.sh:"

COMBINED_LOG_IDENTIFIER="combined"

get_cur_year_and_doy() {
    local CUR_YEAR=$(printf '%(%Y)T' -1)
    local CUR_DOY=$(printf '%(%j)T' -1)
    local CUR_DOY_ZEROS="00${CUR_DOY}"
    local CUR_DOY_PADDED="${CUR_DOY_ZEROS: -3}"
    local CUR_YEAR_AND_DOY="${CUR_YEAR}-${CUR_DOY_PADDED}"
    echo "${CUR_YEAR_AND_DOY}"
}

get_cur_datetime() {
    local CUR_DATETIME=$(printf '%(%Y-%m-%d %H:%M:%S %Z)T' -1)
    echo "${CUR_DATETIME}"
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
    local LOG_LINE=$(printf "%s           %-8s %s" "$(get_cur_datetime)" "${LEVEL^^}" "${MESSAGE}")

    if (( ${EUID:-$(id -u)} == 0 )); then
        sudo -u ${UTILITY_ACCOUNT_USERNAME} printf -- "${LOG_LINE}\n" >> "${LOG_FILE}"
        sudo -u ${UTILITY_ACCOUNT_USERNAME} printf -- "${LOG_LINE}\n" >> "${COMBINED_LOG_FILE}"
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

write_log_message loop info "${LOOP_LOG_PREFIX} Starting ${BASH_SOURCE##*/}"

cd-or-die "${BASE_DIR}"
source "${PYTHON_BIN_DIR}activate"

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

declare -a story_types=(
    "active"
    "best"
    "classic"
    "new"
    "top"
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
    if ! "${BASE_DIR}connect_to_vpn.sh"; then
        exit 1
    fi

    cleanup_venv_temp_files
    sleep 5

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

        if [[ ${ONCE_FLAG} == "once" ]]; then
            if [[ "${ONCE_STORY_TYPE}" == "all" ]]; then
                write_log_message loop info "${LOOP_LOG_PREFIX} ONCE_STORY_TYPE is ${ONCE_STORY_TYPE}"
            else
                if [[ "${cur_story_type}" == "${ONCE_STORY_TYPE}" ]]; then
                    write_log_message loop info "${LOOP_LOG_PREFIX} ONCE_STORY_TYPE is ${ONCE_STORY_TYPE}"
                else
                    continue
                fi
            fi
        fi

        MAIN_PY_START_TS=$(get-time-in-unix-seconds)
        MAIN_PY_CMD="sudo -u \"${UTILITY_ACCOUNT_USERNAME}\" \"${PYTHON_BIN_DIR}python\" \"${BASE_DIR}main.py\" \"${cur_story_type}\" \"${SERVER_NAME}\" \"${SETTINGS_FILE}\""

        write_log_message loop info "${LOOP_LOG_PREFIX} Starting main.py for \"${cur_story_type}\" (loop number ${LOOP_NUMBER})..."
        write_log_message loop info "${LOOP_LOG_PREFIX} main.py invocation: ${MAIN_PY_CMD}"

        CUR_YEAR_AND_DOY=$(get_cur_year_and_doy)
        COMBINED_LOG_FILE="${ALL_LOGS_PATH}${SERVER_NAME}-${COMBINED_LOG_IDENTIFIER}-${CUR_YEAR_AND_DOY}.log"
        MAIN_PY_LOG_FILE="${ALL_LOGS_PATH}${SERVER_NAME}-main-py-${CUR_YEAR_AND_DOY}.log"

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
        SECONDS_SPENT=$((MAIN_PY_END_TS - MAIN_PY_START_TS))
        DURATION=$(date -d@${SECONDS_SPENT} -u +"%Hh:%Mm:%Ss")
        if (( ${MAIN_PY_ERROR_CODE} == 0 )); then
            write_log_message loop info "${LOOP_LOG_PREFIX} Exited main.py \"${cur_story_type}\" after ${DURATION}"
        else
            write_log_message loop error "${LOOP_LOG_PREFIX} Exited main.py \"${cur_story_type}\" with error code ${MAIN_PY_ERROR_CODE} after ${DURATION}"
            ./send-email.sh "THNR exited with error ${MAIN_PY_ERROR_CODE} after ${DURATION}" "$(tail -n 50 ${MAIN_PY_LOG_FILE})"
        fi

        # short pause between story types
        sleep 10

        # remove any leftover chromedriver binaries
        cleanup_uc_temp_files

    done

    if [[ ${ONCE_FLAG} == "once" ]]; then
        exit 0
    fi

    # longer pause between cycles
    write_log_message loop info "${LOOP_LOG_PREFIX} Starting pause for ${PAUSE_BETWEEN_CYCLES_IN_MINUTES} minutes"
	sleep $((PAUSE_BETWEEN_CYCLES_IN_MINUTES * 60))
	# then increment loop number and resume loop
	(( LOOP_NUMBER += 1 ))

    # periodically restart the host as a stability measure, if we're root
    if (( ${LOOP_NUMBER} == 25 )); then
        if am-root; then
            shutdown -r now
        fi
    fi

done
