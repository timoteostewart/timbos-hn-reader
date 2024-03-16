#!/usr/bin/env bash

# debugging switches
# set -o errexit   # abort on nonzero exitstatus; same as set -e
# set -o nounset   # abort on unbound variable; same as set -u
set -o pipefail  # don't hide errors within pipes
# set -o xtrace    # show commands being executed; same as set -x
# set -o verbose   # verbose mode; same as set -v

source /srv/timbos-hn-reader/functions.sh
source /srv/timbos-hn-reader/thnr-common-functions.sh

project_base_dir=/srv/timbos-hn-reader/
all_logs_dir="${project_base_dir}logs/"
combined_log_identifier="combined"
server_name=thnr
TZ=UTC
utility_account_username=tim
log_prefix_local="host-stats.sh:"

# more settings
seconds_between_reports=1


while true; do
    # cpu stats
    nproc_output=$(nproc)
    cpu_load_pct=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
    proc_loadavg_1min=$(awk '{print $1}' /proc/loadavg)
    proc_loadavg_5min=$(awk '{print $2}' /proc/loadavg)
    proc_loadavg_15min=$(awk '{print $3}' /proc/loadavg)

    # ram stats
    ram_in_use_mb=$(free -m | grep Mem | awk '{print $3}')
    ram_total_mb=$(free -m | grep Mem | awk '{print $2}')

    # network stats
    network_io_raw=$(sar -n DEV 1 1)
    network_io_rx_kBps=$(echo "${network_io_raw}" | grep 'Average.*eth0' | awk '{print $5}')
    network_io_tx_kBps=$(echo "${network_io_raw}" | grep 'Average.*eth0' | awk '{print $6}')

    logline="nproc_output=${nproc_output}, \
cpu_load_pct=${cpu_load_pct}, \
proc_loadavg_1min=${proc_loadavg_1min}, \
proc_loadavg_5min=${proc_loadavg_5min}, \
proc_loadavg_15min=${proc_loadavg_15min}, \
ram_in_use_mb=${ram_in_use_mb}, \
ram_total_mb=${ram_total_mb}, \
network_io_rx_kBps=${network_io_rx_kBps}, \
network_io_tx_kBps=${network_io_tx_kBps}"

    write-log-message host-stats info "${logline}" "false"

    sleep ${seconds_between_reports}
done
