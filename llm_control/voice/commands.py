"""
Command processing module for voice control.

This module handles command parsing, validation, and execution.
"""

import os
import sys
import logging
import json
import re
import requests
from typing import Dict, Any, List, Optional, Tuple, Union
import time

# Configure logging
logger = logging.getLogger("voice-control-commands")

# Set up debug mode based on environment variable
DEBUG = os.environ.get("DEBUG", "").lower() in ("true", "1", "yes")

# Import from our modules
from llm_control.voice.utils import clean_llm_response, get_screenshot_dir, cleanup_old_screenshots
from llm_control.voice.prompts import (
    TRANSLATION_PROMPT,
    VERIFICATION_PROMPT,
    SPLIT_COMMAND_PROMPT,
    IDENTIFY_OCR_TARGETS_PROMPT,
    GENERATE_PYAUTOGUI_ACTIONS_PROMPT
)

# Add imports for UI detection and command processing
try:
    from llm_control.command_processing.executor import generate_pyautogui_code_with_ui_awareness
    from llm_control.command_processing.finder import find_ui_element
    from llm_control.ui_detection.element_finder import detect_ui_elements_with_yolo
    from llm_control.ui_detection.element_finder import detect_text_regions, get_ui_description
    logger.debug("Successfully imported command_processing and ui_detection modules")
except ImportError as e:
    logger.warning(f"Failed to import command_processing or ui_detection modules: {e}")

# Constants
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# Import from our own modules if available
try:
    from llm_control.llm.simple_executor import execute_command_with_llm
    logger.debug("Successfully imported execute_command_with_llm from llm_control.llm.simple_executor")
except ImportError:
    # Define a stub function if we can't import
    logger.warning("Failed to import execute_command_with_llm, using stub function")
    def execute_command_with_llm(command, model="llama3.1", ollama_host="http://localhost:11434"):
        logger.warning(f"Using stub execute_command_with_llm function for command: {command}")
        return {
            "success": False,
            "error": "simple_executor module not available",
            "command": command
        }

# Add additional logging to track command processing pipeline
def log_command_pipeline(original_command=None, steps=None, steps_with_targets=None, pyautogui_actions=None):
    """
    Log the complete command processing pipeline for debugging.
    
    Args:
        original_command: The original command text
        steps: The steps extracted from the command
        steps_with_targets: Steps with OCR targets identified
        pyautogui_actions: Generated PyAutoGUI code
    """
    if not DEBUG:
        return
    
    logger.debug("=== COMMAND PROCESSING PIPELINE ===")
    
    if original_command:
        logger.debug(f"ORIGINAL COMMAND: '{original_command}'")
    
    if steps:
        logger.debug("STEPS BREAKDOWN:")
        for i, step in enumerate(steps):
            logger.debug(f"  {i+1}. {step}")
    
    if steps_with_targets:
        logger.debug("STEPS WITH OCR TARGETS:")
        for i, step_data in enumerate(steps_with_targets):
            needs_ocr = step_data.get("needs_ocr", False)
            target = step_data.get("target", "N/A") if needs_ocr else "Not required"
            logger.debug(f"  {i+1}. STEP: {step_data.get('step')}")
            logger.debug(f"     NEEDS OCR: {needs_ocr}")
            logger.debug(f"     TARGET: {target}")
    
    if pyautogui_actions:
        logger.debug("PYAUTOGUI ACTIONS:")
        # Handle both list and dict formats
        if isinstance(pyautogui_actions, list):
            for i, action in enumerate(pyautogui_actions):
                logger.debug(f"  ACTION {i+1}:")
                logger.debug(f"    DESCRIPTION: {action.get('description', 'N/A')}")
                logger.debug(f"    TARGET: {action.get('target', 'N/A')}")
                logger.debug(f"    COMMAND: \n{action.get('pyautogui_cmd', 'N/A')}")
        else:
            # Old format with imports and steps
            if "imports" in pyautogui_actions:
                logger.debug(f"  IMPORTS: {pyautogui_actions['imports']}")
            if "steps" in pyautogui_actions:
                for i, step_data in enumerate(pyautogui_actions['steps']):
                    logger.debug(f"  ACTION {i+1}:")
                    logger.debug(f"    ORIGINAL: {step_data.get('original', 'N/A')}")
                    logger.debug(f"    CODE: \n{step_data.get('code', 'N/A')}")
    
    logger.debug("=== END COMMAND PROCESSING PIPELINE ===")

