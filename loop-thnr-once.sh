#!/usr/bin/env bash

# debugging switches
# set -o errexit   # abort on nonzero exitstatus; same as set -e
# set -o nounset   # abort on unbound variable; same as set -u
# set -o pipefail  # don't hide errors within pipes
# set -o xtrace    # show commands being executed; same as set -x
# set -o verbose   # verbose mode; same as set -v

die () {
    printf -- "\n*\n* Error: ${1:-Unspecified Error}\n"
    printf -- "* An unrecoverable error has occurred. Look above for any error messages.\n"
    printf -- "* The script '${BASH_SOURCE##*/}' will exit now.\n*\n"
    exit 1
}

am-root() {
    if (( ${EUID:-$(id -u)} != 0 )); then
        return 1
    else
        return 0
    fi
}

if ! am-root; then
    die "Please run as root."
fi

# handle of the server THNR is running on
SERVER_NAME=thnr

# THNR's base directory
BASE_DIR=/srv/timbos-hn-reader/

# .venv bin dir
PYTHON_BIN_DIR="${BASE_DIR}.venv/bin"

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
LOOP_LOG_PATH="${BASE_DIR}/logs/"
CUR_YEAR=$(printf '%(%Y)T\n' -1)
CUR_DOY=$(printf '%(%j)T\n' -1)
CUR_DOY_ZEROS="00${CUR_DOY}"
CUR_DOY_PADDED="${CUR_DOY_ZEROS: -3}"
CUR_YEAR_AND_DOY="${CUR_YEAR}-${CUR_DOY_PADDED}"

loop_log_message() {
    CUR_YEAR=$(printf '%(%Y)T' -1)
    CUR_DOY=$(printf '%(%j)T' -1)
    CUR_DOY_ZEROS="00${CUR_DOY}"
    CUR_DOY_PADDED="${CUR_DOY_ZEROS: -3}"
    CUR_YEAR_AND_DOY="${CUR_YEAR}-${CUR_DOY_PADDED}"

	LEVEL="$1"
	MESSAGE="$2"
	CUR_DATETIME=$(printf '%(%Y-%m-%d %H:%M:%S %Z)T' -1)
	LOG_LINE="${CUR_DATETIME} ${LEVEL^^} ${MESSAGE}"
    LOG_FILE="${LOOP_LOG_PATH}${SERVER_NAME}-loop-${CUR_YEAR_AND_DOY}.log"

    if (( ${EUID:-$(id -u)} == 0 )); then
        sudo -u ${UTILITY_ACCOUNT_USERNAME} printf -- "${LOG_LINE}\n" >> "${LOG_FILE}"
    else
        printf -- "${LOG_LINE}\n" >> "${LOG_FILE}"
    fi
}

