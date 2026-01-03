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
    from llm_control import is_packaged
    
    # Use environment variable or default to a directory in the user's temp directory
    screenshot_dir = os.environ.get("SCREENSHOT_DIR")
    
    if not screenshot_dir:
        # Use a subdirectory in the system's temp directory
        temp_dir = os.path.join(tempfile.gettempdir(), "llm_control_screenshots")
        screenshot_dir = temp_dir
    else:
            # If it's a relative path, make it relative to the current working directory
        if not os.path.isabs(screenshot_dir):
            # Use is_packaged() for cross-platform detection
            if is_packaged():
                # Running from packaged executable
                # Use user's home directory for screenshots instead of read-only mount
                screenshot_dir = os.path.join(os.path.expanduser("~"), ".llm-control", "screenshots")
            else:
                # Development mode: use relative to current working directory
                cwd = os.getcwd()
                screenshot_dir = os.path.join(cwd, screenshot_dir)
    
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

def get_command_history_file():
    """
    Get the path to the command history CSV file.
    
    Returns:
        str: Path to the command history CSV file
    """
    from llm_control import is_packaged
    
    # Create a directory for storing history data
    history_dir = os.environ.get("HISTORY_DIR")
    
    if not history_dir:
        # Use a persistent directory instead of system temp directory
        history_dir = "history"
    
    # If it's a relative path, make it relative to the current working directory
    if not os.path.isabs(history_dir):
        # Use is_packaged() for cross-platform detection
        if is_packaged():
            # Running from packaged executable
            # Use user's home directory for history instead of read-only mount
            history_dir = os.path.join(os.path.expanduser("~"), ".llm-control", "history")
        else:
            # Development mode: use relative to current working directory
            cwd = os.getcwd()
            history_dir = os.path.join(cwd, history_dir)
    
    # Ensure the directory exists
    os.makedirs(history_dir, exist_ok=True)
    
    # Return the path to the history CSV file
    return os.path.join(history_dir, "command_history.csv")

