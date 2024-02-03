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
CACHED_STORIES_DIR="${BASE_DIR}cached_stories/"
COMBINED_LOG_IDENTIFIER="combined"
LOGFILE_ARCHIVE_DEST_DIR=/mnt/synology/logs/thnr2.home.arpa
LOG_PREFIX_LOCAL="midnight_maint.sh:"

# retention settings
DAYS_TO_KEEP_CACHED_STORIES=3
DAYS_TO_KEEP_LOGS=3

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

write_log_message() {
    # usage: write_log_message LOG_IDENTIFIER LEVEL MESSAGE
    local CUR_YEAR_AND_DOY=$(get_cur_year_and_doy)
    local LOG_IDENTIFIER="$1"

    local LOG_FILE="${ALL_LOGS_PATH}${SERVER_NAME}-${LOG_IDENTIFIER}-${CUR_YEAR_AND_DOY}.log"
    local COMBINED_LOG_FILE="${ALL_LOGS_PATH}${SERVER_NAME}-${COMBINED_LOG_IDENTIFIER}-${CUR_YEAR_AND_DOY}.log"

    ensure_correct_file_owner "${LOG_FILE}"
    ensure_correct_file_owner "${COMBINED_LOG_FILE}"

    echo "${COMBINED_LOG_FILE}"

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

CMD_INVOCATION="$0 $@"
write_log_message loop info "${LOG_PREFIX_LOCAL} Starting with this invocation: ${CMD_INVOCATION}"

if [[ ! -d "${LOGFILE_ARCHIVE_DEST_DIR}" ]]; then
    write_log_message loop warning "${LOG_PREFIX_LOCAL} ${LOGFILE_ARCHIVE_DEST_DIR} doesn't exist!"
    exit 1
fi

# delete cached stories
write_log_message loop info "${LOG_PREFIX_LOCAL} Deleting cached stories older than ${DAYS_TO_KEEP_CACHED_STORIES} days"
find "${CACHED_STORIES_DIR}" -maxdepth 1 -name "*.pickle" -mtime "+${DAYS_TO_KEEP_CACHED_STORIES}" -exec rm {} \;
find "${CACHED_STORIES_DIR}" -maxdepth 1 -name "*.json" -mtime "+${DAYS_TO_KEEP_CACHED_STORIES}" -exec rm {} \;

# archive old logs
write_log_message loop info "${LOG_PREFIX_LOCAL} Archiving logs older than ${DAYS_TO_KEEP_LOGS} days"
find "${ALL_LOGS_PATH}" -maxdepth 1 -name "*.log" -mtime "+${DAYS_TO_KEEP_LOGS}" -exec rsync -a --no-owner --no-group --remove-source-files {} "${LOGFILE_ARCHIVE_DEST_DIR}" \;

write_log_message loop info "${LOG_PREFIX_LOCAL} Exiting"
