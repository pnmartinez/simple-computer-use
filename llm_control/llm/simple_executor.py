"""
Simple command executor module.

This module provides functionality to execute commands directly using LLMs to generate
PyAutoGUI code, simplifying the command processing pipeline.
"""

import os
import sys
import time
import logging
import tempfile
import json
import io
import subprocess
import requests
from typing import Dict, Any, Optional, List, Union, Tuple
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Get the logger
logger = logging.getLogger("simple-executor")

# Import PyAutoGUI extensions from utils (already auto-executes on import)
try:
    from llm_control.utils import add_pyautogui_extensions
    # Extensions are already added when utils is imported, but we ensure it's called
    add_pyautogui_extensions()
except ImportError:
    logger.warning("Could not import PyAutoGUI extensions from utils")

def execute_command_with_llm(command: str, 
                          model: str = "gemma3:12b", 
                          ollama_host: str = "http://localhost:11434",
                          timeout: int = 30,
                          safe_mode: bool = False,
                          dry_run: bool = False,
                          capture_screenshot: bool = True) -> Dict[str, Any]:
    logger.info(f"Executing command with LLM: {command}")
    
    try:
        if command.strip().startswith('pyautogui.') or 'import pyautogui' in command:
            code = command
            logger.info("Using provided PyAutoGUI code directly")
        else:
            # Determine if the command likely requires visual targeting
            visual_keywords = [
                " box ", " button ", " choose ", " click ", " dialog ", " find ", " go ",
                " icon ", " locate ", " menu ", " move ", " navigate to ", " open ", 
                " select ", " tab ", " window "
            ]
            
            needs_visual_targeting = False
            for keyword in visual_keywords:
                if keyword in command.lower():
                    needs_visual_targeting = True
                    logger.info(f"Visual targeting needed - triggered by keyword: '{keyword}'")
                    break
            
            # Choose the appropriate code generation method
            if needs_visual_targeting:
                logger.info("Command appears to need visual targeting, using vision-based generation")
                code_result = generate_pyautogui_code_with_vision(command, model, ollama_host, timeout)
            else:
                logger.info("Using standard code generation")
                code_result = generate_pyautogui_code(command, model, ollama_host, timeout)
            
            if not code_result.get("success", False):
                return {
                    "success": False,
                    "error": code_result.get("error", "Failed to generate PyAutoGUI code"),
                    "command": command
                }
            
            code = code_result.get("code", "")
            
            if not code:
                return {
                    "success": False,
                    "error": "Generated code is empty",
                    "command": command
                }
        
        allowed_functions = [
            "pyautogui.moveTo", "pyautogui.move", "pyautogui.moveRelative", "pyautogui.click", 
            "pyautogui.doubleClick", "pyautogui.rightClick", "pyautogui.dragTo",
            "pyautogui.write", "pyautogui.press", "pyautogui.hotkey",
            "pyautogui.scroll", "pyautogui.screenshot",
            "pyautogui.FAILSAFE", "pyautogui.size", "pyautogui.position",
            "time.sleep", "import pyautogui", "import time", "print"
        ]
        
        clean_code = clean_pyautogui_code(code)
        
        is_valid = True
        disallowed_functions = []
        
        for line in clean_code.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if line.startswith('import ') or line.startswith('from ') or line.startswith('print('):
                continue
            
            if not any(func in line for func in allowed_functions):
                is_valid = False
                if "pyautogui." in line:
                    func_start = line.find("pyautogui.") + 10
                    func_end = line.find("(", func_start)
                    if func_end > func_start:
                        disallowed_functions.append(line[func_start:func_end])
        
        # Only consider it invalid if we actually found disallowed functions
        if not is_valid and disallowed_functions:
            logger.warning(f"Code uses disallowed functions: {disallowed_functions}")
            return {
                "success": False,
                "error": f"Generated code uses disallowed functions: {', '.join(disallowed_functions)}",
                "command": command,
                "code": code
            }
        
        if dry_run:
            logger.info("Dry run mode, not executing the code")
            
            # Take initial screenshot if requested
            screenshot_data = None
            if capture_screenshot:
                try:
                    import pyautogui
                    import base64
                    import io
                    from PIL import Image
                    
                    # Capture screenshot
                    screenshot = pyautogui.screenshot()
                    
                    # Convert to base64
                    buffered = io.BytesIO()
                    screenshot.save(buffered, format="PNG")
                    screenshot_data = base64.b64encode(buffered.getvalue()).decode('utf-8')
                    
                    logger.info("Captured initial screenshot for dry run")
                except Exception as ss_error:
                    logger.error(f"Error capturing screenshot: {str(ss_error)}")
            
            return {
                "success": True,
                "command": command,
                "code": clean_code,
                "dry_run": True,
                "screenshot": screenshot_data
            }
        
        # Execute the code
        execution_result = execute_pyautogui_code(clean_code, safe_mode)
        
        # Capture final state screenshot if requested
        screenshot_data = None
        if capture_screenshot:
            try:
                import pyautogui
                import base64
                import io
                from PIL import Image
                
                # Give UI a moment to settle
                time.sleep(0.5)
                
                # Capture screenshot
                screenshot = pyautogui.screenshot()
                
                # Convert to base64
                buffered = io.BytesIO()
                screenshot.save(buffered, format="PNG")
                screenshot_data = base64.b64encode(buffered.getvalue()).decode('utf-8')
                
                logger.info("Captured final state screenshot")
            except Exception as ss_error:
                logger.error(f"Error capturing screenshot: {str(ss_error)}")
        
        # Return the result
        return {
            "success": execution_result.get("success", False),
            "command": command,
            "code": clean_code,
            "error": execution_result.get("error", None),
            "output": execution_result.get("output", ""),
            "screenshot": screenshot_data
        }
    
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "success": False,
            "error": str(e),
            "command": command
        }

