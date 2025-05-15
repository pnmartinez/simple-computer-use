"""
Voice control server module.

This module provides a Flask web server for voice command processing.
"""

# Set CUDA device explicitly before any imports that might use CUDA
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"  # Use the first GPU
# Add more CUDA environment settings to help with initialization
os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"  # Match NVIDIA-SMI order
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:512"  # Reduce memory fragmentation

# Standard library imports
import sys
import time
import logging
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union
from functools import wraps
import threading
import base64
import tempfile
import numpy as np

# Configure logging
logger = logging.getLogger("voice-control-server")

# Load environment variables from .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.debug("Loaded environment variables from .env file")
except ImportError:
    logger.warning("python-dotenv not installed, environment variables from .env file won't be loaded")
except Exception as e:
    logger.warning(f"Error loading .env file: {e}")

try:
    from flask import Flask, request, jsonify, send_file, abort, Response, render_template_string, redirect, make_response, send_from_directory
    from flask_cors import CORS
    logger.debug("Successfully imported Flask and Flask-CORS")
except ImportError:
    logger.critical("Flask not installed. Please install flask and flask-cors.")
    sys.exit(1)

# Import from our own modules
from llm_control.voice.utils import error_response, cors_preflight, add_cors_headers, test_cuda_availability, get_screenshot_dir
from llm_control.voice.utils import is_debug_mode, configure_logging, DEBUG
from llm_control.voice.utils import add_to_command_history, get_command_history, get_command_history_file, clean_llm_response
from llm_control.voice.audio import transcribe_audio, translate_text
from llm_control.voice.screenshots import capture_screenshot, capture_with_highlight, get_latest_screenshots, list_all_screenshots, get_screenshot_data
from llm_control.voice.commands import validate_pyautogui_cmd, split_command_into_steps, identify_ocr_targets, generate_pyautogui_actions, execute_command_with_llm
from llm_control.voice.commands import execute_command_with_logging, process_command_pipeline
from llm_control.favorites.utils import save_as_favorite, get_favorites, delete_favorite, run_favorite

