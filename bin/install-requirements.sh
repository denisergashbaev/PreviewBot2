#!/usr/bin/env bash
#http://stackoverflow.com/questions/192292/bash-how-best-to-include-other-scripts
source "${BASH_SOURCE%/*}/check_init.sh"
echo "installing requirements..."
# --no-cache-dir is used to prevent memory error on server
# see http://stackoverflow.com/questions/29466663/memory-error-while-using-pip-install-matplotlib
sudo venv/bin/pip --no-cache-dir install -r preview-bot/requirements.txt

echo "completed installing requirements"
