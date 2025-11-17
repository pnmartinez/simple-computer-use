#!/usr/bin/env bash

# This script starts the LLM control voice server with memory monitoring
# It helps diagnose memory leaks by tracking RAM usage across operations

# This is a fixed version of the start-llm-control.sh script
# Create this file and then run:
# cp fix_start_script.sh /home/nava/start-llm-control.sh
# chmod +x /home/nava/start-llm-control.sh
# systemctl --user restart llm-control.service

# Make sure the path below matches your system
source /home/nava/miniconda3/etc/profile.d/conda.sh

# # Set up memory logging directory
# LOGS_DIR="/home/nava/memory_logs"
# mkdir -p "$LOGS_DIR"
# echo "Memory logs will be saved to $LOGS_DIR"

# Activate conda environment
conda activate autogui

# Change to the project directory if needed
cd /home/nava/Descargas/llm-control

# Run the server with memory tracking via environment variables
# export LOGS_DIR="$LOGS_DIR"
# export WHISPER_MEMORY_CSV="$LOGS_DIR/whisper_memory_stats.csv"
# export PHI3_MEMORY_CSV="$LOGS_DIR/phi3_memory_stats.csv"
# export YOLO_MEMORY_CSV="$LOGS_DIR/yolo_memory_stats.csv"
# export GLOBAL_MEMORY_CSV="$LOGS_DIR/global_memory_stats.csv"

# Start the background memory monitor
# echo "Starting background memory monitor..."
# python scripts/memory_monitor.py --interval 1 --duration 86400 --output "$LOGS_DIR/background_memory.json" &
# MONITOR_PID=$!

# Function to clean up on exit
# cleanup() {
#   echo "Stopping memory monitor..."
#   kill $MONITOR_PID 2>/dev/null || true
#   echo "Running memory analysis..."
#   python scripts/analyze_memory_logs.py \
#     --output-dir "$LOGS_DIR/analysis" \
#     --whisper-log "$WHISPER_MEMORY_CSV" \
#     --phi3-log "$PHI3_MEMORY_CSV" \
#     --yolo-log "$YOLO_MEMORY_CSV" \
#     --global-log "$GLOBAL_MEMORY_CSV"
#   echo "Cleanup complete"
# }

# Register cleanup function
# trap cleanup EXIT

# Start the server with the same parameters as before
# NOTE: Removed the --logs-dir parameter as it's not supported
echo "Starting voice command server" # with memory tracking...
python -m llm_control voice-server \
  --whisper-model large \
  --ssl \
  --ollama-model gemma3:12b \
  --disable-translation

# If the server process exits, also clean up the monitor
# cleanup

# Note: --disable-translation was removed as it's no longer a valid argument
# The new command-line interface simplifies the arguments 
