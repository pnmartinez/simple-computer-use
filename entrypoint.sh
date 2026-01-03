#!/bin/bash

set -e  # Exit on error

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting LLM Control Voice Server container..."

# Ensure required directories exist with proper permissions
mkdir -p /app/data /app/screenshots /app/logs

# Check if we should skip X11 setup for testing
if [ "${SKIP_X11_SETUP:-false}" = "true" ]; then
    log "Skipping X11 setup for testing..."
    export DISPLAY=:99  # Dummy display
else
    # Set X11 authority file
    export XAUTHORITY=/tmp/.Xauthority
    mkdir -p /tmp/.Xauthority
    touch "$XAUTHORITY"
    chmod 777 /tmp/.Xauthority 2>/dev/null || true

    # Try to find an available display number or use host X server
    find_available_display() {
        for display_num in {1..10}; do
            if ! ps aux | grep -q "X.*:$display_num"; then
                echo ":$display_num"
                return 0
            fi
        done
        # If no display available, try to use host display if available
        if [ -n "$HOST_DISPLAY" ]; then
            echo "$HOST_DISPLAY"
        else
            echo ":99"  # fallback
        fi
    }

    # Try to use host X server first, fallback to Xvfb
    if [ -S "/tmp/.X11-unix/X0" ] && [ -n "$DISPLAY" ]; then
        log "Using host X server at $DISPLAY"
        # Copy host Xauthority if available
        if [ -f "$HOME/.Xauthority" ]; then
            cp "$HOME/.Xauthority" /tmp/.Xauthority 2>/dev/null || true
            chmod 777 /tmp/.Xauthority
        fi
    else
        log "Starting Xvfb display server..."
        DISPLAY=$(find_available_display)
        export DISPLAY

        log "Using display $DISPLAY"
        Xvfb $DISPLAY -screen 0 1280x1024x24 -ac +extension GLX +render -noreset &
        Xvfb_pid=$!

        # Wait for Xvfb to be ready
        sleep 3

        # Verify Xvfb is running
        if ! kill -0 $Xvfb_pid 2>/dev/null; then
            log "ERROR: Xvfb failed to start on display $DISPLAY"
            exit 1
        fi
    fi

    log "DISPLAY set to $DISPLAY"

    # Configure X11 access
    log "Configuring X11 access..."
    xhost +local:appuser || log "Warning: xhost command failed, but continuing..."

    # Start window manager in background
    log "Starting window manager..."
    fluxbox &
    fluxbox_pid=$!

    # Start VNC server for remote access (optional)
    log "Starting VNC server..."
    x11vnc -display :1 -nopw -forever -quiet &
    x11vnc_pid=$!

    # Wait a bit for services to initialize
    sleep 2

    # Test screenshot capability
    log "Testing screenshot capability..."
    if python3 -c "
    import sys
    import time
    time.sleep(2)
    try:
        import pyautogui
        screenshot = pyautogui.screenshot()
        print(f'Screen size: {screenshot.size}')
        screenshot.save('/tmp/test_screenshot.png')
        print('Screenshot test successful')
        sys.exit(0)
    except Exception as e:
        print(f'Screenshot test failed: {e}')
        sys.exit(1)
    "; then
        log "Screenshot capability verified"
    else
        log "Warning: Screenshot test failed, but continuing..."
    fi
fi

# Set environment variables with defaults
export OLLAMA_HOST="${OLLAMA_HOST:-http://ollama:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.1}"
export WHISPER_MODEL_SIZE="${WHISPER_MODEL_SIZE:-large}"
export DEFAULT_LANGUAGE="${DEFAULT_LANGUAGE:-es}"
export ENABLE_TRANSLATION="${ENABLE_TRANSLATION:-true}"
export SCREENSHOT_ENABLED="${SCREENSHOT_ENABLED:-true}"

log "Environment configuration:"
log "  DISPLAY=$DISPLAY"
log "  XAUTHORITY=$XAUTHORITY"
log "  OLLAMA_HOST=$OLLAMA_HOST"
log "  OLLAMA_MODEL=$OLLAMA_MODEL"
log "  WHISPER_MODEL_SIZE=$WHISPER_MODEL_SIZE"
log "  DEFAULT_LANGUAGE=$DEFAULT_LANGUAGE"

# Wait for Ollama service (if configured)
if [[ "$OLLAMA_HOST" == http://ollama:* ]]; then
    log "Waiting for Ollama service at $OLLAMA_HOST..."
    max_retries=60
    retry_count=0
    until curl -s --max-time 5 "$OLLAMA_HOST/api/version" > /dev/null 2>&1 || [ $retry_count -ge $max_retries ]; do
        echo "Attempt $((retry_count+1))/$max_retries: Ollama service not available, retrying in 5 seconds..."
        sleep 5
        retry_count=$((retry_count+1))
    done

    if [ $retry_count -ge $max_retries ]; then
        log "WARNING: Could not connect to Ollama service after $max_retries attempts."
        log "The voice control server may not work correctly without Ollama."
        log "Please ensure Ollama is running and accessible."
    else
        log "Ollama service is available"

        # Check if model is available
        if curl -s --max-time 5 "$OLLAMA_HOST/api/tags" | grep -q "\"name\":\"$OLLAMA_MODEL\""; then
            log "Model $OLLAMA_MODEL is available in Ollama"
        else
            log "WARNING: Model $OLLAMA_MODEL not found in Ollama."
            log "The voice control server may not work correctly."
            log "You can pull the model with: docker-compose exec ollama ollama pull $OLLAMA_MODEL"
        fi
    fi
else
    log "Using external Ollama host: $OLLAMA_HOST"
fi

# Function to cleanup background processes on exit
cleanup() {
    log "Shutting down services..."
    kill $Xvfb_pid $fluxbox_pid $x11vnc_pid 2>/dev/null || true
    exit 0
}

# Set trap for cleanup
trap cleanup SIGTERM SIGINT

log "Starting LLM Control Voice Server..."
exec python3 -m llm_control voice-server
