import os
import logging
import tempfile
import requests
import io
import ssl
import json
import sys
import uuid
import base64
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
import threading

# Initialize global variables
_whisper_model = None

# Check Flask version to handle imports differently
try:
    from flask import Flask, request, jsonify, render_template_string, make_response, Response
    # Check for Flask-SocketIO
    SOCKETIO_AVAILABLE = False
    try:
        from flask_socketio import SocketIO
        SOCKETIO_AVAILABLE = True
    except ImportError:
        logging.warning("Flask-SocketIO not installed. WebSocket functionality will not be available.")
except ImportError:
    logging.critical("Flask not installed. Please install Flask")
    raise

try:
    import whisper
except ImportError:
    logging.warning("Whisper not installed. Voice recognition will not work.")

from llm_control.main import run_command
from llm_control.utils.dependencies import check_and_install_package

# Configure logging
logger = logging.getLogger("llm-pc-control")

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'llm-control-secret-key'
# Increase maximum content length for audio uploads (50MB)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# Translation settings
_translation_enabled = False
_ollama_model = "llama3.1"
_ollama_host = "http://localhost:11434"

# Server configuration
_server_start_time = None
_is_ssl_enabled = False
_ssl_cert_path = None
_ssl_cert_expiry = None
_android_wss_path = "/ws"  # Default path for Android WebSocket

# Client connections (for stats/debugging)
_active_connections = 0
_total_connections = 0
_successful_commands = 0
_failed_commands = 0

# Discovery info endpoint template for auto-discovery
DISCOVERY_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>LLM PC Control - WebSocket Discovery</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            background-color: #f5f5f5;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }
        .status-box {
            background-color: #fff;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        code {
            background-color: #f8f9fa;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
            border: 1px solid #e1e4e8;
        }
        .connection-url {
            font-size: 18px;
            padding: 10px;
            background-color: #f0f8ff;
            border: 1px solid #add8e6;
            border-radius: 4px;
            margin: 10px 0;
            word-break: break-all;
        }
        .success {
            color: #008000;
        }
        .error {
            color: #d9534f;
        }
    </style>
</head>
<body>
    <h1>LLM PC Control WebSocket Discovery</h1>
    
    <div class="status-box">
        <h2>Server Status: <span class="success">Running</span></h2>
        <p>This endpoint provides connection information for LLM PC Control clients.</p>
        
        <h3>WebSocket Connection URL:</h3>
        <div class="connection-url">{{ websocket_url }}</div>
        
        <p>Configuration:</p>
        <ul>
            <li>Protocol: {{ protocol }}</li>
            <li>SSL/TLS: {{ ssl_status }}</li>
            <li>Translation: {{ translation_status }}</li>
        </ul>
    </div>
    
    <div class="status-box">
        <h3>For Android Clients:</h3>
        <p>Use the following connection string in your app settings:</p>
        <div class="connection-url">{{ websocket_url }}</div>
    </div>
    
    <div class="status-box">
        <h3>API Endpoints:</h3>
        <ul>
            <li><code>GET /health</code> - Health check endpoint</li>
            <li><code>POST /transcribe</code> - Transcribe audio to text</li>
            <li><code>POST /command</code> - Execute a command</li>
            <li><code>POST /voice-command</code> - Process voice command</li>
        </ul>
    </div>
