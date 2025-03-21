#!/bin/bash
# Script to install additional dependencies in the Docker container

set -e  # Exit on error

echo "=========================================================="
echo "    Installing Additional Dependencies in Container       "
echo "=========================================================="
echo ""

# Check if the container is running
if ! docker ps | grep -q voice-control-server; then
    echo "Error: Voice Control Server container is not running."
    echo "Please start it first with: ../tools/start-voice-control.sh"
    exit 1
fi

# Install additional packages for screenshots
echo "Installing additional packages for screenshots..."
docker exec -i voice-control-server bash -c '
set -e
apt-get update
apt-get install -y gnome-screenshot python3-pil python3-pil.imagetk
pip install --upgrade pillow pyautogui
# Install additional X11 packages
apt-get install -y x11-apps xvfb xserver-xorg-video-dummy
# Reinstall pyautogui with latest version
pip install --force-reinstall pyautogui
# Debug info
python3 -c "import pyautogui; print(\"PyAutoGUI version:\", pyautogui.__version__); print(\"Backend:\", pyautogui._pyautogui_x11.__name__ if hasattr(pyautogui, \"_pyautogui_x11\") else \"Unknown\")"
'

echo ""
echo "Creating a simple test script to verify screenshot functionality..."
docker exec -i voice-control-server bash -c 'cat > /app/test_screenshot.py << EOF
import time
import os
import sys

print("Python version:", sys.version)
print("DISPLAY:", os.environ.get("DISPLAY"))
print("XAUTHORITY:", os.environ.get("XAUTHORITY"))

try:
    print("Waiting 2 seconds before screenshot...")
    time.sleep(2)
    
    print("Importing pyautogui...")
    import pyautogui
    print("PyAutoGUI version:", pyautogui.__version__)
    
    print("Taking screenshot...")
    screenshot = pyautogui.screenshot()
    print("Screenshot dimensions:", screenshot.size)
    
    print("Saving screenshot...")
    screenshot.save("/tmp/screenshot_test.png")
    print("Screenshot saved to /tmp/screenshot_test.png")
    
    # Check if file exists and has size
    if os.path.exists("/tmp/screenshot_test.png"):
        print("File exists, size:", os.path.getsize("/tmp/screenshot_test.png"), "bytes")
    else:
        print("File does not exist!")
        
except Exception as e:
    print("Error:", str(e))
EOF'

echo "Running test script..."
docker exec -i voice-control-server bash -c 'cd /app && python3 test_screenshot.py'

echo ""
echo "Testing with a simple screenshot command..."
docker exec -i voice-control-server bash -c 'export DISPLAY=:1 && scrot -z /tmp/scrot_test.png && echo "scrot screenshot saved" || echo "scrot failed"'

echo ""
echo "Checking installed packages:"
docker exec -i voice-control-server bash -c 'dpkg -l | grep -E "scrot|image|x11|xvfb|python3-pil"'

echo ""
echo "Dependencies installation complete!"
echo "Please try running your command again."
echo "==========================================================" 