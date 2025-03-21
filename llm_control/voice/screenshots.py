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
from llm_control.voice.utils import get_screenshot_dir, error_response, cors_preflight

def capture_screenshot():
    """
    Capture a screenshot and save it to the screenshots directory.
    
    Returns:
        Tuple with (filename, filepath, screenshot_obj)
    """
    try:
        import pyautogui
        from PIL import Image
        
        # Get screenshot directory
        screenshot_dir = get_screenshot_dir()
        
        # Generate a unique filename based on timestamp
        timestamp = int(time.time())
        filename = f"screenshot_{timestamp}.png"
        filepath = os.path.join(screenshot_dir, filename)
        
        # Take a screenshot
        screenshot = pyautogui.screenshot()
        
        # Save the screenshot
        screenshot.save(filepath)
        
        logger.info(f"💾 Captured screenshot and saved to {filepath}")
        
        return filename, filepath, screenshot
        
    except Exception as e:
        logger.error(f"Error capturing screenshot: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None, None, None

def capture_with_highlight(x=None, y=None, width=20, height=20, color='red'):
    """
    Capture a screenshot and highlight a region around the coordinates.
    
    Args:
        x: X coordinate to highlight (or None for no highlight)
        y: Y coordinate to highlight (or None for no highlight)
        width: Width of the highlight box
        height: Height of the highlight box
        color: Color of the highlight
        
    Returns:
        Tuple with (filename, filepath, screenshot_obj)
    """
    try:
        import pyautogui
        from PIL import Image, ImageDraw
        
        # Get screenshot directory
        screenshot_dir = get_screenshot_dir()
        
        # Generate a unique filename based on timestamp
        timestamp = int(time.time())
        filename = f"screenshot_highlight_{timestamp}.png"
        filepath = os.path.join(screenshot_dir, filename)
        
        # Take a screenshot
        screenshot = pyautogui.screenshot()
        
        # Add highlight if coordinates are provided
        if x is not None and y is not None:
            draw = ImageDraw.Draw(screenshot)
            
            # Calculate box coordinates
            x1 = max(0, x - width//2)
            y1 = max(0, y - height//2)
            x2 = x1 + width
            y2 = y1 + height
            
            # Draw a rectangle
            draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
            
            # Draw crosshair lines
            draw.line([x, 0, x, screenshot.height], fill='blue', width=1)
            draw.line([0, y, screenshot.width, y], fill='blue', width=1)
        
        # Save the screenshot
        screenshot.save(filepath)
        
        logger.info(f"💾 Captured screenshot with highlight at ({x}, {y}) and saved to {filepath}")
        
        return filename, filepath, screenshot
        
    except Exception as e:
        logger.error(f"Error capturing screenshot with highlight: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None, None, None

def get_latest_screenshots(limit=10):
    """
    Get information about the latest screenshots.
    
    Args:
        limit: Maximum number of screenshots to return
        
    Returns:
        List of screenshot information dictionaries
    """
    try:
        screenshot_dir = get_screenshot_dir()
        
        # Find all PNG files in the screenshots directory
        screenshot_files = []
        for filename in os.listdir(screenshot_dir):
            if filename.endswith(".png"):
                filepath = os.path.join(screenshot_dir, filename)
                
                # Get file information
                file_stat = os.stat(filepath)
                screenshot_files.append({
                    "filename": filename,
                    "filepath": filepath,
                    "size": file_stat.st_size,
                    "created": file_stat.st_mtime,
                    "created_formatted": datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    "url": f"/screenshots/{filename}"
                })
        
        # Sort by creation time (newest first)
        screenshot_files.sort(key=lambda x: x["created"], reverse=True)
        
        # Limit the number of results
        screenshot_files = screenshot_files[:limit]
        
        return screenshot_files
        
    except Exception as e:
        logger.error(f"Error listing screenshots: {str(e)}")
        return []

def list_all_screenshots():
    """
    List all available screenshots.
    
    Returns:
        List of screenshot filenames
    """
    try:
        screenshot_dir = get_screenshot_dir()
        
        # Find all PNG files in the screenshots directory
        screenshot_files = []
        for filename in os.listdir(screenshot_dir):
            if filename.endswith(".png"):
                screenshot_files.append(filename)
        
        # Sort alphabetically
        screenshot_files.sort()
        
        return screenshot_files
        
    except Exception as e:
        logger.error(f"Error listing screenshots: {str(e)}")
        return []

def get_screenshot_data(filename, format='base64'):
    """
    Get screenshot data in the specified format.
    
    Args:
        filename: Screenshot filename
        format: Output format ('base64' or 'bytes')
        
    Returns:
        Screenshot data in the specified format or None if error
    """
    try:
        from PIL import Image
        
        screenshot_dir = get_screenshot_dir()
        filepath = os.path.join(screenshot_dir, filename)
        
        # Check if file exists
        if not os.path.isfile(filepath):
            logger.error(f"Screenshot file not found: {filepath}")
            return None
        
        # Open the image
        image = Image.open(filepath)
        
        if format == 'base64':
            # Convert to base64
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            return img_str
        else:
            # Return bytes
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            return buffered.getvalue()
            
    except Exception as e:
        logger.error(f"Error getting screenshot data: {str(e)}")
        return None