</body>
</html>
"""

# HTML template for the status page
STATUS_PAGE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>LLM PC Control Server Status</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }
        .server-status {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .server-status h2 {
            margin-top: 0;
            color: #3498db;
        }
        .status-item {
            margin-bottom: 8px;
        }
        .status-label {
            font-weight: bold;
            display: inline-block;
            width: 180px;
        }
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
            margin-left: 8px;
        }
        .badge-success {
            background-color: #2ecc71;
            color: white;
        }
        .badge-warning {
            background-color: #f39c12;
            color: white;
        }
        .badge-secure {
            background-color: #3498db;
            color: white;
        }
        .endpoint {
            background-color: #f1f1f1;
            padding: 10px;
            border-radius: 4px;
            font-family: monospace;
            margin-bottom: 5px;
        }
        .security-warning {
            background-color: #ffe5e5;
            border-left: 4px solid #ff4d4d;
            padding: 10px 15px;
            margin: 20px 0;
            border-radius: 0 4px 4px 0;
        }
        @media (max-width: 600px) {
            .status-label {
                width: 140px;
            }
        }
    </style>
</head>
<body>
    <h1>LLM PC Control Server</h1>
    
    <div class="server-status">
        <h2>Server Status <span class="badge badge-success">Running</span></h2>
        
        <div class="status-item">
            <span class="status-label">Uptime:</span>
            <span>{{ uptime }}</span>
        </div>
        
        <div class="status-item">
            <span class="status-label">WebSocket Protocol:</span>
            <span>{{ ws_protocol }}</span>
            {% if is_ssl_enabled %}
            <span class="badge badge-secure">Secure</span>
            {% else %}
            <span class="badge badge-warning">Insecure</span>
            {% endif %}
        </div>
        
        <div class="status-item">
            <span class="status-label">Active Connections:</span>
            <span>{{ active_connections }}</span>
        </div>
        
        <div class="status-item">
            <span class="status-label">Total Connections:</span>
            <span>{{ total_connections }}</span>
        </div>
        
        <div class="status-item">
            <span class="status-label">Whisper Model:</span>
            <span>{{ whisper_model }}</span>
        </div>
        
        <div class="status-item">
            <span class="status-label">Translation:</span>
            <span>{{ "Enabled" if translation_enabled else "Disabled" }}</span>
            {% if translation_enabled %}
            <span>({{ ollama_model }})</span>
            {% endif %}
        </div>
        
        <div class="status-item">
            <span class="status-label">Commands Processed:</span>
            <span>{{ successful_commands }} successful, {{ failed_commands }} failed</span>
        </div>
    </div>
    
    <h2>API Endpoints</h2>
    
    <div class="status-item">
        <h3>HTTP Endpoints:</h3>
        <div class="endpoint">GET /health - Health check endpoint</div>
        <div class="endpoint">POST /transcribe - Transcribe audio file</div>
        <div class="endpoint">POST /command - Execute a command</div>
        <div class="endpoint">POST /voice-command - Process and execute a voice command</div>
    </div>
    
    <div class="status-item">
        <h3>WebSocket Endpoint:</h3>
        <div class="endpoint">{{ ws_endpoint }}</div>
        <p>WebSocket events:</p>
        <ul>
            <li><code>connect</code> - Connection established</li>
            <li><code>audio_command</code> - Send audio for transcription and execution</li>
            <li><code>command_result</code> - Receive command execution results</li>
            <li><code>audio_response</code> - Receive audio response (if available)</li>
        </ul>
    </div>
    
    {% if not is_ssl_enabled %}
    <div class="security-warning">
        <strong>⚠️ Security Warning:</strong> The server is running without SSL/TLS. WebSocket connections are not encrypted.
        <br>For production use, enable SSL by starting the server with: <br>
        <code>python -m llm_control.cli_server --ssl --ssl-cert your-cert.pem --ssl-key your-key.pem</code>
    </div>
    {% endif %}
</body>
</html>
"""

# Near the top of the file, where other global variables are defined
# Add these global variables for REST API
WHISPER_AVAILABLE = False
TRANSLATION_AVAILABLE = False

# After imports, check for Whisper and translation capabilities
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    logging.warning("Whisper not installed. Voice recognition will not be available.")

try:
    import requests  # For translation API calls
    TRANSLATION_AVAILABLE = True
except ImportError:
    logging.warning("Requests not installed. Translation capabilities will be limited.")

def get_whisper_model():
    """
    Get or load the Whisper model for speech recognition.
    
    Returns:
        The loaded Whisper model, or None if Whisper is not available
    """
    try:
        # First check if whisper is installed
        import whisper
        
        # Get the model size from environment variable
        model_size = os.environ.get("WHISPER_MODEL_SIZE", "base")
        logger.info(f"Loading Whisper model: {model_size}")
        
        # Load and return the model
        model = whisper.load_model(model_size)
        logger.info(f"Whisper model loaded successfully")
        return model
    except ImportError:
        logger.warning("Whisper not installed. Voice recognition will not be available.")
        return None
    except Exception as e:
        logger.error(f"Error loading Whisper model: {str(e)}")
        return None

