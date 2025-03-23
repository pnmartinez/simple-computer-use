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
import tempfile
from datetime import datetime

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
    # Use environment variable or default to a directory in the user's temp directory
    screenshot_dir = os.environ.get("SCREENSHOT_DIR")
    
    if not screenshot_dir:
        # Use a subdirectory in the system's temp directory
        temp_dir = os.path.join(tempfile.gettempdir(), "llm_control_screenshots")
        screenshot_dir = temp_dir
    
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

def cleanup_old_screenshots(max_age_days=None, max_count=None):
    """
    Delete old screenshots to prevent disk space issues.
    
    Args:
        max_age_days: Maximum age in days for screenshots
        max_count: Maximum number of screenshots to keep
        
    Returns:
        Tuple of (number of deleted files, error message or None)
    """
    # Get values from environment variables if not explicitly provided
    if max_age_days is None:
        max_age_days = int(os.environ.get("SCREENSHOT_MAX_AGE_DAYS", "1"))
    if max_count is None:
        max_count = int(os.environ.get("SCREENSHOT_MAX_COUNT", "10"))
        
    logger.info(f"Cleaning up old screenshots (max_age_days={max_age_days}, max_count={max_count})")
    
    try:
        # Get the screenshot directory
        screenshot_dir = get_screenshot_dir()
        logger.debug(f"Using screenshot directory: {screenshot_dir}")
        
        # List all screenshot files with their timestamps
        screenshots = []
        try:
            for filename in os.listdir(screenshot_dir):
                # Include all relevant screenshot patterns
                if (filename.startswith("screenshot_") or 
                    filename.startswith("temp_") or 
                    filename.startswith("before_") or 
                    filename.startswith("after_")) and filename.endswith(".png"):
                    full_path = os.path.join(screenshot_dir, filename)
                    mtime = os.path.getmtime(full_path)
                    mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                    screenshots.append((full_path, mtime, filename, mtime_str))
            logger.debug(f"Found {len(screenshots)} screenshots in {screenshot_dir}")
        except FileNotFoundError:
            logger.error(f"Screenshot directory not found: {screenshot_dir}")
            return 0, f"Screenshot directory not found: {screenshot_dir}"
        
        # If no screenshots to clean, return early
        if not screenshots:
            logger.info(f"No screenshots found to clean up")
            return 0, None
        
        # Calculate the cutoff time
        now = time.time()
        age_cutoff = now - (max_age_days * 24 * 60 * 60)
        cutoff_str = datetime.fromtimestamp(age_cutoff).strftime('%Y-%m-%d %H:%M:%S')
        logger.debug(f"Age cutoff: {cutoff_str} (older files will be deleted)")
        
        # Sort by modification time (oldest first)
        screenshots.sort(key=lambda x: x[1])
        
        # Log the oldest and newest files for debugging
        if screenshots:
            oldest_file = screenshots[0]
            newest_file = screenshots[-1]
            logger.debug(f"Oldest file: {oldest_file[2]} ({oldest_file[3]})")
            logger.debug(f"Newest file: {newest_file[2]} ({newest_file[3]})")
        
        # Delete files older than max_age_days
        deleted_count = 0
        age_deleted = 0
        for full_path, mtime, filename, mtime_str in screenshots:
            if mtime < age_cutoff:
                try:
                    os.remove(full_path)
                    deleted_count += 1
                    age_deleted += 1
                    logger.info(f"Deleted old screenshot ({mtime_str}): {filename}")
                except OSError as e:
                    logger.warning(f"Failed to delete {full_path}: {str(e)}")
        
        logger.debug(f"Deleted {age_deleted} screenshots older than {max_age_days} days")
        
        # If we still have more than max_count, delete the oldest ones
        remaining = [s for s in screenshots if s[1] >= age_cutoff]
        count_to_delete = len(remaining) - max_count
        
        if count_to_delete > 0:
            logger.debug(f"Still have {len(remaining)} screenshots, need to delete {count_to_delete} to reach max_count={max_count}")
            # We've already sorted by time, so just delete the oldest ones
            for full_path, _, filename, mtime_str in remaining[:count_to_delete]:
                try:
                    os.remove(full_path)
                    deleted_count += 1
                    logger.info(f"Deleted excess screenshot ({mtime_str}): {filename}")
                except OSError as e:
                    logger.warning(f"Failed to delete {full_path}: {str(e)}")
        else:
            logger.info(f"No need to delete files by count: {len(remaining)} screenshots <= max_count={max_count}")
        
        logger.info(f"Cleanup complete. Deleted {deleted_count} screenshots total")
        return deleted_count, None
        
    except Exception as e:
        error_msg = f"Error cleaning up screenshots: {str(e)}"
        logger.error(error_msg)
        import traceback
        logger.error(traceback.format_exc())
        return 0, error_msg
