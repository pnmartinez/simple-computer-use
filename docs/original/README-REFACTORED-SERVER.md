# Refactored Voice Control Server

This document explains the changes to the voice control server and how to use the new multi-step LLM processing approach.

## Overview of Changes

The voice command processing has been completely refactored to use a more structured approach:

1. **Step Identification**: The input command is first analyzed by an LLM to break it down into discrete, actionable steps.
2. **OCR Target Identification**: Each step is processed to identify text that needs to be visually detected on screen, and these targets are wrapped in quotes.
3. **PyAutoGUI Command Generation**: Each step is converted into a specific PyAutoGUI command, with explicit target identification.
4. **Sequential Execution**: Each step is executed in order, with proper error handling and feedback.

This approach provides much better reasoning and explainability. By breaking down complex commands into discrete steps, the system can handle multi-part operations more reliably.

## How to Run the Server

There are two ways to run the refactored server:

### 1. Using the Module Entry Point

```bash
# Basic usage with defaults
python -m llm_control voice-server

# With custom options
python -m llm_control voice-server --port 8080 --whisper-model medium
```

### 2. Running the Server File Directly

```bash
# Basic usage
python -m llm_control.voice_control_server

# With custom options
python -m llm_control.voice_control_server --port 8080 --whisper-model medium
```

## Command Line Options

The server supports these command-line options:

