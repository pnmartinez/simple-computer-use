#!/bin/bash
# Script to set up the X11 configuration for the Docker container

set -e  # Exit on error

echo "=========================================================="
echo "    Voice Control Server Docker X11 Setup                 "
echo "=========================================================="

# Check if Docker is running
if ! docker ps &>/dev/null; then
    echo "Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Step 1: Ensure docker-compose.yml has proper X11 configuration
echo "Step 1: Checking docker-compose.yml configuration..."
if ! grep -q "- /tmp/.X11-unix:/tmp/.X11-unix" docker-compose.yml; then
    echo "Updating docker-compose.yml with X11 configuration..."
    cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  voice-control-server:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: voice-control-server
    privileged: true
    environment:
      - DISPLAY=:1
      - XAUTHORITY=/tmp/.Xauthority
      - OLLAMA_HOST=http://localhost:11434
      - OLLAMA_MODEL=llama3.1
      - WHISPER_MODEL=base
      - DEFAULT_LANGUAGE=es
      - ENABLE_TRANSLATION=true
      - SCREENSHOT_ENABLED=true
    volumes:
      - /tmp/.X11-unix:/tmp/.X11-unix
      - ./data:/app/data
    ports:
      - "5000:5000"
    network_mode: host
    restart: unless-stopped
EOF
    echo "docker-compose.yml updated successfully."
else
    echo "docker-compose.yml already has X11 configuration."
fi

# Step 2: Update Dockerfile with X11 dependencies
echo "Step 2: Checking Dockerfile configuration..."
if ! grep -q "xserver-xorg-video-dummy" Dockerfile; then
    echo "Updating Dockerfile with X11 dependencies..."
    cat > Dockerfile << 'EOF'
FROM ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:1 \
    XAUTHORITY=/tmp/.Xauthority \
    LANG=C.UTF-8 \
    LANGUAGE=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=UTC

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-dev \
    xvfb x11-utils xauth x11-apps x11vnc \
    scrot imagemagick wmctrl xdotool fluxbox \
    git wget curl unzip \
    libgl1-mesa-glx libegl1-mesa libxrandr2 \
    libxss1 libxxf86vm1 libxi6 \
    libxtst6 libxt6 libxfixes3 \
    ffmpeg libsm6 libxext6 libgl1-mesa-dri \
    software-properties-common \
    gnome-screenshot python3-pil python3-pil.imagetk \
    xserver-xorg-video-dummy \
    python3-tk python3-dev \
    locales && \
    locale-gen en_US.UTF-8 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt /app/

# Install any needed Python packages
RUN pip3 install --no-cache-dir -r requirements.txt && \
    pip3 install --no-cache-dir --upgrade pillow pyautogui pydbus python-xlib

# Copy the current directory contents into the container at /app
COPY . /app/

# Create directories for X11
RUN mkdir -p /tmp/.X11-unix && \
    chmod 1777 /tmp/.X11-unix

# Create an entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set the entrypoint to a script that starts Xvfb and the voice control server
ENTRYPOINT ["/app/entrypoint.sh"]
EOF
    echo "Dockerfile updated successfully."
else
    echo "Dockerfile already has X11 dependencies."
fi

# Step 3: Update entrypoint.sh with improved X11 setup
echo "Step 3: Checking entrypoint.sh configuration..."
if ! grep -q "Testing screenshot capability" entrypoint.sh; then
    echo "Updating entrypoint.sh with improved X11 setup..."
    cat > entrypoint.sh << 'EOF'
#!/bin/bash

set -e  # Exit on error

# Create runtime directories
mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix

# Make sure XAUTHORITY is set and file exists
touch /tmp/.Xauthority
chmod 777 /tmp/.Xauthority
export XAUTHORITY=/tmp/.Xauthority

echo "Starting Xvfb..."
Xvfb :1 -screen 0 1280x1024x24 -ac +extension GLX +render -noreset &
sleep 2

# Check if Xvfb is running
if ! ps aux | grep -v grep | grep -q Xvfb; then
    echo "ERROR: Xvfb failed to start"
    exit 1
fi

export DISPLAY=:1
echo "DISPLAY set to $DISPLAY"

# Configure X11 utilities
echo "Configuring X11 utilities..."
xhost +local:root || echo "xhost command failed, but continuing..."

# Start a simple window manager in the background to help with window management
fluxbox &

# Start VNC server to allow viewing remotely (optional)
x11vnc -display :1 -nopw -forever -quiet &

# Test screenshot capability
echo "Testing screenshot capability..."
python3 -c "
import time
time.sleep(2)
try:
    import pyautogui
    screenshot = pyautogui.screenshot()
    print('Screen size:', screenshot.size)
    screenshot.save('/tmp/test_screenshot.png')
    print('Screenshot test successful')
except Exception as e:
    print('Screenshot test failed: ' + str(e))
" || echo "Screenshot test failed, but continuing..."

# Ensure python-xlib is properly installed
pip install --upgrade python-xlib pillow pyautogui || echo "Warning: Failed to upgrade python packages"

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
echo "OLLAMA_HOST=$OLLAMA_HOST"
echo "OLLAMA_MODEL=$OLLAMA_MODEL"

