#!/bin/bash

export LC_MESSAGES=C

grep -Hm1 '^' < "${1}" | grep -q '^Binary'

