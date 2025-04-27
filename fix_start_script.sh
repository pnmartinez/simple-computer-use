#!/usr/bin/env bash

# This is a fixed version of the start-llm-control.sh script
# Create this file and then run:
# cp fix_start_script.sh /home/nava/start-llm-control.sh
# chmod +x /home/nava/start-llm-control.sh
# systemctl --user restart llm-control.service

# Make sure the path below matches your system
source /home/nava/miniconda3/etc/profile.d/conda.sh

conda activate autogui
python -m llm_control voice-server --whisper-model large --ssl

# Note: --disable-translation was removed as it's no longer a valid argument
# The new command-line interface simplifies the arguments 