def add_to_command_history(command_data):
    """
    Add a command execution to the history CSV file.
    
    Args:
        command_data: Dictionary containing command execution data with keys:
            - timestamp: ISO format timestamp
            - command: Original command text
            - steps: List of command steps
            - code: Generated code
            - success: Boolean indicating success status
    
    Returns:
        bool: True if successful, False otherwise
    """
    import csv
    
    try:
        # Get the history file path
        history_file = get_command_history_file()
        file_exists = os.path.exists(history_file)
        
        # Convert steps to a string if they're a list
        steps_str = ""
        if 'steps' in command_data and command_data['steps']:
            if isinstance(command_data['steps'], list):
                steps_str = "; ".join(str(step) for step in command_data['steps'])
            else:
                steps_str = str(command_data['steps'])
        
        # Ensure timestamp exists
        if 'timestamp' not in command_data:
            command_data['timestamp'] = datetime.now().isoformat()
        
        screen_summary = command_data.get('screen_summary', '')
        if isinstance(screen_summary, (dict, list)):
            screen_summary = json.dumps(screen_summary, ensure_ascii=False)

        fieldnames = ['timestamp', 'command', 'steps', 'code', 'success', 'screen_summary']

        if file_exists:
            try:
                with open(history_file, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.reader(csvfile)
                    existing_header = next(reader, [])

                if existing_header and 'screen_summary' not in existing_header:
                    with open(history_file, 'r', newline='', encoding='utf-8') as csvfile:
                        reader = csv.DictReader(csvfile)
                        existing_rows = list(reader)

                    with open(history_file, 'w', newline='', encoding='utf-8') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        for row in existing_rows:
                            row.pop(None, None)
                            row.setdefault('screen_summary', '')
                            writer.writerow(row)
            except Exception as exc:
                logger.warning(f"Failed to migrate command history header: {exc}")

        # Write to CSV file
        with open(history_file, 'a', newline='', encoding='utf-8') as csvfile:
            # Create a CSV writer
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # Write header if the file is new
            if not file_exists:
                writer.writeheader()
            
            # Prepare the row to write
            row = {
                'timestamp': command_data.get('timestamp', ''),
                'command': command_data.get('command', ''),
                'steps': steps_str,
                'code': command_data.get('code', ''),
                'success': str(command_data.get('success', False)).lower(),
                'screen_summary': screen_summary
            }
            
            # Write the row
            writer.writerow(row)
        
        logger.debug(f"Added command to history: {command_data.get('command', '')}")
        return True
        
    except Exception as e:
        logger.error(f"Error adding command to history: {str(e)}")
        return False

def get_command_history(limit=None, date_filter='today'):
    """
    Get the command execution history.
    
    Args:
        limit: Maximum number of history entries to return (default: all)
        date_filter: Filter by date - 'today', 'all', or specific date (YYYY-MM-DD format)
    
    Returns:
        List of dictionaries containing command execution data
    """
    import csv
    from datetime import datetime, timezone
    
    try:
        # Get the history file path
        history_file = get_command_history_file()
        
        # Check if the file exists
        if not os.path.exists(history_file):
            return []
        
        # Determine date filter
        filter_date = None
        if date_filter == 'today':
            filter_date = datetime.now().strftime('%Y-%m-%d')
        elif date_filter != 'all' and date_filter:
            # Assume it's a specific date in YYYY-MM-DD format
            try:
                datetime.strptime(date_filter, '%Y-%m-%d')
                filter_date = date_filter
            except ValueError:
                logger.warning(f"Invalid date filter format: {date_filter}, using 'today' instead")
                filter_date = datetime.now().strftime('%Y-%m-%d')
        
        # Read from CSV file
        history = []
        with open(history_file, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                extra_values = row.pop(None, None)
                if extra_values:
                    screen_summary = row.get('screen_summary') or ''
                    extra_text = ",".join(str(value) for value in extra_values if value is not None)
                    if screen_summary and extra_text:
                        screen_summary = f"{screen_summary},{extra_text}"
                    elif extra_text:
                        screen_summary = extra_text
                    row['screen_summary'] = screen_summary

                if row.get('screen_summary') is None:
                    row['screen_summary'] = ''
                # Apply date filter if specified
                if filter_date:
                    try:
                        # Parse the timestamp and extract date
                        entry_time = datetime.fromisoformat(row['timestamp'])
                        entry_date = entry_time.strftime('%Y-%m-%d')
                        
                        # Skip if not matching the filter date
                        if entry_date != filter_date:
                            continue
                    except (ValueError, KeyError):
                        # If timestamp is malformed, skip the entry when filtering
                        logger.warning(f"Invalid timestamp in history entry, skipping: {row.get('timestamp', 'N/A')}")
                        continue
                
                # Convert success string to boolean
                if 'success' in row:
                    row['success'] = row['success'].lower() == 'true'
                
                # Convert steps string back to list
                if 'steps' in row and row['steps']:
                    row['steps'] = [step.strip() for step in row['steps'].split(';')]
                
                history.append(row)
        
        # Apply limit if specified
        if limit is not None and limit > 0:
            history = history[-limit:]
            
        return history
        
    except Exception as e:
        logger.error(f"Error getting command history: {str(e)}")
        return []

def get_latest_command_summary():
    """
    Get the latest command summary entry for TTS output.

    Returns:
        Dictionary with summary data or None if no history exists.
    """
    history = get_command_history(limit=1, date_filter='all')
    if not history:
        return None

    latest = history[-1]
    return {
        "timestamp": latest.get("timestamp", ""),
        "command": latest.get("command", ""),
        "success": latest.get("success", False),
        "screen_summary": latest.get("screen_summary", "")
    }

def cleanup_old_command_history(max_age_days=None, max_count=None):
    """
    Clean up old command history entries based on age and count limits.
    
    Args:
        max_age_days: Maximum age in days for history entries (defaults to env var HISTORY_MAX_AGE_DAYS or 30)
        max_count: Maximum number of history entries to keep (defaults to env var HISTORY_MAX_COUNT or 1000)
    
    Returns:
        Tuple of (deleted_count, error_message)
    """
    import csv
    from datetime import datetime, timezone
    
    # Get configuration from environment variables if not provided
    if max_age_days is None:
        max_age_days = int(os.environ.get("HISTORY_MAX_AGE_DAYS", "30"))
    
    if max_count is None:
        max_count = int(os.environ.get("HISTORY_MAX_COUNT", "1000"))
    
    # If max_age_days is 0, don't delete by age
    # If max_count is 0, don't limit by count
    
    logger.info(f"Cleaning up old command history (max_age_days={max_age_days}, max_count={max_count})")
    
    try:
        history_file = get_command_history_file()
        
        # Check if history file exists
        if not os.path.exists(history_file):
            logger.debug("No command history file found, nothing to clean up")
            return 0, None
        
        # Read all history entries
        history_entries = []
        with open(history_file, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                history_entries.append(row)
        
        original_count = len(history_entries)
        logger.debug(f"Found {original_count} history entries")
        
        if original_count == 0:
            return 0, None
        
        # Filter by age if max_age_days > 0
        filtered_entries = history_entries
        age_deleted = 0
        
        if max_age_days > 0:
            now = datetime.now(timezone.utc)
            age_cutoff = now.timestamp() - (max_age_days * 24 * 60 * 60)
            
            before_age_filter = len(filtered_entries)
            filtered_entries = []
            
            for entry in history_entries:
                try:
                    # Parse the timestamp
                    entry_time = datetime.fromisoformat(entry['timestamp'])
                    
                    # Convert to timestamp for comparison
                    if entry_time.tzinfo is None:
                        # Assume local timezone if no timezone info
                        entry_time = entry_time.replace(tzinfo=timezone.utc)
                    
                    entry_timestamp = entry_time.timestamp()
                    
                    # Keep if newer than cutoff
                    if entry_timestamp > age_cutoff:
                        filtered_entries.append(entry)
                        
                except (ValueError, KeyError) as e:
                    # If timestamp is malformed, keep the entry to be safe
                    logger.warning(f"Invalid timestamp in history entry, keeping entry: {e}")
                    filtered_entries.append(entry)
            
            age_deleted = before_age_filter - len(filtered_entries)
            logger.debug(f"Deleted {age_deleted} history entries older than {max_age_days} days")
        
        # Filter by count if max_count > 0
        count_deleted = 0
        if max_count > 0 and len(filtered_entries) > max_count:
            # Keep only the most recent entries
            before_count_filter = len(filtered_entries)
            filtered_entries = filtered_entries[-max_count:]
            count_deleted = before_count_filter - len(filtered_entries)
            logger.debug(f"Deleted {count_deleted} history entries to maintain max count of {max_count}")
        
        total_deleted = age_deleted + count_deleted
        
        # Write back the filtered entries if any were deleted
        if total_deleted > 0:
            with open(history_file, 'w', newline='', encoding='utf-8') as csvfile:
                if filtered_entries:
                    # Use the fieldnames from the first entry
                    fieldnames = filtered_entries[0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(filtered_entries)
                else:
                    # If no entries left, just write an empty file with headers
                    fieldnames = ['timestamp', 'command', 'steps', 'code', 'success']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
            
            logger.info(f"Command history cleanup completed: {total_deleted} entries deleted, {len(filtered_entries)} remaining")
        else:
            logger.debug("No command history entries needed cleanup")
        
        return total_deleted, None
        
    except Exception as e:
        error_msg = f"Error cleaning up command history: {str(e)}"
        logger.error(error_msg)
        return 0, error_msg

def manual_cleanup_command_history(max_age_days=None, max_count=None):
    """
    Manually trigger cleanup of old command history entries.
    
    Args:
        max_age_days: Maximum age in days for history entries (defaults to env var HISTORY_MAX_AGE_DAYS or 30)
        max_count: Maximum number of history entries to keep (defaults to env var HISTORY_MAX_COUNT or 1000)
        
    Returns:
        Dictionary with cleanup results
    """
    logger.info(f"Manually cleaning up command history with parameters: max_age_days={max_age_days}, max_count={max_count}")
    
    try:
        # Call the cleanup function - it will use environment variables if parameters are None
        deleted_count, error = cleanup_old_command_history(max_age_days, max_count)
        
        # Get the current history count
        history = get_command_history(date_filter='all')
        current_count = len(history)
        
        # Get the history file path
        history_file = get_command_history_file()
        
        # Build the response
        result = {
            "success": error is None,
            "deleted_count": deleted_count,
            "current_count": current_count,
            "history_file": history_file
        }
        
        if error:
            result["error"] = error
            
        logger.info(f"Manual command history cleanup complete: {deleted_count} deleted, {current_count} remaining")
        return result
        
    except Exception as e:
        logger.error(f"Error in manual command history cleanup: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e),
            "deleted_count": 0
        }
