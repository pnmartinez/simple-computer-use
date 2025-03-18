#!/usr/bin/env python3
"""
Simple voice command script that uses LLMs for direct PyAutoGUI execution.

This script provides a simplified approach to voice control by:
1. Recording audio from the microphone
2. Transcribing with Whisper
3. Translating if needed
4. Using an LLM to directly generate and execute PyAutoGUI code
"""

import os
import sys
import time
import json
import logging
import tempfile
import argparse
import subprocess
from datetime import datetime
from typing import Dict, Any, Optional, List, Union, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Get the logger
logger = logging.getLogger("simple-voice-command")

# Try to import our own modules
try:
    # First try to import as a package
    from llm_control.llm.simple_executor import execute_command_with_llm
except ImportError:
    # If that fails, try to add the parent directory to the path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from llm_control.llm.simple_executor import execute_command_with_llm
    except ImportError:
        # Define a stub function if we can't import
        def execute_command_with_llm(command, model="llama3.1", ollama_host="http://localhost:11434"):
            logger.error("Could not import execute_command_with_llm. Make sure the module is installed.")
            return {
                "success": False,
                "error": "simple_executor module not available",
                "command": command
            }

def check_dependencies():
    """
    Check if required dependencies are installed.
    
    Returns:
        Dictionary with dependency status
    """
    dependencies = {
        "whisper": False,
        "pyaudio": False,
        "requests": False,
        "pyautogui": False,
        "ollama": "unknown"
    }
    
    # Check Python packages
    try:
        import whisper
        dependencies["whisper"] = True
    except ImportError:
        pass
    
    try:
        import pyaudio
        dependencies["pyaudio"] = True
    except ImportError:
        pass
    
    try:
        import requests
        dependencies["requests"] = True
        
        # Check if Ollama is running
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            dependencies["ollama"] = response.status_code == 200
        except:
            dependencies["ollama"] = False
    except ImportError:
        pass
    
    try:
        import pyautogui
        dependencies["pyautogui"] = True
    except ImportError:
        pass
    
    return dependencies

def list_audio_devices():
    """
    List available audio input devices.
    
    Returns:
        Dictionary with device information
    """
    try:
        import pyaudio
        
        p = pyaudio.PyAudio()
        devices = []
        
        for i in range(p.get_device_count()):
            device_info = p.get_device_info_by_index(i)
            # Only include input devices
            if device_info.get('maxInputChannels') > 0:
                devices.append({
                    "index": i,
                    "name": device_info.get('name'),
                    "channels": device_info.get('maxInputChannels'),
                    "default": i == p.get_default_input_device_info().get('index')
                })
        
        p.terminate()
        
        return {
            "devices": devices,
            "count": len(devices)
        }
    
    except ImportError:
        return {
            "error": "PyAudio is not installed. Install with 'pip install pyaudio'",
            "devices": [],
            "count": 0
        }
    except Exception as e:
        return {
            "error": str(e),
            "devices": [],
            "count": 0
        }

