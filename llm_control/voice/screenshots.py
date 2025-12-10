"""
Screenshot capture and management functionality.

This module handles capturing, storing, and serving screenshots.
"""

import os
import time
import logging
import base64
import io
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

# Configure logging
logger = logging.getLogger("voice-control-screenshots")

# Import from our modules
from llm_control.voice.utils import get_screenshot_dir, error_response, cors_preflight, DEBUG, is_debug_mode, cleanup_old_screenshots

def capture_screenshot():
    """
    Capture a screenshot of the entire screen.
    
    Returns:
        Tuple of (filename, filepath, success)
    """
    logger.debug("Capturing screenshot of entire screen")
    
    try:
        # Try to import pyautogui
        try:
            import pyautogui
            logger.debug("Successfully imported pyautogui")
        except ImportError:
            logger.error("Failed to import pyautogui")
            return None, None, False
        
        # Get the screenshot directory
        screenshot_dir = get_screenshot_dir()
        logger.debug(f"Using screenshot directory: {screenshot_dir}")
        
        # Generate a filename based on timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        full_path = os.path.join(screenshot_dir, filename)
        logger.debug(f"Screenshot will be saved to: {full_path}")
        
        # Take the screenshot
        start_time = time.time()
        screenshot = pyautogui.screenshot()
        capture_time = time.time() - start_time
        logger.debug(f"Screenshot captured in {capture_time:.3f} seconds")
        
        # Save the screenshot
        screenshot.save(full_path)
        logger.debug(f"Screenshot saved successfully to {full_path}")
        
        # Log some information about the image
        if DEBUG:
            logger.debug(f"Screenshot info: format={screenshot.format}, mode={screenshot.mode}, size={screenshot.size}")
            width, height = screenshot.size
            logger.debug(f"Screenshot dimensions: {width}x{height} pixels")
        
        return filename, full_path, True
    
    except Exception as e:
        logger.error(f"Error capturing screenshot: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None, None, False

def capture_screenshot_with_name(filename: str) -> Optional[str]:
    """
    Capture a screenshot and save it with a specific filename.
    
    Args:
        filelabora un plan para moverlo a 3.10 o 3.11 en Pythonename: Name of the file (will be saved in screenshot directory)
        
    Returns:
        Full path to the saved screenshot, or None if failed
    """
    try:
        import pyautogui
        
        screenshot_dir = get_screenshot_dir()
        full_path = os.path.join(screenshot_dir, filename)
        
        screenshot = pyautogui.screenshot()
        screenshot.save(full_path)
        logger.debug(f"Screenshot saved to {full_path}")
        
        return full_path
    except Exception as e:
        logger.error(f"Error capturing screenshot with name {filename}: {str(e)}")
        return None

def capture_with_highlight(x=None, y=None, width=20, height=20, color='red'):
    """
    Capture a screenshot with a highlighted region.
    
    Args:
        x: X coordinate of highlight center (if None, uses current mouse position)
        y: Y coordinate of highlight center (if None, uses current mouse position)
        width: Width of highlight
        height: Height of highlight
        color: Color of highlight ('red', 'green', 'blue', etc.)
        
    Returns:
        Tuple of (filename, filepath, success)
    """
    logger.debug(f"Capturing screenshot with highlight at ({x}, {y}), size={width}x{height}, color={color}")
    
    try:
        # Try to import pyautogui and PIL
        try:
            import pyautogui
            from PIL import Image, ImageDraw
            logger.debug("Successfully imported pyautogui and PIL modules")
        except ImportError:
            logger.error("Failed to import required modules")
            missing = []
            try:
                import pyautogui
            except ImportError:
                missing.append("pyautogui")
            try:
                from PIL import Image, ImageDraw
            except ImportError:
                missing.append("PIL")
            return None, None, False
        
        # Get the screenshot directory
        screenshot_dir = get_screenshot_dir()
        logger.debug(f"Using screenshot directory: {screenshot_dir}")
        
        # Generate a filename based on timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_highlight_{timestamp}.png"
        full_path = os.path.join(screenshot_dir, filename)
        logger.debug(f"Screenshot will be saved to: {full_path}")
        
        # Get the current mouse position if coordinates not provided
        if x is None or y is None:
            logger.debug("No coordinates provided, using current mouse position")
            current_pos = pyautogui.position()
            x = x if x is not None else current_pos.x
            y = y if y is not None else current_pos.y
            logger.debug(f"Current mouse position: x={x}, y={y}")
        
        # Take the screenshot
        logger.debug("Capturing screenshot")
        start_time = time.time()
        screenshot = pyautogui.screenshot()
        capture_time = time.time() - start_time
        logger.debug(f"Screenshot captured in {capture_time:.3f} seconds")
        
        # Draw the highlight
        logger.debug(f"Drawing highlight at x={x}, y={y}, width={width}, height={height}, color={color}")
        draw = ImageDraw.Draw(screenshot)
        
        # Calculate the rectangle coordinates
        left = x - (width // 2)
        top = y - (height // 2)
        right = left + width
        bottom = top + height
        
        # Draw rectangle border (3 pixels thick)
        for i in range(3):
            draw.rectangle(
                [left-i, top-i, right+i, bottom+i],
                outline=color
            )
        
        # Save the screenshot
        screenshot.save(full_path)
        logger.debug(f"Highlighted screenshot saved successfully to {full_path}")
        
        # Log some information about the image
        if DEBUG:
            logger.debug(f"Screenshot info: format={screenshot.format}, mode={screenshot.mode}, size={screenshot.size}")
            width, height = screenshot.size
            logger.debug(f"Screenshot dimensions: {width}x{height} pixels")
            logger.debug(f"Highlight rectangle: ({left},{top}) to ({right},{bottom})")
        
        return filename, full_path, True
    
    except Exception as e:
        logger.error(f"Error capturing highlighted screenshot: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None, None, False

def get_latest_screenshots(limit=10):
    """
    Get a list of the latest screenshots.
    
    Args:
        limit: Maximum number of screenshots to return
        
    Returns:
        List of screenshot filenames
    """
    logger.debug(f"Getting latest {limit} screenshots")
    
    try:
        # Get the screenshot directory
        screenshot_dir = get_screenshot_dir()
        logger.debug(f"Using screenshot directory: {screenshot_dir}")
        
        # List all files in the screenshot directory
        all_files = []
        try:
            all_files = os.listdir(screenshot_dir)
            logger.debug(f"Found {len(all_files)} files in screenshot directory")
        except FileNotFoundError:
            logger.error(f"Screenshot directory not found: {screenshot_dir}")
            os.makedirs(screenshot_dir, exist_ok=True)
            logger.debug(f"Created screenshot directory: {screenshot_dir}")
            return []
        
        # Filter out non-screenshot files - include all supported patterns
        screenshots = [f for f in all_files if (f.startswith("screenshot_") or 
                                               f.startswith("temp_") or 
                                               f.startswith("before_") or 
                                               f.startswith("after_")) and f.endswith(".png")]
        logger.debug(f"Found {len(screenshots)} screenshot files")
        
        # Sort by modification time (newest first)
        screenshots.sort(key=lambda x: os.path.getmtime(os.path.join(screenshot_dir, x)), reverse=True)
        logger.debug("Screenshots sorted by modification time (newest first)")
        
        # Limit the results
        limited_screenshots = screenshots[:limit]
        logger.debug(f"Limited to {len(limited_screenshots)} screenshots")
        
        # Log the filenames if in debug mode
        if DEBUG:
            for i, screenshot in enumerate(limited_screenshots):
                logger.debug(f"Screenshot {i+1}: {screenshot}")
        
        return limited_screenshots
    
    except Exception as e:
        logger.error(f"Error getting latest screenshots: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return []

def list_all_screenshots():
    """
    List all screenshots with metadata.
    
    Returns:
        List of dictionaries with screenshot metadata
    """
    logger.debug("Listing all screenshots with metadata")
    
    try:
        # Get the screenshot directory
        screenshot_dir = get_screenshot_dir()
        logger.debug(f"Using screenshot directory: {screenshot_dir}")
        
        # List all files in the screenshot directory
        all_files = []
        try:
            all_files = os.listdir(screenshot_dir)
            logger.debug(f"Found {len(all_files)} files in screenshot directory")
        except FileNotFoundError:
            logger.error(f"Screenshot directory not found: {screenshot_dir}")
            os.makedirs(screenshot_dir, exist_ok=True)
            logger.debug(f"Created screenshot directory: {screenshot_dir}")
            return []
        
        # Filter out non-screenshot files - include all supported patterns
        screenshots = [f for f in all_files if (f.startswith("screenshot_") or 
                                               f.startswith("temp_") or 
                                               f.startswith("before_") or 
                                               f.startswith("after_")) and f.endswith(".png")]
        logger.debug(f"Found {len(screenshots)} screenshot files")
        
        # Get metadata for each screenshot
        result = []
        for filename in screenshots:
            full_path = os.path.join(screenshot_dir, filename)
            try:
                # Get file metadata
                stat = os.stat(full_path)
                
                # Check if it's a highlight screenshot
                is_highlight = "highlight" in filename
                
                # Add to result
                result.append({
                    "filename": filename,
                    "timestamp": stat.st_mtime,
                    "size": stat.st_size,
                    "highlight": is_highlight,
                    "date": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
                
                if DEBUG:
                    logger.debug(f"Screenshot metadata: {filename}, {stat.st_size} bytes, created at {datetime.fromtimestamp(stat.st_mtime)}")
            except Exception as e:
                logger.warning(f"Error getting metadata for {filename}: {str(e)}")
        
        # Sort by modification time (newest first)
        result.sort(key=lambda x: x["timestamp"], reverse=True)
        logger.debug(f"Returning metadata for {len(result)} screenshots, sorted by time")
        
        return result
    
    except Exception as e:
        logger.error(f"Error listing all screenshots: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return []

def manual_cleanup_screenshots(max_age_days=None, max_count=None):
    """
    Manually trigger cleanup of old screenshots.
    
    Args:
        max_age_days: Maximum age in days for screenshots (defaults to env var SCREENSHOT_MAX_AGE_DAYS or 7)
        max_count: Maximum number of screenshots to keep (defaults to env var SCREENSHOT_MAX_COUNT or 100)
        
    Returns:
        Dictionary with cleanup results
    """
    logger.info(f"Manually cleaning up screenshots with parameters: max_age_days={max_age_days}, max_count={max_count}")
    
    try:
        # Call the cleanup function - it will use environment variables if parameters are None
        deleted_count, error = cleanup_old_screenshots(max_age_days, max_count)
        
        # Get the current screenshot count
        screenshots = list_all_screenshots()
        current_count = len(screenshots)
        
        # Build the response
        result = {
            "success": error is None,
            "deleted_count": deleted_count,
            "current_count": current_count,
            "screenshot_dir": get_screenshot_dir()
        }
        
        if error:
            result["error"] = error
            
        logger.info(f"Manual cleanup complete: {deleted_count} deleted, {current_count} remaining")
        return result
        
    except Exception as e:
        logger.error(f"Error in manual cleanup: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e),
            "deleted_count": 0
        }

def get_screenshot_data(filename, format='base64'):
    """
    Get the screenshot data in the requested format.
    
    Args:
        filename: Screenshot filename
        format: Output format ('base64' or 'binary')
        
    Returns:
        Screenshot data in the requested format
    """
    logger.debug(f"Getting screenshot data for {filename} in {format} format")
    
    try:
        # Get the screenshot directory
        screenshot_dir = get_screenshot_dir()
        logger.debug(f"Using screenshot directory: {screenshot_dir}")
        
        # Build the full path
        full_path = os.path.join(screenshot_dir, filename)
        logger.debug(f"Full path: {full_path}")
        
        # Check if the file exists
        if not os.path.isfile(full_path):
            logger.error(f"Screenshot not found: {full_path}")
            return None
        
        # Read the file
        with open(full_path, 'rb') as f:
            file_data = f.read()
            logger.debug(f"Read {len(file_data)} bytes from file")
        
        # Convert to the requested format
        if format == 'base64':
            logger.debug("Converting to base64")
            encoded = base64.b64encode(file_data).decode('utf-8')
            logger.debug(f"Base64 encoded data length: {len(encoded)}")
            return encoded
        elif format == 'binary':
            logger.debug("Returning binary data")
            return file_data
        else:
            logger.error(f"Unsupported format: {format}")
            return None
    
    except Exception as e:
        logger.error(f"Error getting screenshot data: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None
