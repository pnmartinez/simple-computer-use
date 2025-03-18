#!/usr/bin/env python3
"""
Simple REST API server for LLM PC Control without WebSockets.
This is a lightweight version focused on REST API endpoints only.
"""

import os
import sys
import argparse
import logging
import json
import ssl
import datetime
from flask import Flask, request, jsonify

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Global variables
server_start_time = datetime.datetime.now()

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Simple REST API server for LLM PC Control"
    )
    
    parser.add_argument(
        "--host", 
        type=str, 
        default="0.0.0.0",
        help="Host address to bind the server to (default: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port", 
        type=int, 
        default=5000,
        help="Port to bind the server to (default: 5000)"
    )
    
    parser.add_argument(
        "--ssl", 
        action="store_true",
        help="Enable SSL/TLS for secure connections"
    )
    
    parser.add_argument(
        "--ssl-cert", 
        type=str, 
        help="Path to SSL certificate file (.crt or .pem)"
    )
    
    parser.add_argument(
        "--ssl-key", 
        type=str, 
        help="Path to SSL private key file (.key)"
    )
    
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="Run the server in debug mode"
    )
    
    return parser.parse_args()

# Define API endpoints
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.datetime.now().isoformat()
    })

@app.route('/api/info', methods=['GET'])
def api_info():
    """API information endpoint for clients to discover capabilities"""
    host = request.host.split(':')[0]
    port = int(request.host.split(':')[1]) if ':' in request.host else 80
    
    # Detect if SSL is being used
    is_secure = request.is_secure
    
    # Build the base URL
    base_url = f"{'https' if is_secure else 'http'}://{host}:{port}"
    
    # Create capability information
    info = {
        "server": {
            "name": "Simple REST API Server",
            "version": "1.0.0",
            "api_version": "1",
            "timestamp": datetime.datetime.now().isoformat()
        },
        "capabilities": {
            "transcription": False,
            "translation": False,
            "voice_commands": False,
            "text_commands": True
        },
        "endpoints": {
            "health": f"{base_url}/health",
            "command": f"{base_url}/command",
            "system_info": f"{base_url}/api/system-info"
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
                "uptime": str(datetime.datetime.now() - server_start_time),
                "started": server_start_time.isoformat()
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

@app.route('/command', methods=['POST'])
def execute_command():
    """Execute a command"""
    if not request.json or 'command' not in request.json:
        return jsonify({"error": "No command provided"}), 400
    
    command = request.json['command']
    
    # Simple demo - just echo the command
    return jsonify({
        "status": "success",
        "command": command,
        "result": f"Simulated execution of: {command}"
    })

def main():
    """Main entry point"""
    args = parse_args()
    
    # Set up SSL context if enabled
    ssl_context = None
    if args.ssl:
        if args.ssl_cert and args.ssl_key:
            # Use provided certificate files
            ssl_context = (args.ssl_cert, args.ssl_key)
            logger.info(f"Using SSL certificate: {args.ssl_cert}")
            logger.info(f"Using SSL key: {args.ssl_key}")
        else:
            logger.error("SSL is enabled but certificate or key path is missing")
            logger.error("Please provide both --ssl-cert and --ssl-key arguments")
            sys.exit(1)
    
    # Print server information
    logger.info(f"Starting simple REST API server on {args.host}:{args.port}")
    if ssl_context:
        logger.info("SSL/TLS is enabled - HTTPS connections are secure")
    else:
        logger.info("Running without SSL/TLS - HTTP connections are not secure")
    
    # Run the server
    try:
        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug,
            ssl_context=ssl_context
        )
    except Exception as e:
        logger.error(f"Error running server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 