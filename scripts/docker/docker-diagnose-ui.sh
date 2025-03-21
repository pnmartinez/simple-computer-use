#!/bin/bash
# Script to diagnose UI detection issues in the Docker container

set -e  # Exit on error

echo "=========================================================="
echo "    UI Detection Diagnosis for Docker Container          "
echo "=========================================================="
echo ""

# Check if Docker is running
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

# Check X11 configuration
echo "Checking X11 configuration..."
docker exec -i voice-control-server bash -c '
export DISPLAY=:1
echo "DISPLAY: $DISPLAY"
echo "XAUTHORITY: $XAUTHORITY"
echo "X11 processes:" 
ps aux | grep -E "X|xvfb|vnc" | grep -v grep

echo "Testing xdpyinfo..."
xdpyinfo | head -10 || echo "xdpyinfo failed"

echo "Testing xrandr..."
xrandr || echo "xrandr failed"

echo "Checking virtual display frames..."
ls -la /tmp/.X11-unix/ || echo "No X11 socket files"
'

# Test screenshot capability
echo -e "\nTesting screenshot capability..."
docker exec -i voice-control-server bash -c '
export DISPLAY=:1
export XAUTHORITY=/tmp/.Xauthority

echo "Trying screenshot with scrot..."
scrot /tmp/scrot-test.png && \
    echo "scrot screenshot successful, size: $(du -h /tmp/scrot-test.png)" || \
    echo "scrot screenshot failed"

echo "Trying screenshot with PyAutoGUI..."
python3 -c "
try:
    import pyautogui
    import time
    time.sleep(1)
    screenshot = pyautogui.screenshot()
    screenshot.save(\"/tmp/pyautogui-test.png\")
    print(\"PyAutoGUI screenshot successful, size: \", screenshot.size)
except Exception as e:
    print(\"PyAutoGUI screenshot failed: \", str(e))
"

echo "Trying screenshot with imagemagick..."
import -window root /tmp/imagemagick-test.png && \
    echo "Imagemagick screenshot successful" || \
    echo "Imagemagick screenshot failed"
'

# Check UI detection modules
echo -e "\nChecking UI detection modules..."
docker exec -i voice-control-server bash -c '
echo "Python version:"
python3 --version

echo "PyAutoGUI installation:"
pip show pyautogui || echo "PyAutoGUI not installed"

echo "Pillow installation:"
pip show pillow || echo "Pillow not installed"

echo "OpenCV installation:"
pip show opencv-python || echo "OpenCV not installed"

echo "Checking imports:"
python3 -c "
try:
    import pyautogui
    print(\"PyAutoGUI import successful, version:\", pyautogui.__version__)
except ImportError as e:
    print(\"PyAutoGUI import failed:\", str(e))

try:
    import cv2
    print(\"OpenCV import successful, version:\", cv2.__version__)
except ImportError as e:
    print(\"OpenCV import failed:\", str(e))

try:
    from PIL import Image
    print(\"PIL import successful, version:\", Image.__version__)
except ImportError as e:
    print(\"PIL import failed:\", str(e))
"
'

# Check permissions and files
echo -e "\nChecking permissions and files..."
docker exec -i voice-control-server bash -c '
echo "User and groups:"
id

echo "Directory permissions:"
ls -la /tmp
ls -la /tmp/.X11-unix || echo "No X11 socket directory"
ls -la /tmp/.X11-unix/X1 || echo "No X1 socket file"

echo "Xauthority file:"
ls -la $XAUTHORITY || echo "No Xauthority file at $XAUTHORITY"
ls -la ~/.Xauthority || echo "No ~/.Xauthority file"
'

# Run a test with UI detection
echo -e "\nRunning a test with UI detection..."
docker exec -i voice-control-server bash -c '
cd /app
echo "Running UI detection test..."
python3 -c "
try:
    import sys
    import os
    import pyautogui
    import time
    
    print(\"Environment variables:\")
    print(\"DISPLAY:\", os.environ.get(\"DISPLAY\"))
    print(\"XAUTHORITY:\", os.environ.get(\"XAUTHORITY\"))
    
    print(\"Taking screenshot...\")
    time.sleep(1)
    screenshot = pyautogui.screenshot()
    
    print(\"Screenshot dimensions:\", screenshot.size)
    print(\"Screenshot type:\", type(screenshot))
    
    # Save the screenshot
    screenshot_path = \"/tmp/ui_test_screenshot.png\"
    screenshot.save(screenshot_path)
    print(\"Screenshot saved to:\", screenshot_path)
    
    if os.path.exists(screenshot_path):
        print(\"Saved screenshot size:\", os.path.getsize(screenshot_path), \"bytes\")
    else:
        print(\"Failed to save screenshot\")
        
except Exception as e:
    print(\"Exception:\", str(e))
    import traceback
    traceback.print_exc()
"
'

echo -e "\nDiagnosis complete. If issues persist, please run ../setup/install-additional-deps.sh"
echo "==========================================================" 