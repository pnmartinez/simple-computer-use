"""
Simplified voice control server module.

This module provides a lightweight web server for voice command processing,
using a more direct LLM-based approach instead of complex parsing rules.

Note: This is maintained for backward compatibility.
For new code, use the modular imports from llm_control.voice package.
"""

# Import directly from our new modular structure
from llm_control.voice.server import app, run_server

# For direct running
if __name__ == '__main__':
    # Parse command-line arguments
    import argparse
    import os
    import sys
    
    parser = argparse.ArgumentParser(description='Simple voice control server with LLM-based multi-step processing')
    
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
    parser.add_argument('--whisper-model', type=str, default='medium',
                        choices=['tiny', 'base', 'small', 'medium', 'large'],
                        help='Whisper model size (default: medium)')
    parser.add_argument('--ollama-model', type=str, default='llama3.1',
                        help='Ollama model to use (default: llama3.1)')
    parser.add_argument('--ollama-host', type=str, default='http://localhost:11434',
                        help='Ollama API host (default: http://localhost:11434)')
    parser.add_argument('--disable-translation', action='store_true',
                        help='Disable automatic translation of non-English languages')
    parser.add_argument('--language', type=str, default='es',
                        help='Default language for voice recognition (default: es)')
    parser.add_argument('--disable-screenshots', action='store_true',
                        help='Disable capturing screenshots after command execution')
    parser.add_argument('--enable-failsafe', action='store_true',
                        help='Enable PyAutoGUI failsafe (move mouse to upper-left corner to abort)')
    parser.add_argument('--screenshot-dir', type=str, default='.',
                        help='Directory where screenshots will be saved (default: current directory)')
    parser.add_argument('--screenshot-max-age', type=int, default=1,
                        help='Maximum age in days for screenshots before cleanup (default: 1)')
    parser.add_argument('--screenshot-max-count', type=int, default=10,
                        help='Maximum number of screenshots to keep (default: 10)')
    
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
    os.environ["SCREENSHOT_MAX_AGE_DAYS"] = str(args.screenshot_max_age)
    os.environ["SCREENSHOT_MAX_COUNT"] = str(args.screenshot_max_count)
    
    # Configure SSL context
    ssl_context = None
    if args.ssl:
        try:
            # Check if pyopenssl is installed
            import ssl
            from werkzeug.serving import make_ssl_devcert
            
            ssl_context = 'adhoc'
            print("Using self-signed certificate for HTTPS")
        except ImportError:
            print("Error: SSL option requires pyopenssl to be installed")
            print("Install with: pip install pyopenssl")
            sys.exit(1)
    elif args.ssl_cert and args.ssl_key:
        ssl_context = (args.ssl_cert, args.ssl_key)
        print(f"Using SSL certificate: {args.ssl_cert}")
        print(f"Using SSL key: {args.ssl_key}")
    
    # Run the server
    run_server(host=args.host, port=args.port, debug=args.debug, ssl_context=ssl_context) 