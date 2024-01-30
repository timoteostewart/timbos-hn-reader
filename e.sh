#!/usr/bin/env bash

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

declare -a log_files_patterns=(
    '/srv/timbos-hn-reader/logs/thnr-combined-*.log'
    '/srv/timbos-hn-reader/logs/thnr-loop-*.log'
    '/srv/timbos-hn-reader/logs/thnr-main-py-*.log'
    '/srv/timbos-hn-reader/logs/thnr-thnr-*.log'
    '/srv/timbos-hn-reader/logs/thnr-vpn-*.log'
)

for each_pattern in "${log_files_patterns[@]}"; do
    cur_log_file=$(get_last_filename "${each_pattern}")
    printf "%s\n" "${cur_log_file}"
done