def record_audio(seconds=5, device_index=None, save_path=None, rate=16000):
    """
    Record audio from the microphone.
    
    Args:
        seconds: Number of seconds to record
        device_index: PyAudio device index (None for default device)
        save_path: Path to save the audio file (None for temporary file)
        rate: Sample rate
        
    Returns:
        Path to the recorded audio file
    """
    try:
        import pyaudio
        import wave
        
        if save_path is None:
            # Create a temporary file
            fd, save_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
        
        logger.info(f"Recording audio for {seconds} seconds...")
        
        # Initialize PyAudio
        p = pyaudio.PyAudio()
        
        # Open stream
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=1024
        )
        
        # Record audio
        frames = []
        
        for i in range(0, int(rate / 1024 * seconds)):
            data = stream.read(1024)
            frames.append(data)
        
        # Stop and close the stream
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        logger.info("Recording finished")
        
        # Save to file
        with wave.open(save_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(rate)
            wf.writeframes(b''.join(frames))
        
        logger.info(f"Audio saved to {save_path}")
        
        return save_path
    
    except ImportError:
        logger.error("PyAudio is not installed. Install with 'pip install pyaudio'")
        return None
    except Exception as e:
        logger.error(f"Error recording audio: {str(e)}")
        return None

def transcribe_audio(audio_path, model_size="base", language=None):
    """
    Transcribe audio using Whisper.
    
    Args:
        audio_path: Path to the audio file
        model_size: Whisper model size
        language: Language code (None for auto-detection)
        
    Returns:
        Dictionary with transcription results
    """
    try:
        import whisper
        
        logger.info(f"Loading Whisper model: {model_size}")
        model = whisper.load_model(model_size)
        
        logger.info(f"Transcribing audio: {audio_path}")
        result = model.transcribe(audio_path, language=language)
        
        logger.info(f"Transcription: {result['text']}")
        
        return {
            "success": True,
            "text": result.get("text", "").strip(),
            "language": result.get("language", "unknown")
        }
    
    except ImportError:
        logger.error("Whisper is not installed. Install with 'pip install -U openai-whisper'")
        return {
            "success": False,
            "error": "Whisper is not installed"
        }
    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def translate_text(text, model="llama3.1", ollama_host="http://localhost:11434"):
    """
    Translate text from any language to English using Ollama.
    
    Args:
        text: Text to translate
        model: Ollama model to use
        ollama_host: Ollama API host
        
    Returns:
        Translated text or None if translation failed
    """
    try:
        import requests
        
        logger.info(f"Translating with Ollama: {text}")
        
        # Check if Ollama is running
        try:
            response = requests.get(f"{ollama_host}/api/tags", timeout=2)
            if response.status_code != 200:
                logger.error(f"Ollama server not responding at {ollama_host}")
                return None
        except requests.exceptions.RequestException:
            logger.error(f"Ollama server not available at {ollama_host}")
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
        - "actividades" should stay as "actividades" (NEVER translate to "activities")
        - "opciones" should stay as "opciones" (NEVER translate to "options")
        - "archivo" should stay as "archivo" (NEVER translate to "file")
        - "nueva pestaña" should stay as "nueva pestaña" (NEVER translate to "new tab")
        
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
            logger.error(f"Error from Ollama API: {response.status_code}")
            return None
        
        # Parse response
        result = response.json()
        translated_text = result["response"].strip()
        
        # Clean up the response
        translated_text = clean_llm_response(translated_text)
        
        logger.info(f"Translated: {text} → {translated_text}")
        
        return translated_text
    
    except Exception as e:
        logger.error(f"Error translating with Ollama: {str(e)}")
        return None

def clean_llm_response(response):
    """
    Clean LLM response to remove explanatory text.
    
    Args:
        response: Raw LLM response
        
    Returns:
        Cleaned response
    """
    if not response:
        return ""
    
    # Remove common prefixes
    prefixes = [
        "Here is the translation",
        "The translation is",
        "Translation:",
        "Translated text:",
        "Here's the translation",
        "Translated version:"
    ]
    
    cleaned = response
    
    for prefix in prefixes:
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip()
            # Remove any punctuation after the prefix
            if cleaned and cleaned[0] in ':.':
                cleaned = cleaned[1:].strip()
    
    # Remove explanatory notes
    explanatory_markers = [
        "\n\nNote:",
        "\n\nPlease note",
        "\n\nI have",
        "\n\nObserve",
        "\n\nAs requested",
        "\n\nThe original"
    ]
    
    for marker in explanatory_markers:
        if marker.lower() in cleaned.lower():
            cleaned = cleaned.split(marker.lower(), 1)[0].strip()
    
    # If multiple paragraphs, take the first one if it looks like a complete command
    paragraphs = [p for p in cleaned.split('\n\n') if p.strip()]
    if len(paragraphs) > 1:
        # Check if first paragraph contains common verbs
        first_para = paragraphs[0].lower()
        if any(verb in first_para for verb in ['click', 'type', 'press', 'move', 'open']):
            cleaned = paragraphs[0]
    
    # Remove markdown code blocks
    cleaned = cleaned.replace('```', '').strip()
    
    # Remove trailing punctuation
    cleaned = cleaned.rstrip('.,:;')
    
    return cleaned.strip()

def process_voice_command(audio_path=None, command=None, model_size="base", translate=True, 
                          language=None, ollama_model="llama3.1", ollama_host="http://localhost:11434",
                          record_seconds=5, device_index=None, dry_run=False):
    """
    Process a voice command.
    
    Args:
        audio_path: Path to the audio file (None to record from microphone)
        command: Text command (bypasses audio recording/transcription)
        model_size: Whisper model size ("tiny", "base", "small", "medium", "large")
        translate: Whether to translate non-English text
        language: Expected language
        ollama_model: Ollama model to use
        ollama_host: Ollama API host
        record_seconds: Number of seconds to record
        device_index: PyAudio device index
        dry_run: Whether to just generate code without executing it
        
    Returns:
        Command processing results
    """
    try:
        # Step 1: Get the command (from text or audio)
        if command is None:
            # If no audio file is provided, record from microphone
            if audio_path is None:
                audio_path = record_audio(record_seconds, device_index)
                
                if audio_path is None:
                    return {
                        "success": False,
                        "error": "Failed to record audio"
                    }
            
            # Transcribe the audio
            result = transcribe_audio(audio_path, model_size, language)
            
            if not result.get("success", False):
                return {
                    "success": False,
                    "error": result.get("error", "Transcription failed")
                }
            
            # Get the transcription and detected language
            text = result.get("text", "").strip()
            detected_language = result.get("language", "unknown")
            
            if not text:
                return {
                    "success": False,
                    "error": "No speech detected in the audio"
                }
        else:
            # Use the provided command
            text = command
            detected_language = language or "unknown"
        
        # Step 2: Translate if needed
        final_command = text
        translated = False
        
        if translate and detected_language not in ["en", "English", "english", "eng"]:
            logger.info(f"Translating: {text} (detected language: {detected_language})")
            
            translated_text = translate_text(text, ollama_model, ollama_host)
            
            if translated_text:
                final_command = translated_text
                translated = True
                logger.info(f"Translation: {text} → {final_command}")
            else:
                logger.warning("Translation failed, using original text")
        
        # Step 3: Execute the command with the LLM
        logger.info(f"Executing command: {final_command}")
        
        execution_result = execute_command_with_llm(
            final_command, 
            ollama_model, 
            ollama_host,
            dry_run=dry_run
        )
        
        # Prepare the response
        response = {
            "success": execution_result.get("success", False),
            "command": {
                "original": text,
                "language": detected_language,
                "translated": translated
            },
            "execution": execution_result
        }
        
        # Add translation if applicable
        if translated:
            response["command"]["translated_text"] = final_command
        
        # Add error message if execution failed
        if not execution_result.get("success", False):
            response["error"] = execution_result.get("error", "Unknown execution error")
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing voice command: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "success": False,
            "error": str(e)
        }

