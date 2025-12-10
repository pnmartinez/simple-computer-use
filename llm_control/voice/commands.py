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
from llm_control.voice.screenshots import capture_screenshot_with_name
from llm_control.voice.prompts import (
    TRANSLATION_PROMPT,
    SPLIT_COMMAND_PROMPT,
    IDENTIFY_OCR_TARGETS_PROMPT,
    GENERATE_PYAUTOGUI_ACTIONS_PROMPT
)

# Add imports for UI detection and command processing
try:
    from llm_control.command_processing.executor import generate_pyautogui_code_with_ui_awareness, process_single_step
    from llm_control.command_processing.finder import find_ui_element
    from llm_control.ui_detection.element_finder import detect_ui_elements_with_yolo
    from llm_control.ui_detection.element_finder import detect_text_regions, get_ui_description
    from llm_control.llm.text_extraction import ensure_text_is_safe_for_typewrite
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
            is_typing_command = any(cmd in step_lower for cmd in ['escribe', 'escribir', 'teclea', 'teclear', 'type', 'enter', 'write', 'input', 'presiona', 'presionar', 'press'])
            
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

def get_ui_snapshot(steps_with_targets):
    """
    Capture a screenshot and analyze the UI elements.

    Args:
        steps_with_targets: List of steps with OCR targets identified
    
    Returns:
        Dictionary containing UI description and paths to generated files
    """
    result = {"elements": [], "success": False}
    
    # Check if any step needs OCR
    any_step_needs_ocr = any(step.get('needs_ocr', False) for step in steps_with_targets)
    
    # If no step needs OCR, return minimal result without taking screenshot
    if not any_step_needs_ocr:
        logger.info("Skipping screenshot and OCR as no steps require it")
        result["success"] = True
        result["screenshot_skipped"] = True
        result["elements"] = []
        return result
    
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
        
        # Capture screenshot using helper function
        timestamp = int(time.time())
        screenshot_path = capture_screenshot_with_name(f"temp_screenshot_{timestamp}.png")
        if screenshot_path:
            result["screenshot_path"] = screenshot_path
        else:
            logger.error("Failed to capture screenshot")
            result["error"] = "Failed to capture screenshot"
            return result
        
        # Get UI description
        try:
            ui_description = get_ui_description(screenshot_path, steps_with_targets)
            result.update(ui_description)
            result["success"] = True
                
            logger.info(f"UI description obtained with {len(ui_description.get('elements', []))} elements")
        except Exception as ui_err:
            logger.warning(f"Error getting UI description: {ui_err}")
            
    except ImportError:
        logger.warning("PyAutoGUI not available for screenshot capture")
        
    return result