# Class to handle JSON serialization for NumPy types
class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON Encoder that handles NumPy types."""
    def default(self, obj):
        # Handle numpy types by converting them to Python native types
        try:
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.bool_):
                return bool(obj)
        except ImportError:
            pass
        
        # Let the base class default method handle other types or raise TypeError
        return super().default(obj)

def sanitize_for_json(obj):
    """
    Recursively sanitize an object for JSON serialization, converting NumPy types to native Python types.
    
    Args:
        obj: The object to sanitize
        
    Returns:
        The sanitized object safe for JSON serialization
    """
    try:
        if isinstance(obj, dict):
            return {k: sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [sanitize_for_json(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(sanitize_for_json(item) for item in obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        else:
            return obj
    except ImportError:
        # If numpy isn't available, just return the object as is
        return obj

# Constants and configuration
DEFAULT_LANGUAGE = os.environ.get("DEFAULT_LANGUAGE", "es")
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "medium")
TRANSLATION_ENABLED = os.environ.get("TRANSLATION_ENABLED", "false").lower() in ("true", "1", "yes")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:12b") 
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

logger.debug(f"Loaded environment configuration:")
logger.debug(f"- DEBUG: {DEBUG}")
logger.debug(f"- DEFAULT_LANGUAGE: {DEFAULT_LANGUAGE}")
logger.debug(f"- WHISPER_MODEL_SIZE: {WHISPER_MODEL_SIZE}")
logger.debug(f"- TRANSLATION_ENABLED: {TRANSLATION_ENABLED}")
logger.debug(f"- OLLAMA_MODEL: {OLLAMA_MODEL}")
logger.debug(f"- OLLAMA_HOST: {OLLAMA_HOST}")

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'voice-control-secret-key'
# Increase maximum content length for audio uploads (50MB)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
# Use the custom JSON encoder
app.json.encoder = CustomJSONEncoder

# Enable CORS for all routes
CORS(app)

# Apply CORS headers to all responses
@app.after_request
def after_request(response):
    return add_cors_headers(response)

# Add PyAutoGUI extension functions
def add_pyautogui_extensions():
    """
    Add extension functions to PyAutoGUI to enhance functionality.
    """
    try:
        import pyautogui
        
        # Add moveRelative as an alias for move
        if not hasattr(pyautogui, 'moveRelative'):
            pyautogui.moveRelative = pyautogui.move
            logging.info("Added moveRelative extension to PyAutoGUI")
    except ImportError:
        logging.warning("Could not import PyAutoGUI to add extensions")

# API routes
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "message": "Voice control server is running",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/transcribe', methods=['POST'])
@cors_preflight
def transcribe_endpoint():
    """Endpoint for transcribing audio to text."""
    try:
        # Check if the request has an audio file
        if 'audio' not in request.files:
            return error_response("No audio file provided", 400)
        
        # Get the audio file
        audio_file = request.files['audio']
        
        # Check if the audio file is empty
        if audio_file.filename == '':
            return error_response("Empty audio file", 400)
        
        # Read the audio data
        audio_data = audio_file.read()
        
        # Get the language from the request
        language = request.form.get('language', DEFAULT_LANGUAGE)
        
        # Get the model size from the request
        model_size = request.form.get('model', WHISPER_MODEL_SIZE)
        
        # Transcribe the audio
        result = transcribe_audio(audio_data, model_size, language)
        
        # Check if there was an error
        if 'error' in result and result['error']:
            return error_response(result['error'], 500)
        
        # Return the transcription
        return jsonify({
            "status": "success",
            "text": result.get('text', ''),
            "language": result.get('language', 'unknown')
        })
    
    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return error_response(f"Error transcribing audio: {str(e)}", 500)

@app.route('/translate', methods=['POST'])
@cors_preflight
def translate_endpoint():
    """Endpoint for translating text to English."""
    try:
        # Get the request data
        data = request.get_json()
        
        # Validate the request data
        if not data or 'text' not in data:
            return error_response("No text provided", 400)
        
        # Get the text to translate
        text = data['text']
        
        # Get the model from the request
        model = data.get('model', OLLAMA_MODEL)
        
        # Get the Ollama host from the request
        ollama_host = data.get('ollama_host', OLLAMA_HOST)
        
        # Translate the text
        translated_text = translate_text(text, model, ollama_host)
        
        # Check if translation was successful
        if translated_text is None:
            return error_response("Translation failed", 500)
        
        # Return the translation
        return jsonify({
            "status": "success",
            "original": text,
            "translated": translated_text
        })
    
    except Exception as e:
        logger.error(f"Error translating text: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return error_response(f"Error translating text: {str(e)}", 500)

@app.route('/command', methods=['POST'])
@cors_preflight
def command_endpoint():
    """Endpoint for executing a command."""
    try:
        # Get the request data
        data = request.get_json()
        
        # Validate the request data
        if not data or 'command' not in data:
            return error_response("No command provided", 400)
        
        # Get the command
        command = data['command']
        
        # Get the model from the request
        model = data.get('model', OLLAMA_MODEL)
        
        # Get the Ollama host from the request
        ollama_host = data.get('ollama_host', OLLAMA_HOST)
        
        # Get screenshot option
        capture_screenshot_flag = data.get('capture_screenshot', True)
        
        logger.info(f"Received command: '{command}'")
        
        # Process command pipeline first to gather detailed debugging info
        if DEBUG:
            # Gather debug information by processing the command pipeline
            pipeline_result = process_command_pipeline(command, model=model)
            logger.debug(f"Command pipeline processed with success: {pipeline_result.get('success', False)}")
        
        # Execute the command with enhanced logging
        execution_start = time.time()
        result = execute_command_with_logging(command, model=model, ollama_host=ollama_host)
        execution_time = time.time() - execution_start
        logger.info(f"Command execution completed in {execution_time:.2f} seconds")
        
        # Add timing information
        result['processing_time'] = {
            'execution': execution_time
        }
        
        # Extract the executed PyAutoGUI code and add it to the result
        executed_code = ""
        if 'pipeline' in result and 'code' in result['pipeline']:
            pipeline_code = result['pipeline']['code']
            if isinstance(pipeline_code, dict):
                # Combine imports and raw code into a formatted string
                code_parts = []
                
                # Add imports
                if 'imports' in pipeline_code:
                    code_parts.append(pipeline_code['imports'])
                
                # Add the raw code
                if 'raw' in pipeline_code:
                    code_parts.append(pipeline_code['raw'])
                
                # If no raw code but steps available, reconstruct from steps
                elif 'steps' in pipeline_code and not code_parts:
                    for step in pipeline_code['steps']:
                        if 'original' in step:
                            code_parts.append(f"# {step['original']}")
                        if 'code' in step:
                            code_parts.append(step['code'])
                
                executed_code = '\n\n'.join(code_parts)
            elif isinstance(pipeline_code, str):
                # If code is directly a string, use it as is
                executed_code = pipeline_code
                
        # Add the executed code to the result
        result['executed_code'] = executed_code
        
        # Store command in history
        command_history_data = {
            'timestamp': datetime.now().isoformat(),
            'command': command,
            'steps': pipeline_result.get('steps', []) if 'pipeline_result' in locals() else [],
            'code': executed_code,
            'success': result.get('success', False)
        }
        add_to_command_history(command_history_data)
        
        # Capture a screenshot if requested
        if capture_screenshot_flag:
            filename, filepath, success = capture_screenshot()
            if success and filepath:
                result['screenshot'] = {
                    'filename': filename,
                    'filepath': filepath,
                    'url': f"/screenshots/{filename}"
                }
                logger.info(f"Captured screenshot and saved to {filepath}")
        
        # Sanitize the result to ensure all values are JSON serializable
        sanitized_result = sanitize_for_json(result)
        
        # Return the sanitized result
        return jsonify(sanitized_result)
    
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        import traceback
        error_trace = traceback.format_exc()
        logger.error(error_trace)
        
        # Include stack trace in debug mode
        if DEBUG:
            return jsonify({
                "error": f"Error executing command: {str(e)}",
                "status": "error",
                "traceback": error_trace
            }), 500
        else:
            return error_response(f"Error executing command: {str(e)}", 500)

@app.route('/api/voice-command', methods=['POST', 'OPTIONS'])
@cors_preflight
def voice_command_endpoint():
    """Process voice command from audio"""
    # Import needed modules only when function is called
    import time
    import traceback
    import gc
    from datetime import datetime
    from llm_control.voice.utils import cleanup_old_screenshots
    from llm_control.voice.audio import transcribe_audio
    
    # Initialize response
    resp = {
        "status": "processing",
        "command_processed": False
    }
    
    # Track memory usage
    memory_before = get_memory_usage()
    logger.debug(f"Memory usage at start: {memory_before:.2f} MiB")
    
    try:
        if request.method == 'OPTIONS':
            return handle_cors_preflight()
            
        # Check if we have the audio file
        if 'audio' not in request.files:
            logger.warning("No audio file in request")
            return error_response("No audio file", 400)
        
        audio_file = request.files['audio']
        
        # Check if the file is empty
        if audio_file.filename == '' or not audio_file:
            logger.warning("Empty audio file")
            return error_response("Empty audio file", 400)
        
        # Read audio data
        audio_data = audio_file.read()
        
        # Check if we actually got any data
        if not audio_data or len(audio_data) < 100:  # Arbitrary small size
            logger.warning(f"Audio file too small: {len(audio_data)} bytes")
            return error_response("Audio file too small or empty", 400)
        
        logger.info(f"Received audio of size: {len(audio_data)} bytes")
        
        # Get language and model size from request
        language = request.form.get('language', DEFAULT_LANGUAGE)
        model_size = request.form.get('model_size', WHISPER_MODEL_SIZE)
        
        logger.info(f"Using language: {language}, model size: {model_size}")
        
        # Check for competing GPU processes
        try:
            gpu_processes = get_gpu_processes()
            
            competitive_processes = []
            our_pid = os.getpid()
            
            for proc in gpu_processes:
                if proc['pid'] != our_pid and proc['memory_mb'] > 500:  # More than 500MB
                    competitive_processes.append(proc)
            
            if competitive_processes:
                # Log competing processes
                logger.warning(f"Found {len(competitive_processes)} competing GPU processes:")
                for proc in competitive_processes:
                    logger.warning(f"  PID {proc['pid']}: {proc['name']} - {proc['memory_mb']:.1f} MB")
                
                # Try to clear CUDA memory
                try:
                    import torch
                    if torch.cuda.is_available():
                        logger.info("Attempting to clear CUDA memory before transcription")
                        torch.cuda.empty_cache()
                        gc.collect()
                except ImportError:
                    logger.debug("PyTorch not available, skipping CUDA memory clearing")
        except Exception as e:
            logger.warning(f"Error checking for GPU processes: {e}")
        
        # Transcribe the audio
        logger.info("Starting audio transcription")
        transcription_start = time.time()
        
        transcription_result = transcribe_audio(
            audio_data, 
            language=language if language != "auto" else None, 
            model_size=model_size,
            fallback_to_cpu=True
        )
        
        transcription_time = time.time() - transcription_start
        logger.info(f"Transcription completed in {transcription_time:.2f} seconds")
        
        # Check for errors in transcription
        if "error" in transcription_result and transcription_result["error"]:
            error_msg = f"Transcription error: {transcription_result['error']}"
            logger.error(error_msg)
            resp["error"] = error_msg
            resp["status"] = "error"
            return jsonify(resp)
        
        # Get transcribed text
        transcribed_text = transcription_result.get("text", "").strip()
        
        # Check if we got any text
        if not transcribed_text:
            logger.warning("Empty transcription result")
            resp["error"] = "Empty transcription result"
            resp["status"] = "error"
            return jsonify(resp)
        
        # Add transcription details to response
        resp["transcription"] = transcribed_text
        resp["language"] = transcription_result.get("language", language)
        
        # Force memory cleanup after transcription
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.debug("Cleared CUDA cache after transcription")
        except Exception as e:
            logger.debug(f"Error clearing CUDA cache: {e}")
        
        # Log the transcribed text
        logger.info(f"Transcribed text: '{transcribed_text[:100]}{'...' if len(transcribed_text) > 100 else ''}'")
        logger.info(f"Detected language: {resp['language']}")
        
        # Process the command
        command_start = time.time()
        logger.info("Processing voice command")
        
        # Set up debug info if we're in debug mode
        if DEBUG:
            resp["debug_info"] = {
                "transcription_time": transcription_time,
                "transcription_details": {
                    "model_size": model_size,
                    "device": transcription_result.get("device", "unknown")
                }
            }
        
        try:
            # Process the transcribed text as a command
            command_result = process_voice_command(transcribed_text, resp["language"])
            
            # Add command results to response
            resp["command"] = transcribed_text
            resp["command_processed"] = True
            resp["command_result"] = command_result
            resp["status"] = "success"
            
            # Add to command history
            try:
                add_to_command_history({
                    "timestamp": datetime.now().isoformat(),
                    "command": transcribed_text,
                    "success": True,
                    "language": resp["language"],
                    "execution_time": time.time() - command_start
                })
            except Exception as e:
                logger.warning(f"Error adding command to history: {e}")
        
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            resp["error"] = f"Error processing command: {str(e)}"
            resp["status"] = "error"
            traceback.print_exc()
        
        # Monitor memory after command processing
        memory_after_command = get_memory_usage()
        logger.debug(f"Memory usage after command: {memory_after_command:.2f} MiB (delta: {memory_after_command - memory_before:.2f} MiB)")
        
        # Force garbage collection after command processing
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.debug("Cleared CUDA cache after command processing")
        except Exception as e:
            logger.debug(f"Error clearing CUDA cache: {e}")
        
        # Sanitize the response to ensure JSON serialization works
        resp = sanitize_for_json(resp)
        return jsonify(resp)
    
    except Exception as e:
        logger.error(f"Error in voice command endpoint: {e}")
        traceback.print_exc()
        resp["error"] = f"Server error: {str(e)}"
        # Sanitize the response to ensure JSON serialization works
        resp = sanitize_for_json(resp)
        return jsonify(resp)
    
    finally:
        # Final memory cleanup
        gc.collect()
        
        # Attempt to clean up screenshots to prevent disk space issues
        try:
            cleanup_old_screenshots()
        except Exception as e:
            logger.warning(f"Error cleaning up screenshots: {e}")
        
        # Monitor memory at end
        memory_end = get_memory_usage()
        logger.debug(f"Memory usage at end: {memory_end:.2f} MiB (total delta: {memory_end - memory_before:.2f} MiB)")

@app.route('/screenshots', methods=['GET'])
def list_screenshots_endpoint():
    """Endpoint for listing available screenshots."""
    try:
        # List all screenshots
        screenshots = list_all_screenshots()
        
        # Return the list
        return jsonify({
            "status": "success",
            "count": len(screenshots),
            "screenshots": screenshots
        })
    
    except Exception as e:
        logger.error(f"Error listing screenshots: {str(e)}")
        return error_response(f"Error listing screenshots: {str(e)}", 500)

@app.route('/screenshots/latest', methods=['GET'])
def latest_screenshots_endpoint():
    """Endpoint for getting information about the latest screenshots."""
    try:
        # Get the limit from the request
        limit = request.args.get('limit', 10, type=int)
        
        # Get the latest screenshots
        screenshots = get_latest_screenshots(limit)
        
        # Return the list
        return jsonify({
            "status": "success",
            "count": len(screenshots),
            "screenshots": screenshots
        })
    
    except Exception as e:
        logger.error(f"Error getting latest screenshots: {str(e)}")
        return error_response(f"Error getting latest screenshots: {str(e)}", 500)

@app.route('/screenshots/<filename>', methods=['GET'])
def serve_screenshot_endpoint(filename):
    """Endpoint for serving a specific screenshot file."""
    try:
        from flask import send_from_directory
        
        # Get the screenshot directory
        screenshot_dir = get_screenshot_dir()
        
        # Check if the file exists
        if not os.path.exists(os.path.join(screenshot_dir, filename)):
            return error_response(f"Screenshot not found: {filename}", 404)
        
        # Serve the file
        return send_from_directory(screenshot_dir, filename)
    
    except Exception as e:
        logger.error(f"Error serving screenshot: {str(e)}")
        return error_response(f"Error serving screenshot: {str(e)}", 500)

@app.route('/screenshots/view', methods=['GET'])
def view_screenshots_endpoint():
    """Endpoint for viewing screenshots in a simple HTML page."""
    try:
        # Get the latest screenshots
        screenshots = get_latest_screenshots(20)
        
        # Generate HTML for each screenshot separately 
        screenshot_html_parts = []
        for screenshot in screenshots:
            screenshot_html = f"""
            <div class="screenshot">
                <img src="/screenshots/{screenshot["filename"]}" alt="{screenshot["filename"]}">
                <div class="info">
                    <strong>Filename:</strong> {screenshot["created_formatted"]}<br>
                    <strong>Time:</strong> {screenshot["time"]}<br>
                    <strong>Size:</strong> {screenshot["size"]} bytes
                </div>
            </div>
            """
            screenshot_html_parts.append(screenshot_html)
        
        # Join all screenshot HTML parts
        all_screenshots_html = "".join(screenshot_html_parts)
        
        # Generate complete HTML
        html = f"""
        <html>
            <head>
                <title>Voice Control Screenshots</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    h1 {{ color: #333; }}
                    .screenshots {{ display: flex; flex-wrap: wrap; gap: 20px; }}
                    .screenshot {{ border: 1px solid #ddd; padding: 10px; border-radius: 5px; width: 300px; }}
                    .screenshot img {{ max-width: 100%; height: auto; }}
                    .info {{ font-size: 12px; color: #666; margin-top: 5px; }}
                </style>
            </head>
            <body>
                <h1>Voice Control Screenshots</h1>
                <p>Showing the {len(screenshots)} most recent screenshots.</p>
                <div class="screenshots">
                    {all_screenshots_html}
                </div>
            </body>
        </html>
        """
        
        return html
    
    except Exception as e:
        logger.error(f"Error viewing screenshots: {str(e)}")
        return error_response(f"Error viewing screenshots: {str(e)}", 500)

def run_screenshot_cleanup():
    """Run screenshot cleanup in the background to prevent disk filling.
    This function is intended to be run in a separate thread after responding to user requests.
    """
    try:
        # Get current cleanup settings
        from llm_control.voice.utils import cleanup_old_screenshots
        max_age_days = int(os.environ.get("SCREENSHOT_MAX_AGE_DAYS", "1"))
        max_count = int(os.environ.get("SCREENSHOT_MAX_COUNT", "10"))
        
        logger.info(f"Running background screenshot cleanup with max_age_days={max_age_days}, max_count={max_count}")
        cleanup_count, cleanup_error = cleanup_old_screenshots(max_age_days, max_count)
        
        if cleanup_error:
            logger.warning(f"Background screenshot cleanup error: {cleanup_error}")
        else:
            logger.info(f"Background cleanup completed: {cleanup_count} old screenshots removed")
            
        # Get total screenshot count for monitoring
        try:
            from llm_control.voice.screenshots import list_all_screenshots
            all_screenshots = list_all_screenshots()
            logger.info(f"Total screenshots after background cleanup: {len(all_screenshots)}")
        except Exception as e:
            logger.warning(f"Error counting screenshots after background cleanup: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error in background screenshot cleanup: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

@app.route('/screenshot/capture', methods=['GET', 'POST'])
@cors_preflight
def capture_screenshot_endpoint():
    """Endpoint for capturing a screenshot on demand."""
    try:
        # Get screenshot directory
        screenshot_dir = get_screenshot_dir()
        
        # Create directory if it doesn't exist
        os.makedirs(screenshot_dir, exist_ok=True)
        
        # Take a screenshot immediately without waiting for cleanup
        filename, filepath, success = capture_screenshot()
        
        if not filename or not filepath:
            return error_response("Failed to capture screenshot", 500)
        
        # Get file information
        file_size = os.path.getsize(filepath)
        
        # Determine response format based on query parameter or request content type
        format_param = request.args.get('format', None)
        
        # If format not specified in query params, check if it's a JSON request
        if format_param is None and request.is_json:
            format_param = 'json'
        # Default to redirect if not specified
        if format_param is None:
            format_param = 'redirect'
        
        # Prepare response before starting cleanup
        if format_param == 'json':
            # Get base64 image data
            img_str = get_screenshot_data(filename, format='base64')
            
            response_data = {
                "status": "success",
                "message": "Screenshot captured successfully",
                "filename": filename,
                "filepath": filepath,
                "url": f"/screenshots/{filename}",
                "size": file_size,
                "timestamp": int(time.time()),
                "image_data": img_str,
                "cleanup_info": {
                    "status": "scheduled",
                    "message": "Cleanup will run in background"
                }
            }
            
            # Start cleanup in background thread after preparing response
            cleanup_thread = threading.Thread(target=run_screenshot_cleanup)
            cleanup_thread.daemon = True  # Allow the thread to be terminated when the main process exits
            cleanup_thread.start()
            
            return jsonify(response_data)
        else:
            # Start cleanup in background thread
            cleanup_thread = threading.Thread(target=run_screenshot_cleanup)
            cleanup_thread.daemon = True
            cleanup_thread.start()
            
            # Redirect to the screenshot URL
            return redirect(f"/screenshots/{filename}")
    
    except Exception as e:
        logger.error(f"Error capturing screenshot: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return error_response(f"Error capturing screenshot: {str(e)}", 500)

@app.route('/screenshots/cleanup', methods=['GET', 'POST'])
@cors_preflight
def cleanup_screenshots_endpoint():
    """Endpoint for manually cleaning up old screenshots."""
    try:
        # Get maximum age and count parameters from request or environment
        max_age_days = request.args.get('max_age_days', None)
        max_count = request.args.get('max_count', None)
        
        if max_age_days is not None:
            max_age_days = int(max_age_days)
        else:
            max_age_days = int(os.environ.get("SCREENSHOT_MAX_AGE_DAYS", "1"))
            
        if max_count is not None:
            max_count = int(max_count)
        else:
            max_count = int(os.environ.get("SCREENSHOT_MAX_COUNT", "10"))
        
        # Force more aggressive cleanup if force parameter is set
        if request.args.get('force', 'false').lower() == 'true':
            if max_age_days > 1:
                max_age_days = 1  # More aggressive: just keep 1 day
            if max_count > 10:
                max_count = 10    # More aggressive: just keep 10 screenshots
        
        logger.info(f"Manual cleanup requested with max_age_days={max_age_days}, max_count={max_count}")
        
        # Get screenshot counts before cleanup
        before_count = 0
        try:
            from llm_control.voice.screenshots import list_all_screenshots
            all_screenshots = list_all_screenshots()
            before_count = len(all_screenshots)
            logger.info(f"Found {before_count} screenshots before cleanup")
        except Exception as e:
            logger.warning(f"Error counting screenshots before cleanup: {str(e)}")
        
        # Run the cleanup
        from llm_control.voice.screenshots import manual_cleanup_screenshots
        result = manual_cleanup_screenshots(max_age_days, max_count)
        
        # Add additional information to the result
        result['before_count'] = before_count
        result['parameters'] = {
            'max_age_days': max_age_days,
            'max_count': max_count,
            'force': request.args.get('force', 'false')
        }
        
        # Return the result
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error cleaning up screenshots: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return error_response(f"Error cleaning up screenshots: {str(e)}", 500)

@app.route('/unlock-screen', methods=['POST'])
@cors_preflight
def unlock_screen_endpoint():
    """Endpoint for unlocking the screen with a password."""
    try:
        # Get the request data
        data = request.get_json() or {}
        
        # Get the password from the request or use a default value (not secure - for demo purposes only)
        password = data.get('password', 'your_password')
        
        # Get the delay from the request or use the default
        delay = data.get('delay', 2)
        
        # Get the key interval from the request or use the default
        interval = data.get('interval', 0.1)
        
        # Get screenshot flag - default to disabled for security reasons
        capture_screenshot = data.get('capture_screenshot', False)
        
        logger.info("Executing screen unlock operation")
        
        # Set screenshot environment variable temporarily if needed
        original_screenshot_setting = os.environ.get("CAPTURE_SCREENSHOTS", "true")
        if not capture_screenshot:
            os.environ["CAPTURE_SCREENSHOTS"] = "false"
            logger.info("Temporarily disabled screenshots for screen unlock operation")
        
        # Execute unlock operation in a background thread to avoid blocking the response
        def unlock_background():
            try:
                import pyautogui
                import time
                
                # Log the beginning of the operation
                logger.info("Starting screen unlock process")
                
                # Wake up the screen
                pyautogui.press('shift')
                logger.info("Pressed shift key to wake up screen")
                
                # Wait for the password field to be ready
                logger.info(f"Waiting {delay} seconds for password field")
                time.sleep(delay)
                
                # Type the password
                logger.info(f"Typing password with interval {interval}")
                # Hide actual password in logs
                pyautogui.write(password, interval=interval)
                
                # Press Enter to unlock
                logger.info("Pressing Enter to unlock")
                pyautogui.press('enter')
                
                logger.info("Screen unlock operation completed")
            except Exception as e:
                logger.error(f"Error in unlock background thread: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
            finally:
                # Restore original screenshot setting
                os.environ["CAPTURE_SCREENSHOTS"] = original_screenshot_setting
                
        # Start the background thread
        unlock_thread = threading.Thread(target=unlock_background)
        unlock_thread.daemon = True
        unlock_thread.start()
        
        # Return a success response
        return jsonify({
            "status": "success",
            "message": "Screen unlock operation initiated",
            "timestamp": datetime.now().isoformat(),
            "screenshots_enabled": capture_screenshot
        })
        
    except Exception as e:
        # Restore original screenshot setting in case of error
        if 'original_screenshot_setting' in locals():
            os.environ["CAPTURE_SCREENSHOTS"] = original_screenshot_setting
            
        logger.error(f"Error unlocking screen: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return error_response(f"Error unlocking screen: {str(e)}", 500)

@app.route('/command-history', methods=['GET'])
def command_history_endpoint():
    """Endpoint for retrieving command execution history."""
    try:
        # Get the limit parameter from the request
        limit = request.args.get('limit', default=None, type=int)
        
        # Get the command history
        history = get_command_history(limit)
        
        # Return the history as JSON
        return jsonify({
            'status': 'success',
            'count': len(history),
            'history': history
        })
        
    except Exception as e:
        logger.error(f"Error retrieving command history: {str(e)}")
        import traceback
        error_trace = traceback.format_exc()
        logger.error(error_trace)
        
        # Include stack trace in debug mode
        if DEBUG:
            return jsonify({
                'error': f"Error retrieving command history: {str(e)}",
                'status': 'error',
                'traceback': error_trace
            }), 500
        else:
            return error_response(f"Error retrieving command history: {str(e)}", 500)

@app.route('/save-favorite', methods=['POST'])
@cors_preflight
def save_favorite_endpoint():
    """Endpoint for saving a command as a favorite script."""
    try:
        # Get the command data from the request
        command_data = request.get_json()
        
        if not command_data:
            return error_response("No command data provided", 400)
        
        # Check for required fields
        required_fields = ['command']
        for field in required_fields:
            if field not in command_data:
                return error_response(f"Missing required field: {field}", 400)
        
        # Get the optional name parameter
        name = command_data.get('name', None)
        
        # Save the command as a favorite
        result = save_as_favorite(command_data, name)
        
        if result['status'] == 'success':
            return jsonify(result)
        else:
            return error_response(result['error'], 500)
        
    except Exception as e:
        logger.error(f"Error saving favorite: {str(e)}")
        import traceback
        error_trace = traceback.format_exc()
        logger.error(error_trace)
        
        # Include stack trace in debug mode
        if DEBUG:
            return jsonify({
                'error': f"Error saving favorite: {str(e)}",
                'status': 'error',
                'traceback': error_trace
            }), 500
        else:
            return error_response(f"Error saving favorite: {str(e)}", 500)
            
@app.route('/favorites', methods=['GET'])
def favorites_endpoint():
    """Endpoint for retrieving favorite commands."""
    try:
        # Get the limit parameter from the request
        limit = request.args.get('limit', default=None, type=int)
        
        # Get the favorites
        favorites = get_favorites(limit)
        
        # Return the favorites as JSON
        return jsonify({
            'status': 'success',
            'count': len(favorites),
            'favorites': favorites
        })
        
    except Exception as e:
        logger.error(f"Error retrieving favorites: {str(e)}")
        import traceback
        error_trace = traceback.format_exc()
        logger.error(error_trace)
        
        # Include stack trace in debug mode
        if DEBUG:
            return jsonify({
                'error': f"Error retrieving favorites: {str(e)}",
                'status': 'error',
                'traceback': error_trace
            }), 500
        else:
            return error_response(f"Error retrieving favorites: {str(e)}", 500)

@app.route('/delete-favorite/<script_id>', methods=['DELETE'])
@cors_preflight
def delete_favorite_endpoint(script_id):
    """Endpoint for deleting a favorite script."""
    try:
        # Delete the favorite script
        result = delete_favorite(script_id)
        
        # Return the result
        if result['status'] == 'success':
            return jsonify(result)
        else:
            return error_response(result['error'], 404 if "not found" in result.get('error', '').lower() else 500)
        
    except Exception as e:
        logger.error(f"Error deleting favorite: {str(e)}")
        import traceback
        error_trace = traceback.format_exc()
        logger.error(error_trace)
        
        # Include stack trace in debug mode
        if DEBUG:
            return jsonify({
                'error': f"Error deleting favorite: {str(e)}",
                'status': 'error',
                'traceback': error_trace
            }), 500
        else:
            return error_response(f"Error deleting favorite: {str(e)}", 500)

@app.route('/run-favorite/<script_id>', methods=['POST'])
@cors_preflight
def run_favorite_endpoint(script_id):
    """Endpoint for running a favorite script."""
    try:
        # Run the favorite script
        result = run_favorite(script_id)
        
        # Return the result
        if result['status'] == 'success':
            return jsonify(result)
        else:
            return error_response(result['error'], 404 if "not found" in result.get('error', '').lower() else 500)
        
    except Exception as e:
        logger.error(f"Error running favorite: {str(e)}")
        import traceback
        error_trace = traceback.format_exc()
        logger.error(error_trace)
        
        # Include stack trace in debug mode
        if DEBUG:
            return jsonify({
                'error': f"Error running favorite: {str(e)}",
                'status': 'error',
                'traceback': error_trace
            }), 500
        else:
            return error_response(f"Error running favorite: {str(e)}", 500)

@app.route('/', methods=['GET'])
def index():
    """Main page showing server information and available endpoints."""
    screenshot_dir = get_screenshot_dir()
    server_config = {
        "whisper_model": os.environ.get("WHISPER_MODEL_SIZE", "base"),
        "ollama_model": os.environ.get("OLLAMA_MODEL", "gemma3:12b"),
        "ollama_host": os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        "language": os.environ.get("DEFAULT_LANGUAGE", "en"),
        "translation_enabled": os.environ.get("TRANSLATION_ENABLED", "False"),
        "screenshot_dir": screenshot_dir
    }
    
    # List of available endpoints
    endpoints = [
        {
            "path": "/",
            "methods": ["GET"],
            "description": "This page - Server information and API documentation"
        },
        {
            "path": "/health",
            "methods": ["GET"],
            "description": "Health check endpoint"
        },
        {
            "path": "/transcribe",
            "methods": ["POST"],
            "description": "Transcribe audio to text",
            "example": """curl -X POST -F "audio=@your-audio-file.wav" http://localhost:5000/transcribe"""
        },
        {
            "path": "/translate",
            "methods": ["POST"],
            "description": "Translate text using the configured LLM",
            "example": """curl -X POST -H "Content-Type: application/json" -d '{"text": "your text to translate"}' http://localhost:5000/translate"""
        },
        {
            "path": "/command",
            "methods": ["POST"],
            "description": "Execute a command",
            "example": """curl -X POST -H "Content-Type: application/json" -d '{"command": "click on Firefox", "capture_screenshot": true}' http://localhost:5000/command"""
        },
        {
            "path": "/voice-command",
            "methods": ["POST"],
            "description": "Process and execute a voice command",
            "example": """curl -X POST -F "audio=@your-command.wav" http://localhost:5000/voice-command"""
        },
        {
            "path": "/screenshots",
            "methods": ["GET"],
            "description": "List available screenshots",
            "example": """curl http://localhost:5000/screenshots"""
        },
        {
            "path": "/screenshots/latest",
            "methods": ["GET"],
            "description": "Get information about the latest screenshots",
            "example": """curl http://localhost:5000/screenshots/latest"""
        },
        {
            "path": "/screenshots/<filename>",
            "methods": ["GET"],
            "description": "Serve a specific screenshot file",
            "example": """curl http://localhost:5000/screenshots/ocr_screenshot.png > screenshot.png"""
        },
        {
            "path": "/screenshots/view",
            "methods": ["GET"],
            "description": "View screenshots in a simple HTML page",
            "example": """Open http://localhost:5000/screenshots/view in your browser"""
        },
        {
            "path": "/screenshot/capture",
            "methods": ["GET", "POST"],
            "description": "Capture a screenshot on demand",
            "example": """curl -X POST -H "Content-Type: application/json" http://localhost:5000/screenshot/capture?format=json"""
        },
        {
            "path": "/screenshots/cleanup",
            "methods": ["GET", "POST"],
            "description": "Manually clean up old screenshots",
            "example": """curl -X POST -H "Content-Type: application/json" http://localhost:5000/screenshots/cleanup?max_age_days=3&max_count=50"""
        },
        {
            "path": "/unlock-screen",
            "methods": ["POST"],
            "description": "Unlock the screen with a password",
            "example": """curl -X POST -H "Content-Type: application/json" -d '{"password": "your_password"}' http://localhost:5000/unlock-screen"""
        },
        {
            "path": "/command-history",
            "methods": ["GET"],
            "description": "Get command execution history",
            "example": """curl http://localhost:5000/command-history?limit=10"""
        },
        {
            "path": "/save-favorite",
            "methods": ["POST"],
            "description": "Save a command as a favorite script",
            "example": """curl -X POST -H "Content-Type: application/json" -d '{"command": "your command", "code": "your code", "steps": ["step1", "step2"], "success": true}' http://localhost:5000/save-favorite"""
        },
        {
            "path": "/favorites",
            "methods": ["GET"],
            "description": "Get favorite commands",
            "example": """curl http://localhost:5000/favorites?limit=10"""
        },
        {
            "path": "/delete-favorite/<script_id>",
            "methods": ["DELETE"],
            "description": "Delete a favorite script",
            "example": """curl -X DELETE http://localhost:5000/delete-favorite/open_firefox_20250426_183939"""
        },
        {
            "path": "/run-favorite/<script_id>",
            "methods": ["POST"],
            "description": "Run a favorite script",
            "example": """curl -X POST http://localhost:5000/run-favorite/open_firefox_20250426_183939"""
        }
    ]
    
    # Generate HTML response
    html = f"""
    <html>
        <head>
            <title>Voice Control Server</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                h1, h2, h3 {{ color: #333; }}
                .section {{ margin-bottom: 30px; }}
                .config {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                .config-item {{ margin-bottom: 5px; }}
                .config-value {{ font-weight: bold; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ text-align: left; padding: 12px; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .method {{ font-weight: bold; }}
                .example {{ background-color: #f5f5f5; padding: 10px; border-radius: 3px; overflow-x: auto; }}
                code {{ font-family: monospace; }}
            </style>
        </head>
        <body>
            <h1>Voice Control Server</h1>
            
            <div class="section">
                <h2>Server Configuration</h2>
                <div class="config">
                    <div class="config-item">Whisper Model: <span class="config-value">{server_config['whisper_model']}</span></div>
                    <div class="config-item">Ollama Model: <span class="config-value">{server_config['ollama_model']}</span></div>
                    <div class="config-item">Ollama Host: <span class="config-value">{server_config['ollama_host']}</span></div>
                    <div class="config-item">Default Language: <span class="config-value">{server_config['language']}</span></div>
                    <div class="config-item">Translation Enabled: <span class="config-value">{server_config['translation_enabled']}</span></div>
                    <div class="config-item">Screenshot Directory: <span class="config-value">{server_config['screenshot_dir']}</span></div>
                </div>
            </div>
            
            <div class="section">
                <h2>Quick Links</h2>
                <ul>
                    <li><a href="/screenshots/view" target="_blank">View Latest Screenshots</a></li>
                    <li><a href="/screenshot/capture" target="_blank">Capture Screenshot Now</a></li>
                </ul>
            </div>
            
            <div class="section">
                <h2>Available Endpoints</h2>
                <table>
                    <tr>
                        <th>Endpoint</th>
                        <th>Methods</th>
                        <th>Description</th>
                        <th>Example</th>
                    </tr>
                    {generate_endpoint_rows(endpoints)}
                </table>
            </div>
        </body>
    </html>
    """
    
    return html

def generate_endpoint_rows(endpoints):
    """Helper function to generate HTML rows for endpoints table."""
    rows = []
    for endpoint in endpoints:
        example_html = '<div class="example"><code>' + endpoint.get('example', 'N/A') + '</code></div>' if endpoint.get('example') else 'N/A'
        row = f"""
        <tr>
            <td>{endpoint['path']}</td>
            <td class="method">{', '.join(endpoint['methods'])}</td>
            <td>{endpoint['description']}</td>
            <td>{example_html}</td>
        </tr>
        """
        rows.append(row)
    return ''.join(rows)

def run_server(host='0.0.0.0', port=5000, debug=False, ssl_context=None, ollama_model=None):
    """Run the voice control server."""
    # Configure the logger level based on debug mode
    configure_logging(debug)
    
    # Si se especifica un modelo de Ollama, actualizarlo directamente en el módulo commands
    if ollama_model:
        import llm_control.voice.commands
        llm_control.voice.commands.OLLAMA_MODEL = ollama_model
        logger.info(f"Overriding Ollama model from argument: {ollama_model}")
    
    # Initialize UI detection models if available
    try:
        from llm_control.ui_detection.element_finder import get_ui_detector#, get_phi3_vision
        
        # Initialize UI detector (this will download if missing)
        ui_detector = get_ui_detector(download_if_missing=True)
        if ui_detector:
            logger.info("UI detector initialized successfully")
        else:
            logger.warning("UI detector initialization failed")
            
        # # Try to initialize Phi-3 Vision if available
        # try:
        #     phi3_vision = get_phi3_vision(download_if_missing=False)  # Don't force download on startup
        #     if phi3_vision:
        #         logger.info("Phi-3 Vision model initialized successfully")
        # except Exception as phi_error:
        #     logger.warning(f"Phi-3 Vision initialization skipped: {phi_error}")
            
    except ImportError as e:
        logger.warning(f"UI detection module import failed: {e}")
    
    # Add PyAutoGUI extensions
    add_pyautogui_extensions()
    
    # Get screenshot settings
    screenshot_dir = os.environ.get("SCREENSHOT_DIR", ".")
    screenshot_dir = get_screenshot_dir()  # This will resolve to the actual directory used
    screenshot_max_age = os.environ.get("SCREENSHOT_MAX_AGE_DAYS", "1")
    screenshot_max_count = os.environ.get("SCREENSHOT_MAX_COUNT", "10")
    
    # Get command history file path
    from llm_control.voice.utils import get_command_history_file
    history_file = get_command_history_file()
    
    # Check GPU availability
    import torch
    gpu_available = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if gpu_available else "None"
    
    print(f"\n{'=' * 40}")
    print(f"🎤 Voice Control Server v1.0 starting...")
    print(f"🌐 Listening on: http{'s' if ssl_context else ''}://{host}:{port}")
    print(f"🔧 Debug mode: {'ON' if debug else 'OFF'}")
    print(f"🗣️ Default language: {DEFAULT_LANGUAGE}")
    print(f"🤖 Using Whisper model: {WHISPER_MODEL_SIZE}")
    print(f"🦙 Using Ollama model: {OLLAMA_MODEL}")
    print(f"📸 Screenshot directory: {screenshot_dir}")
    print(f"📸 Screenshot max age (days): {screenshot_max_age}")
    print(f"📸 Screenshot max count: {screenshot_max_count}")
    print(f"📜 Command history file: {history_file}")
    print(f"⚠️ PyAutoGUI failsafe: {'ENABLED' if os.environ.get('PYAUTOGUI_FAILSAFE') == 'true' else 'DISABLED'}")
    print(f"🖼️ Vision captioning: {'ENABLED' if os.environ.get('VISION_CAPTIONING') == 'true' else 'DISABLED'}")
    print(f"🎮 GPU: {'Available - ' + gpu_name if gpu_available else 'Not available'}")
    print(f"{'=' * 40}\n")
    
    logger.info(f"Screenshot settings - Directory: {screenshot_dir}, Max age: {screenshot_max_age} days, Max count: {screenshot_max_count}")
    
    try:
        app.run(host=host, port=port, debug=debug, ssl_context=ssl_context)
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        print(f"❌ Server error: {str(e)}")
        sys.exit(1)

# Main entry point
if __name__ == '__main__':
    # Parse command-line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description='Voice control server')
    
    parser.add_argument('--host', type=str, default='0.0.0.0',
                        help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000,
                        help='Port to bind to (default: 5000)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug mode')
    parser.add_argument('--ssl', action='store_true',
                        help='Enable SSL with self-signed certificate (adhoc)')
    parser.add_argument('--ssl-cert', type=str,
                        help='Path to SSL certificate file')
    parser.add_argument('--ssl-key', type=str,
                        help='Path to SSL private key file')
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
    parser.add_argument('--screenshot-dir', type=str, default='./screenshots',
                        help='Directory where screenshots will be saved (default: current directory)')
    
    args = parser.parse_args()
    
    # Update environment variables
    os.environ["WHISPER_MODEL_SIZE"] = args.whisper_model
    os.environ["OLLAMA_MODEL"] = args.ollama_model
    os.environ["OLLAMA_HOST"] = args.ollama_host
    os.environ["TRANSLATION_ENABLED"] = "false" if args.disable_translation else "true"
    os.environ["DEFAULT_LANGUAGE"] = args.language
    os.environ["CAPTURE_SCREENSHOTS"] = "false" if args.disable_screenshots else "true"
    os.environ["PYAUTOGUI_FAILSAFE"] = "true" if args.enable_failsafe else "false"
    os.environ["SCREENSHOT_DIR"] = args.screenshot_dir
    
    # Configure SSL context
    ssl_context = None
    
    # Check for custom certificate and key first (prioritize over adhoc)
    if args.ssl_cert and args.ssl_key:
        ssl_context = (args.ssl_cert, args.ssl_key)
        logger.info(f"Using custom SSL certificate: {args.ssl_cert}")
        logger.info(f"Using custom SSL key: {args.ssl_key}")
        # Warn if both --ssl and custom certificates are provided
        if args.ssl:
            logger.warning("Both --ssl and custom certificate options provided. Using custom certificate.")
    # Fall back to adhoc SSL if no custom certificate/key but --ssl flag is set
    elif args.ssl:
        try:
            # Check if pyopenssl is installed
            import ssl
            from werkzeug.serving import make_ssl_devcert
            
            ssl_context = 'adhoc'
            logger.info("Using self-signed certificate for HTTPS")
        except ImportError:
            logger.error("SSL option requires pyopenssl to be installed")
            logger.error("Install with: pip install pyopenssl")
            sys.exit(1)
    
    # Run the server
    run_server(host=args.host, port=args.port, debug=args.debug, ssl_context=ssl_context)

# Helper function to get memory usage
def get_memory_usage():
    """
    Get the current memory usage of the process in MiB.
    
    Returns:
        float: Memory usage in MiB
    """
    try:
        import psutil
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)  # Convert bytes to MiB
        return memory_mb
    except ImportError:
        logger.warning("psutil not available, cannot get memory usage")
        return 0.0
    except Exception as e:
        logger.warning(f"Error getting memory usage: {e}")
        return 0.0

# Helper function to get GPU processes
def get_gpu_processes():
    """
    Get information about processes using GPU.
    
    Returns:
        list: List of dictionaries with process information
    """
    processes = []
    
    try:
        import subprocess
        import re
        
        # Run nvidia-smi to get process information
        result = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,name,used_memory', '--format=csv,noheader,nounits'], 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode == 0:
            # Parse the output
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split(',')
                    if len(parts) >= 3:
                        try:
                            pid = int(parts[0].strip())
                            name = parts[1].strip()
                            mem = float(parts[2].strip())
                            
                            processes.append({
                                'pid': pid,
                                'name': name,
                                'memory_mb': mem
                            })
                        except ValueError:
                            continue
        else:
            logger.warning(f"Error running nvidia-smi: {result.stderr}")
    except Exception as e:
        logger.warning(f"Error getting GPU processes: {e}")
    
    return processes

# Function to process voice commands
def process_voice_command(text, language=None):
    """
    Process a voice command.
    
    Args:
        text: The transcribed text to process as a command
        language: The language of the command
        
    Returns:
        dict: Command processing result
    """
    import gc
    
    logger.info(f"Processing voice command: '{text}'")
    start_time = time.time()
    
    try:
        # Use the same command execution logic as the /command endpoint
        model = os.environ.get("OLLAMA_MODEL", OLLAMA_MODEL)
        ollama_host = os.environ.get("OLLAMA_HOST", OLLAMA_HOST)
        
        # Execute the command with enhanced logging
        result = execute_command_with_logging(text, model=model, ollama_host=ollama_host)
        
        # Add timing information
        result['processing_time'] = {
            'execution': time.time() - start_time
        }
        
        # Force memory cleanup after processing
        gc.collect()
        
        logger.info(f"Command processed successfully in {time.time() - start_time:.2f} seconds")
        return result
        
    except Exception as e:
        logger.error(f"Error processing command: {e}")
        return {
            "success": False,
            "error": str(e),
            "command": text
        }
    finally:
        # Final cleanup
        gc.collect()

# Add a new route to handle /voice-command that forwards to /api/voice-command
@app.route('/voice-command', methods=['POST', 'OPTIONS'])
@cors_preflight
def voice_command_legacy_endpoint():
    """Legacy endpoint for /voice-command - forwards to /api/voice-command"""
    logger.info("Received request to legacy /voice-command endpoint - forwarding to /api/voice-command")
    return voice_command_endpoint()
