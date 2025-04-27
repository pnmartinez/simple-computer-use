#!/usr/bin/env python3
"""
WebRTC screen streaming server module.

This module provides a command-line interface to start the WebRTC screen
streaming server for sending desktop video to Android clients.
"""

import os
import sys
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("webrtc-server")

def main():
    """Run the WebRTC screen streaming server."""
    # Import WebRTC server module
    try:
        from llm_control.webrtc.server import run_server
    except ImportError as e:
        logger.error(f"Failed to import WebRTC server module: {e}")
        logger.error("Make sure all dependencies are installed with: pip install -e .")
        sys.exit(1)
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="WebRTC Screen Streaming Server")
    
    parser.add_argument("--host", type=str, default="0.0.0.0",
                        help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080,
                        help="Port to bind to (default: 8080)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug mode")
    parser.add_argument("--ssl-cert", type=str,
                        help="Path to SSL certificate file")
    parser.add_argument("--ssl-key", type=str,
                        help="Path to SSL private key file")
    parser.add_argument("--fps", type=int, default=30,
                        help="Target frames per second (default: 30)")
    parser.add_argument("--width", type=int, default=1280,
                        help="Video width (default: 1280)")
    parser.add_argument("--height", type=int, default=720,
                        help="Video height (default: 720)")
    parser.add_argument("--monitor", type=int, default=None,
                        help="Monitor number to capture (default: entire screen)")
    
    args = parser.parse_args()
    
    # Set environment variables for screen capture settings
    os.environ["SCREEN_FPS"] = str(args.fps)
    os.environ["SCREEN_WIDTH"] = str(args.width)
    os.environ["SCREEN_HEIGHT"] = str(args.height)
    if args.monitor is not None:
        os.environ["SCREEN_MONITOR"] = str(args.monitor)
    
    # Run the server
    try:
        run_server(
            host=args.host,
            port=args.port,
            debug=args.debug,
            ssl_certfile=args.ssl_cert,
            ssl_keyfile=args.ssl_key,
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main() 