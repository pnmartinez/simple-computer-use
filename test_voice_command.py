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

def transcribe_audio(audio_file, model_size="base", language=None):
    """
    Transcribe audio using Whisper
    
    Args:
        audio_file: Path to the audio file
        model_size: Whisper model size
        language: Language code to expect (if None, uses WHISPER_LANGUAGE env var or defaults to 'es')
        
    Returns:
        Whisper result dictionary containing transcription and metadata
    """
    # Determine the language to use (parameter, env var, or default to Spanish)
    if language is None:
        language = os.environ.get("WHISPER_LANGUAGE", "es")
        
    print(f"\n🔄 Transcribing audio with Whisper ({model_size} model, expecting {language})...")
    
    # Import whisper here to avoid loading it unnecessarily
    import whisper
    
    try:
        # Load the model
        print("Loading Whisper model...")
        model = whisper.load_model(model_size)
        
        # Transcribe the audio
        print("Transcribing audio...")
        result = model.transcribe(audio_file, language=language)
        
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
        
        # Handle typing - support both English and Spanish
        english_type_cmds = ["type", "write", "enter"]
        spanish_type_cmds = ["escribe", "escribir", "teclea", "teclear", "ingresa", "ingresar"]
        
        if any(cmd in command_lower for cmd in english_type_cmds + spanish_type_cmds):
            # Extract text to type
            text_to_type = ""
            
            # Try to find the text after any of the typing commands
            for cmd in english_type_cmds + spanish_type_cmds:
                if cmd in command_lower:
                    start_index = command_lower.find(cmd) + len(cmd)
                    text_to_type = command[start_index:].strip()
                    break
                    
            print(f"Typing: {text_to_type}")
            time.sleep(1)  # Give time to focus
            pyautogui.typewrite(text_to_type)
            return f"Typed: {text_to_type}"
            
        # Handle pressing keys - support both English and Spanish
        elif any(press_cmd in command_lower for press_cmd in ["press", "hit", "pulsa", "presiona", "oprime"]):
            key_mapping = {
                # English keys
                "enter": "enter", "return": "enter",
                "space": "space", "spacebar": "space",
                "tab": "tab",
                "escape": "esc", "esc": "esc",
                "up": "up", "down": "down", "left": "left", "right": "right",
                
                # Spanish keys
                "intro": "enter", "entrar": "enter", "ingresar": "enter",
                "espacio": "space", "barra": "space", "barra espaciadora": "space",
                "tabulador": "tab", "tabulación": "tab",
                "escape": "esc", "salir": "esc",
                "arriba": "up", "subir": "up",
                "abajo": "down", "bajar": "down",
                "izquierda": "left",
                "derecha": "right"
            }
            
            for key_name, key_code in key_mapping.items():
                if key_name in command_lower:
                    print(f"Pressing key: {key_name} → {key_code}")
                    time.sleep(0.5)
                    pyautogui.press(key_code)
                    return f"Pressed key: {key_name}"
            
            # If no specific key found
            return "No recognized key to press"
            
        # Handle clicking - support both English and Spanish
        elif any(click_cmd in command_lower for click_cmd in ["click", "clic", "hacer clic", "pulsa"]):
            print("Performing click")
            time.sleep(0.5)
            pyautogui.click()
            return "Clicked at current position"
            
        # Handle taking screenshot - support both English and Spanish
        elif any(ss_cmd in command_lower for ss_cmd in ["screenshot", "screen shot", "captura", "captura de pantalla"]):
            screenshot_path = f"screenshot_{int(time.time())}.png"
            print(f"Taking screenshot: {screenshot_path}")
            pyautogui.screenshot(screenshot_path)
            return f"Screenshot saved to {screenshot_path}"
            
        # Default case
        else:
            print(f"Command not recognized: '{command}'")
            print("Supported commands: type/write/escribe text, press/pulsa key, click/clic, screenshot/captura")
            return "Command not recognized"
            
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}"

