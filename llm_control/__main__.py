"""
Main entry point for the llm_control package.
This allows running the package as a module via `python -m llm_control`.
"""

import sys
import os
import importlib
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("llm-pc-control")

if __name__ == "__main__":
    # Check if we have a specific command
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        # Remove the command from the arguments so the submodule doesn't see it
        sys.argv.pop(1)
        
        if command == "voice-server":
            # Run the voice control server
            try:
                # Import the module lazily to avoid issues with missing dependencies
                try:
                    # Use the modularized version
                    from llm_control.voice.server import run_server
                    
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
                    if args.ssl:
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
                    elif args.ssl_cert and args.ssl_key:
                        ssl_context = (args.ssl_cert, args.ssl_key)
                        logger.info(f"Using SSL certificate: {args.ssl_cert}")
                        logger.info(f"Using SSL key: {args.ssl_key}")
                    
                    # Run the server
                    run_server(host=args.host, port=args.port, debug=args.debug, ssl_context=ssl_context)
                    
                except ModuleNotFoundError:
                    logger.error("Voice control server module not found")
                    sys.exit(1)
                except ImportError as e:
                    logger.error(f"Error importing voice control server: {e}")
                    sys.exit(1)
                # The module has its own argument parsing and app.run() call
            except Exception as e:
                logger.error(f"Error running voice control server: {e}")
                sys.exit(1)
        
        elif command == "simple-voice":
            # Run the simple voice command script
            simple_voice_path = os.path.join(os.path.dirname(__file__), "..", "simple_voice_command.py")
            if os.path.exists(simple_voice_path):
                # Execute the script directly
                try:
                    import subprocess
                    subprocess.run([sys.executable, simple_voice_path] + sys.argv[1:])
                except Exception as e:
                    logger.error(f"Error running simple voice command: {e}")
                    sys.exit(1)
            else:
                logger.error("Error: simple_voice_command.py not found")
                sys.exit(1)
        
        else:
            print(f"Unknown command: {command}")
            print("Available commands:")
            print("  voice-server - Run the voice control server")
            print("  simple-voice - Run the simple voice command script")
            sys.exit(1)
    else:
        # No command specified, show help
        print("LLM PC Control - Voice Command System")
        print("-------------------------------------")
        print("Usage: python -m llm_control <command> [options]")
        print("\nAvailable commands:")
        print("  voice-server - Run the voice control server")
        print("  simple-voice - Run the simple voice command script")
        print("\nExample:")
        print("  python -m llm_control voice-server --port 8080 --whisper-model medium")
        print("  python -m llm_control simple-voice --command \"click on the Firefox icon\"") 