def parse_args():
    """
    Parse command-line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description='Simple voice command script')
    
    # Input options
    input_group = parser.add_argument_group('Input options')
    input_group.add_argument('--file', type=str, help='Path to audio file (default: record from microphone)')
    input_group.add_argument('--command', type=str, help='Text command (bypass audio recording/transcription)')
    input_group.add_argument('--record-seconds', type=int, default=5, help='Number of seconds to record (default: 5)')
    input_group.add_argument('--device', type=int, help='PyAudio device index (default: system default)')
    input_group.add_argument('--list-devices', action='store_true', help='List available audio devices')
    
    # Whisper options
    whisper_group = parser.add_argument_group('Whisper options')
    whisper_group.add_argument('--whisper-model', type=str, default='base',
                             choices=['tiny', 'base', 'small', 'medium', 'large'],
                             help='Whisper model size (default: base)')
    whisper_group.add_argument('--language', type=str, help='Expected language code (default: auto-detect)')
    
    # Ollama options
    ollama_group = parser.add_argument_group('Ollama options')
    ollama_group.add_argument('--ollama-model', type=str, default='llama3.1',
                             help='Ollama model to use (default: llama3.1)')
    ollama_group.add_argument('--ollama-host', type=str, default='http://localhost:11434',
                             help='Ollama API host (default: http://localhost:11434)')
    
    # Translation options
    translation_group = parser.add_argument_group('Translation options')
    translation_group.add_argument('--disable-translation', action='store_true',
                                help='Disable automatic translation of non-English languages')
    
    # Execution options
    execution_group = parser.add_argument_group('Execution options')
    execution_group.add_argument('--dry-run', action='store_true',
                              help='Generate PyAutoGUI code without executing it')
    
    # Other options
    other_group = parser.add_argument_group('Other options')
    other_group.add_argument('--check-deps', action='store_true',
                          help='Check dependencies and exit')
    other_group.add_argument('--verbose', action='store_true',
                           help='Enable verbose logging')
    
    return parser.parse_args()

def main():
    """
    Main entry point.
    """
    args = parse_args()
    
    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Check dependencies
    if args.check_deps:
        deps = check_dependencies()
        print(json.dumps(deps, indent=2))
        return
    
    # List audio devices
    if args.list_devices:
        devices = list_audio_devices()
        print(json.dumps(devices, indent=2))
        return
    
    # Process voice command
    result = process_voice_command(
        audio_path=args.file,
        command=args.command,
        model_size=args.whisper_model,
        translate=not args.disable_translation,
        language=args.language,
        ollama_model=args.ollama_model,
        ollama_host=args.ollama_host,
        record_seconds=args.record_seconds,
        device_index=args.device,
        dry_run=args.dry_run
    )
    
    # Print the result
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main() 