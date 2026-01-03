# LLM Control API Architecture Documentation

## Overview
The LLM Control API is a voice-controlled system that enables users to interact with their computer through natural language commands. The system combines speech recognition, language processing, and UI automation to execute user commands.

## Core Components

### 1. Voice Control Server
- **Framework**: Flask-based web server
- **Port**: Default 5000
- **Security**: Supports SSL/TLS with both self-signed and custom certificates
- **CORS**: Enabled for cross-origin requests

### 2. Key Modules

#### 2.1 Voice Processing
- Speech-to-text transcription using Whisper
- Multi-language support with automatic translation
- Configurable model sizes (tiny, base, small, medium, large)

#### 2.2 Command Processing
- Natural language command interpretation
- Multi-step command execution
- Command history tracking
- PyAutoGUI integration for UI automation

#### 2.3 UI Detection
- Screenshot capture and management
- OCR capabilities for text recognition
- UI element detection and interaction

#### 2.4 LLM Integration
- Integration with Ollama for language processing
- Configurable model selection
- Customizable host settings

## API Endpoints

### 1. Health and Status
- `GET /health`: Server health check endpoint

### 2. Voice Processing
- `POST /transcribe`: Convert audio to text
  - Accepts audio file
  - Supports language selection
  - Configurable model size
- `POST /translate`: Translate text to English
  - Supports multiple languages
  - Uses Ollama for translation

### 3. Command Execution
- `POST /command`: Execute text-based commands
- `POST /voice-command`: Process and execute voice commands
- `GET /command-history`: Retrieve command execution history

### 4. Screenshot Management
- `GET /screenshots`: List available screenshots
- `GET /screenshots/latest`: Get most recent screenshots
- `GET /screenshots/<filename>`: Retrieve specific screenshot
- `GET /screenshots/view`: Web interface for viewing screenshots
- `GET/POST /screenshot/capture`: Capture new screenshots
- `GET/POST /screenshots/cleanup`: Manage screenshot cleanup

### 5. System Control
- `POST /unlock-screen`: Screen unlocking functionality

## Configuration

### Environment Variables
- `DEFAULT_LANGUAGE`: Default language for voice recognition (default: "es")
- `WHISPER_MODEL_SIZE`: Size of Whisper model (default: "large")
- `TRANSLATION_ENABLED`: Enable/disable translation (default: true)
- `OLLAMA_MODEL`: Selected Ollama model (default: "llama3.1")
- `OLLAMA_HOST`: Ollama API host (default: "http://localhost:11434")
- `CAPTURE_SCREENSHOTS`: Enable/disable screenshot capture
- `PYAUTOGUI_FAILSAFE`: Enable PyAutoGUI failsafe
- `SCREENSHOT_DIR`: Screenshot storage directory
- `SCREENSHOT_MAX_AGE_DAYS`: Maximum age for screenshots
- `SCREENSHOT_MAX_COUNT`: Maximum number of screenshots to keep


## Example Run Command
```bash
# Basic run with default settings
python -m llm_control voice-server

# Run with custom configuration
python -m llm_control voice-server \
  --disable-translation \
  --whisper-model large \
  --ssl \
  --host 0.0.0.0 \
  --port 5000 \
  --debug

# Run with conda environment (recommended)
source /path/to/miniconda3/etc/profile.d/conda.sh
conda activate autogui
python -m llm_control voice-server --disable-translation --whisper-model large --ssl
```

The server supports various command-line arguments:
- `--host`: Host to bind to (default: 0.0.0.0)
- `--port`: Port to bind to (default: 5000)
- `--debug`: Enable debug mode
- `--ssl`: Enable SSL with self-signed certificate
- `--whisper-model`: Whisper model size (tiny, base, small, medium, large)
- `--disable-translation`: Disable automatic translation
- `--language`: Default language for voice recognition (default: es)
- `--disable-screenshots`: Disable capturing screenshots
- `--enable-failsafe`: Enable PyAutoGUI failsafe 