def load_whisper_model(model_size: str = "base"):
    """
    Set up and load the Whisper model with the specified size.
    
    Args:
        model_size: Size of the Whisper model to use (tiny, base, small, medium, large)
        
    Returns:
        The loaded Whisper model, or None if Whisper is not available
    """
    # Set the model size in environment variable
    os.environ["WHISPER_MODEL_SIZE"] = model_size
    
    # Get or load the model
    return get_whisper_model()

def transcribe_audio(audio_file_path: str, model_size: str = "base") -> Dict[str, Any]:
    """
    Transcribe an audio file using Whisper.
    
    Args:
        audio_file_path: Path to the audio file
        model_size: Size of the Whisper model to use
    
    Returns:
        Dictionary containing the transcription and metadata
    """
    # Set the model size in environment variable
    os.environ["WHISPER_MODEL_SIZE"] = model_size
    
    # Try to get the model
    model = get_whisper_model()
    
    if model is None:
        logger.error("Cannot transcribe audio: Whisper model is not available")
        return {
            "error": "Whisper model is not available. Please install the whisper package.",
            "text": "",
            "language": None
        }
    
    logger.info(f"Transcribing audio file: {audio_file_path}")
    
    try:
        result = model.transcribe(audio_file_path)
        logger.info(f"Transcription complete: '{result['text']}'")
        return result
    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        return {
            "error": f"Transcription failed: {str(e)}",
            "text": "",
            "language": None
        }

