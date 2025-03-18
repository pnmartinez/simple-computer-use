"""
Simplified voice control server module.

This module provides a lightweight web server for voice command processing,
using a more direct LLM-based approach instead of complex parsing rules.
"""

import os
import sys
import time
import logging
import tempfile
import json
from typing import Dict, Any, Optional, Tuple
from functools import wraps

from flask import Flask, request, jsonify, make_response, Response

# Import from our own modules if available
try:
    from llm_control.llm.simple_executor import execute_command_with_llm
except ImportError:
    # If we're running the server directly without the package installed
    sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
    try:
        from llm.simple_executor import execute_command_with_llm
    except ImportError:
        # Define a stub function if we can't import
        def execute_command_with_llm(command, model="llama3.1", ollama_host="http://localhost:11434"):
            return {
                "success": False,
                "error": "simple_executor module not available",
                "command": command
            }

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Get the logger
logger = logging.getLogger("voice-control-server")

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'voice-control-secret-key'
# Increase maximum content length for audio uploads (50MB)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# Global settings
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "large")
TRANSLATION_ENABLED = os.environ.get("TRANSLATION_ENABLED", "true").lower() != "false"
DEFAULT_LANGUAGE = os.environ.get("DEFAULT_LANGUAGE", "es")

def error_response(message, status_code=400):
    """Helper function to create error responses"""
    return jsonify({
        "error": message,
        "status": "error"
    }), status_code

def cors_preflight(f):
    """Decorator to handle CORS preflight requests"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'OPTIONS':
            response = make_response()
            response.headers.add('Access-Control-Allow-Origin', '*')
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
            response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
            return response
        return f(*args, **kwargs)
    return decorated_function

def add_cors_headers(response):
    """Add CORS headers to all responses"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

# Register CORS handling
app.after_request(add_cors_headers)

def transcribe_audio(audio_data, model_size=WHISPER_MODEL_SIZE, language=DEFAULT_LANGUAGE) -> Dict[str, Any]:
    """
    Transcribe audio data using Whisper.
    
    Args:
        audio_data: Audio data as bytes
        model_size: Whisper model size
        language: Language code
        
    Returns:
        Dictionary with transcription results
    """
    try:
        import whisper
    except ImportError:
        return {
            "error": "Whisper is not installed. Install with 'pip install -U openai-whisper'",
            "text": ""
        }
    
    try:
        # Save audio data to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = temp_file.name
            temp_file.write(audio_data)
        
        # Load the Whisper model
        logger.info(f"Loading Whisper model: {model_size}")
        model = whisper.load_model(model_size)
        
        # Transcribe the audio
        logger.info(f"Transcribing audio with language: {language}")
        result = model.transcribe(temp_path, language=language)
        
        # Get the transcription
        text = result.get("text", "").strip()
        detected_language = result.get("language", "unknown")
        
        logger.info(f"Transcription: {text} (language: {detected_language})")
        
        return {
            "text": text,
            "language": detected_language
        }
    
    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "error": str(e),
            "text": ""
        }
    
    finally:
        # Clean up temporary file
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except (OSError, PermissionError):
                pass

def translate_text(text, model=OLLAMA_MODEL, ollama_host=OLLAMA_HOST) -> Optional[str]:
    """
    Translate text from any language to English using Ollama.
    
    Args:
        text: Text to translate
        model: Ollama model to use
        ollama_host: Ollama API host
        
    Returns:
        Translated text or None if translation failed
    """
    logger.info(f"Translating with Ollama ({model}): {text}")
    
    try:
        import requests
        
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
        import traceback
        logger.error(traceback.format_exc())
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

