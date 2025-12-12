#!/usr/bin/env bash

# This script starts the LLM control voice server with Python 3.12
# Updated for Python 3.12 migration
# Memory monitoring has been disabled - scripts do not exist

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${LLM_CONTROL_ROOT:-$SCRIPT_DIR}"

# Change to the project directory
cd "$PROJECT_ROOT" || {
    echo "ERROR: Could not change to project directory: $PROJECT_ROOT"
    exit 1
}

# Activate Python 3.12 virtual environment
VENV_PATH="${LLM_CONTROL_VENV:-$PROJECT_ROOT/venv-py312}"
if [ -f "$VENV_PATH/bin/activate" ]; then
    source "$VENV_PATH/bin/activate"
else
    echo "ERROR: Virtual environment not found at: $VENV_PATH"
    echo "Set LLM_CONTROL_VENV environment variable to specify venv path"
    exit 1
fi

# Start the server with structured logging enabled
echo "Starting voice command server with Python 3.12..."
export STRUCTURED_USAGE_LOGS=true
python -m llm_control voice-server \
  --whisper-model large \
  --ssl \
  --ollama-model gemma3:12b \
  --disable-translation
