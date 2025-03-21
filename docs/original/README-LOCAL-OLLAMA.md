# Using Local Ollama with Docker

This document explains how the Voice Control Server Docker setup has been modified to use a locally running Ollama instance instead of running Ollama in a Docker container.

## Overview

The updated Docker configuration:

1. Uses host networking mode to allow direct access to services running on your host machine
2. Connects to Ollama running on your local machine (not in a container)
3. Provides helper scripts for setting up and managing the local Ollama instance

## Benefits

- **Better Performance**: Direct access to GPU resources for Ollama
- **Easier Updates**: Update Ollama independently of the Voice Control Server
- **Shared Models**: Use the same Ollama models for other applications
- **Reduced Complexity**: One less container to manage

## Getting Started

1. **Install and Start Ollama**:
   ```bash
   ./start-ollama.sh
   ```
   This script will:
   - Install Ollama if not already installed
   - Start the Ollama service
   - Pull the required LLM model (llama3)

2. **Start the Voice Control Server**:
   ```bash
   ./start-voice-control.sh
   ```
   This script will:
   - Verify Ollama is running
   - Start the Voice Control Server container

## Configuration

The Voice Control Server is configured to connect to Ollama at `http://localhost:11434`. If you're running Ollama on a different port or host, you can modify this in `docker-compose.yml`:

```yaml
environment:
  - OLLAMA_HOST=http://localhost:11434  # Change this as needed
  - OLLAMA_MODEL=llama3                 # Change to your preferred model
```

## Troubleshooting

If you encounter issues with the Voice Control Server connecting to Ollama:

1. Make sure Ollama is running:
   ```bash
   curl http://localhost:11434/api/tags
   ```

2. Check if your model is available:
   ```bash
   ollama list
   ```

3. Pull the model if needed:
   ```bash
   ollama pull llama3
   ```

4. Check the logs:
   ```bash
   docker logs voice-control-server
   ```

## Advanced Usage

### Using a Different Ollama Model

```bash
# Pull the model
ollama pull mistral

# Update docker-compose.yml
# Change OLLAMA_MODEL=llama3 to OLLAMA_MODEL=mistral

# Restart the Voice Control Server
docker-compose restart voice-control-server
```

### Managing Ollama

```bash
# Start Ollama
ollama serve

# Stop Ollama
killall ollama

# List available models
ollama list

# Remove a model
ollama rm llama3
``` 