def generate_pyautogui_code(command: str, 
                         model: str = "llama3", 
                         ollama_host: str = "http://localhost:11434",
                         timeout: int = 30) -> Dict[str, Any]:
    """
    Generate PyAutoGUI code for a given command using an LLM.
    
    Args:
        command: The command to execute (e.g., "click on the Firefox icon")
        model: The Ollama model to use
        ollama_host: The Ollama API host
        timeout: Timeout for the Ollama API request
        
    Returns:
        Dictionary with the generated code and success status
    """
    logger.info(f"Generating PyAutoGUI code for command: {command}")
    
    try:
        # Check if Ollama is running
        try:
            response = requests.get(f"{ollama_host}/api/tags", timeout=2)
            if response.status_code != 200:
                logger.error(f"Ollama server not responding at {ollama_host}")
                return {
                    "success": False,
                    "error": f"Ollama server not responding at {ollama_host}"
                }
        except requests.exceptions.RequestException:
            logger.error(f"Ollama server not available at {ollama_host}")
            return {
                "success": False,
                "error": f"Ollama server not available at {ollama_host}"
            }
        
        # Prepare the prompt for code generation
        prompt = f"""
        You are a desktop automation assistant. Your task is to generate PyAutoGUI code to execute the following command:
        
        ```
        {command}
        ```
        
        IMPORTANT GUIDELINES:
        
        1. ONLY generate Python code using the pyautogui module.
        2. ALWAYS import pyautogui at the beginning of your code.
        3. DO NOT include any explanations, comments, or markdown - ONLY valid Python code.
        4. Ensure your code is complete and executable as a standalone script.
        5. ONLY use these allowed PyAutoGUI functions:
           - Mouse: moveTo, move, click, doubleClick, rightClick, dragTo
           - Keyboard: write, press, hotkey
           - Other: scroll, screenshot, FAILSAFE, size, position
        6. Implement sleeps (0.5-1s) between actions to account for UI responsiveness.
        7. For typing special keys, use pyautogui.press() with the key name (e.g., 'enter', 'tab').
        8. For combinations like Ctrl+C, use pyautogui.hotkey('ctrl', 'c').
        9. Set pyautogui.FAILSAFE = False at the beginning for uninterrupted operation.
        10. Add appropriate delays for UI elements to appear using time.sleep().
        
        Here are some code examples for common tasks:
        
        Clicking on an element:
        ```python
        import pyautogui
        import time
        pyautogui.FAILSAFE = False
        
        # Click on a specific position
        pyautogui.click(x=100, y=200)
        
        # Or find and click on an image (simplified approach)
        # Click where the element should be
        pyautogui.click(x=500, y=300)  # Position where element is expected
        ```
        
        Typing text:
        ```python
        import pyautogui
        import time
        pyautogui.FAILSAFE = False
        
        # Click on a text field
        pyautogui.click(x=300, y=400)
        time.sleep(0.5)
        # Type text
        pyautogui.write("Hello world", interval=0.05)
        # Press Enter
        pyautogui.press('enter')
        ```
        
        Using keyboard shortcuts:
        ```python
        import pyautogui
        import time
        pyautogui.FAILSAFE = False
        
        # Copy selected text
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(0.5)
        # Paste
        pyautogui.hotkey('ctrl', 'v')
        ```
        """

        print(f"DEBUG: Prompt to generate pyautogui code: {prompt}")
        # Make API request to Ollama
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            timeout=timeout
        )
        
        if response.status_code != 200:
            logger.error(f"Error from Ollama API: {response.status_code}")
            return {
                "success": False,
                "error": f"Ollama API error: {response.status_code}"
            }
        
        # Parse response
        result = response.json()
        code = result.get("response", "").strip()
        
        # Clean up the response
        # Remove any markdown code blocks
        code = code.replace("```python", "").replace("```", "").strip()
        
        logger.info(f"Generated PyAutoGUI code: {len(code)} characters")
        
        return {
            "success": True,
            "code": code
        }
        
    except Exception as e:
        logger.error(f"Error generating PyAutoGUI code: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "success": False,
            "error": str(e)
        }