def clean_llm_response(response: str, original_text: str) -> str:
    """
    Clean LLM response to remove explanatory text, notes, headers, etc.
    
    Args:
        response: Raw LLM response to clean
        original_text: Original text that was translated (for length reference)
        
    Returns:
        Cleaned response with only the translated text
    """
    # Remove common prefixes LLMs might add
    prefixes = [
        "Here is the translation",
        "The translation is",
        "Translation:",
        "Translated text:",
        "Here's the translation",
        "Translated version:"
    ]
    
    cleaned_response = response
    
    for prefix in prefixes:
        if cleaned_response.lower().startswith(prefix.lower()):
            # Find the first occurrence after the prefix that's not a whitespace
            start_idx = len(prefix)
            while start_idx < len(cleaned_response) and cleaned_response[start_idx] in [' ', ':', '\n', '\t']:
                start_idx += 1
            cleaned_response = cleaned_response[start_idx:]
    
    # Remove explanatory notes often added at the end
    explanatory_markers = [
        "\n\nNote:",
        "\n\nPlease note",
        "\n\nI have",
        "\n\nObserve",
        "\n\nAs requested",
        "\n\nThe original"
    ]
    
    for marker in explanatory_markers:
        if marker.lower() in cleaned_response.lower():
            end_idx = cleaned_response.lower().find(marker.lower())
            cleaned_response = cleaned_response[:end_idx].strip()
    
    # Sanity check: if the cleaned text is much shorter than the original, 
    # it might be an indication that we removed too much
    if len(cleaned_response) < 0.5 * len(original_text) and len(original_text) > 20:
        print(f"⚠️ Cleaned response is significantly shorter than original, using original LLM output")
        return response
        
    # If the response has multiple paragraphs and the first one looks like a complete command,
    # just keep the first paragraph
    paragraphs = [p for p in cleaned_response.split('\n\n') if p.strip()]
    if len(paragraphs) > 1 and any(verb in paragraphs[0].lower() for verb in ['click', 'type', 'press', 'move', 'select']):
        cleaned_response = paragraphs[0].strip()
        
    # Remove any trailing periods or other punctuation
    cleaned_response = cleaned_response.rstrip('.,:;')
    
    return cleaned_response.strip()

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
        Translate the following text to English.
        
        CRITICAL: DO NOT translate any of the following:
        1. Proper nouns, UI element names, button labels, or technical terms
        2. Menu items, tabs, or buttons (like "Actividades", "Archivo", "Configuración")
        3. Application names (like "Firefox", "Chrome", "Terminal")
        4. Text inside quotes (e.g., "Hola mundo")
        5. Any word that might be a desktop element or application name
        
        EXAMPLES of words to KEEP in original language:
        - "actividades" should stay as "actividades"
        - "opciones" should stay as "opciones" 
        - "archivo" should stay as "archivo"
        - "nueva pestaña" should stay as "nueva pestaña"
        
        Spanish → English examples with preserved text:
        - "haz clic en el botón Cancelar" → "click on the Cancelar button"
        - "escribe 'Hola mundo' en el campo Mensaje" → "type 'Hola mundo' in the Mensaje field"
        - "presiona enter en la ventana Configuración" → "press enter in the Configuración window"
        - "selecciona Archivo desde el menú" → "select Archivo from the menu"
        - "mueve el cursor a actividades" → "move the cursor to actividades"
        
        ```
        {text}
        ```
        
        RETURN ONLY THE TRANSLATED TEXT - NOTHING ELSE. NO EXPLANATIONS. NO HEADERS. NO NOTES.
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
        
        # Clean the response to remove explanatory text
        translated_text = clean_llm_response(translated_text, text)
        
        print(f"✅ Original text: {text}")
        print(f"✅ Translated with preserved UI targets: {translated_text}")
        
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
    
    parser.add_argument(
        "--language", 
        type=str, 
        default="es",
        help="Expected language for voice recognition (default: es - Spanish)"
    )
    
    return parser.parse_args()

def main():
    """Main entry point"""
    # Check dependencies
    check_dependencies()
    
    # Parse arguments
    args = parse_args()
    
    # Set language environment variable for any subprocesses
    os.environ["WHISPER_LANGUAGE"] = args.language
    
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
        model_size=args.whisper_model,
        language=args.language
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