#!/usr/bin/env bash

# handle of the server THNR is running on
SERVER_NAME=thnr

# THNR's base directory
BASE_DIR=/srv/timbos-hn-reader/

# settings yaml file
SETTINGS_FILE="${BASE_DIR}settings.yaml"

# non-root username to run THNR program
UTILITY_ACCOUNT_USERNAME=tim

# looping settings
PAUSE_BETWEEN_CYCLES_IN_MINUTES=20


# NordVPN logging
NORDVPN_LOG_FILE="${BASE_DIR}most_recent_nordvpn_messages.txt"

# logging setup
LOOP_LOG_PATH="${BASE_DIR}"
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
        sudo -u ${UTILITY_ACCOUNT_USERNAME} echo -e "${LOG_LINE}" >> "${LOG_FILE}"
    else
        echo -e "${LOG_LINE}" >> "${LOG_FILE}"
    fi
}

LOOP_NUMBER=1

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

while true
do

    printf -- "$(date)" >> ${NORDVPN_LOG_FILE}
    nordvpn connect >> ${NORDVPN_LOG_FILE}
    sleep 5
    nordvpn status >> ${NORDVPN_LOG_FILE}
    printf -- "\n" >> ${NORDVPN_LOG_FILE}
    nordvpn settings >> ${NORDVPN_LOG_FILE}
    printf -- "\n" >> ${NORDVPN_LOG_FILE}

    if nordvpn connect; then
        loop_log_message info "NordVPN connected."
        curl_res=$(curl --silent icanhazip.com)
        curl_res_error=$(curl --silent icanhazip.com 2>&1 >/dev/null)
        loop_log_message info "curl icanhazip.com = ${curl_res}"
        loop_log_message info "curl icanhazip.com (error) = ${curl_res_error}"
    else
        loop_log_message error "NordVPN not connected."
        curl_res=$(curl --silent icanhazip.com)
        curl_res_error=$(curl --silent icanhazip.com 2>&1 >/dev/null)
        loop_log_message info "curl icanhazip.com = ${curl_res}"
        loop_log_message info "curl icanhazip.com (error) = ${curl_res_error}"

        loop_log_message info "Trying to restart NordVPN client..."
        NORDVPN_RESTARTED_FLAG=0
        for i in $(seq 1 10); do
            systemctl restart nordvpn >> ${NORDVPN_LOG_FILE}
            sleep 30
            nordvpn connect >> ${NORDVPN_LOG_FILE}
            sleep 10
            if nordvpn connect; then
                NORDVPN_RESTARTED_FLAG=1
                break
            fi
            sleep 10
        done

        if (( ${NORDVPN_RESTARTED_FLAG} == 0 )); then
            loop_log_message error "Failed to activate NordVPN. Exiting."
            exit 1
        else
            loop_log_message info "NordVPN successfully restarted."
            loop_log_message info "curl icanhazip.com = $(curl icanhazip.com)"
        fi
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
        rm "/home/${UTILITY_ACCOUNT_USERNAME}/.local/share/undetected_chromedriver/*"

    done

	
    
    # longer pause between cycles
    loop_log_message info "Starting pause for ${PAUSE_BETWEEN_CYCLES_IN_MINUTES} minutes"
	sleep $((PAUSE_BETWEEN_CYCLES_IN_MINUTES * 60))
	# then increment loop number and resume loop
	((LOOP_NUMBER += 1))
done