def validate_pyautogui_cmd(cmd):
    """
    Validate that a PyAutoGUI command only uses allowed functions.
    
    Args:
        cmd: The PyAutoGUI command to validate 

    Returns:
        Tuple of (is_valid, disallowed_functions)
    """
    allowed_functions = [
        "pyautogui.moveTo", "pyautogui.move", "pyautogui.click", 
        "pyautogui.doubleClick", "pyautogui.rightClick", "pyautogui.dragTo",
        "pyautogui.write", "pyautogui.press", "pyautogui.hotkey",
        "pyautogui.scroll", "pyautogui.screenshot",
        # Allow these basic utility functions as well
        "pyautogui.FAILSAFE", "pyautogui.size", "pyautogui.position"
    ]
    
    is_valid = True
    disallowed_functions = []
    
    for line in cmd.split('\n'):
        # Skip comments and empty lines
        line = line.strip()
        if not line or line.startswith('#'):
            continue
            
        # Handle lines with semicolons or comments mid-line
        if ';' in line:
            # Split by semicolon and process each part separately
            parts = line.split(';')
            for part in parts:
                part = part.strip()
                if not part or part.startswith('#'):
                    continue
                    
                # Check for comments at the end of the part
                if '#' in part:
                    part = part[:part.find('#')].strip()
                
                # Skip common imports and utility lines
                if part.startswith('import ') or part.startswith('from ') or part.startswith('print('):
                    continue
                
                # Check if this part contains any allowed functions
                if not any(func in part for func in allowed_functions) and "pyautogui." in part:
                    is_valid = False
                    try:
                        # Extract the function name
                        func_start = part.find("pyautogui.") + 10
                        func_end = part.find("(", func_start)
                        if func_end > func_start:
                            disallowed_functions.append(part[func_start:func_end])
                    except:
                        # If we can't extract the function name, just add the whole part
                        disallowed_functions.append(part)
            continue
            
        # Handle lines with comments
        if '#' in line:
            line = line[:line.find('#')].strip()
            if not line:
                continue
        
        # Skip common imports and utility lines
        if line.startswith('import ') or line.startswith('from ') or line.startswith('print('):
            continue
        
        # Check if line contains any allowed functions
        if not any(func in line for func in allowed_functions):
            # Only flag as invalid if it's a pyautogui function call
            if "pyautogui." in line:
                is_valid = False
                try:
                    # Extract the function name
                    func_start = line.find("pyautogui.") + 10
                    func_end = line.find("(", func_start)
                    if func_end > func_start:
                        disallowed_functions.append(line[func_start:func_end])
                except:
                    # If we can't extract the function name, just add the whole line
                    disallowed_functions.append(line)
    
    return (is_valid, disallowed_functions)

