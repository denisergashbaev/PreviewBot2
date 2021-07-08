#!/usr/bin/env bash
#Automating pip and virtualenv with shell scripts
#http://www.pindi.us/blog/automating-pip-and-virtualenv-shell-scripts

#make sure the script is sourced
#http://stackoverflow.com/questions/2683279/how-to-detect-if-a-script-is-being-sourced
if [[ $_ == $0 ]]; then
 echo "ERROR: script is a subshell. You need to source it instead: source $0"
 exit 1
fi


#http://stackoverflow.com/questions/192292/bash-how-best-to-include-other-scripts
source "${BASH_SOURCE%/*}/check_init.sh"

if [ ! -d "$PREVIEWBOT_HOME/venv" ]; then
    virtualenv $PREVIEWBOT_HOME/venv --no-site-packages
    echo "venv created."
fi

#http://stackoverflow.com/questions/15454174/how-can-a-shell-function-know-if-it-is-running-within-a-virtualenv
v=$(venv/bin/python -c 'import sys; print hasattr(sys, "real_prefix")')
#TODO: it seems like it stopped working ;) but it's not that bad, venv is always created
# somehow i need to navigate to the preview-bot first, otherwise it's not created (not seen in prompt)
if [[ $v == "False" ]]
then
  echo "venv already activated"
else
  echo "venv not activated. activating it"
  source $PREVIEWBOT_HOME/venv/bin/activate
fi