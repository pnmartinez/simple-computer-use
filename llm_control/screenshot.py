"""
Screenshot module for LLM Control.

This module provides functions for capturing and processing screenshots.
It's separated to avoid circular imports between ui_detection and utils.
"""

import os
import sys
import logging
import tempfile
from typing import Union, Tuple, Dict, Any, Optional

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def take_screenshot(region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
    """
    Take a screenshot of the entire screen or a specific region.
    
    Args:
        region: Optional tuple (left, top, width, height) to capture a specific region
        
    Returns:
        Dictionary with screenshot path and metadata
    """
    try:
        # Import here to avoid circular dependencies
        import pyautogui
        from PIL import Image
        
        logger.debug("Taking screenshot...")
        
        # Take the screenshot
        if region:
            screenshot = pyautogui.screenshot(region=region)
        else:
            screenshot = pyautogui.screenshot()
        
        # Save the screenshot to a temporary file
        temp_path = tempfile.mktemp(suffix='.png')
        screenshot.save(temp_path)
        
        logger.debug(f"Screenshot saved to temporary file: {temp_path}")
        
        # Get screen resolution
        screen_width, screen_height = pyautogui.size()
        
        return {
            "success": True,
            "path": temp_path,
            "width": screenshot.width,
            "height": screenshot.height,
            "screen_width": screen_width,
            "screen_height": screen_height,
            "region": region
        }
    
    except Exception as e:
        logger.error(f"Error taking screenshot: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "success": False,
            "error": str(e)
        }

def enhanced_screenshot_processing(screenshot_path_or_data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Perform enhanced processing on a screenshot for UI analysis.
    
    Args:
        screenshot_path_or_data: Path to the screenshot file or screenshot data dictionary
        
    Returns:
        Dictionary with processed data and UI information
    """
    try:
        from PIL import Image
        import hashlib
        
        # Handle if input is already a dictionary (from take_screenshot)
        if isinstance(screenshot_path_or_data, dict):
            if not screenshot_path_or_data.get('success', False):
                # If screenshot wasn't successful, just return it
                return screenshot_path_or_data
                
            # Use the path from the dictionary
            screenshot_path = screenshot_path_or_data.get('path')
            if not screenshot_path or not os.path.exists(screenshot_path):
                return {
                    "success": False,
                    "error": "Screenshot path not found in screenshot data",
                    "ui_description": {}
                }
        else:
            screenshot_path = screenshot_path_or_data
        
        # Load the image
        image = Image.open(screenshot_path)
        
        # Calculate a hash of the image for caching/reference
        with open(screenshot_path, 'rb') as f:
            image_hash = hashlib.md5(f.read()).hexdigest()
        
        # Extract basic image properties
        width, height = image.size
        mode = image.mode
        
        # Don't do too much processing here to avoid circular imports
        # More advanced UI processing will be handled in ui_detection modules
        
        return {
            "success": True,
            "path": screenshot_path,
            "width": width,
            "height": height,
            "mode": mode,
            "hash": image_hash,
            "ui_description": {
                "screen_size": (width, height),
                "elements": []  # Will be populated by ui_detection modules
            }
        }
    
    except Exception as e:
        logger.error(f"Error processing screenshot: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "success": False,
            "error": str(e),
            "path": screenshot_path if isinstance(screenshot_path_or_data, str) else "",
            "ui_description": {}
        } 