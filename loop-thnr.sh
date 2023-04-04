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

# handle of the server THNR is running on
SERVER_NAME=thnr

# THNR's base directory
BASE_DIR=/srv/timbos-hn-reader/

# settings yaml file
SETTINGS_FILE="${BASE_DIR}settings.yaml"

# non-root username to run THNR program
UTILITY_ACCOUNT_USERNAME=tim

if [[ -z ${UTILITY_ACCOUNT_USERNAME} ]]; then
    die "The variable ${UTILITY_ACCOUNT_USERNAME} cannot be blank."
fi

# looping settings
PAUSE_BETWEEN_CYCLES_IN_MINUTES=10

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

cleanup_uc_binaries() {
    uc_temp_dir="/home/${UTILITY_ACCOUNT_USERNAME}/.local/share/undetected_chromedriver"
    rm -r "${uc_temp_dir}"

    if (( ${EUID:-$(id -u)} == 0 )); then
        sudo -u "${UTILITY_ACCOUNT_USERNAME}" mkdir "${uc_temp_dir}"
    else
        mkdir "${uc_temp_dir}"
    fi
}

loop_log_message info "Starting ${BASH_SOURCE##*/}"

cd "${BASE_DIR}"
source "${BASE_DIR}.venv/bin/activate"

export PYTHONWARNINGS="ignore:Unverified HTTPS request"

declare -a story_types=(
    "top"
    "best"
    "new"
    "classic"
    "active"
)

LOOP_NUMBER=1

while true
do
    if ! "${BASE_DIR}connect_to_vpn.sh"; then
        exit 1
    fi

    for cur_story_type in ${story_types[@]}; do
        loop_log_message info "Starting main.py for \"${cur_story_type}\" (loop number ${LOOP_NUMBER})..."
        TIME_STARTED=$(printf '%(%s)T' -1)

        if (( ${EUID:-$(id -u)} == 0 )); then
            sudo -u "${UTILITY_ACCOUNT_USERNAME}" "${BASE_DIR}.venv/bin/python" main.py "${cur_story_type}" "${SERVER_NAME}" "${SETTINGS_FILE}"
        else
            "${BASE_DIR}.venv/bin/python" main.py "${cur_story_type}" "${SERVER_NAME}" "${SETTINGS_FILE}"
        fi
        
        THNR_ERROR_CODE=$?
        
        TIME_STOPPED=$(printf '%(%s)T' -1)
        SECONDS_SPENT=$((TIME_STOPPED - TIME_STARTED))
        DURATION=$(date -d@${SECONDS_SPENT} -u +"%Hh:%Mm:%Ss")
        if (( ${THNR_ERROR_CODE} == 0 )); then
            loop_log_message info "Exited main.py \"${cur_story_type}\" after ${DURATION}"
        else
            loop_log_message error "Exited main.py \"${cur_story_type}\" with error code ${THNR_ERROR_CODE} after ${DURATION}"
        fi

        # short pause between story types
        sleep 10

        # remove any leftover chromedriver binaries
        cleanup_uc_binaries

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
