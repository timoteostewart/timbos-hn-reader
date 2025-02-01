#!/usr/bin/env bash

# debugging switches
set -o errexit  # abort on nonzero exit status; same as set -e
# set -o nounset  # abort on unbound variable; same as set -u
set -o pipefail # don't hide errors within pipes
set -o xtrace   # show commands being executed; same as set -x
# set -o verbose  # verbose mode; same as set -v


source /srv/timbos-hn-reader/.venv/bin/activate

pip install wheel
pip install beautifulsoup4
pip install boto3
pip install goose3
pip install hrequests[all]
pip install intervaltree
#pip install newspaper3k
#pip install playwright
#pip install playwright-stealth
pip install pypdf
pip install python-magic
pip install pytz
pip install PyYAML
pip install requests
pip install undetected_chromedriver
pip install urllib3
pip install Wand
