#!/usr/bin/env bash

# Script para iniciar el servicio con logging estructurado habilitado

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${LLM_CONTROL_ROOT:-$SCRIPT_DIR}"

# Load conda
CONDA_HOME="${CONDA_HOME:-$HOME/miniconda3}"
if [ -n "$CONDA_PREFIX" ]; then
    # Conda is already initialized
    :
elif [ -f "$CONDA_HOME/etc/profile.d/conda.sh" ]; then
    source "$CONDA_HOME/etc/profile.d/conda.sh"
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
else
    echo "ERROR: Could not find conda.sh"
    echo "Set CONDA_HOME environment variable to specify conda installation path"
    exit 1
fi

conda activate autogui

cd "$PROJECT_ROOT" || {
    echo "ERROR: Could not change to project directory: $PROJECT_ROOT"
    exit 1
}

export STRUCTURED_USAGE_LOGS=true
echo "Iniciando servicio con STRUCTURED_USAGE_LOGS=true"

python -m llm_control voice-server \
  --whisper-model large \
  --ssl \
  --ollama-model gemma3:12b \
  --disable-translation