def validate_pyautogui_cmd(cmd):
    """
    Validate that a PyAutoGUI command only uses allowed functions.
    
    Args:
        cmd: The PyAutoGUI command to validate 

    Returns:
        Tuple of (is_valid, disallowed_functions)
    """
    logger.debug(f"Validating PyAutoGUI command: {cmd[:100]}..." if len(cmd) > 100 else f"Validating PyAutoGUI command: {cmd}")
    allowed_functions = [
        "pyautogui.moveTo", "pyautogui.move", "pyautogui.moveRelative", "pyautogui.click", 
        "pyautogui.doubleClick", "pyautogui.rightClick", "pyautogui.dragTo",
        "pyautogui.write", "pyautogui.press", "pyautogui.hotkey",
        "pyautogui.scroll", "pyautogui.screenshot",
        # Allow these basic utility functions as well
        "pyautogui.FAILSAFE", "pyautogui.size", "pyautogui.position"
    ]
    logger.debug(f"Allowed PyAutoGUI functions: {allowed_functions}")
    
    is_valid = True
    disallowed_functions = []
    
    for line in cmd.split('\n'):
        # Skip comments and empty lines
        line = line.strip()
        if not line or line.startswith('#'):
            continue
            
        # Handle lines with semicolons or comments mid-line
        if ';' in line:
            # Split by semicolon and process each part separately
            logger.debug(f"Processing line with semicolons: {line}")
            parts = line.split(';')
            for part in parts:
                part = part.strip()
                if not part or part.startswith('#'):
                    continue
                    
                # Check for comments at the end of the part
                if '#' in part:
                    part = part[:part.find('#')].strip()
                
                # Skip common imports and utility lines
                if part.startswith('import ') or part.startswith('from ') or part.startswith('print('):
                    continue
                
                # Check if this part contains any allowed functions
                if not any(func in part for func in allowed_functions) and "pyautogui." in part:
                    is_valid = False
                    logger.debug(f"Found disallowed function in part: {part}")
                    try:
                        # Extract the function name
                        func_start = part.find("pyautogui.") + 10
                        func_end = part.find("(", func_start)
                        if func_end > func_start:
                            disallowed_function = part[func_start:func_end]
                            logger.debug(f"Identified disallowed function: {disallowed_function}")
                            disallowed_functions.append(disallowed_function)
                    except:
                        # If we can't extract the function name, just add the whole part
                        logger.debug(f"Could not extract function name, adding whole part as disallowed: {part}")
                        disallowed_functions.append(part)
            continue
            
        # Handle lines with comments
        if '#' in line:
            logger.debug(f"Processing line with comments: {line}")
            line = line[:line.find('#')].strip()
            if not line:
                continue
        
        # Skip common imports and utility lines
        if line.startswith('import ') or line.startswith('from ') or line.startswith('print('):
            continue
        
        # Check if line contains any allowed functions
        if not any(func in line for func in allowed_functions):
            # Only flag as invalid if it's a pyautogui function call
            if "pyautogui." in line:
                is_valid = False
                logger.debug(f"Found disallowed function in line: {line}")
                try:
                    # Extract the function name
                    func_start = line.find("pyautogui.") + 10
                    func_end = line.find("(", func_start)
                    if func_end > func_start:
                        disallowed_function = line[func_start:func_end]
                        logger.debug(f"Identified disallowed function: {disallowed_function}")
                        disallowed_functions.append(disallowed_function)
                except:
                    # If we can't extract the function name, just add the whole line
                    logger.debug(f"Could not extract function name, adding whole line as disallowed: {line}")
                    disallowed_functions.append(line)
    
    # Remove duplicates
    disallowed_functions = list(set(disallowed_functions))
    logger.debug(f"Validation result: is_valid={is_valid}, disallowed_functions={disallowed_functions}")
    
    return is_valid, disallowed_functions

