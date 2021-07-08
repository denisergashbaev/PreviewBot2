#!/usr/bin/env bash
#http://stackoverflow.com/questions/59895/can-a-bash-script-tell-which-directory-it-is-stored-in
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
#http://stackoverflow.com/questions/3601515/how-to-check-if-a-variable-is-set-in-bash
if [ -z "$PREVIEWBOT_HOME" ]; then
    #export PREVIEWBOT_HOME=$DIR
    echo "export PREVIEWBOT_HOME=$DIR" >> ~/.bashrc
    #http://stackoverflow.com/questions/5055059/reload-environment-variables-in-a-bash-script
    PS1='$ '
    source ~/.bashrc
fi
# todo: if i run  run init.sh on the prod server, the $PREVIEWBOT_HOME is not visible in the beginning, although it's written
# to ~/.bashrc. i need to manually source it first to see it in the terminal
echo "Your PREVIEWBOT_HOME environment variable is set to $PREVIEWBOT_HOME"
