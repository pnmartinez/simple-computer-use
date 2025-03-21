# Simplified Voice Control System

This is a streamlined version of the LLM PC Control system that uses a more direct approach to control your computer with voice commands. It leverages language models to interpret commands and generate PyAutoGUI code for automation.

## Key Features

- **Simple Architecture**: Direct pipeline from voice to action using LLMs
- **Lower Dependencies**: Simplified codebase with minimal required packages
- **Flexible Command Handling**: Uses LLMs directly for interpreting commands and generating automation code
- **Multiple Input Methods**: Record audio from microphone, use audio files, or input commands directly
- **Multilingual Support**: Automatic translation with preservation of UI element names

## Requirements

- Python 3.8+
- OpenAI Whisper (for speech-to-text)
- PyAudio (for audio recording)
- PyAutoGUI (for desktop automation)
- Ollama (for LLM inference)

## Installation

1. Ensure you have Python 3.8+ installed
2. Install required packages:

```bash
# Core dependencies
pip install pyautogui pyaudio requests

# Install Whisper for speech recognition
pip install -U openai-whisper

# For full functionality
pip install numpy soundfile
```

3. Install and run Ollama from [https://ollama.ai/](https://ollama.ai/)
4. Pull the required model (llama3 recommended):

```bash
ollama pull llama3
```

## Usage

### Basic Usage

```bash
# Record audio for 5 seconds and execute the command
./simple_voice_command.py
```

### Command-line Options

```bash
# List all audio devices
./simple_voice_command.py --list-devices

# Check dependencies
./simple_voice_command.py --check-deps

# Use a specific audio device
./simple_voice_command.py --device 1

# Record for a specific duration
./simple_voice_command.py --record-seconds 10

# Use a specific Whisper model
./simple_voice_command.py --whisper-model medium

# Direct command without audio
./simple_voice_command.py --command "click on the Firefox icon"

# Generate code but don't execute (dry run)
./simple_voice_command.py --dry-run
```

### Advanced Options

```bash
# Specify language for transcription
./simple_voice_command.py --language es

# Disable translation
./simple_voice_command.py --disable-translation

# Use a different Ollama model
./simple_voice_command.py --ollama-model mistral

# Use a specific Ollama API host
./simple_voice_command.py --ollama-host http://192.168.1.100:11434
```

## Web Server

A Flask-based web server is also available for integration with web applications:

```bash
# Start the server
python -m llm_control.voice_control_server

# With custom options
python -m llm_control.voice_control_server --host 0.0.0.0 --port 5000 --whisper-model small
```

### Server Endpoints

- `/health` - Check server status
- `/transcribe` - Transcribe audio to text
- `/translate` - Translate text
- `/command` - Execute a text command
- `/voice-command` - Process a voice command from audio

## Examples

### Voice Command Examples

- "Click on the Firefox icon"
- "Open the terminal and type hello world"
- "Press Ctrl+A then delete"
- "Move the mouse to the top-left corner"
- "Find and click on the Settings button"
- "Scroll down"

### Direct Command Examples

```bash
# Open Firefox
./simple_voice_command.py --command "open Firefox"

# Take a screenshot
./simple_voice_command.py --command "take a screenshot"

# Type text
./simple_voice_command.py --command "type 'Hello, world!'"
```

## Troubleshooting

- **Audio recording issues**: Try listing devices with `--list-devices` and select a specific device with `--device`
- **Transcription quality**: Try a larger model with `--whisper-model medium` or `--whisper-model large`
- **Command execution fails**: Try using `--dry-run` to see the generated code without executing it
- **Ollama connection errors**: Make sure Ollama is running and accessible at the specified host
- **Dependencies missing**: Run with `--check-deps` to verify all required packages are installed

## Development

The simplified system consists of:

- `simple_voice_command.py` - Command-line interface for voice commands
- `llm_control/llm/simple_executor.py` - LLM-based command executor
- `llm_control/voice_control_server.py` - Web server for voice commands

## License

This project is licensed under the MIT License - see the LICENSE file for details. 