#!/bin/bash
# Start Voice Control Server with locally running Ollama LLM integration

set -e  # Exit on error

# Display banner
echo "=========================================================="
echo "       Voice Control Server Docker Setup Script           "
echo "=========================================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not installed. Please install Docker Compose first."
    echo "Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo "Error: Docker daemon is not running. Please start Docker first."
    exit 1
fi

# Check if X11 is available
if [ -z "$DISPLAY" ]; then
    echo "Warning: DISPLAY environment variable not set."
    echo "X11 may not be properly configured."
fi

# Setup X11 for Docker
echo "Setting up X11 for Docker..."
xhost +local:root &>/dev/null || echo "Warning: Failed to run xhost command, X11 may not work properly."

# Check if Ollama is installed locally
if ! command -v ollama &> /dev/null; then
    echo "Warning: Ollama is not installed or not in your PATH."
    echo "Please install Ollama from: https://ollama.ai/"
    echo "The Voice Control Server needs Ollama running locally."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if Ollama is running locally
if ! curl -s http://localhost:11434/api/tags &> /dev/null; then
    echo "Warning: Ollama service is not running on localhost:11434."
    echo "Please start Ollama with: ollama serve"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "Ollama service is running on localhost:11434."
    
    # Check for required model if Ollama is running
    if ! ollama list 2>/dev/null | grep -q "llama3.1"; then
        echo "Required model 'llama3.1' not found in Ollama."
        echo "Pulling llama3.1 model (this may take a while)..."
        ollama pull llama3.1
    else
        echo "llama3.1 model already available."
    fi
fi

# Create data directory for persistent storage
mkdir -p data

# Stop and remove any existing containers to avoid conflicts
echo "Cleaning up any existing containers..."
docker-compose down
docker rm -f voice-control-server 2>/dev/null || true

# Ensure proper cleanup of Docker resources
docker system prune -f --volumes &>/dev/null || true

# Build and start the container
echo "Starting Voice Control Server container..."
docker-compose up -d

# Check if the container started successfully
if ! docker ps | grep -q voice-control-server; then
    echo "Error: Failed to start the Voice Control Server container."
    echo "Checking container logs for errors:"
    docker-compose logs voice-control-server
    exit 1
fi

# Display server status
echo ""
echo "Voice Control Server is now running!"
echo "=========================================================="
echo "Server URL: http://localhost:5000"
echo "Health check: http://localhost:5000/health"
echo ""
echo "View logs with: docker-compose logs -f"
echo "Stop with: docker-compose down"
echo "=========================================================="

# Get the IP address for easier access from other devices
ip_address=$(hostname -I | awk '{print $1}')
if [ -n "$ip_address" ]; then
    echo "Access from other devices: http://$ip_address:5000"
    echo "=========================================================="
fi

# Display initial logs to show startup progress
echo "Initial container logs:"
docker-compose logs --tail=20 voice-control-server 