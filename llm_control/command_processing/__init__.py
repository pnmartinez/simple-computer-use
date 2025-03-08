import logging
from llm_control.command_processing.executor import generate_pyautogui_code_with_ui_awareness, process_single_step
from llm_control.command_processing.parser import normalize_step, split_user_input_into_steps, clean_and_normalize_steps
from llm_control.command_processing.history import (
    reset_command_history, update_ui_element_history, update_command_history,
    add_step_to_history, get_last_ui_element, get_last_coordinates,
    get_last_command, get_step_history
)
from llm_control.command_processing.finder import find_ui_element

# Get the package logger
logger = logging.getLogger("llm-pc-control")

# Export the main functions
__all__ = [
    'generate_pyautogui_code_with_ui_awareness',
    'process_single_step',
    'normalize_step',
    'split_user_input_into_steps',
    'clean_and_normalize_steps',
    'reset_command_history',
    'update_ui_element_history',
    'update_command_history',
    'add_step_to_history',
    'get_last_ui_element',
    'get_last_coordinates',
    'get_last_command',
    'get_step_history',
    'find_ui_element'
]
