#!/usr/bin/env bash

# Script purposes:
#   - delete local cached (i.e., pickled) stories
# Script frequency:
#   - @daily via cron

# name of server this script is running on
SERVER_NAME=thnr

# THNR's base directory
BASE_DIR=/srv/timbos-hn-reader/

# name of non-root account to use to write log entries
UTILITY_ACCOUNT_USERNAME=tim

# retention settings
DAYS_TO_KEEP_CACHED_STORIES=3

# setup logging details
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
        sudo -u ${UTILITY_ACCOUNT_USERNAME} echo -e "${LOG_LINE}" >> "${LOG_FILE}"
    else
        echo -e "${LOG_LINE}" >> "${LOG_FILE}"
    fi
}

loop_log_message info "${BASH_SOURCE##*/} starting"

loop_log_message info "${BASH_SOURCE##*/} deleting cached stories older than ${DAYS_TO_KEEP_CACHED_STORIES} days"

# delete cached stories
find "${BASE_DIR}cached_stories" -maxdepth 1 -name "*.pickle" -mtime "+${DAYS_TO_KEEP_CACHED_STORIES}" -exec rm {} \;

loop_log_message info "${BASH_SOURCE##*/} exiting"