def translate_with_ollama(text: str, model: str = "llama3.1", ollama_host: str = "http://localhost:11434") -> Optional[str]:
    """
    Translate text from any language to English using Ollama
    
    Args:
        text: Text to translate
        model: Ollama model to use
        ollama_host: Ollama API host
        
    Returns:
        Translated text or None if translation failed
    """
    logger.info(f"Translating with Ollama ({model}): '{text}'")
    
    try:
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
            logger.error(f"Error from Ollama API: {response.status_code}")
            logger.error(response.text)
            return None
        
        # Parse response
        result = response.json()
        translated_text = result["response"].strip()
        
        logger.info(f"Original: {text}")
        logger.info(f"Translated to English: {translated_text}")
        
        return translated_text
    
    except Exception as e:
        logger.error(f"Error translating with Ollama: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def generate_text_to_speech(text: str, language: str = "en") -> Optional[bytes]:
    """
    Convert text to speech (placeholder for actual TTS implementation)
    
    Args:
        text: Text to convert to speech
        language: Language code (en, es, etc.)
        
    Returns:
        Audio bytes or None if generation failed
    """
    # This is a placeholder. In a real implementation, you would:
    # 1. Use a TTS service (e.g., gTTS, Mozilla TTS, etc.)
    # 2. Generate audio from the text
    # 3. Return the audio bytes
    
    logger.info(f"TTS requested for: '{text}' (lang: {language})")
    logger.warning("TTS functionality is not implemented. Returning empty audio.")
    
    # Return a short empty OGG file (with valid header)
    # This is just a minimal OGG header that players will recognize
    # In production, replace with actual TTS implementation
    ogg_header = bytes.fromhex("4F67675300020000000000000000")
    return ogg_header + b"\x00" * 100

def check_ssl_certificate(cert_path: str) -> Dict[str, Any]:
    """
    Check SSL certificate details and expiration
    
    Args:
        cert_path: Path to the SSL certificate
        
    Returns:
        Dict containing certificate details
    """
    try:
        import datetime
        import cryptography.x509
        from cryptography.hazmat.backends import default_backend
        
        with open(cert_path, 'rb') as f:
            cert_data = f.read()
            cert = cryptography.x509.load_pem_x509_certificate(cert_data, default_backend())
            
        expiry = cert.not_valid_after
        now = datetime.datetime.now()
        days_remaining = (expiry - now).days
        
        return {
            "issued_to": cert.subject.rfc4514_string(),
            "issued_by": cert.issuer.rfc4514_string(),
            "expiry": expiry.strftime("%Y-%m-%d"),
            "days_remaining": days_remaining,
            "is_valid": days_remaining > 0,
            "is_self_signed": cert.issuer == cert.subject
        }
    except Exception as e:
        logger.warning(f"Failed to parse SSL certificate: {str(e)}")
        return {
            "error": str(e),
            "is_valid": False
        }

def setup_server(translation_enabled=False, ollama_model="llama3.1", ollama_host="http://localhost:11434", 
                 ssl_context=None, ssl_cert_path=None):
    """Set up the server and ensure dependencies are installed"""
    import datetime
    
    global _translation_enabled, _ollama_model, _ollama_host, _server_start_time, _is_ssl_enabled, _ssl_cert_path, _ssl_cert_expiry
    
    logger.info("Setting up server...")
    _server_start_time = datetime.datetime.now()
    
    # Set translation settings
    _translation_enabled = translation_enabled
    _ollama_model = ollama_model
    _ollama_host = ollama_host
    
    # Set SSL settings
    _is_ssl_enabled = ssl_context is not None
    _ssl_cert_path = ssl_cert_path
    
    if _is_ssl_enabled and ssl_cert_path:
        cert_info = check_ssl_certificate(ssl_cert_path)
        if cert_info.get("is_valid", False):
            logger.info(f"SSL certificate valid until {cert_info.get('expiry')} ({cert_info.get('days_remaining')} days remaining)")
            if cert_info.get("is_self_signed", False):
                logger.warning("Certificate is self-signed, which may cause issues with some clients")
        else:
            logger.warning(f"SSL certificate validation failed: {cert_info.get('error', 'Unknown error')}")
    
    # Check for required packages
    check_and_install_package("flask")
    check_and_install_package("flask-socketio", "pip install -U flask-socketio")
    check_and_install_package("openai-whisper", "pip install -U openai-whisper")
    
    if translation_enabled:
        check_and_install_package("requests")
        # Check if Ollama is available
        try:
            response = requests.get(f"{ollama_host}/api/tags", timeout=2)
            if response.status_code == 200:
                logger.info(f"Ollama server found at {ollama_host}")
                # Check if model is available
                models = response.json().get("models", [])
                if any(model["name"] == ollama_model for model in models):
                    logger.info(f"Ollama model '{ollama_model}' found")
                else:
                    logger.warning(f"Ollama model '{ollama_model}' not found. Attempting to pull it...")
                    # Try to pull the model
                    try:
                        pull_response = requests.post(
                            f"{ollama_host}/api/pull",
                            json={"name": ollama_model},
                            timeout=5  # Just to start the pull, it will continue in background
                        )
                        if pull_response.status_code == 200:
                            logger.info(f"Started pulling model '{ollama_model}'")
                        else:
                            logger.error(f"Failed to pull model '{ollama_model}'")
                    except Exception as e:
                        logger.error(f"Error pulling model: {str(e)}")
            else:
                logger.warning(f"Ollama server not responding properly at {ollama_host}")
        except requests.exceptions.RequestException:
            logger.warning(f"Ollama server not available at {ollama_host}")
            logger.warning("Translation functionality will be limited")
    
    logger.info("Server setup complete")

def process_audio_command(audio_data: bytes, model_size: str = "base") -> Dict[str, Any]:
    """
    Process audio command: transcribe, translate if needed, execute command
    
    Args:
        audio_data: Raw audio data (bytes)
        model_size: Whisper model size
    
    Returns:
        Dictionary with results (transcription, command result)
    """
    global _successful_commands, _failed_commands
    
    try:
        # Save audio data to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
            temp_path = temp_file.name
            temp_file.write(audio_data)
        
        # Process the audio
        try:
            # Transcribe
            result = transcribe_audio(temp_path, model_size)
            command = result["text"].strip()
            original_command = command
            
            if not command:
                _failed_commands += 1
                return {
                    "status": "error",
                    "error": "No speech detected in audio",
                    "original_audio": audio_data
                }
            
            # Translate if needed
            translated = False
            if _translation_enabled and result.get("language") != "en":
                logger.info(f"Detected non-English text (language: {result.get('language')}), translating: '{command}'")
                translated_text = translate_with_ollama(
                    command,
                    model=_ollama_model,
                    ollama_host=_ollama_host
                )
                
                if translated_text:
                    logger.info(f"Translation successful: '{translated_text}'")
                    command = translated_text
                    translated = True
                else:
                    logger.warning(f"Translation failed, using original text: '{command}'")
            
            # Execute the command
            logger.info(f"Executing voice command: {command}")
            command_result = run_command(command)
            
            # Prepare the response
            response_data = {
                "status": "success",
                "transcription": original_command,
                "language": result.get("language", "unknown"),
                "steps": len(command_result),
                "result": "Command executed successfully"
            }
            
            # Add translation info if applicable
            if translated:
                response_data["translated"] = True
                response_data["translation"] = command
            
            # Generate mock TTS response (in real implementation, you would generate audio from command result)
            response_audio = generate_text_to_speech(
                f"Command received: {original_command}. Executed {len(command_result)} steps successfully.",
                language=result.get("language", "en")
            )
            
            if response_audio:
                response_data["audio_response"] = response_audio
            
            _successful_commands += 1
            return response_data
            
        except Exception as e:
            _failed_commands += 1
            logger.error(f"Error processing audio: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "status": "error",
                "error": f"Error processing audio: {str(e)}",
                "transcription": "",
                "original_audio": audio_data
            }
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    except Exception as e:
        _failed_commands += 1
        logger.error(f"Error handling audio data: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "error": f"Error handling audio data: {str(e)}"
        }

# Root route for status page
@app.route('/')
def index():
    global _server_start_time, _active_connections, _total_connections
    global _successful_commands, _failed_commands, _is_ssl_enabled
    
    # Calculate server uptime
    import datetime
    if _server_start_time:
        uptime = datetime.datetime.now() - _server_start_time
        uptime_str = str(uptime).split('.')[0]  # Remove microseconds
    else:
        uptime_str = "Unknown"
    
    # Get Whisper model information
    model = get_whisper_model()
    model_size = model.model.name if hasattr(model, 'model') else "Unknown"
    
    # Get SSL certificate information
    ssl_info = "Not enabled"
    if _is_ssl_enabled:
        ssl_info = f"Enabled"
        if _ssl_cert_path and _ssl_cert_expiry:
            ssl_info += f" (Certificate expires: {_ssl_cert_expiry})"
    
    # Get translation information
    translation_info = "Not enabled"
    if _translation_enabled:
        translation_info = f"Enabled (Model: {_ollama_model})"
    
    return render_template_string(
        STATUS_PAGE_TEMPLATE,
        uptime=uptime_str,
        whisper_model=model_size,
        connections={
            "active": _active_connections,
            "total": _total_connections
        },
        commands={
            "successful": _successful_commands,
            "failed": _failed_commands
        },
        ssl_enabled=_is_ssl_enabled,
        ssl_info=ssl_info,
        translation_enabled=_translation_enabled,
        translation_info=translation_info
    )

# Android compatibility endpoint for WebSocket discovery
@app.route('/ws', defaults={'path': ''})
@app.route('/ws/<path:path>')
def android_wss_discovery(path):
    """
    Endpoint for Android app to discover WebSocket connection details
    
    This returns HTML with connection details that can be parsed by the Android app
    or displayed to the user for manual configuration.
    """
    global _is_ssl_enabled, _translation_enabled, _ollama_model, _android_wss_path
    
    # Get the protocol based on SSL status
    protocol = "wss" if _is_ssl_enabled else "ws"
    
    # Get the host from the request
    host = request.host
    
    # Build the WebSocket URL
    websocket_url = f"{protocol}://{host}{_android_wss_path}"
    
    # SSL status
    ssl_status = "Enabled" if _is_ssl_enabled else "Disabled"
    
    # Translation status
    translation_status = f"Enabled (Model: {_ollama_model})" if _translation_enabled else "Disabled"
    
    # Add a header to help Android clients identify this response
    response = make_response(render_template_string(
        DISCOVERY_TEMPLATE,
        websocket_url=websocket_url,
        protocol=protocol,
        ssl_status=ssl_status,
        translation_status=translation_status
    ))
    response.headers['X-LLM-PC-Control-Discovery'] = 'true'
    response.headers['X-WebSocket-URL'] = websocket_url
    response.headers['X-SSL-Enabled'] = str(_is_ssl_enabled).lower()
    
    return response

# Health check endpoint
@app.route('/health')
def health():
    return jsonify({"status": "ok"})

# Regular HTTP routes (same as before)
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "websocket": True,
        "active_connections": _active_connections
    })

