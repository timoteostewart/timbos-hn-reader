#!/usr/bin/env bash

recipient="timoteostewart1977@gmail.com"
sender="timoteostewart1977@gmail.com"
subject="$1"
body="$2"

{
    echo "To: ${recipient}"
    echo "From: ${sender}"
    echo "Subject: ${subject}"
    echo
    echo "${body}"
} | sendmail -t
