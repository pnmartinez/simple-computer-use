"""
Utility functions for the LLM PC Control package.

This module provides various utility functions for the LLM PC Control package, including:
1. Dependency management - checking and installing required packages
2. Model download utilities - downloading and managing LLM models
3. GPU utilities - optimizing GPU memory and checking GPU availability
4. PyAutoGUI extensions - adding custom functionality to PyAutoGUI
5. Wait utilities - implementing smart waiting mechanisms between UI actions
"""

import logging
from llm_control.utils.dependencies import (
    check_and_install_package,
    check_and_install_dependencies
)
from llm_control.utils.download import (
    download_file,
    download_models_if_needed
)
from llm_control.utils.wait import wait_for_visual_stability, wait_based_on_action

# Import PyAutoGUI extensions
try:
    from llm_control.utils.pyautogui_extensions import add_pyautogui_extensions
except ImportError:
    def add_pyautogui_extensions():
        """Stub for add_pyautogui_extensions when not available"""
        return False

try:
    from llm_control.utils.gpu_utils import (
        check_gpu_info,
        clear_gpu_memory,
        optimize_gpu_memory,
        choose_device_for_model
    )
except ImportError:
    # If torch or related dependencies aren't available, provide stub functions
    def check_gpu_info():
        return {"available": False, "message": "GPU utilities not available"}
    
    def clear_gpu_memory():
        return False
    
    def optimize_gpu_memory():
        pass
    
    def choose_device_for_model(*args, **kwargs):
        return "cpu"

# Import Ollama utilities
try:
    from llm_control.utils.ollama import (
        check_ollama_model,
        get_model_not_found_message,
        check_ollama_model_with_message,
        warmup_ollama_model
    )
except ImportError:
    # Stub functions if requests is not available
    def check_ollama_model(*args, **kwargs):
        return False, "Ollama utilities not available"
    
    def get_model_not_found_message(model):
        return f"Ollama model '{model}' not found"
    
    def check_ollama_model_with_message(*args, **kwargs):
        return False, "Ollama utilities not available"
    
    def warmup_ollama_model(*args, **kwargs):
        return False, "Ollama utilities not available"

# Get the package logger
logger = logging.getLogger("llm-pc-control")

# Export the main functions
__all__ = [
    'check_and_install_package',
    'check_and_install_dependencies',
    'download_file',
    'download_models_if_needed',
    'wait_for_visual_stability',
    'wait_based_on_action',
    'check_gpu_info',
    'clear_gpu_memory',
    'optimize_gpu_memory',
    'choose_device_for_model',
    'add_pyautogui_extensions',
    'check_ollama_model',
    'get_model_not_found_message',
    'check_ollama_model_with_message',
    'warmup_ollama_model'
]

# Initialize PyAutoGUI extensions when importing utils
add_pyautogui_extensions()
