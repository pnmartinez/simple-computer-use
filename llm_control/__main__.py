"""
LLM Control Command Line Interface.

This module provides the command-line interface for the llm-control package.
Allows running different components and tools from the command line.
"""

import sys
import os
import argparse
import logging
from typing import Any, Dict, List, Optional, Tuple

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("llm-control")


def main():
    """Parse arguments and run the appropriate subcommand."""
    parser = argparse.ArgumentParser(
        description="LLM Control - Control your computer using natural language",
        prog="llm-control",
    )
    
    # Add global arguments
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    # Add subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")
    
    # Voice server command
    voice_parser = subparsers.add_parser("voice-server", help="Run the voice control server")
    voice_parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    voice_parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    voice_parser.add_argument("--ssl", action="store_true", help="Enable SSL with self-signed cert")
    voice_parser.add_argument("--ssl-cert", type=str, help="Path to SSL certificate")
    voice_parser.add_argument("--ssl-key", type=str, help="Path to SSL key")
    voice_parser.add_argument("--whisper-model", type=str, default="medium", 
                             choices=["tiny", "base", "small", "medium", "large"],
                             help="Whisper model to use")
    voice_parser.add_argument("--ollama-model", type=str, default="gemma3:12b",
                             help="Ollama model to use")
    voice_parser.add_argument("--ollama-host", type=str, default="http://localhost:11434",
                             help="Ollama host URL")
    voice_parser.add_argument("--disable-screenshots", action="store_true",
                             help="Disable screenshot capture")
    
    # WebRTC server command
    webrtc_parser = subparsers.add_parser("webrtc-server", help="Run the WebRTC screen streaming server")
    webrtc_parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    webrtc_parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    webrtc_parser.add_argument("--ssl-cert", type=str, help="Path to SSL certificate")
    webrtc_parser.add_argument("--ssl-key", type=str, help="Path to SSL key")
    webrtc_parser.add_argument("--fps", type=int, default=30, 
                              help="Target frames per second (default: 30)")
    webrtc_parser.add_argument("--width", type=int, default=1280,
                              help="Video width (default: 1280)")
    webrtc_parser.add_argument("--height", type=int, default=720,
                              help="Video height (default: 720)")
    webrtc_parser.add_argument("--monitor", type=int, 
                              help="Monitor number to capture (default: entire screen)")
    
    # Screenshot command
    screenshot_parser = subparsers.add_parser("screenshot", help="Capture a screenshot")
    screenshot_parser.add_argument("--output", "-o", type=str, help="Output file path")
    screenshot_parser.add_argument("--full", action="store_true", help="Capture full screen (default)")
    screenshot_parser.add_argument("--region", type=str, help="Region to capture (x,y,width,height)")
    
    # Voice command
    voice_cmd_parser = subparsers.add_parser("voice-cmd", help="Execute a voice command")
    voice_cmd_parser.add_argument("--file", "-f", type=str, help="Audio file path")
    voice_cmd_parser.add_argument("--device", "-d", type=int, default=None, 
                                 help="Audio device index to use for recording")
    voice_cmd_parser.add_argument("--language", "-l", type=str, default="es",
                                 help="Language of the voice command")
    voice_cmd_parser.add_argument("--model", "-m", type=str, default="medium",
                                 choices=["tiny", "base", "small", "medium", "large"],
                                 help="Whisper model to use")
    
    # Simple command
    simple_cmd_parser = subparsers.add_parser("simple-cmd", help="Execute a simple text command")
    simple_cmd_parser.add_argument("--command", "-c", type=str, required=True,
                                  help="Command text to execute")
    simple_cmd_parser.add_argument("--screenshot", "-s", action="store_true",
                                  help="Capture a screenshot before executing")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Handle --version
    if args.version:
        from llm_control import __version__
        print(f"llm-control version {__version__}")
        sys.exit(0)
    
    # Configure debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Handle no command
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Handle voice-server command
    elif args.command == "voice-server":
        try:
            from llm_control.voice.server import run_server
            
            # Set environment variables from args
            if args.whisper_model:
                os.environ["WHISPER_MODEL_SIZE"] = args.whisper_model
                logger.info(f"Setting WHISPER_MODEL_SIZE={args.whisper_model}")
                
            if args.ollama_model:
                os.environ["OLLAMA_MODEL"] = args.ollama_model
                logger.info(f"Setting OLLAMA_MODEL={args.ollama_model}")
                
            if args.ollama_host:
                os.environ["OLLAMA_HOST"] = args.ollama_host
                logger.info(f"Setting OLLAMA_HOST={args.ollama_host}")
                
            if args.disable_screenshots:
                os.environ["CAPTURE_SCREENSHOTS"] = "false"
            
            # Determine SSL config
            ssl_context = None
            if args.ssl_cert and args.ssl_key:
                ssl_context = (args.ssl_cert, args.ssl_key)
            elif args.ssl:
                ssl_context = "adhoc"
            
            logger.info(f"Starting voice control server on {args.host}:{args.port}")
            run_server(host=args.host, port=args.port, 
                      debug=args.debug, ssl_context=ssl_context,
                      ollama_model=args.ollama_model)
            
        except ImportError as e:
            logger.error(f"Failed to import voice server: {e}")
            logger.error("Make sure all dependencies are installed.")
            sys.exit(1)
    
    # Handle webrtc-server command
    elif args.command == "webrtc-server":
        try:
            # Check if WebRTC dependencies are installed
            try:
                from llm_control import HAS_WEBRTC
                if not HAS_WEBRTC:
                    logger.error("WebRTC dependencies not installed.")
                    logger.error("Install them with: pip install aiortc mss fastapi uvicorn websockets")
                    sys.exit(1)
                    
                from llm_control.webrtc.server import run_server
            except ImportError as e:
                logger.error(f"Failed to import WebRTC server: {e}")
                logger.error("Make sure WebRTC dependencies are installed.")
                sys.exit(1)
            
            # Set environment variables for screen capture settings
            os.environ["SCREEN_FPS"] = str(args.fps)
            os.environ["SCREEN_WIDTH"] = str(args.width)
            os.environ["SCREEN_HEIGHT"] = str(args.height)
            if args.monitor is not None:
                os.environ["SCREEN_MONITOR"] = str(args.monitor)
            
            logger.info(f"Starting WebRTC screen streaming server on {args.host}:{args.port}")
            run_server(host=args.host, port=args.port, debug=args.debug,
                      ssl_certfile=args.ssl_cert, ssl_keyfile=args.ssl_key)
            
        except Exception as e:
            logger.error(f"Error running WebRTC server: {e}")
            import traceback
            logger.error(traceback.format_exc())
            sys.exit(1)
    
    # Handle screenshot command
    elif args.command == "screenshot":
        try:
            from llm_control.voice.screenshots import capture_screenshot
            
            logger.info("Capturing screenshot...")
            filename, filepath, success = capture_screenshot()
            
            if success:
                logger.info(f"Screenshot saved to {filepath}")
            else:
                logger.error("Failed to capture screenshot")
                sys.exit(1)
                
        except ImportError as e:
            logger.error(f"Failed to import screenshot module: {e}")
            sys.exit(1)
    
    # Handle voice-cmd command
    elif args.command == "voice-cmd":
        # Implementation of voice command handling
        logger.error("Voice command execution not yet implemented")
        sys.exit(1)
    
    # Handle simple-cmd command
    elif args.command == "simple-cmd":
        try:
            from llm_control.voice.commands import execute_command_with_logging
            
            if args.screenshot:
                from llm_control.voice.screenshots import capture_screenshot
                logger.info("Capturing screenshot before command execution...")
                capture_screenshot()
            
            logger.info(f"Executing command: {args.command}")
            result = execute_command_with_logging(args.command)
            
            if result.get("success", False):
                logger.info("Command executed successfully")
            else:
                logger.error("Command execution failed")
                logger.error(result.get("error", "Unknown error"))
                sys.exit(1)
                
        except ImportError as e:
            logger.error(f"Failed to import command module: {e}")
            sys.exit(1)
    
    # Handle unknown command
    else:
        logger.error(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1) 