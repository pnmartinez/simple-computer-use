import logging
from llm_control.utils.dependencies import check_and_install_dependencies
from llm_control.utils.download import download_models_if_needed
from llm_control.utils.wait import wait_for_visual_stability, wait_based_on_action

# Get the package logger
logger = logging.getLogger("llm-pc-control")

# Export the main functions
__all__ = [
    'check_and_install_dependencies',
    'download_models_if_needed',
    'wait_for_visual_stability',
    'wait_based_on_action'
]