# Start the Voice Control Server
echo "Starting Voice Control Server..."
exec python3 voice_control_server.py
EOF
    chmod +x entrypoint.sh
    echo "entrypoint.sh updated successfully."
else
    echo "entrypoint.sh already has improved X11 setup."
fi

# Step 4: Update start-voice-control.sh to configure X11 properly
echo "Step 4: Checking start-voice-control.sh configuration..."
if ! grep -q "Setting up X11 for Docker" start-voice-control.sh; then
    echo "Updating start-voice-control.sh with X11 configuration..."
    cat > start-voice-control.sh << 'EOF'
#!/bin/bash
# Start Voice Control Server with X11 and Ollama LLM integration

set -e  # Exit immediately if a command exits with a non-zero status.

echo "=========================================================="
echo "    Voice Control Server Docker Setup Script              "
echo "=========================================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo "Error: Docker daemon is not running. Please start Docker daemon first."
    exit 1
fi

# Setting up X11 for Docker
echo "Setting up X11 for Docker..."
if [ -z "$DISPLAY" ]; then
    echo "Warning: DISPLAY environment variable is not set."
    echo "X11 forwarding may not work correctly."
else
    xhost + &>/dev/null || echo "Warning: xhost command failed. X11 may not work correctly."
fi

# Check if the Ollama service is running on localhost
echo "Checking Ollama service..."
if ! curl -s http://localhost:11434/api/version &> /dev/null; then
    echo "Warning: Ollama service is not running on localhost:11434."
    echo "The Voice Control Server uses Ollama for LLM integration."
    echo "Please make sure Ollama is installed and running."
    
    # Offer to continue anyway
    read -p "Do you want to continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup canceled."
        exit 1
    fi
else
    echo "Ollama service is running on localhost:11434."
    
    # Check if the required model is available
    MODEL_NAME="llama3.1"
    if ! curl -s http://localhost:11434/api/tags | grep -q "\"name\":\"$MODEL_NAME\""; then
        echo "Warning: Model $MODEL_NAME is not available in Ollama."
        echo "Pulling the model now (this may take some time)..."
        ollama pull $MODEL_NAME || echo "Warning: Failed to pull the model. You can manually pull it with: ollama pull $MODEL_NAME"
    else
        echo "Model $MODEL_NAME is available in Ollama."
    fi
fi

# Create data directory for persistent storage
mkdir -p ./data

# Clean up any existing containers
echo "Cleaning up existing containers..."
docker-compose down --remove-orphans || true
docker stop voice-control-server &>/dev/null || true
docker rm voice-control-server &>/dev/null || true
docker system prune -f

# Build and start the container
echo "Building and starting Voice Control Server..."
docker-compose up -d --build

# Check if container started successfully
echo "Checking if container started successfully..."
sleep 5
if docker ps | grep -q voice-control-server; then
    echo "Voice Control Server container is running."
    echo "Server logs (press Ctrl+C to stop viewing):"
    docker-compose logs -f voice-control-server &
    LOG_PID=$!
    sleep 5
    kill $LOG_PID &>/dev/null || true
    
    echo ""
    echo "=========================================================="
    echo "Voice Control Server is now running at: http://localhost:5000"
    echo "Health check: http://localhost:5000/health"
    echo ""
    echo "To view logs: docker-compose logs -f voice-control-server"
    echo "To stop server: docker-compose down"
    echo ""
    echo "You can access the server from other devices on your network at:"
    echo "http://$(hostname -I | awk '{print $1}'):5000"
    echo "=========================================================="
else
    echo "Error: Voice Control Server container failed to start."
    echo "Check logs with: docker-compose logs voice-control-server"
    exit 1
fi
EOF
    chmod +x start-voice-control.sh
    echo "start-voice-control.sh updated successfully."
else
    echo "start-voice-control.sh already has X11 configuration."
fi

# Update requirements.txt to avoid conflicts
echo "Step 5: Checking requirements.txt for conflicts..."
if grep -q "flask-socketio==5." requirements.txt && grep -q "flask-socketio==4." requirements.txt; then
    echo "Fixing conflicting dependencies in requirements.txt..."
    
    # Create a temporary file
    TEMP_FILE=$(mktemp)
    
    # Keep only one version of flask-socketio
    grep -v "flask-socketio" requirements.txt > "$TEMP_FILE"
    echo "flask-socketio==5.3.6" >> "$TEMP_FILE"
    
    # Also fix other common conflicts
    sed -i '/python-xlib/d' "$TEMP_FILE"
    echo "python-xlib>=0.33" >> "$TEMP_FILE"
    
    # Remove duplicates
    sort "$TEMP_FILE" | uniq > requirements.txt
    
    # Clean up
    rm "$TEMP_FILE"
    
    echo "requirements.txt updated to fix conflicts."
else
    echo "No obvious conflicts found in requirements.txt."
fi

echo ""
echo "Setup complete! You can now start the Voice Control Server with:"
echo "../tools/start-voice-control.sh"
echo ""
echo "If you experience any issues with X11 or screenshots, run:"
echo "./docker-diagnose-ui.sh"
echo ""
echo "==========================================================" 