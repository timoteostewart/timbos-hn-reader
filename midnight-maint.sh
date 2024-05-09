#!/usr/bin/env bash

# debugging switches
set -o errexit # abort on nonzero exitstatus; same as set -e
# set -o nounset   # abort on unbound variable; same as set -u
set -o pipefail # don't hide errors within pipes
# set -o xtrace    # show commands being executed; same as set -x
# set -o verbose   # verbose mode; same as set -v

source /srv/timbos-hn-reader/functions.sh
source /srv/timbos-hn-reader/thnr-common-functions.sh

if ! am-root; then
    die "Please run as root."
fi

TZ=UTC

server_name=thnr
utility_account_username=tim

project_base_dir="/srv/timbos-hn-reader/"
all_logs_dir="${project_base_dir}logs/"
CACHED_STORIES_DIR="${project_base_dir}cached_stories/"
combined_log_identifier="combined"
LOGFILE_ARCHIVE_DEST_DIR=/mnt/synology/logs/thnr2.home.arpa
LOG_PREFIX_LOCAL="midnight-maint.sh:"

# retention settings
DAYS_TO_KEEP_CACHED_STORIES=3
DAYS_TO_KEEP_LOGS=3

CUR_YEAR_AND_DOY=$(get-cur-year-and-doy)
LOOP_LOG_FILE="${all_logs_dir}${server_name}-loop-${CUR_YEAR_AND_DOY}.log"

exit_with_fail() {
    /srv/timbos-hn-reader/send-email.sh "midnight_maint.sh exited with error" "$(cat ${LOOP_LOG_FILE})"
}

trap exit_with_fail ERR

CMD_INVOCATION="$0 $@"
write-log-message loop info "${LOG_PREFIX_LOCAL} Starting with this invocation: ${CMD_INVOCATION}"

if [[ ! -d "${LOGFILE_ARCHIVE_DEST_DIR}" ]]; then
    write-log-message loop warning "${LOG_PREFIX_LOCAL} ${LOGFILE_ARCHIVE_DEST_DIR} doesn't exist!"
    exit 1
fi

# delete cached stories
write-log-message loop info "${LOG_PREFIX_LOCAL} Deleting cached stories older than ${DAYS_TO_KEEP_CACHED_STORIES} days"

num_pickle=0
while IFS= read -r file; do
    if ! rm "${file}"; then
        write-log-message loop error "${LOG_PREFIX_LOCAL} Failed to delete ${file}"
    else
        ((num_pickle += 1))
    fi
done < <(find "${CACHED_STORIES_DIR}" -maxdepth 1 -name "*.pickle" -type f -mtime "+${DAYS_TO_KEEP_CACHED_STORIES}")
write-log-message loop info "${LOG_PREFIX_LOCAL} Deleted ${num_pickle} .pickle files"

num_json=0
while IFS= read -r file; do
    if ! rm "${file}"; then
        write-log-message loop error "${LOG_PREFIX_LOCAL} Failed to delete ${file}"
    else
        ((num_json += 1))
    fi
done < <(find "${CACHED_STORIES_DIR}" -maxdepth 1 -name "*.json" -type f -mtime "+${DAYS_TO_KEEP_CACHED_STORIES}")
write-log-message loop info "${LOG_PREFIX_LOCAL} Deleted ${num_json} .json files"

# archive old logs
write-log-message loop info "${LOG_PREFIX_LOCAL} Archiving logs older than ${DAYS_TO_KEEP_LOGS} days"
# find "${all_logs_dir}" -maxdepth 1 -name "*.log" -mtime "+${DAYS_TO_KEEP_LOGS}" -exec rsync -a --no-owner --no-group --remove-source-files {} "${LOGFILE_ARCHIVE_DEST_DIR}" \;

num_logs=0
while IFS= read -r file; do
    if rsync -a --no-owner --no-group --remove-source-files "${file}" "${LOGFILE_ARCHIVE_DEST_DIR}"; then
        write-log-message loop info "${LOG_PREFIX_LOCAL} Successfully archived ${file}"
        ((num_logs += 1))
    else
        write-log-message loop error "${LOG_PREFIX_LOCAL} Failed to archive ${file}"
    fi
done < <(find "${all_logs_dir}" -maxdepth 1 -name "*.log" -type f -mtime "+${DAYS_TO_KEEP_LOGS}")
write-log-message loop info "${LOG_PREFIX_LOCAL} Archived ${num_logs} .log files"

write-log-message loop info "${LOG_PREFIX_LOCAL} Exiting"
