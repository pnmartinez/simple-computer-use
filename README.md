# 🤖 LLM PC Control

Control your computer with natural language commands using Large Language Models (LLMs), OCR, and voice input. This project lets you automate tasks on your desktop using everyday language.

## ✨ Features

- 🗣️ **Natural Language Commands**: Control your computer using everyday language
- 🔍 **UI Element Detection**: Automatically detects UI elements on your screen
- 📝 **Multi-Step Commands**: Execute complex sequences of actions with a single command
- 👁️ **OCR Integration**: Reads text from your screen to better understand the context
- ⌨️ **Keyboard and Mouse Control**: Simulates keyboard and mouse actions
- 🎤 **Voice Input Support**: Control your PC with voice commands
- 🌎 **Multilingual Support**: Automatic translation with preservation of UI element names
- 🖥️ **Multiple Deployment Options**: Run locally, as a server, or in Docker

## 🚀 Installation

### Standard Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/llm-pc-control.git
cd llm-pc-control

# Install the package
pip install -e .
```

### Docker Installation

For a Docker-based setup:

1. Make sure Docker and Docker Compose are installed
2. Ensure [Ollama](https://ollama.ai/) is installed and running locally
3. Run the setup script:

```bash
./scripts/docker/setup-docker-x11.sh
```

## 📋 Requirements

- Python 3.8 or higher
- Ollama (for local LLM inference)
- EasyOCR and PaddleOCR (for text recognition)
- PyAutoGUI (for keyboard and mouse control)
- PyAudio (for voice input)
- OpenAI Whisper (for speech-to-text)

## 📖 Usage

### Command Line Interface

```bash
# Set up the environment (download models, check dependencies)
llm-pc-control setup

# Run a single command
llm-pc-control run "click on the button"

# Run in interactive mode
llm-pc-control interactive
```

### Voice Control Server

The system includes a refactored voice control server that processes commands using a multi-step approach:

1. **Step Identification**: Breaks down commands into discrete, actionable steps
2. **OCR Target Identification**: Identifies text to be detected on screen
3. **PyAutoGUI Command Generation**: Converts steps into specific PyAutoGUI commands
4. **Sequential Execution**: Executes steps in order with error handling

To run the server:

```bash
# Basic usage with defaults
python -m llm_control voice-server

# With custom options
python -m llm_control voice-server --port 8080 --whisper-model medium
```

### Server API Endpoints

The server provides the following API endpoints:

- **GET /health**: Check server status
- **POST /command**: Execute a text command
- **POST /voice-command**: Process a voice command from audio data
- **POST /transcribe**: Transcribe audio without executing commands
- **POST /translate**: Translate text to English

#### Example: Sending a Direct Command

```bash
curl -X POST http://localhost:5000/command \
  -H "Content-Type: application/json" \
  -d '{"command": "open Firefox, go to gmail.com and compose a new email"}'
```

#### Example: Sending a Voice Command

```bash
curl -X POST http://localhost:5000/voice-command \
  -F "audio_file=@recording.wav" \
  -F "translate=true" \
  -F "language=es"
```

## 🐳 Docker Deployment

### Docker Components

The Docker setup consists of:

1. **Voice Control Server**: A Flask-based server for processing commands
2. **Ollama**: Running locally on your host machine
3. **X11 Configuration**: For screenshot and UI interaction capabilities

### Starting with Docker

After running the setup script:

```bash
# Start the voice control server
docker-compose up -d

# Check logs
docker-compose logs -f
```

## 🔄 Using Local Ollama

The Docker configuration is designed to use a locally running Ollama instance:

1. **Install and Start Ollama**:
   ```bash
   ./scripts/tools/start-ollama.sh
   ```

2. **Start the Voice Control Server**:
   ```bash
   docker-compose up -d
   ```

Benefits of using local Ollama:
- Better performance with direct GPU access
- Easier updates independent of the server
- Shared models with other applications
- Reduced complexity in container management

## 🔍 Troubleshooting

### Docker X11 Issues

If you encounter X11 connection issues:

```bash
# Fix X11 permissions
./scripts/setup/fix-x11.sh

