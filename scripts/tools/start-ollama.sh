#!/bin/bash
# Script to install and start Ollama locally

set -e  # Exit on error

# Display banner
echo "=========================================================="
echo "                Ollama Setup Script                       "
echo "=========================================================="
echo ""

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "Ollama is not installed. Would you like to install it? (y/n)"
    read -p "> " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Installing Ollama..."
        
        # Detect OS
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            # Linux installation
            curl -fsSL https://ollama.ai/install.sh | sh
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            # MacOS installation
            echo "Please download Ollama for MacOS from https://ollama.ai/"
            echo "After installation, run this script again."
            exit 1
        else
            echo "Unsupported OS. Please install Ollama manually from https://ollama.ai/"
            exit 1
        fi
        
        echo "Ollama installed successfully!"
    else
        echo "Exiting without installing Ollama."
        echo "Please install Ollama manually from https://ollama.ai/ before running the Voice Control Server."
        exit 1
    fi
fi

# Check if Ollama is already running
if curl -s http://localhost:11434/api/tags &> /dev/null; then
    echo "Ollama is already running on localhost:11434."
else
    # Start Ollama
    echo "Starting Ollama service..."
    ollama serve &
    
    # Wait for Ollama to start
    echo "Waiting for Ollama to be ready..."
    attempt=0
    max_attempts=30
    while ! curl -s http://localhost:11434/api/tags &> /dev/null; do
        attempt=$((attempt+1))
        if [ $attempt -eq $max_attempts ]; then
            echo "Error: Timed out waiting for Ollama to start."
            exit 1
        fi
        echo "Waiting for Ollama service (attempt $attempt/$max_attempts)..."
        sleep 2
    done
    
    echo "Ollama service is now running!"
fi

# Check if the required model is available
echo "Checking for required LLM model..."
if ! ollama list 2>/dev/null | grep -q "llama3"; then
    echo "The llama3 model is not available. Would you like to pull it now? (y/n)"
    read -p "> " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Pulling llama3 model (this may take a while)..."
        ollama pull llama3
        echo "Model downloaded successfully!"
    else
        echo "Note: The Voice Control Server will need the model to function properly."
        echo "You can pull it later with: ollama pull llama3"
    fi
else
    echo "The llama3 model is already available."
fi

echo ""
echo "=========================================================="
echo "Ollama is now set up and running!"
echo "You can now start the Voice Control Server with:"
echo "./start-voice-control.sh"
echo "=========================================================="
echo ""
echo "To stop Ollama when you're done, run:"
echo "killall ollama"
echo "==========================================================" 