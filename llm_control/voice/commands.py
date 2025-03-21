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

# Configure logging
logger = logging.getLogger("voice-control-commands")

# Import from our modules
from llm_control.voice.utils import clean_llm_response

# Constants
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# Import from our own modules if available
try:
    from llm_control.llm.simple_executor import execute_command_with_llm
except ImportError:
    # Define a stub function if we can't import
    def execute_command_with_llm(command, model="llama3.1", ollama_host="http://localhost:11434"):
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
    allowed_functions = [
        "pyautogui.moveTo", "pyautogui.move", "pyautogui.moveRelative", "pyautogui.click", 
        "pyautogui.doubleClick", "pyautogui.rightClick", "pyautogui.dragTo",
        "pyautogui.write", "pyautogui.press", "pyautogui.hotkey",
        "pyautogui.scroll", "pyautogui.screenshot",
        # Allow these basic utility functions as well
        "pyautogui.FAILSAFE", "pyautogui.size", "pyautogui.position"
    ]
    
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
                    try:
                        # Extract the function name
                        func_start = part.find("pyautogui.") + 10
                        func_end = part.find("(", func_start)
                        if func_end > func_start:
                            disallowed_functions.append(part[func_start:func_end])
                    except:
                        # If we can't extract the function name, just add the whole part
                        disallowed_functions.append(part)
            continue
            
        # Handle lines with comments
        if '#' in line:
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
                try:
                    # Extract the function name
                    func_start = line.find("pyautogui.") + 10
                    func_end = line.find("(", func_start)
                    if func_end > func_start:
                        disallowed_functions.append(line[func_start:func_end])
                except:
                    # If we can't extract the function name, just add the whole line
                    disallowed_functions.append(line)
    
    # Remove duplicates
    disallowed_functions = list(set(disallowed_functions))
    
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
    try:
        steps_str = "\n".join([f"- {step}" for step in steps])
        
        # Prepare the prompt for verification
        prompt = f"""
        I need you to verify that these parsed steps correctly represent the user's command.
        
        Original command: "{original_command}"
        
        Parsed steps:
        {steps_str}
        
        Please verify:
        1. Do the steps accurately reflect the intent of the original command?
        2. Are there any missing actions that were in the original command?
        3. Are there any steps that weren't asked for in the original command?
        
        Return only JSON in this format:
        {{
          "is_valid": true/false,
          "reason": "explanation if invalid"
        }}
        """
        
        # Make API request to Ollama
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"Error from Ollama API: {response.status_code}")
            return False, "Error communicating with Ollama API"
        
        # Parse response
        result = response.json()
        text_response = result["response"].strip()
        
        # Extract JSON
        try:
            # Find JSON in the response
            json_start = text_response.find('{')
            json_end = text_response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = text_response[json_start:json_end]
                verification = json.loads(json_str)
                
                if 'is_valid' in verification:
                    return verification.get('is_valid'), verification.get('reason', '')
                else:
                    return False, "Invalid verification response format"
            else:
                return False, "Could not find JSON in verification response"
        except json.JSONDecodeError:
            return False, "Invalid JSON in verification response"
        except Exception as e:
            return False, f"Error parsing verification: {str(e)}"
    
    except Exception as e:
        logger.error(f"Error verifying command integrity: {str(e)}")
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
    try:
        # Prepare the prompt for step splitting
        prompt = f"""
        I need you to divide this user command into a sequence of specific steps for automation.
        
        USER COMMAND: "{command}"
        
        I need you to:
        
        1. Break down this command into CLEAR, SPECIFIC, SELF-CONTAINED steps.
        2. Each step should describe a SINGLE ACTION, like "click", "type", "move", etc.
        3. If there are multiple locations or targets, create a separate step for each.
        4. Do not include explanations or commentary, only the direct steps.
        5. Steps should follow a logical sequence.
        6. Include EVERY detail needed for each action (exact text to type, specific elements to click, etc.)
        
        FORMAT YOUR RESPONSE LIKE THIS:
        ```
        1. [First step action]
        2. [Second step action]
        ```
        
        NOTHING ELSE - NO EXPLANATIONS BEFORE OR AFTER.
        """
        
        # Make API request to Ollama
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"Error from Ollama API: {response.status_code}")
            return None
        
        # Parse response
        result = response.json()
        steps_text = result["response"].strip()
        
        # Clean and extract the steps
        steps = []
        
        # Remove any code blocks
        steps_text = steps_text.replace("```", "").strip()
        
        # Extract steps by matching numbered lines
        step_pattern = re.compile(r'^\s*(\d+)\.\s+(.+)$', re.MULTILINE)
        matches = step_pattern.findall(steps_text)
        
        for _, step in matches:
            steps.append(step.strip())
        
        # If no steps were found, try another approach to extract lines
        if not steps:
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
        return []
        
    try:
        # Prepare the prompt for OCR target identification
        steps_str = "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps)])
        
        prompt = f"""
        I need you to analyze these automation steps and identify which ones need OCR (Optical Character Recognition) to find UI elements on screen.
        
        STEPS:
        {steps_str}
        
        For EACH step, determine:
        1. If it's trying to interact with a visible UI element (button, link, menu item, icon, text field, etc.)
        2. Exactly what TEXT or VISUAL ELEMENT the step is looking for (the "target")
        
        RETURN ONLY A JSON ARRAY with this format:
        ```
        [
          {{
            "step": "original step text",
            "needs_ocr": true/false,
            "target": "text to look for" (only if needs_ocr is true)
          }},
          // repeat for each step
        ]
        ```
        
        NO EXPLANATIONS BEFORE OR AFTER. JUST THE JSON. The JSON must be properly formatted.
        """
        
        # Make API request to Ollama
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"Error from Ollama API: {response.status_code}")
            return steps  # Return original steps if API call fails
        
        # Parse response
        result = response.json()
        analysis_text = result["response"].strip()
        
        # Extract JSON
        try:
            # Strip any surrounding non-JSON text
            json_start = analysis_text.find('[')
            json_end = analysis_text.rfind(']') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = analysis_text[json_start:json_end]
                steps_with_targets = json.loads(json_str)
                
                return steps_with_targets
            else:
                logger.error("Could not find JSON array in response")
                return [{"step": step, "needs_ocr": False} for step in steps]
        
        except json.JSONDecodeError:
            logger.error("Invalid JSON in response")
            return [{"step": step, "needs_ocr": False} for step in steps]
            
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
        Dictionary with PyAutoGUI code for each step
    """
    if not steps_with_targets:
        return {}
        
    try:
        # Prepare the prompt for code generation
        steps_json = json.dumps(steps_with_targets, indent=2)
        
        prompt = f"""
        I need you to generate PyAutoGUI code for each of these steps.
        
        STEPS WITH TARGETS:
        ```
        {steps_json}
        ```
        
        For each step, generate the PyAutoGUI code to perform that action.
        
        IMPORTANT CODE RULES:
        1. Use ONLY these PyAutoGUI functions: moveTo, move, click, doubleClick, rightClick, dragTo, write, press, hotkey, scroll
        2. Add a 0.5 second sleep between actions: time.sleep(0.5)
        3. Use proper error handling
        4. For "type" or "write" actions, use pyautogui.write('exact text')
        5. For keyboard shortcuts, use pyautogui.hotkey('key1', 'key2', ...)
        6. Use RELATIVE movements when possible
        7. Make code resilient - add try/except blocks
        
        RETURN ONLY A JSON OBJECT with this format:
        ```
        {{
          "imports": "import pyautogui\\nimport time",
          "steps": [
            {{
              "original": "original step text",
              "code": "python code for this step"
            }},
            // repeat for each step
          ]
        }}
        ```
        
        NO EXPLANATIONS BEFORE OR AFTER. JUST THE JSON. The JSON must be properly formatted.
        """
        
        # Make API request to Ollama
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            timeout=45  # Longer timeout for code generation
        )
        
        if response.status_code != 200:
            logger.error(f"Error from Ollama API: {response.status_code}")
            return {}
        
        # Parse response
        result = response.json()
        code_text = result["response"].strip()
        
        # Extract JSON
        try:
            # Strip any surrounding non-JSON text
            json_start = code_text.find('{')
            json_end = code_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = code_text[json_start:json_end]
                actions = json.loads(json_str)
                
                return actions
            else:
                logger.error("Could not find JSON object in response")
                return {}
        
        except json.JSONDecodeError:
            logger.error("Invalid JSON in response")
            return {}
            
    except Exception as e:
        logger.error(f"Error generating PyAutoGUI actions: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {}