# Diagnose UI detection issues
./scripts/docker/docker-diagnose-ui.sh
```

### Common Issues

1. **No audio input detected**: Check your microphone settings and PyAudio installation
2. **LLM connection failed**: Verify Ollama is running and accessible
3. **OCR not working properly**: Ensure proper lighting and screen resolution
4. **Commands not executing**: Check PyAutoGUI permissions

## 🧪 Development Guide

### Project Structure

```
llm-control/
├── data/                # Data files
├── docs/                # Documentation
├── llm_control/         # Main Python package
├── scripts/             # Utility scripts
│   ├── docker/          # Docker-related scripts
│   ├── setup/           # Installation scripts
│   └── tools/           # Utility tools
├── tests/               # Test suite
├── logs/                # Log files
└── screenshots/         # Screenshots directory
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Inspired by [OmniParser](https://github.com/microsoft/OmniParser) by Microsoft
- Uses various open-source projects including Ollama, PyAutoGUI, and EasyOCR

[demo.webm](https://github.com/user-attachments/assets/bdd5bc25-fe88-4105-a3ed-f435f98e4f18)

## 💡 Examples

Here are some examples of commands you can use:

- "Click on the Submit button"
- "Type 'Hello, world!' in the search box"
- "Press Enter"
- "Move to the top-right corner of the screen"
- "Double-click on the file icon"
- "Right-click on the image"
- "Scroll down"
- "Click on the button, then type 'Hello', then press Enter"

## ⚙️ How It Works

1. 📸 **Screenshot Analysis**: Takes a screenshot of your screen
2. 🔎 **UI Detection**: Analyzes the screenshot to detect UI elements
3. 🔄 **Command Parsing**: Parses your natural language command into steps
4. ⚡ **Action Generation**: Generates the corresponding actions for each step
5. ▶️ **Execution**: Executes the actions using PyAutoGUI

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## Voice Command Client

The LLM PC Control system supports voice commands through a client-server architecture. 

### Running the Voice Command Client

The voice command client allows you to speak commands into your microphone, which are then transcribed and executed by the system.

```bash
python -m llm_control voice-server
```

Options:
- `--list-devices`: List available audio input devices
- `--device ID`: Audio input device ID
- `--whisper-model`: Whisper model size (choices: tiny, base, small, medium, large)
- `--transcribe-only`: Only transcribe without executing commands
- `--translate`: Enable automatic translation of Spanish voice commands to English
- `--ollama-model`: Ollama model to use for translation (default: llama3)
- `--ollama-host`: Ollama host URL

Example:
```bash
# List audio devices
python -m llm_control voice-server --list-devices

# Record for 8 seconds with a specific device
python -m llm_control voice-server --device 1

# Use a different Whisper model
python -m llm_control voice-server --whisper-model medium

# Only transcribe without executing
python -m llm_control voice-server --transcribe-only
```

### Example Voice Commands

You can speak commands naturally, such as:
- "Open Firefox and go to Google.com"
- "Click on the search box and type hello world"
- "Press Enter"
- "Take a screenshot"

The system will transcribe your voice command and execute it as if it was typed into the command interface.

### Local Voice Command Testing

If you don't want to set up the full server, you can use the local testing script:

```bash
python -m llm_control simple-voice
```

This script has similar options to the client:

```bash
# List audio devices
python -m llm_control simple-voice --list-devices

# Record for 8 seconds with a specific device
python -m llm_control simple-voice --device 1

# Use a different Whisper model
python -m llm_control simple-voice --whisper-model medium

# Only transcribe without executing
python -m llm_control simple-voice --transcribe-only
```

### Spanish to English Translation

The local testing script now supports automatic translation of Spanish voice commands to English using Ollama:

```bash
# Enable automatic Spanish detection and translation
python -m llm_control simple-voice --translate

# Specify a different Ollama model
python -m llm_control simple-voice --translate --ollama-model mixtral

# Specify a custom Ollama host
python -m llm_control simple-voice --translate --ollama-host http://192.168.1.100:11434
```

The script will automatically detect Spanish commands and translate them to English before execution. You need to have Ollama running locally with your preferred model installed.

#### Installing Ollama

To use the translation feature, you need to have Ollama installed:

1. Install Ollama from [ollama.ai](https://ollama.ai/)
2. Run Ollama in a separate terminal:
   ```bash
   ollama serve
   ```
3. Pull your preferred model:
   ```bash
   ollama pull llama3
   ```

The local testing script uses Whisper directly without a server, which is useful for quick tests and debugging.

### Troubleshooting Voice Commands

#### PortAudio Not Found

If you see an error like `OSError: PortAudio library not found` when trying to use voice commands, you need to install the PortAudio library on your system. We've provided a helper script to install it:

```bash
# For Linux/macOS
sudo python -m llm_control install-system-deps

# For Windows (run as Administrator)
python -m llm_control install-system-deps
```

Or install manually based on your operating system:

- **Ubuntu/Debian**: `sudo apt-get install portaudio19-dev`
- **Fedora/RHEL**: `sudo dnf install portaudio-devel`
- **Arch Linux**: `sudo pacman -S portaudio`
- **macOS**: `brew install portaudio`
- **Windows**: PortAudio is included in the Windows wheel for sounddevice

After installing PortAudio, reinstall the sounddevice package:

```bash
pip uninstall -y sounddevice
pip install sounddevice
```

## WebSocket Server for Mobile Clients

The LLM PC Control system now includes a WebSocket server that can accept connections from mobile clients, including Android applications. This enables you to send voice commands from your mobile device to control your computer.

### Running the WebSocket Server

You can start the WebSocket server using the CLI script:

```bash
python -m llm_control android-server-rest
```

Options:
- `--host`: Host address to bind the server to (default: 0.0.0.0)
- `--port`: Port to bind the server to (default: 5000)
- `--debug`: Run the server in debug mode
- `--whisper-model`: Whisper model size (choices: tiny, base, small, medium, large)
- `--log-level`: Logging level (choices: DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `--enable-translation`: Enable automatic Spanish to English translation
- `--ollama-model`: Ollama model to use for translation (default: llama3)
- `--ssl`: Enable SSL/TLS for secure WebSocket connections (WSS)
- `--ssl-cert`: Path to SSL certificate file (.crt or .pem)
- `--ssl-key`: Path to SSL private key file (.key)

Example:

```bash
# Start the server with default settings
python -m llm_control android-server-rest

# Start on a specific host and port
python -m llm_control android-server-rest --host 192.168.1.100 --port 8080

# Enable secure WebSocket (WSS) with SSL
python -m llm_control android-server-rest --ssl --ssl-cert /path/to/cert.pem --ssl-key /path/to/key.pem

# Enable translation for Spanish commands
python -m llm_control android-server-rest --enable-translation --ollama-model llama3
```

### Connecting Mobile Clients

Mobile clients can connect to the server using the WebSocket protocol. The server supports both regular WebSocket (ws://) and secure WebSocket (wss://) connections.

Endpoints:
- WebSocket: `ws://<host>:<port>/socket.io/` or `wss://<host>:<port>/socket.io/` (if SSL is enabled)
- REST API: `http://<host>:<port>/` or `https://<host>:<port>/` (if SSL is enabled)

The WebSocket server accepts audio data from clients, transcribes it using Whisper, executes the command on the server computer, and sends back the results to the client.

### Android Client Example

The repository includes an example Android client (`AudioService.kt`) that demonstrates how to record audio and send it to the server using WebSockets. The client can be configured to connect to the server using either the regular WebSocket protocol (ws://) or the secure WebSocket protocol (wss://).

To use the Android client with your LLM PC Control server:

1. Start the server with the appropriate options (enable SSL if needed)
2. Configure the Android client with the correct server address and port
3. Record audio commands on your Android device
4. The server will transcribe, process, and execute the commands

Note: For secure connections (wss://), you need to generate a valid SSL certificate and configure the server to use it.

### Generating SSL Certificates for Testing

For testing purposes, you can generate a self-signed SSL certificate:

```bash
# Generate a private key
openssl genrsa -out server.key 2048

# Generate a self-signed certificate
openssl req -new -x509 -key server.key -out server.crt -days 365 -subj "/CN=localhost"
```

Then run the server with these certificates:

```bash
python -m llm_control android-server-rest --ssl --ssl-cert server.crt --ssl-key server.key
```

Note: Mobile clients will need to accept the self-signed certificate as a security exception.

## Android Compatibility: REST API vs WebSockets

The LLM PC Control server supports two different connection methods for Android clients:

### REST API Approach (Recommended)

The REST API approach is simpler and more reliable for mobile clients. It uses standard HTTP/HTTPS requests that are well-supported on all platforms and avoids the complexity of WebSocket connections.

To start the server with the REST API mode:

```bash
# Start with REST API mode (recommended for Android)
python -m llm_control android-server-rest --qr

# Generate a QR code for easy connection
python -m llm_control android-server-rest --qr-file connection.png
```

#### REST API Endpoints

The Android REST API provides the following endpoints:

- `GET /api/info` - Discover server capabilities and available endpoints
- `GET /api/system-info` - Get system information (CPU, memory, disk usage)
- `POST /transcribe` - Transcribe audio to text
- `POST /command` - Execute a command directly
- `POST /voice-command` - Process and execute a voice command

#### Connecting with QR Codes

The server can generate a QR code that contains all the connection information. Android clients can scan this QR code to automatically configure their connection settings.

#### Android Integration Guide

For a comprehensive guide on integrating the REST API with Android apps, see the [Android API Integration Guide](ANDROID_API.md). This guide includes:

- Detailed API documentation
- Android code examples using Retrofit and OkHttp
- SSL certificate handling for Android
- Troubleshooting common issues
- QR code integration

### WebSocket Approach (Legacy)

For backward compatibility, the server still supports WebSocket connections. However, this approach is more complex and may have issues with certain network configurations.

To start the server with WebSocket support:

```bash
# Start with WebSocket support (legacy)
python -m llm_control android-server

# Use a custom WebSocket path
python -m llm_control android-server --android-wss-path /custom-ws
```

### SSL/TLS Considerations

When using either approach, it's recommended to enable SSL/TLS for secure connections:

```bash
# Use self-signed certificates with REST API
python -m llm_control android-server-rest --ssl --self-signed-ssl

# Use custom certificates with REST API
python -m llm_control android-server-rest --ssl --ssl-cert your-cert.crt --ssl-key your-key.key
```

Note: Mobile clients will need to either add a security exception for self-signed certificates or have the certificate properly installed.

## Testing and Troubleshooting

### Testing the REST API

The project includes several tools to help you test and troubleshoot the REST API:

#### Simple REST Server

For quick testing without setting up the full LLM PC Control server, you can use the simple REST server:

```bash
# Start the simple REST server
python -m llm_control rest-server
```

#### Testing API Endpoints

To test the REST API endpoints, use the test script:

```bash
# Test the API with default settings
python -m llm_control test-rest-api

# Test against a specific server
python -m llm_control test-rest-api --url https://your-server-ip:5000

# Skip command testing
python -m llm_control test-rest-api --no-command

# Verbose output for debugging
python -m llm_control test-rest-api --verbose
```

#### Android Client Simulation

To simulate how an Android client would interact with the REST API:

```bash
# Run the Android client simulation
python -m llm_control android-client --url https://your-server-ip:5000

# Test with a voice command audio file
python -m llm_control android-client --audio-file your-audio-file.wav
```

### Troubleshooting Common Issues

#### SSL Certificate Issues

If you're having trouble with SSL certificates on Android:

1. Ensure the SSL certificate includes your server's IP address in the Subject Alternative Name (SAN) field
2. For self-signed certificates, add the certificate to your Android device's trusted certificates
3. Try using `--no-ssl` during testing to verify the REST API works without SSL

#### Connection Issues

If the Android client can't connect to the server:

1. Make sure the server is accessible from your Android device (check firewalls, network configuration)
2. Verify the server is running and the port is open
3. Use the `test_rest_api.py` script to verify the API is working correctly

#### API Endpoint Not Found

If you get "404 Not Found" errors:

1. Use the `/api/info` endpoint to discover the correct endpoint URLs
2. Check that you're using the correct URL path for your server configuration
3. Verify the server is configured correctly for Android compatibility

## UI Detection Troubleshooting

If you're experiencing issues with the UI detection module, you can use the included diagnostic tool to help identify and resolve problems:

```bash
# Run the UI detection diagnostic tool
python -m llm_control diagnose-ui
```

This tool will:
1. Check if all required dependencies are installed
2. Test the screenshot functionality
3. Attempt to run OCR on a test screenshot
4. Test YOLO-based UI element detection
5. Provide installation recommendations for any missing dependencies

If you see the error "UI detection module not available", it's likely that you're missing some required dependencies. The diagnostic tool will help you identify which ones and provide installation instructions.

You can install all UI detection dependencies at once using:

```bash
# Install with UI detection dependencies
pip install -e .[ui]
```

### Visualizing UI Element Detection

To help debug issues with UI element detection, you can use the included visualization tool:

```bash
# Search for a specific UI element and visualize all potential matches
python -m llm_control visualize-ui "Firefox"

# Save the visualization to a specific file
python -m llm_control visualize-ui "Settings" --output settings_matches.png

# Use an existing screenshot
python -m llm_control visualize-ui "Menu" --screenshot my_screenshot.png

# Show more or fewer top matches
python -m llm_control visualize-ui "Button" --top 10
```

This tool will:
1. Take a screenshot (or use an existing one)
2. Detect all UI elements and text on the screen
3. Find potential matches for your target text
4. Create a visualization that highlights the matches, color-coded by confidence:
   - Green: High confidence matches (>80%)
   - Yellow: Medium confidence matches (50-80%)
   - Red: Low confidence matches (<50%)
5. Show details about each match, including its confidence score

The visualization tool is helpful for understanding why certain UI elements might not be detected correctly, or why the system might be choosing the wrong element when multiple similar options are available.

### Common Issues

1. **Circular imports**: If you see import errors related to circular dependencies, make sure your code is updated to the latest version which resolves these issues.

2. **Missing models**: Some models (like YOLO or OCR language models) might need to be downloaded the first time you use them, which can cause delays or timeouts.

3. **GPU requirements**: For best performance, UI detection components work best with GPU acceleration. Make sure you have the CUDA-enabled version of PyTorch installed if you have a compatible GPU.