def verify_command_integrity(original_command, steps, model=OLLAMA_MODEL):
    """
    Use Ollama to verify that the split steps don't contain hallucinated text
    that wasn't in the original command.
    
    Args:
        original_command: The original voice command
        steps: List of command steps extracted by the LLM
        model: Ollama model to use
        
    Returns:
        List of verified steps with hallucinated content removed
    """
    logger.info(f"Steps: {steps}")
    logger.info(f"Verifying command integrity for {len(steps)} steps against original: '{original_command}'")
    
    try:
        import requests
        
        verified_steps = []
        
        # Process each step to verify it against the original command
        for step in steps:
            # Prepare the prompt for verification
            prompt = f"""
            Your task is to verify that a step extracted from a voice command doesn't contain hallucinated text that wasn't in the original command.
            
            Original Voice Command: "{original_command}"
            
            Extracted Step: "{step}"
            
            Check if all parts of the extracted step are semantically present in the original command. If the step contains details not implied by the original command, remove those details.
            
            RULES:
            1. Keep all words and phrases that directly appear in or are strongly implied by the original command
            2. Remove details, explanations, or actions that aren't mentioned or strongly implied in the original
            3. Maintain the overall intent and instruction of the step
            4. Focus on removing just hallucinated content, not rewording the entire step
            
            EXAMPLES:
            
            Original: "Open Firefox and go to Gmail"
            Step: "Find and click on the Firefox icon on the desktop then wait 5 seconds for it to load"
            Result: "Find and click on the Firefox icon" 
            (Removed details about "on the desktop" and "wait 5 seconds" as those weren't in the original)
            
            Original: "Type Hello World in Notepad"
            Step: "Open Notepad application from the Start menu"
            Result: "Open Notepad application"
            (Removed "from the Start menu" as it wasn't specified in the original)
            
            Return only the verified or corrected step with no additional text or explanations.
            """
            
            # Make API request to Ollama
            response = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Error from Ollama API: {response.status_code}")
                verified_steps.append(step)  # Use original step if API call fails
                continue
            
            # Parse response
            result = response.json()
            verified_step = result["response"].strip()
            
            # Clean up the response
            verified_step = clean_llm_response(verified_step)
            
            # Log if there were changes
            if verified_step != step:
                logger.info(f"Step modified during verification: '{step}' → '{verified_step}'")
            
            verified_steps.append(verified_step)
        
        logger.info(f"Command integrity verification complete. Verified {len(verified_steps)} steps.")
        return verified_steps
    
    except Exception as e:
        logger.error(f"Error verifying command integrity: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return steps  # Return original steps if function fails

def process_voice_command(audio_data, model_size=WHISPER_MODEL_SIZE, translate=TRANSLATION_ENABLED, 
                          language=DEFAULT_LANGUAGE, ollama_model=OLLAMA_MODEL, capture_screenshot=True):
    """
    Process a voice command from audio data.
    
    Args:
        audio_data: Audio data as bytes
        model_size: Whisper model size
        translate: Whether to translate non-English text
        language: Expected language
        ollama_model: Ollama model to use
        capture_screenshot: Whether to capture a screenshot after command execution
        
    Returns:
        Command processing results
    """
    try:
        # Determine if failsafe should be enabled
        enable_failsafe = os.environ.get("PYAUTOGUI_FAILSAFE", "false").lower() == "true"
        
        # Step 1: Transcribe the audio
        result = transcribe_audio(audio_data, model_size, language)
        
        # Check for transcription errors
        if "error" in result and result["error"]:
            return {
                "status": "error",
                "error": result["error"],
                "step": "transcription"
            }
        
        # Get the transcription and detected language
        text = result.get("text", "").strip()
        detected_language = result.get("language", language)
        
        if not text:
            return {
                "status": "error",
                "error": "No speech detected in the audio",
                "step": "transcription"
            }
        
        # Enhanced logging of transcription
        logger.info(f"📝 TRANSCRIPTION: '{text}' (language: {detected_language})")
        
        # Step 2: Translate if needed
        command_text = text
        translated = False
        
        # if translate and detected_language != "en":
        #     logger.info(f"Translating: {text} (detected language: {detected_language})")
            
        #     translated_text = translate_text(text, ollama_model)
            
        #     if translated_text:
        #         command_text = translated_text
        #         translated = True
        #         logger.info(f"Translation: {text} → {command_text}")
        #     else:
        #         logger.warning("Translation failed, using original text")
        
        # NEW APPROACH: Use Ollama for multi-step command processing
        # Step 3: Split the command into discrete steps using Ollama
        logger.info(f"Splitting command into steps: {command_text}")
        steps = split_command_into_steps(command_text, ollama_model)
        
        if not steps:
            return {
                "status": "error",
                "error": "Failed to parse command into steps",
                "step": "step_parsing"
            }
        
        # Step 3.5: Verify command integrity (remove hallucinated content)
        # logger.info(f"Verifying integrity of {len(steps)} steps")
        # verified_steps = verify_command_integrity(command_text, steps, ollama_model)
        # SKIP VERIFICATION FOR NOW
        verified_steps = steps
        
        # Step 4: Process each step to identify OCR targets
        logger.info(f"Identifying OCR targets for {len(verified_steps)} steps")
        steps_with_targets = identify_ocr_targets(verified_steps, ollama_model)
        
        # Step 5: Generate PyAutoGUI commands for each step
        logger.info(f"Generating PyAutoGUI commands for {len(steps_with_targets)} steps")
        actions = generate_pyautogui_actions(steps_with_targets, ollama_model)
        
        # Step 7: Execute each command sequentially
        steps_summary = []
        overall_success = True
        final_screenshot = None
        
        logger.info(f"🚀 EXECUTING {len(actions)} COMMANDS")
        
        for i, action in enumerate(actions):
            step_number = i + 1
            step_description = action.get('description', f"Step {step_number}")
            
            logger.info(f"  Command {step_number}/{len(actions)}: {step_description}")
            
            # Check if this action should be skipped
            if "# Skipping" in action.get('pyautogui_cmd', ''):
                logger.warning(f"  ⚠️ Skipping command {step_number}/{len(actions)}: {step_description}")
                steps_summary.append({
                    "step_number": step_number,
                    "description": step_description,
                    "target": action.get('target'),
                    "success": False,
                    "error": "Command validation failed"
                })
                continue
            
            # Check if command is empty
            if not action.get('pyautogui_cmd', '').strip():
                logger.warning(f"  ⚠️ Empty command for step {step_number}/{len(actions)}: {step_description}")
                steps_summary.append({
                    "step_number": step_number,
                    "description": step_description,
                    "target": action.get('target'),
                    "success": False,
                    "error": "Empty command"
                })
                continue
                
            # Determine if we should capture a screenshot for this step
            is_final_action = (i == len(actions) - 1)
            should_capture = capture_screenshot and is_final_action
            
            # Execute the command with the LLM
            result = execute_command_with_llm(
                action['pyautogui_cmd'], 
                ollama_model,
                capture_screenshot=should_capture,
                safe_mode=enable_failsafe
            )
            
            # If this is the last step, store the screenshot
            if should_capture and result.get('screenshot'):
                final_screenshot = result.get('screenshot')
            
            # Check the result
            if result.get('success', False):
                logger.info(f"  ✅ Command {step_number}/{len(actions)} succeeded")
                steps_summary.append({
                    "step_number": step_number,
                    "description": step_description,
                    "target": action.get('target'),
                    "success": True
                })
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.warning(f"  ❌ Command {step_number}/{len(actions)} failed: {error_msg}")
                steps_summary.append({
                    "step_number": step_number,
                    "description": step_description,
                    "target": action.get('target'),
                    "success": False,
                    "error": error_msg
                })
                overall_success = False
        
        # Prepare the response
        response = {
            "status": "success" if overall_success else "error",
            "command": {
                "original": text,
                "language": detected_language,
                "translated": translated
            },
            "steps": verified_steps,  # Use verified steps in the response
            "steps_summary": steps_summary
        }
        
        # Add translation if applicable
        if translated:
            response["command"]["translated_text"] = command_text
        
        # Add final screenshot if available
        if final_screenshot:
            response["screenshot"] = final_screenshot
        
        # Add error message if execution failed
        if not overall_success:
            response["error"] = "One or more steps failed during execution"
            response["step"] = "execution"
        
        logger.info(f"🏁 COMMAND PROCESSING COMPLETE: {'✅ All steps succeeded' if overall_success else '❌ Some steps failed'}")
        return response
        
    except Exception as e:
        logger.error(f"Error processing voice command: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "status": "error",
            "error": str(e),
            "step": "processing"
        }

def split_command_into_steps(command, model=OLLAMA_MODEL):
    """
    Use LLM to split a command into discrete steps.
    
    Args:
        command: The command to split
        model: Ollama model to use
        
    Returns:
        List of step strings
    """
    logger.info(f"Splitting command into steps: {command}")
    
    try:
        import requests
        
        # Prepare the prompt for step identification
        prompt = f"""
        Split this command into separate steps, step by step. Format your response as a bulleted list, with each step on a new line starting with "- ".
        
        EXAMPLES:
        
        Input: "Open Firefox, go to Gmail and compose a new email"
        Output:
        "- Open Firefox
        - Go to Gmail
        - Compose a new email"
        
        Input: "Click Settings then change theme"
        Output:
        "- Click Settings
        - Change theme"
        
        Split this series of commands:
        ```
        {command}
        ```
        
        IMPORTANT: keep the original content, only reformat as bullet point list WITH NO ADDITIONAL TEXT. Each line should start with "- ".
        """
        
        # Make API request to Ollama
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1
                }
            },
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"Error from Ollama API: {response.status_code}")
            return []
        
        # Parse response
        result = response.json()
        steps_text = result["response"].strip()
        
        # Clean up the response and extract steps
        steps = []
        for line in steps_text.split('\n'):
            line = line.strip()
            if line.startswith('- '):
                step = line[2:].strip()  # Remove the bullet point marker
                if step:
                    steps.append(step)
        
        logger.info(f"🔀 SPLIT INTO {len(steps)} STEPS: {steps}")
        return steps
    
    except Exception as e:
        logger.error(f"Error splitting command into steps: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return []

def identify_ocr_targets(steps, model=OLLAMA_MODEL):
    """
    Use LLM to identify and mark OCR targets in each step by wrapping them in quotes.
    
    Args:
        steps: List of command steps
        model: Ollama model to use
        
    Returns:
        List of steps with OCR targets wrapped in quotes
    """
    logger.info(f"Identifying OCR targets for {len(steps)} steps")
    
    try:
        import requests
        
        steps_with_targets = []
        
        for step in steps:
            # Prepare the prompt for OCR target identification
            prompt = f"""
            Your task is to identify text that needs to be visually detected on screen (OCR targets) in this UI automation step:

            ```
            {step}
            ```
            
            For any UI element that needs to be located visually by text (like buttons, menu items, labels, icons), wrap ONLY that text in double quotes.
            
            EXAMPLES:
            
            Input: Find and click on the Settings button
            Output: Find and click on the "Settings" button
            
            Input: Click on the Compose button in Gmail
            Output: Click on the "Compose" button in Gmail
            
            Input: Type hello in the search field
            Output: Type "hello" in the "search" field
            
            Input: Press Alt+F4 to close the window
            Output: Press Alt+F4 to close the window
            (Note: No quotes needed as there's no text to find visually)

            Input: haz clic.
            Output: haz clic.
            (Note: No change or quotes needed as there's no text to find visually)
            
            ONLY add quotes around specific text that would be seen on screen that needs to be located.
            DO NOT add quotes around general descriptions or actions, such as "click"
            Return only the modified step with NO additional explanations or boilerplate.
            """
            # Make API request to Ollama with low temperature for more consistent output
            response = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.1
                },
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Error from Ollama API: {response.status_code}")
                steps_with_targets.append(step)  # Use original step if API call fails
                continue
            
            # Parse response
            result = response.json()
            modified_step = result["response"].strip()
            
            # Clean up the response and add to list
            steps_with_targets.append(modified_step)
        
        logger.info(f"🎯 OCR TARGETS IDENTIFIED: {steps_with_targets}")
        return steps_with_targets
    
    except Exception as e:
        logger.error(f"Error identifying OCR targets: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return steps  # Return original steps if function fails

def generate_pyautogui_actions(steps_with_targets, model=OLLAMA_MODEL):
    """
    Use LLM to generate PyAutoGUI commands for each step, with optional targets.
    
    Args:
        steps_with_targets: List of steps with OCR targets
        model: Ollama model to use
        
    Returns:
        List of dictionaries with PyAutoGUI commands and metadata
    """
    logger.info(f"Generating PyAutoGUI actions for {len(steps_with_targets)} steps")
    
    try:
        import requests
        
        actions = []
        
        for step in steps_with_targets:
            # Prepare the prompt for PyAutoGUI command generation
            prompt = f"""
            Generate a PyAutoGUI command for this UI automation step:
            
            ```
            {step}
            ```
            
            Your response should be in JSON format with these fields:
            1. "pyautogui_cmd": A Python command that uses PyAutoGUI to execute this step
            2. "target": The primary OCR target (if any) that would be visually detected on screen
            3. "description": A short description of this action
            
            IMPORTANT: ONLY use the following PyAutoGUI functions - DO NOT use any other functions:
            
            1. Mouse operations:
               - pyautogui.moveTo(x, y) - Move mouse to absolute position
               - pyautogui.move(x, y) - Move mouse relative to current position
               - pyautogui.click(x, y) - Click at position
               - pyautogui.doubleClick(x, y) - Double-click at position
               - pyautogui.rightClick(x, y) - Right-click at position
               - pyautogui.dragTo(x, y) - Drag to position
            
            2. Keyboard operations:
               - pyautogui.write('text') - Type text
               - pyautogui.press('key') - Press a key (e.g., 'enter', 'tab', 'escape')
               - pyautogui.hotkey('key1', 'key2', ...) - Press keys together (e.g., 'ctrl', 'c')
            
            3. Scrolling operations:
               - pyautogui.scroll(amount) - Scroll up (positive) or down (negative)
            
            4. Screenshot operations:
               - pyautogui.screenshot() - Take a screenshot
            
            For UI element detection, use these patterns:
            - For finding elements: Simple string search approach mentioning the target
            - For multi-step operations: Use multiple basic PyAutoGUI commands separated by semicolons
            
            EXAMPLES:
            
            Step: Find and click on the "Settings" button
            Response:
            {{
              "pyautogui_cmd": "# Find and click on Settings\\npyautogui.click(x, y)  # Coordinates would be determined at runtime",
              "target": "Settings",
              "description": "Click on Settings button"
            }}
            
            Step: Type hello in the "search" field
            Response:
            {{
              "pyautogui_cmd": "# Click on search field\\npyautogui.click(x, y);  # Coordinates for search field\\npyautogui.write('hello')",
              "target": "search",
              "description": "Type hello in search field"
            }}
            
            Step: Press Alt+F4 to close the window
            Response:
            {{
              "pyautogui_cmd": "pyautogui.hotkey('alt', 'f4')",
              "target": null,
              "description": "Close window with Alt+F4"
            }}
            
            Step: Scroll down to see more content
            Response:
            {{
              "pyautogui_cmd": "pyautogui.scroll(-10)  # Negative values scroll down",
              "target": null,
              "description": "Scroll down"
            }}
            
            Step: Right-click on the "image" and select Save
            Response:
            {{
              "pyautogui_cmd": "# Right-click on image\\npyautogui.rightClick(x, y);  # Coordinates for image\\n# Then click on Save option\\npyautogui.move(0, 50);  # Move down to Save option\\npyautogui.click()",
              "target": "image",
              "description": "Right-click image and select Save"
            }}
            
            IMPORTANT: 
            1. Return valid JSON with no additional explanation or text
            2. If there is no specific target, set "target" to null
            3. Use ONLY the PyAutoGUI functions listed above
            4. Do not attempt to use coordinates directly - use placeholders and comments
            5. For locating screen elements, keep it simple and reference the target - don't use locateOnScreen()
            6. Use comments to explain the steps where appropriate
            """
            
            # Make API request to Ollama
            response = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Error from Ollama API: {response.status_code}")
                # Add a placeholder if API call fails
                actions.append({
                    "pyautogui_cmd": f"print('Unable to generate command for: {step}')",
                    "target": None,
                    "description": step,
                    "error": "Failed to generate PyAutoGUI command"
                })
                continue
            
            # Parse response
            result = response.json()
            json_response = result["response"].strip()
            
            try:
                # Try to parse the JSON response
                # Extract just the JSON part if there's extra text
                json_start = json_response.find('{')
                json_end = json_response.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_content = json_response[json_start:json_end]
                    action_data = json.loads(json_content)
                    
                    # Add the original step to the action data
                    action_data["original_step"] = step
                    
                    # Validate the generated code
                    is_valid, disallowed_functions = validate_pyautogui_cmd(action_data.get("pyautogui_cmd", ""))
                    
                    # Only consider the code invalid if disallowed functions were found
                    if not is_valid and disallowed_functions:
                        logger.warning(f"Generated code for step {step} uses disallowed functions: {disallowed_functions}")
                        # Use a stripped-down version of the code or fallback
                        if "pyautogui.click" in action_data.get("pyautogui_cmd", "") or "pyautogui.moveTo" in action_data.get("pyautogui_cmd", ""):
                            action_data["pyautogui_cmd"] = "pyautogui.click(x=100, y=100)" if "pyautogui.click" in action_data.get("pyautogui_cmd", "") else "pyautogui.moveTo(x=100, y=100)"
                        elif "pyautogui.write" in action_data.get("pyautogui_cmd", ""):
                            action_data["pyautogui_cmd"] = "pyautogui.write('text')"
                        elif "pyautogui.press" in action_data.get("pyautogui_cmd", ""):
                            action_data["pyautogui_cmd"] = "pyautogui.press('enter')" if "enter" in step.lower() else "pyautogui.press('escape')"
                        else:
                            action_data["pyautogui_cmd"] = "# Skipping this step - validation failed"
                    
                    actions.append(action_data)
                else:
                    # Fallback if JSON parsing fails
                    logger.warning(f"Could not extract JSON from response: {json_response}")
                    actions.append({
                        "pyautogui_cmd": f"print('Invalid response format for: {step}')",
                        "target": None,
                        "description": step,
                        "error": "Invalid JSON response format"
                    })
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON response: {json_response}")
                actions.append({
                    "pyautogui_cmd": f"print('JSON parsing error for: {step}')",
                    "target": None,
                    "description": step,
                    "error": "JSON parsing error"
                })
        
        logger.info(f"⚙️ GENERATED {len(actions)} PYAUTOGUI ACTIONS")
        # Log the first few actions for debugging
        for i, action in enumerate(actions[:3]):  # Only log first 3 to avoid overwhelming logs
            logger.info(f"  Action {i+1}: {action.get('description')} - Target: {action.get('target')}")
        if len(actions) > 3:
            logger.info(f"  ... and {len(actions) - 3} more actions")
            
        return actions
    
    except Exception as e:
        logger.error(f"Error generating PyAutoGUI actions: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Return a list of placeholder actions if function fails
        return [{"pyautogui_cmd": f"print('Error generating command: {str(e)}')",
                "target": None,
                "description": step,
                "error": str(e)} for step in steps_with_targets]

# API Routes

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        import whisper
        whisper_available = True
    except ImportError:
        whisper_available = False
    
    try:
        import requests
        ollama_available = True
        try:
            response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=2)
            ollama_running = response.status_code == 200
        except:
            ollama_running = False
    except ImportError:
        ollama_available = False
        ollama_running = False
    
    # Check the failsafe status
    enable_failsafe = os.environ.get("PYAUTOGUI_FAILSAFE", "false").lower() == "true"
    
    return jsonify({
        "status": "healthy",
        "components": {
            "whisper": {
                "available": whisper_available,
                "model": WHISPER_MODEL_SIZE
            },
            "ollama": {
                "available": ollama_available,
                "running": ollama_running,
                "model": OLLAMA_MODEL,
                "host": OLLAMA_HOST
            }
        },
        "settings": {
            "translation_enabled": TRANSLATION_ENABLED,
            "default_language": DEFAULT_LANGUAGE,
            "capture_screenshots": os.environ.get("CAPTURE_SCREENSHOTS", "true").lower() == "true",
            "pyautogui_failsafe": enable_failsafe
        }
    })

@app.route('/transcribe', methods=['POST'])
@cors_preflight
def transcribe_endpoint():
    """Endpoint to transcribe audio to text"""
    if 'audio_file' not in request.files:
        return error_response("No audio file provided")
    
    try:
        # Get parameters
        audio_file = request.files['audio_file']
        model_size = request.form.get('model_size', WHISPER_MODEL_SIZE)
        language = request.form.get('language', DEFAULT_LANGUAGE)
        
        # Read the audio data
        audio_data = audio_file.read()
        
        # Check if the audio data is empty
        if not audio_data:
            return error_response("Empty audio file")
        
        # Transcribe the audio
        result = transcribe_audio(audio_data, model_size, language)
        
        # Check for errors
        if "error" in result and result["error"]:
            return error_response(result["error"])
        
        # Return the result
        return jsonify({
            "status": "success",
            "transcription": result.get("text", ""),
            "language": result.get("language", "unknown")
        })
    
    except Exception as e:
        logger.error(f"Error in transcribe endpoint: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return error_response(f"Transcription error: {str(e)}", 500)

@app.route('/translate', methods=['POST'])
@cors_preflight
def translate_endpoint():
    """Endpoint to translate text"""
    if not request.is_json:
        return error_response("Request must be JSON")
    
    try:
        # Get parameters
        data = request.json
        text = data.get('text')
        model = data.get('model', OLLAMA_MODEL)
        
        # Check if text is provided
        if not text:
            return error_response("No text provided")
        
        # Translate the text
        translated = translate_text(text, model)
        
        # Check if translation failed
        if translated is None:
            return error_response("Translation failed")
        
        # Return the result
        return jsonify({
            "status": "success",
            "original": text,
            "translated": translated
        })
    
    except Exception as e:
        logger.error(f"Error in translate endpoint: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return error_response(f"Translation error: {str(e)}", 500)

@app.route('/command', methods=['POST'])
@cors_preflight
def command_endpoint():
    """Endpoint to execute a command"""
    if not request.is_json:
        return error_response("Request must be JSON")
    
    try:
        # Get parameters
        data = request.json
        command = data.get('command')
        model = data.get('model', OLLAMA_MODEL)
        capture_screenshot = data.get('capture_screenshot', True)
        # Allow client to override failsafe setting
        enable_failsafe = data.get('enable_failsafe', os.environ.get("PYAUTOGUI_FAILSAFE", "false").lower() == "true")
        
        # Check if command is provided
        if not command:
            return error_response("No command provided")
        
        # Enhanced logging of the command
        logger.info(f"📝 COMMAND: '{command}'")
        logger.info(f"PyAutoGUI failsafe: {'enabled' if enable_failsafe else 'disabled'}")
        
        # Split command into steps
        steps = split_command_into_steps(command, model)
        
        if not steps:
            return error_response("Failed to parse command into steps")
        
        # Verify command integrity (remove hallucinated content)
        logger.info(f"Verifying integrity of {len(steps)} steps")
        verified_steps = verify_command_integrity(command, steps, model)
        
        # Process each step to identify OCR targets
        steps_with_targets = identify_ocr_targets(verified_steps, model)
        
        # Generate PyAutoGUI commands for each step
        actions = generate_pyautogui_actions(steps_with_targets, model)
        
        # Process each step
        steps_summary = []
        overall_success = True
        final_screenshot = None
        
        logger.info(f"🚀 EXECUTING {len(actions)} COMMANDS")
        
        for i, action in enumerate(actions):
            step_number = i + 1
            step_description = action.get('description', f"Step {step_number}")
            
            logger.info(f"  Command {step_number}/{len(actions)}: {step_description}")
            
            # Check if this action should be skipped
            if "# Skipping" in action.get('pyautogui_cmd', ''):
                logger.warning(f"  ⚠️ Skipping command {step_number}/{len(actions)}: {step_description}")
                steps_summary.append({
                    "step_number": step_number,
                    "description": step_description,
                    "target": action.get('target'),
                    "success": False,
                    "error": "Command validation failed"
                })
                continue
            
            # Check if command is empty
            if not action.get('pyautogui_cmd', '').strip():
                logger.warning(f"  ⚠️ Empty command for step {step_number}/{len(actions)}: {step_description}")
                steps_summary.append({
                    "step_number": step_number,
                    "description": step_description,
                    "target": action.get('target'),
                    "success": False,
                    "error": "Empty command"
                })
                continue
            
            # Determine if we should capture a screenshot for this step
            is_final_action = (i == len(actions) - 1)
            should_capture = capture_screenshot and is_final_action
            
            # Execute the command with the LLM
            result = execute_command_with_llm(
                action['pyautogui_cmd'], 
                model, 
                capture_screenshot=should_capture,
                safe_mode=enable_failsafe
            )
            
            # If this is the last step, store the screenshot
            if should_capture and result.get('screenshot'):
                final_screenshot = result.get('screenshot')
            
            # Check the result
            if result.get('success', False):
                logger.info(f"  ✅ Command {step_number}/{len(actions)} succeeded")
                steps_summary.append({
                    "step_number": step_number,
                    "description": step_description,
                    "target": action.get('target'),
                    "success": True
                })
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.warning(f"  ❌ Command {step_number}/{len(actions)} failed: {error_msg}")
                steps_summary.append({
                    "step_number": step_number,
                    "description": step_description,
                    "target": action.get('target'),
                    "success": False,
                    "error": error_msg
                })
                overall_success = False
        
        logger.info(f"🏁 COMMAND PROCESSING COMPLETE: {'✅ All steps succeeded' if overall_success else '❌ Some steps failed'}")
        
        # Prepare the response
        response = {
            "status": "success",
            "command": command,
            "steps": verified_steps,  # Use verified steps in the response
            "steps_summary": steps_summary
        }
        
        if final_screenshot:
            response["screenshot"] = final_screenshot
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error in command endpoint: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return error_response(f"Command execution error: {str(e)}", 500)

@app.route('/voice-command', methods=['POST'])
@cors_preflight
def voice_command_endpoint():
    """Endpoint to process a voice command"""
    if 'audio_file' not in request.files:
        return error_response("No audio file provided")
    
    try:
        # Get parameters
        audio_file = request.files['audio_file']
        model_size = request.form.get('model_size', WHISPER_MODEL_SIZE)
        translate = request.form.get('translate', 'true').lower() != 'false'
        language = request.form.get('language', DEFAULT_LANGUAGE)
        model = request.form.get('model', OLLAMA_MODEL)
        capture_screenshot = request.form.get('capture_screenshot', 'true').lower() != 'false'
        enable_failsafe = request.form.get('enable_failsafe', 'false').lower() == 'true'
        
        # Update environment variable for this request
        if enable_failsafe:
            os.environ["PYAUTOGUI_FAILSAFE"] = "true"
        else:
            os.environ["PYAUTOGUI_FAILSAFE"] = "false"
        
        logger.info(f"PyAutoGUI failsafe: {'enabled' if enable_failsafe else 'disabled'}")
        
        # Read the audio data
        audio_data = audio_file.read()
        
        # Check if the audio data is empty
        if not audio_data:
            return error_response("Empty audio file")
        
        # Process the voice command
        result = process_voice_command(
            audio_data, 
            model_size, 
            translate, 
            language, 
            model,
            capture_screenshot=capture_screenshot
        )
        
        # Return the result with additional information about the new multi-step approach
        if result.get("status") == "success":
            message = f"Successfully processed voice command with {len(result.get('steps', []))} steps"
            result["message"] = message
            
            # Include detailed breakdown of steps in the response
            steps_info = []
            for i, action in enumerate(result.get("steps_summary", [])):
                step_info = {
                    "step_number": i + 1,
                    "description": action.get("description", "Unknown action"),
                    "target": action.get("target"),
                    "success": action.get("success", False)
                }
                steps_info.append(step_info)
            
            result["steps_summary"] = steps_info
            
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error in voice-command endpoint: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return error_response(f"Voice command processing error: {str(e)}", 500)

# Main entry point
if __name__ == '__main__':
    # Parse command-line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple voice control server with LLM-based multi-step processing')
    
    parser.add_argument('--host', type=str, default='0.0.0.0',
                        help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000,
                        help='Port to bind to (default: 5000)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug mode')
    parser.add_argument('--whisper-model', type=str, default=WHISPER_MODEL_SIZE,
                        choices=['tiny', 'base', 'small', 'medium', 'large'],
                        help=f'Whisper model size (default: {WHISPER_MODEL_SIZE})')
    parser.add_argument('--ollama-model', type=str, default=OLLAMA_MODEL,
                        help=f'Ollama model to use (default: {OLLAMA_MODEL})')
    parser.add_argument('--ollama-host', type=str, default=OLLAMA_HOST,
                        help=f'Ollama API host (default: {OLLAMA_HOST})')
    parser.add_argument('--disable-translation', action='store_true',
                        help='Disable automatic translation of non-English languages')
    parser.add_argument('--language', type=str, default=DEFAULT_LANGUAGE,
                        help=f'Default language for voice recognition (default: {DEFAULT_LANGUAGE})')
    parser.add_argument('--disable-screenshots', action='store_true',
                        help='Disable capturing screenshots after command execution')
    parser.add_argument('--enable-failsafe', action='store_true',
                        help='Enable PyAutoGUI failsafe (move mouse to upper-left corner to abort)')
    
    args = parser.parse_args()
    
    # Update environment variables instead of using globals
    os.environ["WHISPER_MODEL_SIZE"] = args.whisper_model
    os.environ["OLLAMA_MODEL"] = args.ollama_model
    os.environ["OLLAMA_HOST"] = args.ollama_host
    os.environ["TRANSLATION_ENABLED"] = "false" if args.disable_translation else "true"
    os.environ["DEFAULT_LANGUAGE"] = args.language
    os.environ["CAPTURE_SCREENSHOTS"] = "false" if args.disable_screenshots else "true"
    os.environ["PYAUTOGUI_FAILSAFE"] = "true" if args.enable_failsafe else "false"
    
    # Log server configuration
    logger.info(f"Starting voice control server with multi-step LLM processing")
    logger.info(f"Server running at {args.host}:{args.port} (debug={args.debug})")
    logger.info(f"Whisper model: {args.whisper_model}")
    logger.info(f"Ollama model: {args.ollama_model}")
    logger.info(f"Ollama host: {args.ollama_host}")
    logger.info(f"Translation: {'disabled' if args.disable_translation else 'enabled'}")
    logger.info(f"Default language: {args.language}")
    logger.info(f"Screenshots: {'disabled' if args.disable_screenshots else 'enabled'}")
    logger.info(f"PyAutoGUI failsafe: {'enabled' if args.enable_failsafe else 'disabled'}")
    
    # Run the server
    app.run(host=args.host, port=args.port, debug=args.debug) 