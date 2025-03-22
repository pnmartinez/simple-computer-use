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

# Configure logging
logger = logging.getLogger("voice-control-server")

try:
    from flask import Flask, request, jsonify, send_file, abort, Response, render_template_string, redirect, make_response
    from flask_cors import CORS
    logger.debug("Successfully imported Flask and Flask-CORS")
except ImportError:
    logger.critical("Flask not installed. Please install flask and flask-cors.")
    sys.exit(1)

# Import from our own modules
from llm_control.voice.utils import error_response, cors_preflight, add_cors_headers, test_cuda_availability, get_screenshot_dir
from llm_control.voice.utils import is_debug_mode, configure_logging, DEBUG
from llm_control.voice.audio import transcribe_audio, translate_text
from llm_control.voice.screenshots import capture_screenshot, capture_with_highlight, get_latest_screenshots, list_all_screenshots, get_screenshot_data
from llm_control.voice.commands import validate_pyautogui_cmd, split_command_into_steps, identify_ocr_targets, generate_pyautogui_actions, execute_command_with_llm
from llm_control.voice.commands import execute_command_with_logging, process_command_pipeline

# Constants and configuration
DEFAULT_LANGUAGE = os.environ.get("DEFAULT_LANGUAGE", "es")
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "medium")
TRANSLATION_ENABLED = os.environ.get("TRANSLATION_ENABLED", "true").lower() != "false"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1") 
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
        
        # Add more debug information if in debug mode
        if DEBUG:
            result['debug'] = {
                'server_version': '1.0.0',
                'timestamp': datetime.now().isoformat(),
                'environment': {
                    'ollama_model': model,
                    'ollama_host': ollama_host
                }
            }
            
            # Add pipeline debugging info if available
            if 'pipeline_result' in locals() and pipeline_result:
                result['debug']['pipeline'] = pipeline_result
                
                # Explicitly extract and format PyAutoGUI code for easier access
                if 'code' in pipeline_result and pipeline_result['code']:
                    pyautogui_code = []
                    
                    # Add imports
                    if 'imports' in pipeline_result['code']:
                        pyautogui_code.append(pipeline_result['code']['imports'])
                    
                    # Add step-by-step code
                    if 'steps' in pipeline_result['code']:
                        for step in pipeline_result['code']['steps']:
                            pyautogui_code.append(f"# {step.get('original', 'Step')}")
                            pyautogui_code.append(step.get('code', ''))
                    
                    # Add the formatted code to the debug section
                    result['debug']['pyautogui_code'] = '\n\n'.join(pyautogui_code)
        
        # Capture a screenshot if requested
        if capture_screenshot_flag:
            success, filepath = capture_screenshot()
            if success and filepath:
                # Extract just the filename from the full path
                filename = os.path.basename(filepath)
                result['screenshot'] = {
                    'filename': filename,
                    'filepath': filepath,
                    'url': f"/screenshots/{filename}"
                }
                logger.info(f"Captured screenshot and saved to {filepath}")
        
        # Return the result
        return jsonify(result)
    
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

