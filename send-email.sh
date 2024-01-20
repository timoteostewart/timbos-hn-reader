#!/bin/bash

recipient="timoteostewart1977@gmail.com"
sender="timoteostewart1977@gmail.com"
subject="$1"
body="$2"

printf "To: ${recipient}\nFrom: ${sender}\nSubject: ${subject}\n\n${body}\n" | sendmail -t