def clean_pyautogui_code(code: str) -> str:
    """
    Clean generated PyAutoGUI code, removing unnecessary parts and ensuring it follows best practices.
    
    Args:
        code: Raw PyAutoGUI code generated by LLM
        
    Returns:
        Cleaned code
    """
    if not code:
        return ""
    
    # Remove markdown code blocks
    cleaned = code.replace("```python", "").replace("```", "").strip()
    
    # Ensure imports are present
    has_pyautogui_import = False
    has_time_import = False
    has_failsafe = False
    
    for line in cleaned.split('\n'):
        if "import pyautogui" in line:
            has_pyautogui_import = True
        if "import time" in line:
            has_time_import = True
        if "pyautogui.FAILSAFE" in line:
            has_failsafe = True
    
    lines = []
    
    # Add missing imports and failsafe
    if not has_pyautogui_import:
        lines.append("import pyautogui")
    
    if not has_time_import and "time.sleep" in cleaned:
        lines.append("import time")
    
    if not has_failsafe:
        lines.append("pyautogui.FAILSAFE = False")
    
    # Add the rest of the code
    lines.extend([line for line in cleaned.split('\n') if not (
        "import pyautogui" in line or 
        "import time" in line or 
        "pyautogui.FAILSAFE" in line
    )])
    
    return "\n".join(lines)