def verify_command_integrity(original_command, steps, model=OLLAMA_MODEL):
    """
    Verify that the parsed steps match the intent of the original command.
    
    Args:
        original_command: Original natural language command
        steps: List of parsed steps
        model: LLM model to use for verification
        
    Returns:
        Tuple of (is_valid, reason)
    """
    logger.debug(f"Verifying command integrity. Original command: '{original_command}'")
    logger.debug(f"Steps to verify: {steps}")
    
    all_valid = True
    invalid_reason = None
    
    try:
        # Verify each step individually
        for step in steps:
            # Prepare the prompt for verification using the template from prompts.py
            prompt = VERIFICATION_PROMPT.format(
                original_command=original_command,
                step=step
            )
            
            logger.debug(f"Sending verification prompt to Ollama API at {OLLAMA_HOST} for step: {step}")
            
            # Make API request to Ollama
            start_time = time.time()
            response = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.1  # Use low temperature for more deterministic output
                },
                timeout=30
            )
            
            request_time = time.time() - start_time
            logger.debug(f"Ollama API request completed in {request_time:.2f} seconds with status code: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"Error from Ollama API: {response.status_code}")
                logger.error(f"Response content: {response.text[:500]}")
                return False, "Error communicating with Ollama API"
            
            # Parse response
            result = response.json()
            verified_step = result["response"].strip()
            logger.debug(f"Verified step from Ollama: {verified_step}")
            
            # If the verified step is significantly different or empty, mark as invalid
            if not verified_step or len(verified_step) < len(step) * 0.5:
                all_valid = False
                invalid_reason = f"Step '{step}' was not validated"
                break
        
        return all_valid, invalid_reason if invalid_reason else ""
        
    except Exception as e:
        logger.error(f"Error verifying command integrity: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False, f"Verification error: {str(e)}"

def split_command_into_steps(command, model=OLLAMA_MODEL):
    """
    Split a natural language command into discrete steps.
    
    Args:
        command: Natural language command
        model: LLM model to use
        
    Returns:
        List of steps or None if processing failed
    """
    logger.debug(f"Splitting command into steps: '{command}'")
    logger.debug(f"Using model: {model}")
    
    try:
        # Prepare the prompt for step splitting using the template from prompts.py
        prompt = SPLIT_COMMAND_PROMPT.format(command=command)
        
        logger.debug("Sending request to Ollama API for step splitting")
        
        # Make API request to Ollama
        start_time = time.time()
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.1  # Use low temperature for more deterministic output
            },
            timeout=30
        )
        
        request_time = time.time() - start_time
        logger.debug(f"Ollama API request completed in {request_time:.2f} seconds with status code: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Error from Ollama API: {response.status_code}")
            logger.error(f"Response content: {response.text[:500]}")
            return None
        
        # Parse response
        result = response.json()
        steps_text = result["response"].strip()
        logger.debug(f"Raw steps text from Ollama: {steps_text[:500]}")
        
        # Clean and extract the steps
        steps = []
        
        # Remove any code blocks
        steps_text = steps_text.replace("```", "").strip()
        
        # Extract steps by matching numbered lines
        step_pattern = re.compile(r'^\s*(\d+)\.\s+(.+)$', re.MULTILINE)
        matches = step_pattern.findall(steps_text)
        logger.debug(f"Found {len(matches)} step matches with numbered pattern")
        
        for _, step in matches:
            steps.append(step.strip())
        
        # If no steps were found, try another approach to extract lines
        if not steps:
            logger.debug("No steps found with numbered pattern, trying line-by-line approach")
            for line in steps_text.split('\n'):
                line = line.strip()
                # Skip empty lines
                if not line:
                    continue
                    
                # Try to remove numbering if present
                line_match = re.match(r'^\s*\d+\.\s*(.+)$', line)
                if line_match:
                    steps.append(line_match.group(1).strip())
                else:
                    steps.append(line)
        
        logger.debug(f"Final extracted steps: {steps}")
        
        # Log the transcription segmentation for tracking purposes
        logger.info(f"Command '{command}' was segmented into {len(steps)} steps")
        for i, step in enumerate(steps):
            logger.info(f"Step {i+1}: {step}")
        
        return steps
        
    except Exception as e:
        logger.error(f"Error splitting command into steps: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def identify_ocr_targets(steps, model=OLLAMA_MODEL):
    """
    Identify steps that would benefit from OCR targeting (looking for UI elements).
    
    Args:
        steps: List of steps from split_command_into_steps
        model: LLM model to use
        
    Returns:
        List of steps with OCR targets identified
    """
    if not steps:
        logger.debug("No steps provided to identify_ocr_targets")
        return []
    
    logger.debug(f"Identifying OCR targets for {len(steps)} steps")
    logger.debug(f"Steps: {steps}")
    
    results = []
        
    try:
        # Process each step individually
        for step in steps:
            # Remove any bullet points or numbering from the step
            clean_step = re.sub(r'^[-\d.]\s*', '', step).strip()

             # Check if this is a typing command
            step_lower = clean_step.lower()
            is_typing_command = any(cmd in step_lower for cmd in ['escribe', 'escribir', 'teclea', 'teclear', 'type', 'enter', 'write', 'input'])
            
            if is_typing_command:
                # For typing commands, don't mark as needing OCR
                results.append({
                    "step": clean_step,
                    "needs_ocr": False,
                    "target": None
                })
                continue
            
            # Prepare the prompt for OCR target identification using the template from prompts.py
            prompt = IDENTIFY_OCR_TARGETS_PROMPT.format(step=clean_step)
            
            logger.debug(f"Sending request to Ollama API for OCR target identification of step: {clean_step}")
            
            # Make API request to Ollama
            start_time = time.time()
            response = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.1  # Use low temperature for more deterministic output
                },
                timeout=30
            )
            
            request_time = time.time() - start_time
            logger.debug(f"Ollama API request completed in {request_time:.2f} seconds with status code: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"Error from Ollama API: {response.status_code}")
                logger.error(f"Response content: {response.text[:500]}")
                results.append({"step": clean_step, "needs_ocr": False})
                continue
            
            # Parse response
            result = response.json()
            modified_step = result["response"].strip()
            logger.debug(f"Modified step from Ollama: {modified_step}")
            
            # Remove any bullet points or numbering from the response
            modified_step = re.sub(r'^[-\d.]\s*', '', modified_step).strip()
            
            # Check if the step contains any quoted text (indicating OCR targets)
            has_ocr_targets = '"' in modified_step
            step_result = {
                "step": modified_step,
                "needs_ocr": has_ocr_targets,
                "target": None
            }
            
            # If there are OCR targets, extract them
            if has_ocr_targets:
                # Extract text between quotes
                targets = re.findall(r'"([^"]+)"', modified_step)
                if targets:
                    # Use the first target as primary target
                    step_result["target"] = targets[0]
            
            results.append(step_result)
            
        logger.info(f"OCR target identification completed for {len(results)} steps")
        for i, step_data in enumerate(results):
            needs_ocr = step_data.get("needs_ocr", False)
            target = step_data.get("target", "None") if needs_ocr else "Not required"
            logger.info(f"Step {i+1}: '{step_data.get('step')}' - Needs OCR: {needs_ocr}, Target: '{target}'")
        
        return results
        
    except Exception as e:
        logger.error(f"Error identifying OCR targets: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return [{"step": step, "needs_ocr": False} for step in steps]

def generate_pyautogui_actions(steps_with_targets, model=OLLAMA_MODEL):
    """
    Generate PyAutoGUI code for each step.
    
    Args:
        steps_with_targets: List of steps with OCR targets identified
        model: LLM model to use
        
    Returns:
        List of dictionaries with PyAutoGUI commands and metadata
    """
    if not steps_with_targets:
        logger.debug("No steps with targets provided to generate_pyautogui_actions")
        return []
    
    logger.debug(f"Generating PyAutoGUI actions for {len(steps_with_targets)} steps")
    if DEBUG:
        logger.debug(f"Steps with targets: {json.dumps(steps_with_targets, indent=2)}")
        
    actions = []
    
    try:
        # Process each step individually
        for step_data in steps_with_targets:
            step = step_data.get('step', '')
            target = step_data.get('target')
            
            # Clean the step text
            clean_step = re.sub(r'^[-\d.]\s*', '', step).strip()
            
            # Make API request to Ollama
            start_time = time.time()
            response = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": model,
                    "prompt": GENERATE_PYAUTOGUI_ACTIONS_PROMPT.replace("{step}", clean_step),
                    "stream": False,
                    "temperature": 0.1
                },
                timeout=45  # Longer timeout for code generation
            )
            
            request_time = time.time() - start_time
            logger.debug(f"Ollama API request completed in {request_time:.2f} seconds with status code: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"Error from Ollama API: {response.status_code}")
                logger.error(f"Response content: {response.text[:500]}")
                # Add a placeholder if API call fails
                actions.append({
                    "pyautogui_cmd": f"print('Unable to generate command for: {clean_step}')",
                    "target": target,
                    "description": clean_step,
                    "error": "Failed to generate PyAutoGUI command"
                })
                continue
            
            # Parse response
            result = response.json()
            json_response = result["response"].strip()
            
            try:
                # Try to parse the JSON response
                # Extract just the JSON part if there's extra text
                json_start = json_response.find('{')
                json_end = json_response.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_content = json_response[json_start:json_end]
                    action_data = json.loads(json_content)
                    
                    # Extract the command from the response structure
                    if "pyautogui_cmd" in action_data:
                        cmd = action_data["pyautogui_cmd"]
                    elif "steps" in action_data and action_data["steps"]:
                        # If we got the new format response, extract the code from the first step
                        first_step = action_data["steps"][0]
                        cmd = first_step.get("code", "")
                        action_data["description"] = first_step.get("description", clean_step)
                    else:
                        cmd = ""
                    
                    # Validate the generated code
                    is_valid, disallowed_functions = validate_pyautogui_cmd(cmd)
                    
                    # Only consider the code invalid if disallowed functions were found
                    if not is_valid and disallowed_functions:
                        logger.warning(f"Generated code for step {clean_step} uses disallowed functions: {disallowed_functions}")
                        # Use a stripped-down version of the code or fallback
                        if "pyautogui.click" in cmd or "pyautogui.moveTo" in cmd:
                            cmd = "pyautogui.click(x=100, y=100)" if "pyautogui.click" in cmd else "pyautogui.moveTo(x=100, y=100)"
                        elif "pyautogui.write" in cmd:
                            cmd = "pyautogui.write('text')"
                        elif "pyautogui.press" in cmd:
                            cmd = "pyautogui.press('enter')" if "enter" in clean_step.lower() else "pyautogui.press('escape')"
                        else:
                            cmd = "# Skipping this step - validation failed"
                    
                    # Create the action data structure
                    action = {
                        "pyautogui_cmd": cmd,
                        "target": target,
                        "description": action_data.get("description", clean_step),
                        "original_step": clean_step
                    }
                    
                    actions.append(action)
                else:
                    # Fallback if JSON parsing fails
                    logger.warning(f"Could not extract JSON from response: {json_response}")
                    actions.append({
                        "pyautogui_cmd": f"print('Invalid response format for: {clean_step}')",
                        "target": target,
                        "description": clean_step,
                        "error": "Invalid JSON response format"
                    })
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON response: {json_response}")
                actions.append({
                    "pyautogui_cmd": f"print('JSON parsing error for: {clean_step}')",
                    "target": target,
                    "description": clean_step,
                    "error": "JSON parsing error"
                })
        
        logger.info(f"Generated {len(actions)} PyAutoGUI actions: {actions}")
        # Log the first few actions for debugging
        for i, action in enumerate(actions[:3]):  # Only log first 3 to avoid overwhelming logs
            logger.info(f"Action {i+1}: {action.get('description')} - Target: {action.get('target')}")
        if len(actions) > 3:
            logger.info(f"... and {len(actions) - 3} more actions")
            
        return actions
        
    except Exception as e:
        logger.error(f"Error generating PyAutoGUI actions: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return []

def process_command_pipeline(command, model=OLLAMA_MODEL):
    """
    Process the command through the full pipeline and return detailed information.
    
    Args:
        command: The command to process
        model: The LLM model to use
        
    Returns:
        Dictionary with detailed information about the processing pipeline
    """
    result = {
        "success": False,
        "original_command": command,
        "steps": [],
        "ui_description": None,
        "code": None,
        "error": None
    }
    
    try:
        # Capture a screenshot for UI analysis
        try:
            import pyautogui
            
            # Clean up old screenshots before capturing a new one
            max_age_days = int(os.environ.get("SCREENSHOT_MAX_AGE_DAYS", "1"))
            max_count = int(os.environ.get("SCREENSHOT_MAX_COUNT", "10"))
            cleanup_count, cleanup_error = cleanup_old_screenshots(max_age_days, max_count)
            if cleanup_error:
                logger.warning(f"Error cleaning up screenshots before capture: {cleanup_error}")
            else:
                logger.debug(f"Cleaned up {cleanup_count} old screenshots before capture")
            
            # Capture screenshot
            screenshot = pyautogui.screenshot()
            screenshot_path = os.path.join(get_screenshot_dir(), f"temp_screenshot_{int(time.time())}.png")
            screenshot.save(screenshot_path)
            
            # Get UI description
            try:
                ui_description = get_ui_description(screenshot_path)
                result["ui_description"] = ui_description
                
                # Save UI description to file alongside screenshot
                ui_desc_path = screenshot_path.replace('.png', '_ui_desc.json')
                from .server import sanitize_for_json
                with open(ui_desc_path, 'w') as f:
                    json.dump(sanitize_for_json(ui_description), f, indent=2)
                    
                # Create visualization of UI description
                ui_viz_path = screenshot_path.replace('.png', '_ui_viz.png')
                try:
                    import matplotlib
                    # Use 'Agg' backend which doesn't require a GUI
                    matplotlib.use('Agg')
                    import matplotlib.pyplot as plt
                    import cv2
                    
                    # Load the screenshot for visualization
                    image = cv2.imread(screenshot_path)
                    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                    
                    # Create the visualization
                    plt.figure(figsize=(16, 10))
                    plt.imshow(image_rgb)
                    
                    # Draw bounding boxes for all UI elements
                    for element in ui_description.get('elements', []):
                        bbox = element.get('bbox', [])
                        if len(bbox) == 4:  # Ensure we have valid bbox coordinates
                            x_min, y_min, x_max, y_max = bbox
                            
                            # Choose color based on element type
                            element_type = element.get('type', '').lower()
                            if 'button' in element_type:
                                color = 'red'
                            elif 'input' in element_type or 'field' in element_type:
                                color = 'blue'
                            elif 'menu' in element_type:
                                color = 'green'
                            else:
                                color = 'yellow'
                            
                            # Draw rectangle
                            plt.gca().add_patch(plt.Rectangle((x_min, y_min), x_max - x_min, y_max - y_min,
                                                           fill=False, edgecolor=color, linewidth=2))
                            
                            # Draw label with text if available
                            label = element.get('text', element.get('type', 'unknown'))
                            confidence = element.get('confidence', 0)
                            plt.text(x_min, y_min - 5, f"{label} ({confidence:.2f})",
                                   bbox={'facecolor': color, 'alpha': 0.5, 'pad': 2})
                    
                    plt.axis('off')
                    plt.savefig(ui_viz_path, bbox_inches='tight')
                    plt.close('all')  # Explicitly close all figures
                    
                    logger.info(f"UI visualization saved to {ui_viz_path}")
                except Exception as viz_err:
                    logger.warning(f"Error creating UI visualization: {viz_err}")
                    
                logger.info(f"UI description obtained with {len(ui_description.get('elements', []))} elements and saved to {ui_desc_path}")
            except Exception as ui_err:
                logger.warning(f"Error getting UI description: {ui_err}")
                # Continue with empty UI description
                result["ui_description"] = {"elements": []}
            
        except ImportError:
            logger.warning("PyAutoGUI not available for screenshot capture")
            # Continue without UI description
            result["ui_description"] = {"elements": []}
        
        # Step 1: Split the command into steps
        steps = split_command_into_steps(command, model=model)
        if not steps:
            result["error"] = "Failed to split command into steps"
            return result
        
        result["steps"] = steps
        
        # Step 2: Identify OCR targets
        steps_with_targets = identify_ocr_targets(steps, model=model)
        if not steps_with_targets:
            result["error"] = "Failed to identify OCR targets"
            return result
        
        result["steps_with_targets"] = steps_with_targets
        
        # Step 3: Generate PyAutoGUI actions
        # if result["ui_description"]:
        #     # Use the enhanced command processing if UI description is available
        #     try:
        #         enhanced_result = generate_pyautogui_code_with_ui_awareness(command, result["ui_description"])
        #         if enhanced_result and "code" in enhanced_result:
        #             result["code"] = {
        #                 "imports": "import pyautogui\nimport time",
        #                 "raw": enhanced_result["code"],
        #                 "explanation": enhanced_result.get("explanation", "")
        #             }
        #             result["success"] = True
                    
        #             # Log the enhanced code
        #             logger.debug(f"Generated enhanced PyAutoGUI code with UI awareness:\n{enhanced_result['code']}")
                    
        #             return result
        #     except Exception as e:
        #         logger.warning(f"Error using enhanced command processing: {e}")
        #         # Fall back to standard generation
        
        # Standard generation (fallback)
        actions = generate_pyautogui_actions(steps_with_targets, model=model)
        if not actions:
            result["error"] = "Failed to generate PyAutoGUI actions"
            return result
        
        result["actions"] = actions
        
        # Combine all actions into a single code block
        imports = "import pyautogui\nimport time"
        code_blocks = []
        
        for action in actions:
            if "pyautogui_cmd" in action and action["pyautogui_cmd"]:
                code_blocks.append(action["pyautogui_cmd"])
        
        combined_code = "\n\n".join(code_blocks)
        
        result["code"] = {
            "imports": imports,
            "raw": combined_code,
            "steps": actions
        }
        
        result["success"] = True
        
        return result
    
    except Exception as e:
        logger.error(f"Error in command pipeline: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
        
        return result

# Wrap execute_command_with_llm to add more logging
def execute_command_with_logging(command, model=OLLAMA_MODEL, ollama_host=OLLAMA_HOST):
    """
    Execute the given command with enhanced logging.
    
    Args:
        command: The command to execute
        model: The LLM model to use
        ollama_host: The Ollama API host
        
    Returns:
        Dictionary with the execution results
    """
    logger.debug(f"Executing command with logging: '{command}'")
    
    try:
        # Process command pipeline first to gather detailed debugging info
        pipeline_result = process_command_pipeline(command, model=model)
        
        # Check if pipeline processing was successful and has code
        if pipeline_result.get("success", False) and pipeline_result.get("code"):
            logger.info("Using processed pipeline code for execution")
            
            # Execute the processed code directly
            try:
                import pyautogui
                import time
                
                # Apply PyAutoGUI extensions
                if not hasattr(pyautogui, 'moveRelative'):
                    pyautogui.moveRelative = pyautogui.move
                
                # Set failsafe based on environment variable
                if os.environ.get("PYAUTOGUI_FAILSAFE", "false").lower() == "true":
                    pyautogui.FAILSAFE = True
                    logger.info("PyAutoGUI failsafe enabled (move mouse to upper-left corner to abort)")
                else:
                    pyautogui.FAILSAFE = False
                
                # Capture before screenshot if needed
                if os.environ.get("CAPTURE_SCREENSHOTS", "true").lower() != "false":
                    # Cleanup old screenshots before capturing a new one
                    max_age_days = int(os.environ.get("SCREENSHOT_MAX_AGE_DAYS", "1"))
                    max_count = int(os.environ.get("SCREENSHOT_MAX_COUNT", "10"))
                    cleanup_count, cleanup_error = cleanup_old_screenshots(max_age_days, max_count)
                    if cleanup_error:
                        logger.warning(f"Error cleaning up screenshots before 'before' capture: {cleanup_error}")
                    else:
                        logger.debug(f"Cleaned up {cleanup_count} old screenshots before 'before' capture")
                    
                    # Take a screenshot before execution
                    before_path = os.path.join(get_screenshot_dir(), f"before_{int(time.time())}.png")
                    pyautogui.screenshot().save(before_path)
                    logger.info(f"Captured before-execution screenshot: {before_path}")
                
                # Get the raw code from the pipeline result
                raw_code = ""
                if isinstance(pipeline_result["code"], dict) and "raw" in pipeline_result["code"]:
                    raw_code = pipeline_result["code"]["raw"]
                elif isinstance(pipeline_result["code"], str):
                    raw_code = pipeline_result["code"]
                    
                # Execute code in a temporary namespace
                namespace = {'pyautogui': pyautogui, 'time': time}
                logger.info(f"Executing generated PyAutoGUI code:\n{raw_code}")
                exec(raw_code, namespace)
                logger.info("Code execution completed successfully")
                
                # Capture after screenshot if needed
                if os.environ.get("CAPTURE_SCREENSHOTS", "true").lower() != "false":
                    # Wait a little for UI to update
                    time.sleep(1)

                    # Take a screenshot after execution
                    after_path = os.path.join(get_screenshot_dir(), f"after_{int(time.time())}.png")
                    pyautogui.screenshot().save(after_path)
                    logger.info(f"Captured after-execution screenshot: {after_path}")
                    
                    # Cleanup old screenshots after capturing a new one
                    max_age_days = int(os.environ.get("SCREENSHOT_MAX_AGE_DAYS", "1"))
                    max_count = int(os.environ.get("SCREENSHOT_MAX_COUNT", "10"))
                    cleanup_count, cleanup_error = cleanup_old_screenshots(max_age_days, max_count)
                    if cleanup_error:
                        logger.warning(f"Error cleaning up screenshots before 'after' capture: {cleanup_error}")
                    else:
                        logger.debug(f"Cleaned up {cleanup_count} old screenshots before 'after' capture")
                
                # Return success result
                return {
                    "success": True,
                    "command": command,
                    "pipeline": pipeline_result
                }
            
            except Exception as exec_error:
                logger.error(f"Error executing generated code: {str(exec_error)}")
                import traceback
                logger.error(traceback.format_exc())
                
                return {
                    "success": False,
                    "error": f"Error executing generated code: {str(exec_error)}",
                    "command": command,
                    "pipeline": pipeline_result
                }
        
        # Fall back to simple executor if pipeline processing failed
        logger.info("Pipeline processing failed or didn't produce code, falling back to simple executor")
        result = execute_command_with_llm(command, model=model, ollama_host=ollama_host)
        return result
    
    except Exception as e:
        logger.error(f"Error in execute_command_with_logging: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "success": False,
            "error": str(e),
            "command": command
        }
