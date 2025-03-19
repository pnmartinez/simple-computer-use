"""
Extensions and enhancements for PyAutoGUI.

This module adds additional functionality to PyAutoGUI to make it more
powerful and easier to use with LLM-generated code.
"""

import logging
import sys

logger = logging.getLogger("llm-pc-control")

def add_pyautogui_extensions():
    """
    Add extension functions to PyAutoGUI to enhance functionality.
    
    This function adds:
    - moveRelative: An alias for move() that makes relative movements more intuitive
    - Other utility functions as needed
    
    Returns:
        bool: True if extensions were added successfully, False otherwise
    """
    try:
        import pyautogui
        
        # Add moveRelative as an alias for move
        if not hasattr(pyautogui, 'moveRelative'):
            # Original move function takes xOffset, yOffset as parameters
            pyautogui.moveRelative = pyautogui.move
            logger.info("Added moveRelative extension to PyAutoGUI")
            
            # Document the function to help with auto-completion
            pyautogui.moveRelative.__doc__ = """
            moveRelative(xOffset, yOffset, duration=0.0, tween=pyautogui.linear)
            
            Moves the mouse cursor relative to its current position.
            
            Args:
              xOffset (int, float): The x offset to move.
              yOffset (int, float): The y offset to move.
              duration (float, optional): The duration of the movement.
              tween (func, optional): The tweening/easing function.
            
            Returns:
              None
            """
        
        # Add more extensions as needed here
        
        return True
        
    except ImportError as e:
        logger.warning(f"Could not import PyAutoGUI to add extensions: {e}")
        return False
    except Exception as e:
        logger.error(f"Error adding PyAutoGUI extensions: {e}")
        return False

# Add the extensions when this module is imported
success = add_pyautogui_extensions()
if not success:
    logger.warning("Failed to add PyAutoGUI extensions. Some commands may not work properly.")
else:
    logger.debug("PyAutoGUI extensions added successfully.") 