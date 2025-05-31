# 🤖 LLM PC Control

[![Voice Server Verification](https://github.com//pnmartinez/simple-computer-use/actions/workflows/voice-server-verification.yml/badge.svg)](https://github.com/pnmartinez/simple-computer-use/actions/workflows/voice-server-verification.yml)

> For voice control with phone check: https://github.com/pnmartinez/computer-use-android-app

[demo.webm](https://github.com/user-attachments/assets/bdd5bc25-fe88-4105-a3ed-f435f98e4f18)

Control your computer with natural language commands using Large Language Models (LLMs), OCR, and voice input.

Get the Android app to control your PC with voice on the [Computer Use Android App](https://github.com/pnmartinez/computer-use-android-app) repo.

![imagen](https://github.com/user-attachments/assets/c9e3408e-b708-4633-bf4e-a6698cb1cee1)


## ✨ Features

- 🗣️ **Natural Language Commands**: Control your computer using everyday language
- 🔍 **UI Element Detection**: Automatically detects UI elements on your screen
- 📝 **Multi-Step Commands**: Execute complex sequences of actions with a single command
- 👁️ **OCR Integration**: Reads text from your screen to better understand the context
- ⌨️ **Keyboard and Mouse Control**: Simulates keyboard and mouse actions
- 🎤 **Voice Input Support**: Control your PC with voice commands
- 🌎 **Multilingual Support**: Automatic translation with preservation of UI element names
- 🖥️ **Multiple Deployment Options**: Run locally or in Docker

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

### Voice Control Server

```bash
# Run the voice control server
python -m llm_control voice-server

# With custom options
python -m llm_control voice-server --port 8080 --whisper-model medium --ollama-model llama3.1
```

### Simple Command

```bash
# Run a simple command
python -m llm_control simple-voice --command "click on the Firefox icon"
```

## 🖥️ Server API

The voice control server provides the following API endpoints:

- **GET /health**: Check server status
- **POST /command**: Execute a text command
- **POST /voice-command**: Process a voice command from audio data
- **POST /transcribe**: Transcribe audio without executing commands
- **POST /translate**: Translate text to English

### Example: Sending a Direct Command

```bash
curl -X POST http://localhost:5000/command \
  -H "Content-Type: application/json" \
  -d '{"command": "open Firefox, go to gmail.com and compose a new email"}'
```

### Example: Sending a Voice Command

```bash
curl -X POST http://localhost:5000/voice-command \
  -F "audio_file=@recording.wav" \
  -F "translate=true" \
  -F "language=es"
```

## 🧪 Project Structure

```
llm-control/
├── llm_control/         # Main Python package
├── scripts/             # Utility scripts
│   ├── docker/          # Docker-related scripts
│   ├── setup/           # Installation scripts
│   └── tools/           # Utility tools
├── data/                # Data files
├── tests/               # Test suite
└── screenshots/         # Screenshots directory
```

## 💡 Command Examples

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

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
