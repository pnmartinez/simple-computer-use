import logging
import time
from llm_control import command_history

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def reset_command_history():
    """Reset the command history for a new session"""
    command_history['last_ui_element'] = None
    command_history['last_coordinates'] = None
    command_history['last_command'] = None
    command_history['steps'] = []
    logger.info("Command history reset")

def update_ui_element_history(element, coordinates):
    """Update the command history with a new UI element"""
    command_history['last_ui_element'] = element
    command_history['last_coordinates'] = coordinates
    logger.debug(f"Updated command history with UI element: {element.get('type', 'unknown')}")

def update_command_history(command_type):
    """Update the command history with a new command type"""
    command_history['last_command'] = command_type
    logger.debug(f"Updated command history with command type: {command_type}")

def add_step_to_history(original_step, normalized_step=None):
    """Add a step to the command history"""
    if normalized_step is None:
        normalized_step = original_step
        
    step_entry = {
        'original': original_step,
        'normalized': normalized_step,
        'timestamp': time.time()
    }
    command_history['steps'].append(step_entry)
    logger.debug(f"Added step to command history: {original_step}")

def get_last_ui_element():
    """Get the last UI element that was targeted"""
    return command_history['last_ui_element']

def get_last_coordinates():
    """Get the last coordinates that were targeted"""
    return command_history['last_coordinates']

def get_last_command():
    """Get the last command that was executed"""
    return command_history['last_command']

def get_step_history():
    """Get the full step history"""
    return command_history['steps']