def find_visual_target(target_text: str) -> Dict[str, Any]:
    """
    Find a visual target on the screen based on text description.
    
    Args:
        target_text: The text or description of the UI element to find
        
    Returns:
        Dictionary with information about the found target, including coordinates
    """
    logger.info(f"Looking for visual target: '{target_text}'")
    
    try:
        # Import necessary modules
        import pyautogui
        
        try:
            from llm_control.ui_detection.element_finder import (
                detect_ui_elements_with_yolo, 
                detect_text_regions,
                get_center_point
            )
        except ImportError as e:
            logger.error(f"UI detection module import error: {str(e)}")
            import traceback
            logger.error(f"Full import traceback: {traceback.format_exc()}")
            logger.warning("UI detection module not available, using direct coordinate input")
            return {
                "success": False,
                "error": f"UI detection module not available: {str(e)}",
                "traceback": traceback.format_exc()
            }
        
        # Take a screenshot
        screenshot = pyautogui.screenshot()
        screenshot_path = tempfile.mktemp(suffix='.png')
        screenshot.save(screenshot_path)
        
        # Search for UI elements using YOLO
        ui_elements = detect_ui_elements_with_yolo(screenshot_path)
        
        # Search for text regions (OCR)
        text_regions = detect_text_regions(screenshot_path)
        
        # Combine UI elements and text regions
        all_ui_elements = ui_elements + text_regions
        
        logger.info(f"Found {len(ui_elements)} UI elements and {len(text_regions)} text regions")
        
        # Normalize the target text for comparison
        normalized_target = target_text.lower()
        
        # Find potential matches and their confidence scores
        matches = []
        
        # Search in UI elements
        for elem in all_ui_elements:
            if 'text' in elem and elem['text']:
                # Normalize element text
                elem_text = elem['text'].lower()
                
                # Calculate a simple score based on substring matching
                if normalized_target == elem_text:
                    # Exact match
                    score = 1.0
                elif normalized_target in elem_text:
                    # Substring match - score based on relative length
                    score = len(normalized_target) / len(elem_text)
                elif elem_text in normalized_target:
                    # Element text is substring of target
                    score = len(elem_text) / len(normalized_target)
                else:
                    # Partial word matching for more fuzzy matches
                    target_words = normalized_target.split()
                    elem_words = elem_text.split()
                    common_words = set(target_words) & set(elem_words)
                    
                    if common_words:
                        score = len(common_words) / max(len(target_words), len(elem_words))
                    else:
                        # No word match
                        score = 0.0
                
                # Only add if there's some match
                if score > 0.0:
                    match_info = {
                        'text': elem['text'],
                        'bbox': elem.get('bbox', [0, 0, 0, 0]),
                        'confidence': score,
                        'type': elem.get('type', 'text')
                    }
                    matches.append(match_info)
        
        # Sort matches by confidence (highest first)
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Log the top matches for debugging
        logger.info(f"Found {len(matches)} potential matches for target: '{target_text}'")
        
        # Log the top 3 matches (or fewer if there aren't that many)
        for i, match in enumerate(matches[:3]):
            logger.info(f"Match #{i+1}: '{match['text']}' at confidence {match['confidence']:.2f}, type: {match['type']}")
        
        # Save the screenshot with detected targets highlighted for debugging
        try:
            # Import PIL modules here to avoid requiring them at the top level
            from PIL import Image, ImageDraw, ImageFont
            
            # Load the original screenshot
            img = Image.open(screenshot_path)
            draw = ImageDraw.Draw(img)
            
            # Get a font for drawing text
            try:
                # Try to load a system font (adjust path as needed)
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            except:
                font = ImageFont.load_default()
            
            # Draw bounding boxes for all potential matches
            for i, match in enumerate(matches[:10]):  # Limit to top 10 matches
                if 'bbox' in match:
                    bbox = match['bbox']
                    # Draw rectangle around the element
                    color = (255, 0, 0) if i == 0 else (0, 255, 0)  # Red for best match, green for others
                    draw.rectangle(bbox, outline=color, width=2)
                    
                    # Draw text with confidence score
                    text = f"{match['text']} ({match['confidence']:.2f})"
                    # Position text above the bbox
                    text_pos = (bbox[0], bbox[1] - 15)
                    # Add a background rectangle for the text for better visibility
                    text_size = draw.textbbox(text_pos, text, font=font)
                    draw.rectangle((text_size[0]-2, text_size[1]-2, text_size[2]+2, text_size[3]+2), fill=(255, 255, 255, 180))
                    draw.text(text_pos, text, fill=color, font=font)
            
            # Add the target text at the top
            draw.text((10, 10), f"Target: '{target_text}'", fill=(0, 0, 255), font=font)
            
            # Get screenshot directory from environment and ensure it's absolute
            screenshot_dir = os.environ.get("SCREENSHOT_DIR", ".")
            if not os.path.isabs(screenshot_dir):
                # If it's a relative path, make it absolute from the workspace root
                workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                screenshot_dir = os.path.join(workspace_root, screenshot_dir)
            
            # Create directory if it doesn't exist
            os.makedirs(screenshot_dir, exist_ok=True)
            
            # Save the annotated image
            annotated_path = os.path.join(screenshot_dir, "ocr_detection.png")
            img.save(annotated_path)
            logger.info(f"💾 Saved annotated OCR detection image to {annotated_path}")
            
        except Exception as e:
            logger.error(f"Error creating annotated screenshot: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
        # If we found matches
        if matches:
            # Get the best match
            best_match = matches[0]
            
            # Get coordinates for the best match
            if 'bbox' in best_match:
                bbox = best_match['bbox']
                center_x, center_y = get_center_point(bbox)
                
                logger.info(f"Found target '{best_match['text']}' at coordinates ({center_x}, {center_y}) with confidence {best_match['confidence']:.2f}")
                
                return {
                    "success": True,
                    "found": True,
                    "coordinates": (center_x, center_y),
                    "text": best_match['text'],
                    "confidence": best_match['confidence'],
                    "bbox": bbox
                }
        
        # If no matches were found
        logger.warning(f"No matching UI elements found for target: '{target_text}'")
        return {
            "success": True,
            "found": False,
            "error": f"No UI elements found matching '{target_text}'"
        }
    
    except Exception as e:
        logger.error(f"Error finding visual target: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "success": False,
            "found": False,
            "error": str(e)
        }

def generate_pyautogui_code_with_vision(command: str, 
                                     model: str = "gemma3:12b", 
                                     ollama_host: str = "http://localhost:11434",
                                     timeout: int = 30) -> Dict[str, Any]:
    """
    Generate PyAutoGUI code for a command, using vision detection for targets.
    This is an enhanced version of generate_pyautogui_code that attempts to
    find visual targets on the screen.
    
    Args:
        command: The command to execute (e.g., "click on the Firefox icon")
        model: The Ollama model to use
        ollama_host: The Ollama API host
        timeout: Timeout for the Ollama API request
        
    Returns:
        Dictionary with the generated code and success status
    """
    logger.info(f"Generating PyAutoGUI code with vision detection for: {command}")
    
    # Check if this is a pure typing command - if so, skip vision detection
    is_typing_command = any(cmd in command.lower() for cmd in ['escribe', 'escribir', 'teclea', 'teclear', 'type', 'enter', 'write', 'input', 'presiona', 'presionar', 'press'])
    
    if is_typing_command:
        logger.info("Detected typing command, skipping vision detection and using standard code generation")
        return generate_pyautogui_code(command, model, ollama_host, timeout)
    
    try:
        # Step 1: Use LLM to extract target text from the command
        # Using ollama chat to get the target
        extract_prompt = f"""
        You are a computer vision assistant. Extract the target UI element from this command.
        
        Command: "{command}"
        
        Give me ONLY the name of the UI element or text to look for, nothing else.
        For example:
        - For "click on Firefox", respond with: Firefox
        - For "type hello in the search box", respond with: search box
        - For "double click on the file icon", respond with: file icon
        
        Your response should be a single word or brief phrase, no explanation.
        """
        
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model": model,
                "prompt": extract_prompt,
                "stream": False
            },
            timeout=timeout
        )
        
        if response.status_code != 200:
            logger.error(f"Error from Ollama API: {response.status_code}")
            # Fall back to standard generation without vision
            return generate_pyautogui_code(command, model, ollama_host, timeout)
        
        # Extract the target text
        result = response.json()
        target_text = result.get("response", "").strip()
        
        # Clean up the target text (remove quotes, periods, etc.)
        target_text = target_text.strip('"\'.,!?:;()[]{}').strip()
        
        logger.info(f"Extracted visual target: '{target_text}'")
        
        # Step 2: If we have a valid target, try to find it on screen
        if target_text and len(target_text) > 1:
            target_info = find_visual_target(target_text)
            
            # Check if there was an error finding the target
            if not target_info.get("success", False):
                error_msg = target_info.get("error", "Unknown error")
                # Log detailed error information if available
                if "traceback" in target_info:
                    logger.error(f"Detailed target detection error: {error_msg}")
                    logger.error(f"Traceback: {target_info['traceback']}")
                    # If this is a module import error, log helpful installation instructions
                    if "No module named" in error_msg:
                        missing_module = error_msg.split("No module named ")[-1].strip("'")
                        logger.error(f"Missing module: {missing_module}")
                        if "element_finder" in missing_module:
                            logger.error("UI detection components are missing. Make sure the llm_control package is installed correctly.")
                            logger.error("You might need to install additional dependencies with: pip install -e .[ui]")
                
                logger.info("Falling back to standard code generation due to target detection error")
                return generate_pyautogui_code(command, model, ollama_host, timeout)
            
            # Step 3: If target found, generate code with exact coordinates
            if target_info.get("found", False):
                x, y = target_info.get("coordinates", (0, 0))
                
                # Get detected text and confidence
                detected_text = target_info.get("text", target_text)
                confidence = target_info.get("confidence", 0.0)
                
                # Log the reasoning for why this target was selected
                logger.info(f"Using target '{detected_text}' (confidence: {confidence:.2f}) for command: '{command}'")
                if detected_text.lower() != target_text.lower():
                    logger.info(f"Note: Original target '{target_text}' mapped to UI element '{detected_text}'")
                
                # Generate the action based on the command type
                action_type = "click"  # Default action
                
                if any(word in command.lower() for word in ["double", "twice"]):
                    action_type = "doubleClick"
                elif any(word in command.lower() for word in ["right", "context"]):
                    action_type = "rightClick"
                elif any(word in command.lower() for word in ["move", "hover"]):
                    action_type = "moveTo"
                elif any(word in command.lower() for word in ["drag", "drop"]):
                    action_type = "dragTo"
                    # For drag operations, we need a destination as well
                    # Here we're just using a relative position as an example
                    # In a real implementation, you'd want to find the target destination
                    dest_x = x + 100
                    dest_y = y + 100
                
                # Generate code based on the action type
                code = ""
                description = ""
                
                if action_type == "click":
                    code = f"import pyautogui\n\n# Click on '{detected_text}'\npyautogui.click(x={x}, y={y})"
                    description = f"Click on '{detected_text}' at coordinates ({x}, {y})"
                elif action_type == "doubleClick":
                    code = f"import pyautogui\n\n# Double-click on '{detected_text}'\npyautogui.doubleClick(x={x}, y={y})"
                    description = f"Double-click on '{detected_text}' at coordinates ({x}, {y})"
                elif action_type == "rightClick":
                    code = f"import pyautogui\n\n# Right-click on '{detected_text}'\npyautogui.rightClick(x={x}, y={y})"
                    description = f"Right-click on '{detected_text}' at coordinates ({x}, {y})"
                elif action_type == "moveTo":
                    code = f"import pyautogui\n\n# Move to '{detected_text}'\npyautogui.moveTo(x={x}, y={y})"
                    description = f"Move to '{detected_text}' at coordinates ({x}, {y})"
                elif action_type == "dragTo":
                    code = f"import pyautogui\n\n# Drag from '{detected_text}' to a new position\npyautogui.moveTo(x={x}, y={y})\npyautogui.dragTo(x={dest_x}, y={dest_y}, duration=0.5)"
                    description = f"Drag from '{detected_text}' at ({x}, {y}) to ({dest_x}, {dest_y})"
                
                return {
                    "success": True,
                    "code": code,
                    "description": description,
                    "coordinates": (x, y),
                    "target": detected_text,
                    "confidence": confidence,
                    "used_vision": True
                }
            else:
                # If target wasn't found even though UI detection seemed to work,
                # log this specifically and fall back to standard code generation
                logger.warning(f"Visual target '{target_text}' not found on screen, falling back to standard code generation")
                return generate_pyautogui_code(command, model, ollama_host, timeout)
        else:
            # No valid target text extracted
            logger.warning(f"Couldn't extract a valid target from command: '{command}'")
            return generate_pyautogui_code(command, model, ollama_host, timeout)
    
    except Exception as e:
        logger.error(f"Error generating PyAutoGUI code with vision: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Fall back to standard code generation without vision
        logger.info("Falling back to standard code generation due to error")
        return generate_pyautogui_code(command, model, ollama_host, timeout)

def execute_pyautogui_code(code: str, safe_mode: bool = False) -> Dict[str, Any]:
    """
    Execute PyAutoGUI code safely.
    
    Args:
        code: PyAutoGUI code to execute
        safe_mode: Whether to run in safe mode
        
    Returns:
        Dictionary with execution results
    """
    logger.info(f"Executing PyAutoGUI code ({len(code)} characters)")
    
    try:
        # Try to import PyAutoGUI
        try:
            import pyautogui
        except ImportError:
            return {
                "success": False,
                "error": "PyAutoGUI is not installed. Install with 'pip install pyautogui'"
            }
        
        # Set failsafe mode (move mouse to top-left corner to abort)
        if safe_mode:
            pyautogui.FAILSAFE = True
        else:
            pyautogui.FAILSAFE = False
        
        # Create a temporary file with the code
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as temp_file:
            temp_path = temp_file.name
            
            # Add imports if not present in the code
            if "import pyautogui" not in code:
                temp_file.write("import pyautogui\n")
            
            if "import time" not in code and "time.sleep" in code:
                temp_file.write("import time\n")
            
            # Set failsafe if not in the code
            if "pyautogui.FAILSAFE" not in code:
                if safe_mode:
                    temp_file.write("pyautogui.FAILSAFE = True\n")
                else:
                    temp_file.write("pyautogui.FAILSAFE = False\n")
            
            # Write the code
            temp_file.write(code)
        
        # Execute the temporary file
        logger.info(f"Executing PyAutoGUI code from temporary file: {temp_path}")
        
        # Create a subprocess to run the code
        result = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=30  # Timeout after 30 seconds
        )
        
        # Check if execution was successful
        if result.returncode == 0:
            logger.info("PyAutoGUI code executed successfully")
            return {
                "success": True,
                "output": result.stdout.strip()
            }
        else:
            logger.error(f"Error executing PyAutoGUI code: {result.stderr}")
            return {
                "success": False,
                "error": result.stderr.strip(),
                "output": result.stdout.strip()
            }
    
    except subprocess.TimeoutExpired:
        logger.error("PyAutoGUI code execution timed out")
        return {
            "success": False,
            "error": "Execution timed out (30 seconds)"
        }
    
    except Exception as e:
        logger.error(f"Error executing PyAutoGUI code: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "success": False,
            "error": str(e)
        }
    
    finally:
        # Clean up temporary file
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except (OSError, PermissionError):
                pass