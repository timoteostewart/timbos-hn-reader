#!/usr/bin/env bash

alert_email=$(cat /srv/timbos-hn-reader/secret_alert_email.txt)

recipient="${alert_email}"
sender="${alert_email}"
subject="$1"
body="$2"

{
    echo "To: ${recipient}"
    echo "From: ${sender}"
    echo "Subject: ${subject}"
    echo
    echo "${body}"
} | sendmail -t
