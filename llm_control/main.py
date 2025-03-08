import logging
import os
import sys
import time
from typing import List, Dict, Any, Optional, Tuple

import pyautogui
from PIL import Image

from llm_control.utils.dependencies import check_and_install_dependencies
from llm_control.utils.download import download_models_if_needed
from llm_control.ui_detection import take_screenshot, enhanced_screenshot_processing
from llm_control.command_processing import (
    split_user_input_into_steps,
    clean_and_normalize_steps,
    process_single_step,
    reset_command_history
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def setup() -> None:
    """
    Set up the environment for the LLM PC Control package.
    Checks dependencies and downloads required models.
    """
    logger.info("Setting up LLM PC Control...")
    
    # Check and install dependencies
    check_and_install_dependencies()
    
    # Download models if needed
    download_models_if_needed()
    
    # Reset command history for a new session
    reset_command_history()
    
    logger.info("Setup complete!")

def process_user_command(user_input: str) -> List[Dict[str, Any]]:
    """
    Process a user command and generate the corresponding actions.
    
    Args:
        user_input: The user's command as a string
        
    Returns:
        A list of dictionaries containing the generated code and metadata for each step
    """
    logger.info(f"Processing user command: '{user_input}'")
    
    # Take a screenshot to analyze the current UI state
    screenshot = take_screenshot()
    
    # Process the screenshot to detect UI elements
    screenshot_data = enhanced_screenshot_processing(screenshot)
    ui_description = screenshot_data['ui_description']
    
    # Split the user input into individual steps
    steps = split_user_input_into_steps(user_input)
    
    # Clean and normalize the steps
    cleaned_steps = clean_and_normalize_steps(steps)
    
    # Process each step and generate the corresponding code
    results = []
    print(f"🔄 Processing multi-step query with {len(cleaned_steps)} steps:")
    
    for i, step in enumerate(cleaned_steps):
        print(f"  Step {i+1}: '{step}'")
        
        # Process the step and generate the corresponding code
        result = process_single_step(step, ui_description, screenshot)
        
        # Add the result to the list
        results.append(result)
    
    return results

def execute_actions(actions: List[Dict[str, Any]]) -> None:
    """
    Execute the generated actions.
    
    Args:
        actions: A list of dictionaries containing the generated code and metadata
    """
    logger.info(f"Executing {len(actions)} actions...")
    
    for i, action in enumerate(actions):
        code = action.get("code")
        if code:
            logger.info(f"Executing action {i+1}: {action.get('description', 'No description')}")
            
            try:
                # Execute the generated code
                exec(code)
                
                # Add a small delay between actions
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error executing action: {str(e)}")
        else:
            logger.warning(f"No code to execute for action {i+1}")
    
    logger.info("All actions executed!")

def run_command(user_input: str) -> List[Dict[str, Any]]:
    """
    Run a user command, processing it and executing the corresponding actions.
    
    Args:
        user_input: The user's command as a string
        
    Returns:
        A list of dictionaries containing the generated code and metadata for each step
    """
    # Process the user command
    actions = process_user_command(user_input)
    
    # Execute the actions
    execute_actions(actions)
    
    return actions

if __name__ == "__main__":
    # Set up the environment
    setup()
    
    # If a command is provided as a command-line argument, run it
    if len(sys.argv) > 1:
        command = " ".join(sys.argv[1:])
        run_command(command)
    else:
        print("Please provide a command to run.")
        print("Example: python -m llm_control.main 'click on the button'") 