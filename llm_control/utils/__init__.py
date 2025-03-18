"""Utility functions for the LLM PC Control package"""

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
    'choose_device_for_model'
]