- `--host ADDRESS`: Host address to bind to (default: 0.0.0.0)
- `--port NUMBER`: Port to bind to (default: 5000)
- `--debug`: Enable debug mode
- `--whisper-model SIZE`: Whisper model size (tiny/base/small/medium/large)
- `--ollama-model MODEL`: Ollama model to use (default: llama3.1)
- `--ollama-host URL`: Ollama API host (default: http://localhost:11434)
- `--disable-translation`: Disable automatic translation
- `--language CODE`: Default language for voice recognition (default: es)

## Server Endpoints

The refactored server provides the following endpoints:

### `/health` (GET)

Checks the server health and provides information about available components (Whisper and Ollama).

### `/transcribe` (POST)

Transcribes audio data to text.

**Parameters**:
- `audio_file`: The audio file to transcribe (form data)
- `model_size`: Whisper model size (optional, default from server config)
- `language`: Language code (optional, default from server config)

### `/translate` (POST)

Translates text from one language to English.

**Parameters**:
- `text`: Text to translate (JSON body)
- `model`: Ollama model to use (optional, default from server config)

### `/command` (POST)

Executes a command using the multi-step LLM processing approach.

**Parameters**:
- `command`: Command to execute (JSON body)
- `model`: Ollama model to use (optional)

**Response**:
```json
{
  "status": "success",
  "command": "click on the Firefox icon",
  "steps": ["Find and click on the Firefox icon"],
  "actions": [
    {
      "description": "Click on Firefox icon",
      "target": "Firefox",
      "pyautogui_cmd": "...",
      "execution_result": { "success": true }
    }
  ],
  "steps_summary": [
    {
      "step_number": 1,
      "description": "Click on Firefox icon",
      "target": "Firefox",
      "success": true
    }
  ]
}
```

### `/voice-command` (POST)

Processes a voice command from audio data using the multi-step approach.

**Parameters**:
- `audio_file`: The audio file containing the voice command (form data)
- `model_size`: Whisper model size (optional)
- `translate`: Whether to translate non-English text (optional)
- `language`: Language code (optional)
- `model`: Ollama model to use (optional)

**Response**: Same structure as the `/command` endpoint, with additional information about transcription and translation.

## Example Usage

### 1. Sending a Direct Command

```bash
curl -X POST http://localhost:5000/command \
  -H "Content-Type: application/json" \
  -d '{"command": "open Firefox, go to gmail.com and compose a new email"}'
```

### 2. Sending a Voice Command (Using Recorded Audio)

```bash
curl -X POST http://localhost:5000/voice-command \
  -F "audio_file=@recording.wav" \
  -F "translate=true" \
  -F "language=es"
```

## How the Multi-Step Process Works

1. **Input**: User provides a voice command or direct text command
2. **Step 1**: Transcription (for voice commands)
3. **Step 2**: Translation if needed (for non-English input)
4. **Step 3**: The LLM breaks down the command into individual steps
   - Example: "Open Firefox and go to Gmail" → ["Find and click on Firefox icon", "Wait for Firefox to load", "Type gmail.com in address bar", "Press Enter"]
5. **Step 4**: Command integrity verification - removes any hallucinated content
   - Compares each step against the original command to ensure no extra details were added
   - Example: "Find and click on the Firefox icon on the desktop" → "Find and click on the Firefox icon"
6. **Step 5**: For each step, OCR targets are identified and wrapped in quotes
   - Example: "Find and click on Firefox icon" → "Find and click on "Firefox" icon"
7. **Step 6**: Each step with OCR targets is converted to a PyAutoGUI command
8. **Step 7**: Each command is executed sequentially

This approach provides better understanding of complex tasks and more reliable execution of multi-step commands.

## Customizing the Refactored Server

You can modify the prompts and behavior of the LLM calls in the following functions:

- `split_command_into_steps()`: Controls how commands are broken down into steps
- `identify_ocr_targets()`: Controls how OCR targets are identified
- `generate_pyautogui_actions()`: Controls how PyAutoGUI commands are generated

## Allowed PyAutoGUI Commands

For security and reliability, the system restricts PyAutoGUI commands to only the following operations:

### 1. Mouse Operations
- `pyautogui.moveTo(x, y)` - Move mouse to absolute position
- `pyautogui.move(x, y)` - Move mouse relative to current position
- `pyautogui.click(x, y)` - Click at position
- `pyautogui.doubleClick(x, y)` - Double-click at position
- `pyautogui.rightClick(x, y)` - Right-click at position
- `pyautogui.dragTo(x, y)` - Drag to position

### 2. Keyboard Operations
- `pyautogui.write('text')` - Type text
- `pyautogui.press('key')` - Press a key (e.g., 'enter', 'tab', 'escape')
- `pyautogui.hotkey('key1', 'key2', ...)` - Press keys together (e.g., 'ctrl', 'c')

### 3. Scrolling Operations
- `pyautogui.scroll(amount)` - Scroll up (positive) or down (negative)

### 4. Screenshot Operations
- `pyautogui.screenshot()` - Take a screenshot

These restrictions ensure that only simple, predictable operations are performed, making the system more reliable and secure. If the LLM generates code using disallowed functions, the system automatically substitutes a safe fallback implementation.

## PyAutoGUI Failsafe Control

For safety reasons, PyAutoGUI typically includes a "failsafe" feature that stops all automation when the mouse cursor is moved to the upper-left corner of the screen. This is intended as an emergency stop mechanism.

In the refactored server, **PyAutoGUI failsafe is disabled by default** to ensure uninterrupted execution of commands. However, you can still enable it if desired.

### Control Failsafe via Command Line

```bash
# Run with failsafe disabled (default)
python -m llm_control.voice_control_server

# Run with failsafe enabled
python -m llm_control.voice_control_server --enable-failsafe
```

### Control Failsafe via API

When using the `/command` endpoint, you can set the failsafe option:

```bash
# Command with failsafe disabled
curl -X POST http://localhost:5000/command \
  -H "Content-Type: application/json" \
  -d '{"command": "click on Firefox", "enable_failsafe": false}'

# Command with failsafe enabled
curl -X POST http://localhost:5000/command \
  -H "Content-Type: application/json" \
  -d '{"command": "click on Firefox", "enable_failsafe": true}'
```

When using the `/voice-command` endpoint:

```bash
# Voice command with failsafe disabled (default)
curl -X POST http://localhost:5000/voice-command \
  -F "audio_file=@recording.wav" \
  -F "enable_failsafe=false"

# Voice command with failsafe enabled
curl -X POST http://localhost:5000/voice-command \
  -F "audio_file=@recording.wav" \
  -F "enable_failsafe=true"
```

### Caution

When the failsafe is disabled, automated actions can't be stopped by moving the mouse to the corner. Make sure you have another way to stop runaway automation if needed (like Ctrl+C in the terminal where the server is running). 