def process_command_pipeline(command, model=OLLAMA_MODEL):
    """Process a command through the full pipeline: split into steps, identify OCR targets, generate and execute code.
    
    Args:
        command: The command string to process
        model: The LLM model to use for processing
        
    Returns:
        Dictionary containing the processing results
    """
    logger.info(f"Processing command through pipeline: '{command}'")
    
    # Initialize result
    result = {
        "command": command,
        "model": model,
        "success": False,
        "error": None,
        "ui_description": None,
        "steps": [],
        "steps_with_targets": [],
        "code": None
    }
        
    # Step 1: Split the command into steps
    steps = split_command_into_steps(command, model=model)
    if not steps:
        result["error"] = "Failed to split command into steps"
        return result
    
    result["steps"] = steps
    
    # Step 2: Identify OCR targets, if any, in the strings
    steps_with_targets = identify_ocr_targets(steps, model=model)
    if not steps_with_targets:
        result["error"] = "Failed to identify OCR targets"
        return result

    result["steps_with_targets"] = steps_with_targets
    
    # Check if any step needs OCR
    any_step_needs_ocr = any(step.get('needs_ocr', False) for step in steps_with_targets)
    
    # Get UI snapshot (screenshot and UI description) only if needed
    if any_step_needs_ocr:
        ui_snapshot = get_ui_snapshot(steps_with_targets)
        if ui_snapshot.get("success", False):
            result["ui_description"] = ui_snapshot
        else:
            # Continue with empty UI description
            result["ui_description"] = {"elements": []}
    else:
        # Skip UI detection completely for typing-only commands
        result["ui_description"] = {"elements": [], "screenshot_skipped": True}
        logger.info("Skipping UI detection completely as no steps require OCR")
    
    # Step 3: Generate PyAutoGUI actions based on command types
    # For pure typing commands, we can generate code directly without complex UI processing
    all_typing_commands = all(not step.get('needs_ocr', False) for step in steps_with_targets)
    
    if all_typing_commands:
        # Fast path for typing commands
        try:
            code_blocks = []
            explanations = []
            
            # Generate simple PyAutoGUI code for typing commands directly
            for step_data in steps_with_targets:
                step = step_data.get('step', '')
                
                # Simple parsing for typing commands
                if "escribe" in step.lower() or "teclea" in step.lower() or "type" in step.lower() or "write" in step.lower():
                    # Try to use the LLM text extraction first if available
                    text_to_type = ""
                    try:
                        from llm_control.llm.text_extraction import extract_text_to_type_with_llm
                        text_to_type = extract_text_to_type_with_llm(step)
                        logger.info(f"Using LLM text extraction: '{text_to_type}'")
                    except ImportError:
                        logger.warning("LLM text extraction module not available, using regex fallback")
                    
                    # Fall back to regex if LLM extraction failed or returned empty
                    if not text_to_type:
                        # Pattern 1: Try to match text after a typing command (with or without quotes)
                        match = re.search(r'(?:escribe|teclea|type|write|escribir|teclear)(?:\s+[\'"]?([^\'"]+)[\'"]?)', step.lower())
                        if match:
                            text_to_type = match.group(1)
                        else:
                            # Pattern 2: Split by the typing command and take everything after it
                            typing_commands = ['escribe', 'teclea', 'type', 'write', 'escribir', 'teclear']
                            for cmd in typing_commands:
                                if cmd in step.lower():
                                    parts = re.split(rf'\b{cmd}\b', step, flags=re.IGNORECASE, maxsplit=1)
                                    if len(parts) > 1:
                                        text_to_type = parts[1].strip()
                                        break
                        
                        logger.info(f"Using regex fallback text extraction: '{text_to_type}'")
                    
                    # If we found text to type, add it to the code blocks
                    if text_to_type:
                        # Ensure text is safe for pyautogui
                        safe_text = ensure_text_is_safe_for_typewrite(text_to_type)
                        code = f"# Write text\npyautogui.typewrite('{safe_text}')"
                        code_blocks.append(code)
                        explanations.append(f"Type the text: '{text_to_type}'")
                
                elif "enter" in step.lower() or "return" in step.lower():
                    code = "# Press Enter\npyautogui.press('enter')"
                    code_blocks.append(code)
                    explanations.append("Press the Enter key")
                
                elif "tab" in step.lower():
                    code = "# Press Tab\npyautogui.press('tab')"
                    code_blocks.append(code)
                    explanations.append("Press the Tab key")
                
                # Add more keyboard shortcuts as needed
                
            if code_blocks:
                # Combine code blocks with pauses between steps
                combined_code = "# Generated from multiple typing steps\nimport pyautogui\nimport time\n\n"
                for i, code in enumerate(code_blocks):
                    combined_code += f"# Step {i+1}\n{code}\n"
                    if i < len(code_blocks) - 1:
                        combined_code += "time.sleep(0.5)  # Pause between steps\n\n"
                
                result["code"] = {
                    "imports": "import pyautogui\nimport time",
                    "raw": combined_code,
                    "explanation": "\n".join(explanations)
                }
                result["success"] = True
                logger.info("Generated simplified PyAutoGUI code for typing commands")
                return result
        except Exception as e:
            logger.warning(f"Error in fast path for typing commands: {e}")
            # Continue with normal processing if fast path fails
    
    # Use the enhanced command processing if UI description is available or we had issues with fast path
    if result["ui_description"] is not None:
        try:
            # Use the segmented steps we already identified
            code_blocks = []
            explanations = []
            
            # Process each step with UI awareness
            processed_count = 0
            skipped_count = 0
            for i, step_data in enumerate(steps_with_targets):
                step = step_data.get('step', '')
                target = step_data.get('target')
                
                try:
                    # Process single step with UI awareness
                    step_result = process_single_step(step, result["ui_description"])
                    
                    if step_result and "code" in step_result and step_result["code"]:
                        code_blocks.append(step_result["code"])
                        if "explanation" in step_result:
                            explanations.append(step_result["explanation"])
                        processed_count += 1
                    else:
                        skipped_count += 1
                        logger.warning(f"Step {i+1} ('{step}') did not generate code in pipeline processing")
                except Exception as e:
                    skipped_count += 1
                    logger.error(f"Error processing step {i+1} ('{step}') in pipeline: {str(e)}")
            
            # Log summary
            if skipped_count > 0:
                logger.warning(f"Pipeline processing: {processed_count} steps processed, {skipped_count} steps skipped out of {len(steps_with_targets)} total")
            
            if code_blocks:
                # Combine code blocks with pauses between steps
                combined_code = "# Generated from multiple steps\nimport time\n\n"
                for i, code in enumerate(code_blocks):
                    combined_code += f"# Step {i+1}\n{code}\n"
                    if i < len(code_blocks) - 1:
                        combined_code += "time.sleep(0.5)  # Pause between steps\n\n"
                
                result["code"] = {
                    "imports": "import pyautogui\nimport time",
                    "raw": combined_code,
                    "explanation": "\n".join(explanations)
                }
                result["success"] = True
                
                logger.debug(f"Generated enhanced PyAutoGUI code with UI awareness:\n{combined_code}")
                return result
        
        except Exception as e:
            logger.warning(f"Error using enhanced command processing: {e}")
            # Fall back to standard generation
    
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
    
    # Check if this is a pure typing command to determine if we need screenshots
    is_typing_command = any(cmd in command.lower() for cmd in ['escribe', 'escribir', 'teclea', 'teclear', 'type', 'enter', 'write', 'input', 'presiona', 'presionar', 'press'])
    capture_screenshot = not is_typing_command
    
    if is_typing_command:
        logger.info("Detected typing command, screenshots will be skipped")
        
        # Log if special characters are present in the command
        if any(c in command for c in ['á', 'é', 'í', 'ó', 'ú', 'ñ', 'ü', '¿', '¡']):
            logger.info("Command contains special characters that will be sanitized for typing")
    
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
                if capture_screenshot:
                    # Cleanup old screenshots before capturing a new one
                    max_age_days = int(os.environ.get("SCREENSHOT_MAX_AGE_DAYS", "1"))
                    max_count = int(os.environ.get("SCREENSHOT_MAX_COUNT", "10"))
                    cleanup_count, cleanup_error = cleanup_old_screenshots(max_age_days, max_count)
                    if cleanup_error:
                        logger.warning(f"Error cleaning up screenshots before 'before' capture: {cleanup_error}")
                    else:
                        logger.debug(f"Cleaned up {cleanup_count} old screenshots before 'before' capture")
                    
                    # Take a screenshot before execution using helper function
                    before_path = capture_screenshot_with_name(f"before_{int(time.time())}.png")
                    if before_path:
                        logger.info(f"Captured before-execution screenshot: {before_path}")
                    else:
                        logger.warning("Failed to capture before-execution screenshot")
                
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
                if capture_screenshot:
                    # Wait a little for UI to update
                    time.sleep(1)

                    # Take a screenshot after execution using helper function
                    after_path = capture_screenshot_with_name(f"after_{int(time.time())}.png")
                    if after_path:
                        logger.info(f"Captured after-execution screenshot: {after_path}")
                    else:
                        logger.warning("Failed to capture after-execution screenshot")
                    
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
        # Log this event with detailed information for monitoring
        pipeline_success = pipeline_result.get("success", False)
        pipeline_has_code = bool(pipeline_result.get("code"))
        pipeline_error = pipeline_result.get("error", "Unknown error")
        
        logger.warning(
            f"⚠️ FALLBACK TRIGGERED: Pipeline processing failed, falling back to simple_executor. "
            f"Command: '{command}', Pipeline success: {pipeline_success}, "
            f"Has code: {pipeline_has_code}, Error: {pipeline_error}"
        )
        
        # Emit structured log event for monitoring
        try:
            from llm_control import structured_usage_log
            structured_usage_log(
                "command.fallback.triggered",
                command=command,
                pipeline_success=pipeline_success,
                pipeline_has_code=pipeline_has_code,
                pipeline_error=pipeline_error,
                fallback_type="simple_executor",
                model=model,
                ollama_host=ollama_host
            )
        except ImportError:
            # If structured logging is not available, continue without it
            pass
        
        result = execute_command_with_llm(command, model=model, ollama_host=ollama_host)
        
        # Log the result of the fallback execution
        fallback_success = result.get("success", False)
        if fallback_success:
            logger.info(f"✅ Fallback execution succeeded for command: '{command}'")
        else:
            logger.error(
                f"❌ Fallback execution failed for command: '{command}'. "
                f"Error: {result.get('error', 'Unknown error')}"
            )
        
        return result
    
    except Exception as e:
        logger.error(f"Error in execute_command_with_logging: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
        
        return result
