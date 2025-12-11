#!/usr/bin/env bash

# This script starts the LLM control voice server with Python 3.12
# Updated for Python 3.12 migration
# Memory monitoring has been disabled - scripts do not exist

# Change to the project directory
cd /home/nava/Descargas/llm-control

# Activate Python 3.12 virtual environment
source /home/nava/Descargas/llm-control/venv-py312/bin/activate

# Start the server with structured logging enabled
echo "Starting voice command server with Python 3.12..."
export STRUCTURED_USAGE_LOGS=true
python -m llm_control voice-server \
  --whisper-model large \
  --ssl \
  --ollama-model gemma3:12b \
  --disable-translation
