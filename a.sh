#!/usr/bin/env bash

# debugging switches
set -o errexit  # abort on nonzero exit status; same as set -e
# set -o nounset  # abort on unbound variable; same as set -u
set -o pipefail # don't hide errors within pipes
set -o xtrace   # show commands being executed; same as set -x
# set -o verbose  # verbose mode; same as set -v


source /srv/timbos-hn-reader/.venv/bin/activate

pip install --upgrade wheel
pip install --upgrade beautifulsoup4
pip install --upgrade boto3
pip install --upgrade goose3
#pip install --upgrade hrequests[all]
pip install --upgrade intervaltree
pip install --upgrade newspaper3k
pip install --upgrade playwright
pip install --upgrade playwright-stealth
pip install --upgrade pypdf
pip install --upgrade python-magic
pip install --upgrade pytz
pip install --upgrade PyYAML
pip install --upgrade requests
pip install --upgrade undetected_chromedriver
pip install --upgrade urllib3
pip install --upgrade Wand
