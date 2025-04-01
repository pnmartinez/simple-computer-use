"""
Scripts package for LLM PC Control.

This package contains modules for managing and executing scripts.
"""

# Import main classes and functions for easy access
from llm_control.scripts.piautobike import (
    PiautobikeScript,
    load_script,
    list_scripts,
    delete_script,
    execute_script,
    SCRIPTS_DIR
) 