@app.route('/transcribe', methods=['POST'])
def transcribe_endpoint():
    """
    Endpoint to transcribe an audio file.
    
    Expected form data:
    - audio_file: The audio file to transcribe
    - model_size: (Optional) Size of the Whisper model to use
    
    Returns:
        JSON response with the transcription
    """
    if 'audio_file' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files['audio_file']
    model_size = request.form.get('model_size', 'base')
    
    # Create a temporary file for the audio
    with tempfile.NamedTemporaryFile(suffix=f".{audio_file.filename.split('.')[-1]}", delete=False) as temp_file:
        temp_path = temp_file.name
        audio_file.save(temp_path)
    
    try:
        # Get the file size for logging
        file_size = os.path.getsize(temp_path)
        logger.info(f"Received audio file of size {file_size} bytes for transcription")
        
        # Transcribe the audio
        result = transcribe_audio(temp_path, model_size)
        
        # Handle error from transcription
        if "error" in result and result["error"]:
            return jsonify({"error": result["error"]}), 500
            
        # Extract the transcription text
        transcription = result.get("text", "").strip()
        
        # Check if transcription is empty
        if not transcription:
            return jsonify({
                "error": "Empty transcription detected. No speech could be recognized in the audio.",
                "possible_causes": [
                    "The audio file is silent or too quiet",
                    "The audio format is not supported",
                    "The speech is unclear or contains too much background noise",
                    "The language may not be recognized by the current model"
                ],
                "suggestions": [
                    "Check your microphone settings",
                    "Speak clearly and closer to the microphone",
                    "Try a different audio format (WAV or MP3)",
                    "Try using a larger Whisper model size"
                ]
            }), 422  # 422 Unprocessable Entity
        
        return jsonify({
            "transcription": transcription,
            "language": result.get("language", "unknown"),
            "segments": result.get("segments", [])
        })
    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        return jsonify({"error": f"Transcription failed: {str(e)}"}), 500
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.route('/command', methods=['POST'])
def command_endpoint():
    """
    Endpoint to execute a command.
    
    Expected JSON body:
    - command: The command to execute
    - translate: (Optional) Whether to translate to English (default: True)
    
    Returns:
        JSON response with the result of the command
    """
    data = request.json
    
    if not data or 'command' not in data:
        return jsonify({"error": "No command provided"}), 400
    
    command = data['command']
    
    # Check if translation is requested or enabled globally
    # Default is True unless explicitly disabled
    translate = data.get('translate', True)
    
    # Translate if needed
    if translate and result.get("language") != "en":
        logger.info(f"Detected non-English text (language: {result.get('language')}), translating: '{command}'")
        translated_text = translate_with_ollama(
            command,
            model=_ollama_model,
            ollama_host=_ollama_host
        )
        
        if translated_text:
            logger.info(f"Translation successful: '{translated_text}'")
            command = translated_text
        else:
            logger.warning(f"Translation failed, using original text: '{command}'")
    
    try:
        # Execute the command
        logger.info(f"Executing command from API: {command}")
        result = run_command(command)
        
        return jsonify({
            "status": "success",
            "command": command,
            "steps": len(result),
            "result": "Command executed successfully"
        })
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        return jsonify({"error": f"Command execution failed: {str(e)}"}), 500

