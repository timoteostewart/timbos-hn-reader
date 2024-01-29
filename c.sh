#!/bin/bash


get_cur_year_and_doy() {
    TZ=UTC
    local CUR_YEAR=$(printf '%(%Y)T' -1)
    local CUR_DOY=$(printf '%(%j)T' -1)
    local CUR_DOY_ZEROS="00${CUR_DOY}"
    local CUR_DOY_PADDED="${CUR_DOY_ZEROS: -3}"
    local CUR_YEAR_AND_DOY="${CUR_YEAR}-${CUR_DOY_PADDED}"
    echo "${CUR_YEAR_AND_DOY}"
}


printf "$(get_cur_year_and_doy)\n"

