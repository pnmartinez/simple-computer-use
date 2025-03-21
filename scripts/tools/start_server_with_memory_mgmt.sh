#!/bin/bash
# Script to start the LLM PC Control server with memory management
# This clears GPU memory before starting the server

set -e  # Exit on error

# Default variables
MODEL_SIZE="base"
PORT=5000
LANGUAGE="es"
CLEAR_GPU=true
USE_CPU=false

# Print banner
echo "=========================================================="
echo "  LLM PC Control Server with Memory Management"
echo "=========================================================="

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --model)
      MODEL_SIZE="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --language)
      LANGUAGE="$2"
      shift 2
      ;;
    --no-clear-gpu)
      CLEAR_GPU=false
      shift
      ;;
    --use-cpu)
      USE_CPU=true
      export CUDA_VISIBLE_DEVICES=-1  # Disable CUDA
      shift
      ;;
    --help)
      echo "Usage: $0 [options]"
      echo ""
      echo "Options:"
      echo "  --model MODEL      Whisper model size (tiny, base, small, medium, large)"
      echo "  --port PORT        Port to use for the server"
      echo "  --language LANG    Language code for speech recognition"
      echo "  --no-clear-gpu     Don't clear GPU memory before starting"
      echo "  --use-cpu          Force CPU usage (disable GPU)"
      echo "  --help             Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

echo "Using model size: $MODEL_SIZE"
echo "Using port: $PORT"
echo "Using language: $LANGUAGE"
echo ""

# Check for required Python packages
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not found. Please install Python 3."
    exit 1
fi

# Clear GPU memory if requested
if $CLEAR_GPU && ! $USE_CPU; then
    echo "Clearing GPU memory before starting server..."
    if [ -f "../setup/clear_gpu_memory.py" ]; then
        python3 ../setup/clear_gpu_memory.py --all
    else
        echo "GPU memory clearing script not found. Skipping."
    fi
    echo ""
fi

# Check if we're forcing CPU usage
if $USE_CPU; then
    echo "Forcing CPU usage (GPU disabled)"
    export CUDA_VISIBLE_DEVICES=-1
fi

# Configure PyTorch memory management
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"

# Start the server
echo "Starting server..."
echo "python -m llm_control.cli_server --host 0.0.0.0 --port $PORT --whisper-model $MODEL_SIZE --android-compat --use-rest-api --language $LANGUAGE"
python -m llm_control.cli_server --host 0.0.0.0 --port $PORT --whisper-model $MODEL_SIZE --android-compat --use-rest-api --language $LANGUAGE 