@app.route('/voice-command', methods=['POST'])
@cors_preflight
def voice_command_endpoint():
    """Endpoint for processing and executing a voice command."""
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
        
        # Get screenshot option
        capture_screenshot_flag = request.form.get('capture_screenshot', 'true').lower() == 'true'
        
        # Log the start of voice command processing
        logger.info(f"Processing voice command with language: {language}, model: {model_size}")
        logger.info(f"Audio file size: {len(audio_data)} bytes")
        
        # Transcribe the audio
        transcription_start = time.time()
        transcription_result = transcribe_audio(audio_data, model_size, language)
        transcription_time = time.time() - transcription_start
        
        # Check if there was an error
        if 'error' in transcription_result and transcription_result['error']:
            logger.error(f"Transcription error: {transcription_result['error']}")
            return error_response(transcription_result['error'], 500)
        
        # Get the transcribed text
        transcribed_text = transcription_result.get('text', '')
        detected_language = transcription_result.get('language', 'unknown')
        
        logger.info(f"Transcription completed in {transcription_time:.2f} seconds")
        logger.info(f"Detected language: {detected_language}")
        logger.info(f"Transcribed text: '{transcribed_text}'")
        
        # Skip empty transcription
        if not transcribed_text:
            logger.warning("No speech detected in audio")
            return error_response("No speech detected", 400)
        
        # Translate if needed
        command_text = transcribed_text
        was_translated = False
        translation_time = 0
        
        # if TRANSLATION_ENABLED and detected_language != 'en' and detected_language != 'eng':
        #     logger.info(f"Translating from {detected_language} to English")
        #     translation_start = time.time()
        #     translated = translate_text(transcribed_text)
        #     translation_time = time.time() - translation_start
            
        #     if translated:
        #         command_text = translated
        #         was_translated = True
        #         logger.info(f"Translation completed in {translation_time:.2f} seconds")
        #         logger.info(f"Translated text: '{command_text}'")
        #     else:
        #         logger.warning("Translation failed, using original text")
        
        # Log detailed information about the command
        logger.info(f"Processing command: '{command_text}'")
        
        # Process command pipeline first to gather detailed debugging info if in debug mode
        if DEBUG:
            # Gather debug information by processing the command pipeline
            pipeline_result = process_command_pipeline(command_text, model=OLLAMA_MODEL)
            logger.debug(f"Command pipeline processed with success: {pipeline_result.get('success', False)}")
        
        # Execute the command with enhanced logging
        execution_start = time.time()
        result = execute_command_with_logging(command_text, model=OLLAMA_MODEL, ollama_host=OLLAMA_HOST)
        execution_time = time.time() - execution_start
        
        logger.info(f"Command execution completed in {execution_time:.2f} seconds")
        logger.info(f"Command execution success: {result.get('success', False)}")
        
        # Add transcription information to result
        result['transcription'] = {
            'text': transcribed_text,
            'language': detected_language,
            'translated': was_translated,
            'translated_text': command_text if was_translated else None,
            'processing_time': {
                'transcription': transcription_time,
                'translation': translation_time if was_translated else 0,
                'execution': execution_time,
                'total': transcription_time + (translation_time if was_translated else 0) + execution_time
            }
        }
        
        # Add segments information if in debug mode
        if DEBUG and 'segments' in transcription_result:
            result['transcription']['segments'] = transcription_result['segments']
        
        # Include command processing pipeline information if in debug mode
        if DEBUG and 'processed_steps' in result:
            logger.info(f"Command processed into {len(result['processed_steps'])} steps")
        
        # Add detailed debug information
        if DEBUG:
            # Create a debug section with all processing details
            result['debug'] = {
                'server_version': '1.0.0',
                'timestamp': datetime.now().isoformat(),
                'environment': {
                    'whisper_model': WHISPER_MODEL_SIZE,
                    'ollama_model': OLLAMA_MODEL,
                    'ollama_host': OLLAMA_HOST,
                    'default_language': DEFAULT_LANGUAGE,
                    'translation_enabled': TRANSLATION_ENABLED,
                },
                'request': {
                    'audio_size': len(audio_data),
                    'language': language,
                    'model': model_size,
                    'capture_screenshot': capture_screenshot_flag
                }
            }
            
            # Add pipeline debugging info if available - including PyAutoGUI code
            if 'pipeline_result' in locals() and pipeline_result:
                result['debug']['pipeline'] = pipeline_result
                
                # Explicitly extract and format PyAutoGUI code for easier access
                if 'code' in pipeline_result and pipeline_result['code']:
                    pyautogui_code = []
                    
                    # Add imports
                    if 'imports' in pipeline_result['code']:
                        pyautogui_code.append(pipeline_result['code']['imports'])
                    
                    # Add step-by-step code
                    if 'steps' in pipeline_result['code']:
                        for step in pipeline_result['code']['steps']:
                            pyautogui_code.append(f"# {step.get('original', 'Step')}")
                            pyautogui_code.append(step.get('code', ''))
                    
                    # Add the formatted code to the debug section
                    result['debug']['pyautogui_code'] = '\n\n'.join(pyautogui_code)
        
        # Capture a screenshot if requested
        if capture_screenshot_flag:
            success, filepath = capture_screenshot()
            if success and filepath:
                # Extract just the filename from the full path
                filename = os.path.basename(filepath)
                result['screenshot'] = {
                    'filename': filename,
                    'filepath': filepath,
                    'url': f"/screenshots/{filename}"
                }
                logger.info(f"Captured screenshot and saved to {filepath}")
        
        # Return the result
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error processing voice command: {str(e)}")
        import traceback
        error_trace = traceback.format_exc()
        logger.error(error_trace)
        
        # Include stack trace in debug mode
        if DEBUG:
            return jsonify({
                "error": f"Error processing voice command: {str(e)}",
                "status": "error",
                "traceback": error_trace
            }), 500
        else:
            return error_response(f"Error processing voice command: {str(e)}", 500)

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
        
        # Generate HTML
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
                    {''.join([f"""
                    <div class="screenshot">
                        <img src="/screenshots/{screenshot['filename']}" alt="{screenshot['filename']}">
                        <div class="info">
                            <strong>Filename:</strong> {screenshot['filename']}<br>
                            <strong>Time:</strong> {screenshot['created_formatted']}<br>
                            <strong>Size:</strong> {screenshot['size']} bytes
                        </div>
                    </div>
                    """ for screenshot in screenshots])}
                </div>
            </body>
        </html>
        """
        
        return html
    
    except Exception as e:
        logger.error(f"Error viewing screenshots: {str(e)}")
        return error_response(f"Error viewing screenshots: {str(e)}", 500)

@app.route('/screenshot/capture', methods=['GET', 'POST'])
@cors_preflight
def capture_screenshot_endpoint():
    """Endpoint for capturing a screenshot on demand."""
    try:
        # Get screenshot directory
        screenshot_dir = get_screenshot_dir()
        
        # Create directory if it doesn't exist
        os.makedirs(screenshot_dir, exist_ok=True)
        
        # Take a screenshot
        filename, filepath, _ = capture_screenshot()
        
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
        
        if format_param == 'json':
            # Get base64 image data
            img_str = get_screenshot_data(filename, format='base64')
            
            return jsonify({
                "status": "success",
                "message": "Screenshot captured successfully",
                "filename": filename,
                "filepath": filepath,
                "url": f"/screenshots/{filename}",
                "size": file_size,
                "timestamp": int(time.time()),
                "image_data": img_str
            })
        else:
            # Redirect to the screenshot URL
            return redirect(f"/screenshots/{filename}")
    
    except Exception as e:
        logger.error(f"Error capturing screenshot: {str(e)}")
        return error_response(f"Error capturing screenshot: {str(e)}", 500)

@app.route('/', methods=['GET'])
def index():
    """Main page showing server information and available endpoints."""
    screenshot_dir = get_screenshot_dir()
    server_config = {
        "whisper_model": os.environ.get("WHISPER_MODEL_SIZE", "base"),
        "ollama_model": os.environ.get("OLLAMA_MODEL", "llama3.1"),
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
                    {''.join([f"""
                    <tr>
                        <td>{endpoint['path']}</td>
                        <td class="method">{', '.join(endpoint['methods'])}</td>
                        <td>{endpoint['description']}</td>
                        <td>{'<div class="example"><code>' + endpoint.get('example', 'N/A') + '</code></div>' if endpoint.get('example') else 'N/A'}</td>
                    </tr>
                    """ for endpoint in endpoints])}
                </table>
            </div>
        </body>
    </html>
    """
    
    return html

def run_server(host='0.0.0.0', port=5000, debug=False, ssl_context=None):
    """Run the voice control server."""
    # Configure the logger level based on debug mode
    configure_logging(debug)
    
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
    
    print(f"\n{'=' * 40}")
    print(f"🎤 Voice Control Server v1.0 starting...")
    print(f"🌐 Listening on: http{'s' if ssl_context else ''}://{host}:{port}")
    print(f"🔧 Debug mode: {'ON' if debug else 'OFF'}")
    print(f"🗣️ Default language: {DEFAULT_LANGUAGE}")
    print(f"🤖 Using Whisper model: {WHISPER_MODEL_SIZE}")
    print(f"🦙 Using Ollama model: {OLLAMA_MODEL}")
    print(f"⚠️ PyAutoGUI failsafe: {'ENABLED' if os.environ.get('PYAUTOGUI_FAILSAFE') == 'true' else 'DISABLED'}")
    print(f"{'=' * 40}\n")
    
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
    parser.add_argument('--screenshot-dir', type=str, default='.',
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
