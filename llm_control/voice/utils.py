"""
Utility functions for the voice control server.

This module contains helper functions used across the voice control server.
"""

import os
import time
import logging
import json
import sys
from typing import Dict, Any, Optional, Tuple
from functools import wraps

# Configure basic logging
logger = logging.getLogger("voice-control-utils")

# Set up debug mode based on environment variable
DEBUG = os.environ.get("DEBUG", "").lower() in ("true", "1", "yes")

def is_debug_mode():
    """
    Check if debug mode is enabled.
    
    Returns:
        bool: True if debug mode is enabled, False otherwise
    """
    return DEBUG

def configure_logging(debug_mode=None):
    """
    Configure logging levels based on debug mode.
    
    Args:
        debug_mode: Override debug mode (if None, uses the global DEBUG setting)
    """
    debug = debug_mode if debug_mode is not None else DEBUG
    
    # Set up root logger
    root_logger = logging.getLogger()
    
    # Set log level based on debug mode
    if debug:
        root_logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    else:
        root_logger.setLevel(logging.INFO)
    
    # Check if we need to add a handler (avoid duplicate handlers)
    if not root_logger.handlers:
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        root_logger.addHandler(console_handler)
        
    logger.debug("Logging configured successfully")

# Call configure_logging to set up logging as soon as this module is imported
configure_logging()

def get_screenshot_dir():
    """Get the directory for storing screenshots."""
    # Use environment variable or default to current directory
    screenshot_dir = os.environ.get("SCREENSHOT_DIR", ".")
    
    # If it's a relative path, make it relative to the current working directory
    if not os.path.isabs(screenshot_dir):
        screenshot_dir = os.path.join(os.getcwd(), screenshot_dir)
    
    # Ensure the directory exists
    os.makedirs(screenshot_dir, exist_ok=True)
    
    return screenshot_dir

def error_response(message, status_code=400):
    """Helper function to create error responses"""
    from flask import jsonify
    
    return jsonify({
        "error": message,
        "status": "error"
    }), status_code

def cors_preflight(f):
    """Decorator to handle CORS preflight requests"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import request, make_response
        
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

def test_cuda_availability():
    """Test CUDA availability and print diagnostic information"""
    logger.info("Testing CUDA availability...")
    try:
        import torch
        logger.info(f"PyTorch version: {torch.__version__}")
        
        if hasattr(torch, 'cuda'):
            is_available = torch.cuda.is_available()
            logger.info(f"CUDA available: {is_available}")
            
            if is_available:
                logger.info(f"CUDA version: {torch.version.cuda}")
                logger.info(f"CUDA device count: {torch.cuda.device_count()}")
                logger.info(f"Current CUDA device: {torch.cuda.current_device()}")
                logger.info(f"CUDA device properties:")
                for i in range(torch.cuda.device_count()):
                    logger.info(f"  Device {i}: {torch.cuda.get_device_properties(i)}")
            else:
                logger.warning("CUDA is not available. Using CPU only.")
                # Check if CUDA initialization failed
                try:
                    import ctypes
                    cuda = ctypes.CDLL("libcuda.so")
                    result = cuda.cuInit(0)
                    logger.info(f"CUDA driver initialization result: {result}")
                except Exception as e:
                    logger.warning(f"Failed to check CUDA driver: {str(e)}")
        else:
            logger.warning("PyTorch was not built with CUDA support")
    except ImportError as e:
        logger.warning(f"Could not import PyTorch: {str(e)}")
    except Exception as e:
        logger.warning(f"Error testing CUDA: {str(e)}")
        import traceback
        logger.warning(traceback.format_exc())
