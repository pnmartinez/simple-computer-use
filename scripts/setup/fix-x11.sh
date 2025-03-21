#!/bin/bash
# Script to fix X11 authentication issues in the Docker container

set -e  # Exit on error

echo "=========================================================="
echo "    Fixing X11 Authentication for Docker Container        "
echo "=========================================================="
echo ""

# Ensure Docker is running
if ! docker ps &>/dev/null; then
    echo "Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Check if the container is running
if ! docker ps | grep -q voice-control-server; then
    echo "Error: Voice Control Server container is not running."
    echo "Please start it first with: ../tools/start-voice-control.sh"
    exit 1
fi

# Fix host X11 permissions
echo "Setting up X11 permissions on host..."
xhost + &>/dev/null || echo "Warning: xhost command failed"

# Get host display
HOST_DISPLAY=${DISPLAY:-:0}
echo "Host display: $HOST_DISPLAY"

# Create temporary Xauthority file for Docker
echo "Creating Xauthority file for Docker..."
XAUTH_FILE=$(mktemp)
touch "$XAUTH_FILE"
xauth nlist "$HOST_DISPLAY" | sed -e 's/^..../ffff/' | xauth -f "$XAUTH_FILE" nmerge -

# Copy the Xauthority file to the container
echo "Copying Xauthority file to container..."
docker cp "$XAUTH_FILE" voice-control-server:/tmp/.Xauthority
docker exec -i voice-control-server chmod 777 /tmp/.Xauthority

# Clean up temporary file
rm "$XAUTH_FILE"

# Execute fix script inside container
echo "Running X11 fix inside container..."
docker exec -i voice-control-server bash -c '
echo "Setting up X11 environment inside container..."
export DISPLAY=:1
export XAUTHORITY=/tmp/.Xauthority

# Create directories if needed
mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix

# Restart Xvfb with proper configuration
killall Xvfb 2>/dev/null || true
Xvfb :1 -screen 0 1280x1024x24 -ac +extension GLX +render -noreset &
sleep 2

# Set up X11 permissions
xhost +local:root 2>/dev/null || echo "Warning: xhost failed"

# Test screenshot capability
echo "Testing screenshot capability..."
python3 -c "
try:
    import pyautogui
    screenshot = pyautogui.screenshot()
    screenshot.save(\"/tmp/test_screenshot.png\")
    print(\"Screenshot test successful\")
except Exception as e:
    print(f\"Screenshot test failed: {str(e)}\")
"

# Check if screenshot was created
if [ -f "/tmp/test_screenshot.png" ]; then
    echo "Screenshot created successfully."
    ls -l /tmp/test_screenshot.png
else
    echo "Failed to create screenshot."
fi
'

echo ""
echo "X11 fix complete!"
echo "Please try running your command again."
echo "==========================================================" 