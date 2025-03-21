# Voice Control Server Docker Setup

This README provides instructions for setting up and running the Voice Control Server in a Docker container.

## Prerequisites

- Docker and Docker Compose installed
- [Ollama](https://ollama.ai/) installed and running locally
- NVIDIA GPU (optional, but recommended for better performance)
- X11 server running on the host (for UI interaction features)

## Components

The Docker setup consists of:

1. **Voice Control Server**: A Flask-based server that processes voice commands, performs OCR, and executes desktop automation
2. **Ollama**: Running locally on your host machine (not in a container)
3. **X11 Configuration**: Setup for screenshot and UI interaction capabilities

## Getting Started

### Quick Setup

For a quick and automated setup:

1. Clone this repository
2. Make sure Ollama is installed and running on your host machine
3. Run the setup script:

```bash
./setup-docker-x11.sh
```

4. Start the server:

```bash
./start-voice-control.sh
```

### Manual Setup

If you prefer to set up manually:

1. Review and modify the `docker-compose.yml` file if needed
2. Build and start the container:

```bash
docker-compose up -d --build
```

## Configuration

Configuration is done primarily through environment variables in the `docker-compose.yml` file:

- `OLLAMA_HOST`: URL of the Ollama service (default: http://localhost:11434)
- `OLLAMA_MODEL`: Model to use for LLM features (default: llama3.1)
- `WHISPER_MODEL`: Model to use for speech recognition (default: base)
- `DEFAULT_LANGUAGE`: Default language for voice commands (default: es)
- `ENABLE_TRANSLATION`: Whether to enable translation features (default: true)
- `SCREENSHOT_ENABLED`: Whether to enable screenshot capabilities (default: true)

## API Endpoints

The Voice Control Server exposes the following endpoints:

- `GET /health`: Check the server health status
- `POST /command`: Submit a voice command
- `GET /listen`: Start listening for voice commands (WebSocket)
- `GET /screenshots`: Get the latest screenshots

## Troubleshooting

### UI Detection Issues

If you encounter problems with UI detection or screenshot capabilities:

1. Run the diagnostic script:

```bash
./docker-diagnose-ui.sh
```

2. If issues are detected, run the additional dependencies installation script:

```bash
./install-additional-deps.sh
```

3. For detailed X11 debugging, run:

```bash
./fix-x11.sh
```

### Common Issues

1. **Container fails to start**: Check Docker logs with `docker-compose logs voice-control-server`
2. **Screenshot capabilities not working**: Ensure X11 is properly configured with `./fix-x11.sh`
3. **Cannot connect to Ollama**: Make sure Ollama is running on your host machine with `ollama serve`
4. **LLM model not found**: Pull the required model with `ollama pull llama3.1`
5. **Dependency conflicts**: Run the setup script again with `./setup-docker-x11.sh`

## Advanced Usage

### Customizing the Docker Environment

You can customize the Docker environment by modifying:

- `Dockerfile`: To add or change installed packages
- `entrypoint.sh`: To change the startup behavior
- `docker-compose.yml`: To change environment variables and volume mounts

### Accessing the Container

You can access the running container with:

```bash
docker exec -it voice-control-server bash
```

### Running in a Different Network Configuration

By default, the container uses the host network for easy access to the Ollama service. If you need a different network configuration, modify the `network_mode` in the `docker-compose.yml` file.

## Security Considerations

- The server listens on port 5000 by default, which is exposed to the host
- The X11 setup requires some permissions that may have security implications
- Running in privileged mode is required for full X11 functionality

## License

See the LICENSE file for details. 