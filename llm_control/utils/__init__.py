import logging
from llm_control.utils.dependencies import check_and_install_package
from llm_control.utils.download import download_file, download_models_if_needed

# Get the package logger
logger = logging.getLogger("llm-pc-control")

# Export the main functions
__all__ = [
    'check_and_install_package',
    'download_file',
    'download_models_if_needed'
]