@app.route('/voice-command', methods=['POST'])
def voice_command_endpoint():
    """
    Process a voice command from an audio file
    
    Expects:
        - 'audio_file': the audio file in the request data
        - 'model_size': (optional) Whisper model size to use (default: base)
        - 'translate': (optional) Whether to enable translation (default: true)
    
    Returns:
        A JSON object with the transcription and command execution result
    """
    try:
        # Check if the request contains a file
        if 'audio_file' not in request.files:
            return jsonify({"error": "No audio file provided"}), 400
        
        # Get parameters
        audio_file = request.files['audio_file']
        model_size = request.form.get('model_size', 'base')
        translate = request.form.get('translate', 'true').lower() != 'false'
        
        # Save the audio to a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.ogg')
        temp_path = temp_file.name
        audio_file.save(temp_path)
        
        # Get the file size for logging
        file_size = os.path.getsize(temp_path)
        logger.info(f"Received audio file of size {file_size} bytes")
        
        # Transcribe the audio
        result = transcribe_audio(temp_path, model_size)
        
        if "error" in result and result["error"]:
            return jsonify({"error": result["error"]}), 500
            
        # Extract the text from the result
        original_command = result.get('text', '')
        
        # Check if transcription is empty
        if not original_command or original_command.strip() == '':
            return jsonify({
                "error": "Empty transcription detected. No speech could be recognized in the audio.",
                "possible_causes": [
                    "The audio file is silent or too quiet",
                    "The audio format is not supported",
                    "The speech is unclear or contains too much background noise",
                    "The language may not be recognized by the current model"
                ],
                "suggestions": [
                    "Check your microphone settings",
                    "Speak clearly and closer to the microphone",
                    "Try a different audio format (WAV or MP3)",
                    "Try using a larger Whisper model size"
                ]
            }), 422  # 422 Unprocessable Entity
        
        # Use the original command as the command to execute
        command = original_command
        
        # Translate if needed
        translated = False
        if translate and result.get("language") != "en":
            logger.info(f"Detected non-English text (language: {result.get('language')}), translating: '{command}'")
            translated_text = translate_with_ollama(
                command,
                model=_ollama_model,
                ollama_host=_ollama_host
            )
            
            if translated_text:
                logger.info(f"Translation successful: '{translated_text}'")
                command = translated_text
                translated = True
            else:
                logger.warning(f"Translation failed, using original text: '{command}'")
        
        # Execute the command
        logger.info(f"Executing voice command: {command}")
        command_result = run_command(command)
        
        response_data = {
            "status": "success",
            "transcription": original_command,
            "language": result.get("language", "unknown"),
            "steps": len(command_result),
            "result": "Command executed successfully"
        }
        
        # Add translation info if applicable
        if translated:
            response_data["translated"] = True
            response_data["translation"] = command
        
        # Generate audio response (in production implementation)
        audio_response = generate_text_to_speech(
            f"Command received: {original_command}. Executed {len(command_result)} steps successfully.", 
            language=result.get("language", "en")
        )
        
        if audio_response:
            # In a real implementation, we would send this as an audio file
            # Here we'll just acknowledge it's available
            response_data["audio_response_available"] = True
        
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error processing voice command: {str(e)}")
        return jsonify({"error": f"Voice command processing failed: {str(e)}"}), 500
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)

