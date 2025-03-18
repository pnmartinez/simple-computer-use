#!/usr/bin/env python3
"""
Test voice command functionality locally without a server.
Records audio from the microphone, transcribes it with Whisper, 
and executes the resulting command.
"""

import os
import sys
import time
import argparse
import tempfile
import logging
import numpy as np
import sounddevice as sd
import soundfile as sf
import pyautogui  # For executing commands directly
import json
import requests  # For Ollama API calls

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Get the logger
logger = logging.getLogger("test-voice-command")

def check_dependencies():
    """Check if required packages are installed"""
    try:
        # First try to import the packages
        import sounddevice
        import soundfile
        import whisper
        import numpy
        import pyautogui
        import requests
    except ImportError as e:
        print(f"Missing required dependency: {e}")
        print("Please install the required packages:")
        print("pip install sounddevice soundfile openai-whisper numpy pyautogui requests")
        sys.exit(1)
    except OSError as e:
        if "PortAudio" in str(e):
            print("❌ PortAudio library not found")
            print("This is a system dependency required for audio recording.")
            print("\nPlease install PortAudio on your system:")
            print("- Ubuntu/Debian: sudo apt-get install portaudio19-dev")
            print("- Fedora/RHEL: sudo dnf install portaudio-devel")
            print("- Arch Linux: sudo pacman -S portaudio")
            print("- macOS: brew install portaudio")
            print("\nAfter installing PortAudio, reinstall sounddevice:")
            print("pip uninstall -y sounddevice && pip install sounddevice")
            sys.exit(1)
        else:
            # Re-raise if it's not a PortAudio issue
            raise

def list_audio_devices():
    """List available audio input devices"""
    print("\nAvailable audio input devices:")
    print("-" * 60)
    print(f"{'ID':<5} {'Name':<30} {'Channels':<10} {'Sample Rate':<15}")
    print("-" * 60)
    
    devices = sd.query_devices()
    
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            name = device['name']
            channels = device['max_input_channels']
            sample_rate = device['default_samplerate']
            print(f"{i:<5} {name[:30]:<30} {channels:<10} {sample_rate:<15.0f}")
    
    print("\nUse --device <ID> to select a specific device")

def record_audio(device=None, duration=5, sample_rate=16000, channels=1):
    """
    Record audio from the microphone
    
    Args:
        device: Audio device ID or name
        duration: Recording duration in seconds
        sample_rate: Sample rate in Hz
        channels: Number of channels
        
    Returns:
        Path to the recorded audio file
    """
    print(f"\n🎙️ Recording audio for {duration} seconds...")
    print("Speak your command now")
    
    # Create countdown
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(0.5)
    
    print("Recording...")
    
    # Record audio
    recording = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=channels,
        device=device,
        dtype='float32'
    )
    
    # Wait for the recording to finish
    sd.wait()
    
    print("Recording finished!")
    
    # Normalize the recording
    recording = recording / np.max(np.abs(recording))
    
    # Create a temporary file for the audio
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_path = temp_file.name
    
    # Save the recording to a WAV file
    sf.write(temp_path, recording, sample_rate)
    
    print(f"Audio saved to {temp_path}")
    
    return temp_path

def transcribe_audio(audio_file, model_size="base"):
    """
    Transcribe audio using Whisper
    
    Args:
        audio_file: Path to the audio file
        model_size: Whisper model size
        
    Returns:
        Whisper result dictionary containing transcription and metadata
    """
    print(f"\n🔄 Transcribing audio with Whisper ({model_size} model)...")
    
    # Import whisper here to avoid loading it unnecessarily
    import whisper
    
    try:
        # Load the model
        print("Loading Whisper model...")
        model = whisper.load_model(model_size)
        
        # Transcribe the audio
        print("Transcribing audio...")
        result = model.transcribe(audio_file)
        
        # Get the transcription
        transcription = result["text"].strip()
        
        print(f"✅ Transcription: {transcription}")
        print(f"🔍 Detected language: {result.get('language', 'unknown')}")
        
        return result
    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def execute_command(command):
    """
    Execute a simplified version of the command
    This is a standalone implementation that doesn't rely on llm_control.main
    
    Args:
        command: Command to execute
        
    Returns:
        Result of the command execution
    """
    print(f"\n⚙️ Executing command: {command}")
    
    try:
        # Simple command execution based on keywords
        if not command:
            print("Empty command, nothing to execute")
            return "No command detected"
        
        command_lower = command.lower()
        
        # Handle typing
        if "type" in command_lower or "write" in command_lower:
            # Extract text to type - simple method, just get everything after "type" or "write"
            text_to_type = ""
            if "type" in command_lower:
                text_to_type = command[command_lower.find("type") + 4:].strip()
            elif "write" in command_lower:
                text_to_type = command[command_lower.find("write") + 5:].strip()
                
            print(f"Typing: {text_to_type}")
            time.sleep(1)  # Give time to focus
            pyautogui.typewrite(text_to_type)
            return f"Typed: {text_to_type}"
            
        # Handle pressing keys
        elif "press" in command_lower:
            key_mapping = {
                "enter": "enter",
                "return": "enter",
                "space": "space",
                "tab": "tab",
                "escape": "esc",
                "esc": "esc",
                "up": "up",
                "down": "down",
                "left": "left",
                "right": "right",
            }
            
            for key_name, key_code in key_mapping.items():
                if key_name in command_lower:
                    print(f"Pressing key: {key_name}")
                    time.sleep(0.5)
                    pyautogui.press(key_code)
                    return f"Pressed key: {key_name}"
            
            # If no specific key found
            return "No recognized key to press"
            
        # Handle clicking
        elif "click" in command_lower:
            print("Performing click")
            time.sleep(0.5)
            pyautogui.click()
            return "Clicked at current position"
            
        # Handle taking screenshot
        elif "screenshot" in command_lower or "screen shot" in command_lower:
            screenshot_path = f"screenshot_{int(time.time())}.png"
            print(f"Taking screenshot: {screenshot_path}")
            pyautogui.screenshot(screenshot_path)
            return f"Screenshot saved to {screenshot_path}"
            
        # Default case
        else:
            print(f"Command not recognized: '{command}'")
            print("Supported commands: type/write text, press key, click, screenshot")
            return "Command not recognized"
            
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}"