main_py_log_message() {
    local CUR_YEAR=$(printf '%(%Y)T' -1)
    local CUR_DOY=$(printf '%(%j)T' -1)
    local CUR_DOY_ZEROS="00${CUR_DOY}"
    local CUR_DOY_PADDED="${CUR_DOY_ZEROS: -3}"
    local CUR_YEAR_AND_DOY="${CUR_YEAR}-${CUR_DOY_PADDED}"
    local CUR_DATETIME=$(printf '%(%Y-%m-%d %H:%M:%S %Z)T' -1)

	local LEVEL="$1"
    local MESSAGE="$2"
    local LOG_LINE=$(printf "%s %-8s %s" "${CUR_DATETIME}" "${LEVEL^^}" "${MESSAGE}")
    local LOG_FILE="$3"
    # ${MAIN_PY_LOG_FILE}

    if (( ${EUID:-$(id -u)} == 0 )); then
        sudo -u ${UTILITY_ACCOUNT_USERNAME} printf -- "${LOG_LINE}\n" >> "${LOG_FILE}"
    else
        printf -- "${LOG_LINE}\n" >> "${LOG_FILE}"
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

loop_log_message info "Starting ${BASH_SOURCE##*/}"

cd "${BASE_DIR}"
source "${PYTHON_BIN_DIR}/activate"

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

declare -a story_types=(
    "top"
    "best"
    "new"
    "classic"
    "active"
)

declare -a apt_packages=(
    "chromium-browser-l10n"
    "chromium-browser"
    "chromium-chromedriver"
    "chromium-codecs-ffmpeg-extra"
    "google-chrome-beta"
    "google-chrome-stable"
    "nordvpn"
)

declare -a pip_packages=(
    "pip"
    "wheel"
    "boto3"
    "botocore"
    # "requests"
    "selenium"
    "undetected-chromedriver"
    # "urllib3"
)

LOOP_NUMBER=1

while true
do
    if ! "${BASE_DIR}connect_to_vpn.sh"; then
        exit 1
    fi

    # update APT packages
    for cur_package in ${apt_packages[@]}; do
        apt-get -y install "${cur_package}"
    done

    # update pip packages
    for cur_package in ${pip_packages[@]}; do
        "${PYTHON_BIN_DIR}/pip" install "${cur_package}" --upgrade
    done

    # "${PYTHON_BIN_DIR}/pip-review"

    for cur_story_type in ${story_types[@]}; do
        loop_log_message info "Starting main.py for \"${cur_story_type}\" (loop number ${LOOP_NUMBER})..."
        TIME_STARTED=$(printf '%(%s)T' -1)

        CUR_YEAR=$(printf '%(%Y)T' -1)
        CUR_DOY=$(printf '%(%j)T' -1)
        CUR_DOY_ZEROS="00${CUR_DOY}"
        CUR_DOY_PADDED="${CUR_DOY_ZEROS: -3}"
        CUR_YEAR_AND_DOY="${CUR_YEAR}-${CUR_DOY_PADDED}"
        MAIN_PY_LOG_FILE="${LOOP_LOG_PATH}${SERVER_NAME}-main-py-${CUR_YEAR_AND_DOY}.log"

        main_py_log_message info "Starting main.py for \"${cur_story_type}\" (loop number ${LOOP_NUMBER})..." "${MAIN_PY_LOG_FILE}"

        MAIN_PY_CMD="sudo -u \"${UTILITY_ACCOUNT_USERNAME}\" \"${PYTHON_BIN_DIR}/python\" main.py \"${cur_story_type}\" \"${SERVER_NAME}\" \"${SETTINGS_FILE}\""

        main_py_log_message info "Invocation: ${MAIN_PY_CMD}" "${MAIN_PY_LOG_FILE}"

        if (( ${EUID:-$(id -u)} == 0 )); then
            sudo -u "${UTILITY_ACCOUNT_USERNAME}" "${PYTHON_BIN_DIR}/python" main.py "${cur_story_type}" "${SERVER_NAME}" "${SETTINGS_FILE}" >> ${MAIN_PY_LOG_FILE} 2>&1
        else
            "${PYTHON_BIN_DIR}/python" main.py "${cur_story_type}" "${SERVER_NAME}" "${SETTINGS_FILE}"
        fi

        THNR_ERROR_CODE=$?

        TIME_STOPPED=$(printf '%(%s)T' -1)
        SECONDS_SPENT=$((TIME_STOPPED - TIME_STARTED))
        DURATION=$(date -d@${SECONDS_SPENT} -u +"%Hh:%Mm:%Ss")
        if (( ${THNR_ERROR_CODE} == 0 )); then
            loop_log_message info "Exited main.py \"${cur_story_type}\" after ${DURATION}"
        else
            loop_log_message error "Exited main.py \"${cur_story_type}\" with error code ${THNR_ERROR_CODE} after ${DURATION}"
            ./send-email.sh "THNR exited with error ${THNR_ERROR_CODE} after ${DURATION}" "$(tail -n 50 ${MAIN_PY_LOG_FILE})"
        fi

        # short pause between story types
        sleep 10

        # remove any leftover chromedriver binaries
        cleanup_uc_temp_files

        exit 0

    done

    # longer pause between cycles
    loop_log_message info "Starting pause for ${PAUSE_BETWEEN_CYCLES_IN_MINUTES} minutes"
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