def register_android_websocket(app, path):
    """
    Register Android WebSocket endpoints at the specified path
    
    Args:
        app: Flask application
        path: Base path for WebSocket endpoints
    """
    logger.info(f"Registering Android WebSocket endpoints at {path}")
    
    # This is a placeholder for WebSocket endpoints
    # In REST API mode, these endpoints are not used
    # but defining the function prevents errors
    pass

def run_server(
    host: str = "0.0.0.0", 
    port: int = 5000, 
    debug: bool = False,
    translation_enabled: bool = True,
    ollama_model: str = "llama3.1",
    ollama_host: str = "http://localhost:11434",
    ssl_context: Optional[Union[ssl.SSLContext, tuple, str, bool]] = None,
    android_compat: bool = False,
    android_wss_path: str = "/ws",  # Kept for backward compatibility
    use_rest_api: bool = False
):
    """
    Run the LLM PC Control server
    
    Args:
        host: Host address to bind the server to
        port: Port to bind the server to
        debug: Whether to run in debug mode
        translation_enabled: Whether to enable translation (default: True)
        ollama_model: Ollama model to use for translation
        ollama_host: Ollama host URL
        ssl_context: SSL context to use for HTTPS
        android_compat: Whether to enable compatibility mode for Android clients
        android_wss_path: Legacy parameter, kept for backward compatibility
        use_rest_api: Whether to use REST API instead of WebSockets
    """
    global _translation_enabled, _ollama_model, _ollama_host, _server_start_time, _is_ssl_enabled
    
    # Update global configuration
    _translation_enabled = translation_enabled
    _ollama_model = ollama_model
    _ollama_host = ollama_host
    _server_start_time = datetime.now()
    _is_ssl_enabled = ssl_context is not None
    
    # Register REST API endpoints
    @app.route('/api/info', methods=['GET'])
    def api_info():
        """API information endpoint for clients to discover capabilities"""
        host_url = request.host_url.rstrip('/')
        
        # Detect if SSL is being used
        is_secure = request.is_secure
        
        # Build the base URL
        base_url = f"{'https' if is_secure else 'http'}://{request.host}"
        
        whisper_available = False
        try:
            import whisper
            whisper_available = True
        except ImportError:
            pass
        
        # Create capability information
        info = {
            "server": {
                "name": "LLM PC Control Server",
                "version": "1.0.0",
                "api_version": "1",
                "timestamp": datetime.now().isoformat(),
                "uptime": str(datetime.now() - _server_start_time)
            },
            "capabilities": {
                "transcription": whisper_available,
                "translation": _translation_enabled and TRANSLATION_AVAILABLE,
                "voice_commands": whisper_available,
                "text_commands": True
            },
            "endpoints": {
                "health": f"{base_url}/health",
                "transcribe": f"{base_url}/transcribe",
                "command": f"{base_url}/command",
                "voice_command": f"{base_url}/voice-command",
                "system_info": f"{base_url}/api/system-info"
            },
            "settings": {
                "ssl_enabled": _is_ssl_enabled,
                "translation_enabled": _translation_enabled,
                "ollama_model": _ollama_model if _translation_enabled else None
            }
        }
        
        return jsonify(info)
    
    @app.route('/api/system-info', methods=['GET'])
    def system_info():
        """System information endpoint"""
        import platform
        
        try:
            # Basic system info
            system_data = {
                "platform": {
                    "system": platform.system(),
                    "release": platform.release(),
                    "version": platform.version(),
                    "machine": platform.machine()
                },
                "server": {
                    "uptime": str(datetime.now() - _server_start_time),
                    "started": _server_start_time.isoformat()
                }
            }
                
            # Try to get additional system info if psutil is available
            try:
                import psutil
                cpu_percent = psutil.cpu_percent(interval=0.5)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                system_data.update({
                    "cpu": {
                        "percent": cpu_percent,
                        "cores": psutil.cpu_count(logical=False),
                        "threads": psutil.cpu_count(logical=True)
                    },
                    "memory": {
                        "total": memory.total,
                        "available": memory.available,
                        "percent": memory.percent
                    },
                    "disk": {
                        "total": disk.total,
                        "free": disk.free,
                        "percent": disk.percent
                    }
                })
            except ImportError:
                # psutil not available
                pass
                
            return jsonify(system_data)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # Log server configuration
    logger.info(f"Starting server on {host}:{port} with debug={debug}")
    if _is_ssl_enabled:
        logger.info("SSL/TLS is enabled - HTTPS connections are secure")
    else:
        logger.warning("SSL/TLS is not enabled - HTTP connections are not secure")
    
    # Run server based on available modules and config
    if SOCKETIO_AVAILABLE and android_compat and not use_rest_api:
        # Try to run with SocketIO only if not using REST API
        try:
            # Set up SocketIO
            from flask_socketio import SocketIO
            socketio = SocketIO(app, cors_allowed_origins="*")
            
            # Add WebSocket support for Android clients
            if android_wss_path:
                register_android_websocket(app, android_wss_path)
            
            # Run with SocketIO
            socketio.run(app, host=host, port=port, debug=debug, ssl_context=ssl_context)
            return
        except Exception as e:
            logger.warning(f"Failed to run with SocketIO: {e}")
            logger.warning("Falling back to standard Flask server")
    
    # Fallback to standard Flask server (or primary choice for REST API mode)
    try:
        app.run(host=host, port=port, debug=debug, ssl_context=ssl_context)
    except Exception as e:
        logger.error(f"Failed to run server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_server(debug=True) 