def translate_with_ollama(text, model="llama3.1", ollama_host="http://localhost:11434"):
    """
    Translate text from any language to English using Ollama
    
    Args:
        text: Text to translate
        model: Ollama model to use
        ollama_host: Ollama API host
        
    Returns:
        Translated text
    """
    print(f"\n🔄 Translating with Ollama ({model})...")
    
    try:
        # Check if Ollama is running
        try:
            response = requests.get(f"{ollama_host}/api/tags", timeout=2)
            if response.status_code != 200:
                print(f"❌ Ollama server not responding at {ollama_host}")
                return None
        except requests.exceptions.RequestException:
            print(f"❌ Ollama server not available at {ollama_host}")
            return None
        
        # Prepare the prompt for translation
        prompt = f"""
        Translate the following text to English:
        
        ```
        {text}
        ```
        
        Respond with ONLY the translated English text, nothing else.
        """
        
        # Make API request to Ollama
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Error from Ollama API: {response.status_code}")
            print(response.text)
            return None
        
        # Parse response
        result = response.json()
        translated_text = result["response"].strip()
        
        print(f"✅ Original text: {text}")
        print(f"✅ Translated to English: {translated_text}")
        
        return translated_text
    
    except Exception as e:
        logger.error(f"Error translating with Ollama: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Test voice command functionality"
    )
    
    parser.add_argument(
        "--duration", 
        type=int, 
        default=5,
        help="Recording duration in seconds (default: 5)"
    )
    
    parser.add_argument(
        "--device", 
        type=int,
        help="Audio input device ID"
    )
    
    parser.add_argument(
        "--list-devices", 
        action="store_true",
        help="List available audio input devices"
    )
    
    parser.add_argument(
        "--sample-rate", 
        type=int, 
        default=16000,
        help="Sample rate in Hz (default: 16000)"
    )
    
    parser.add_argument(
        "--transcribe-only", 
        action="store_true",
        help="Only transcribe the audio, don't execute the command"
    )
    
    parser.add_argument(
        "--whisper-model", 
        type=str, 
        choices=["tiny", "base", "small", "medium", "large"],
        default="base",
        help="Whisper model size (default: base)"
    )
    
    parser.add_argument(
        "--no-translate", 
        action="store_true",
        help="Disable automatic translation of non-English languages to English (enabled by default)"
    )
    
    parser.add_argument(
        "--ollama-model", 
        type=str, 
        default="llama3.1",
        help="Ollama model to use for translation (default: llama3.1)"
    )
    
    parser.add_argument(
        "--ollama-host", 
        type=str, 
        default="http://localhost:11434",
        help="Ollama API host (default: http://localhost:11434)"
    )
    
    return parser.parse_args()

def main():
    """Main entry point"""
    # Check dependencies
    check_dependencies()
    
    # Parse arguments
    args = parse_args()
    
    # List audio devices if requested
    if args.list_devices:
        list_audio_devices()
        sys.exit(0)
    
    # Record audio
    audio_file = record_audio(
        device=args.device,
        duration=args.duration,
        sample_rate=args.sample_rate
    )
    
    # Transcribe audio
    result = transcribe_audio(
        audio_file=audio_file,
        model_size=args.whisper_model
    )
    
    # Clean up audio file
    os.unlink(audio_file)
    
    # If transcription failed, exit
    if result is None:
        print("\n❌ Transcription failed")
        sys.exit(1)
    
    # Get the text from the result
    transcription = result["text"].strip()
    
    # If only transcribing, exit
    if args.transcribe_only:
        print("\n✅ Transcription only mode, not executing command")
        sys.exit(0)
    
    # Check if translation is needed (unless explicitly disabled)
    command = transcription
    language = result.get("language", "unknown")
    if (not args.no_translate) and language != "en":
        print(f"\n🌍 Detected non-English text (language={language}), translating to English...")
        translated = translate_with_ollama(
            transcription,
            model=args.ollama_model,
            ollama_host=args.ollama_host
        )
        
        if translated:
            command = translated
        else:
            print("⚠️ Translation failed, using original text")
    
    # Execute command
    result = execute_command(command)
    
    # Display result
    print("\n📋 Command execution result:")
    print("-" * 60)
    print(result)
    print("-" * 60)
    
    if result.startswith("Error:"):
        print("\n❌ Command execution failed")
        sys.exit(1)
    else:
        print("\n✅ Command executed successfully")

if __name__ == "__main__":
    main() 