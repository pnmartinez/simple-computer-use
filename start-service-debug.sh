#!/usr/bin/env bash

# Script para iniciar el servicio con logging estructurado y captura de errores
LOG_FILE="/tmp/llm-control-debug.log"

echo "=== Iniciando servicio LLM Control $(date) ===" | tee -a "$LOG_FILE"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${LLM_CONTROL_ROOT:-$SCRIPT_DIR}"

# Cargar conda
CONDA_HOME="${CONDA_HOME:-$HOME/miniconda3}"
if [ -n "$CONDA_PREFIX" ]; then
    # Conda is already initialized
    echo "Conda ya está inicializado" | tee -a "$LOG_FILE"
elif [ -f "$CONDA_HOME/etc/profile.d/conda.sh" ]; then
    source "$CONDA_HOME/etc/profile.d/conda.sh"
    echo "Conda cargado desde $CONDA_HOME" | tee -a "$LOG_FILE"
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
    echo "Conda cargado desde $HOME/anaconda3" | tee -a "$LOG_FILE"
else
    echo "ERROR: No se encontró conda.sh" | tee -a "$LOG_FILE"
    echo "Set CONDA_HOME environment variable to specify conda installation path" | tee -a "$LOG_FILE"
    exit 1
fi

# Activar entorno
conda activate autogui 2>&1 | tee -a "$LOG_FILE"
if [ $? -ne 0 ]; then
    echo "ERROR: No se pudo activar el entorno conda 'autogui'" | tee -a "$LOG_FILE"
    exit 1
fi

echo "Entorno conda activado" | tee -a "$LOG_FILE"

# Cambiar al directorio del proyecto
cd "$PROJECT_ROOT" || {
    echo "ERROR: No se pudo cambiar al directorio del proyecto: $PROJECT_ROOT" | tee -a "$LOG_FILE"
    exit 1
}

# Configurar variable de entorno para logging estructurado
export STRUCTURED_USAGE_LOGS=true
echo "STRUCTURED_USAGE_LOGS=true configurado" | tee -a "$LOG_FILE"

# Verificar que Python puede importar el módulo
python -c "import llm_control" 2>&1 | tee -a "$LOG_FILE"
if [ $? -ne 0 ]; then
    echo "ERROR: No se pudo importar llm_control" | tee -a "$LOG_FILE"
    exit 1
fi

echo "Iniciando servidor..." | tee -a "$LOG_FILE"

# Ejecutar el servidor
python -m llm_control voice-server \
  --whisper-model large \
  --ssl \
  --ollama-model gemma3:12b \
  --disable-translation 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=$?
echo "=== Servidor terminó con código $EXIT_CODE $(date) ===" | tee -a "$LOG_FILE"
exit $EXIT_CODE

