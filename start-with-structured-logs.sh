#!/usr/bin/env bash

# Script para iniciar el servicio con logging estructurado habilitado
source /home/nava/miniconda3/etc/profile.d/conda.sh
conda activate autogui

cd /home/nava/Descargas/llm-control

export STRUCTURED_USAGE_LOGS=true
echo "Iniciando servicio con STRUCTURED_USAGE_LOGS=true"

python -m llm_control voice-server \
  --whisper-model large \
  --ssl \
  --ollama-model gemma3:12b \
  --disable-translation

