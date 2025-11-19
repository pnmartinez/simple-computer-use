#!/bin/bash
# Entrypoint script for the Voice Control Server Docker container

set -e  # Exit on error

echo "=========== Voice Control Server starting up ==========="

# Add PyAutoGUI extensions - register moveRelative
echo "Setting up PyAutoGUI extensions..."
python3 -c '
try:
    import pyautogui
    if not hasattr(pyautogui, "moveRelative"):
        pyautogui.moveRelative = pyautogui.move
        print("Successfully added moveRelative function to PyAutoGUI")
    else:
        print("moveRelative function already exists in PyAutoGUI")
except ImportError as e:
    print(f"Failed to import PyAutoGUI: {e}")
except Exception as e:
    print(f"Error setting up PyAutoGUI extensions: {e}")
'

# Create runtime directories
mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix

# Handle Xauthority properly - set it to /tmp/.Xauthority rather than ~/.Xauthority
export XAUTHORITY=/tmp/.Xauthority
touch $XAUTHORITY
chmod 777 $XAUTHORITY
echo "XAUTHORITY set to $XAUTHORITY"

# Create root's .Xauthority file as well (for backward compatibility)
touch /root/.Xauthority
chmod 600 /root/.Xauthority
cp $XAUTHORITY /root/.Xauthority

# Start Xvfb
echo "Starting Xvfb..."
Xvfb :1 -screen 0 1280x1024x24 -ac +extension GLX +render -noreset &
sleep 2

# Make sure display variable is set
export DISPLAY=:1
echo "DISPLAY set to $DISPLAY"

# Configure X11 utilities
echo "Configuring X11 utilities..."
xauth generate $DISPLAY . trusted
xhost +local:root || echo "xhost command failed, but continuing..."

# Start a simple window manager in the background to help with window management
fluxbox &

# Start VNC server (optional)
x11vnc -display :1 -nopw -forever -quiet &

# Test screenshot capability
echo "Testing screenshot capability with PyAutoGUI..."
python3 -c "
import time
time.sleep(2)  # Give X server time to start
try:
    import pyautogui
    screenshot = pyautogui.screenshot()
    print('Screen size:', screenshot.size)
    screenshot.save('/tmp/test_screenshot.png')
    print('Screenshot test SUCCESSFUL')
    print('Screenshot saved to /tmp/test_screenshot.png')
except Exception as e:
    print('Screenshot test FAILED: ' + str(e))
    # Try to diagnose the issue
    import os
    print('DISPLAY =', os.environ.get('DISPLAY'))
    print('XAUTHORITY =', os.environ.get('XAUTHORITY'))
    print('Xauthority exists:', os.path.exists(os.environ.get('XAUTHORITY', '')))
    print('~/.Xauthority exists:', os.path.exists(os.path.expanduser('~/.Xauthority')))
"

# Ensure python-xlib and other packages are properly installed
echo "Ensuring required Python packages are installed..."
pip install --upgrade python-xlib pillow pyautogui || echo "Warning: Failed to upgrade Python packages"

# Check if Ollama host is set, default to localhost if not
if [ -z "$OLLAMA_HOST" ]; then
    export OLLAMA_HOST="http://localhost:11434"
    echo "OLLAMA_HOST not set, defaulting to $OLLAMA_HOST"
else
    echo "OLLAMA_HOST set to $OLLAMA_HOST"
fi

# Check if model is set, default to llama3.1 if not
if [ -z "$OLLAMA_MODEL" ]; then
    export OLLAMA_MODEL="llama3.1"
    echo "OLLAMA_MODEL not set, defaulting to $OLLAMA_MODEL"
else
    echo "OLLAMA_MODEL set to $OLLAMA_MODEL"
fi

# Wait for Ollama service to be available
echo "Waiting for Ollama service at $OLLAMA_HOST..."
max_retries=30
retry_count=0
until curl -s "$OLLAMA_HOST/api/version" > /dev/null || [ $retry_count -ge $max_retries ]; do
    echo "Attempt $((retry_count+1))/$max_retries: Ollama service not available, retrying in 5 seconds..."
    sleep 5
    retry_count=$((retry_count+1))
done

if [ $retry_count -ge $max_retries ]; then
    echo "ERROR: Could not connect to Ollama service after $max_retries attempts."
    echo "Please make sure Ollama is running at $OLLAMA_HOST"
    exit 1
fi

# Verify model availability
echo "Checking if model $OLLAMA_MODEL is available in Ollama..."
if ! curl -s "$OLLAMA_HOST/api/tags" | grep -q "\"name\":\"$OLLAMA_MODEL\""; then
    echo "WARNING: Model $OLLAMA_MODEL does not appear to be available in Ollama."
    echo "The voice control server may not work correctly."
    echo "You can pull the model with: ollama pull $OLLAMA_MODEL"
fi

# Print environment variables for debugging
echo "Environment variables:"
echo "DISPLAY=$DISPLAY"
echo "XAUTHORITY=$XAUTHORITY"
echo "HOME=$HOME"
echo "OLLAMA_HOST=$OLLAMA_HOST"
echo "OLLAMA_MODEL=$OLLAMA_MODEL"

# Start the Voice Control Server
echo "Starting Voice Control Server..."
cd /app
exec python3 -m llm_control voice-server 