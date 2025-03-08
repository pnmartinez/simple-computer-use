import re
import logging
import time
from llm_control import KEY_MAPPING, KEY_COMMAND_PATTERN, REFERENCE_WORDS, command_history
from llm_control.command_processing.parser import normalize_step
from llm_control.command_processing.history import (
    update_ui_element_history, update_command_history, 
    add_step_to_history, get_last_ui_element
)
from llm_control.llm.text_extraction import extract_text_to_type_with_llm, ensure_text_is_safe_for_typewrite
from llm_control.llm.intent_detection import extract_target_text_with_llm

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def is_reference_command(step):
    """Check if the step is a reference command like 'click it' or standalone 'click'"""
    # Check for standalone "click"
    if step.lower() == 'click' or step.lower() == 'click on':
        return True
    
    # Check for "click it", "click on that", etc.
    for ref_word in REFERENCE_WORDS:
        if re.search(rf'\b{ref_word}\b', step.lower()) and 'click' in step.lower():
            return True
    
    return False

def handle_reference_command(step):
    """Handle reference commands that refer to previous elements or positions"""
    code_lines = []
    explanation = []
    
    # By default, just click at the current position
    code_lines.append("pyautogui.click()")
    
    # Add a more detailed explanation if we have history
    last_element = get_last_ui_element()
    if last_element:
        element_type = last_element.get('type', 'unknown')
        element_text = last_element.get('text', '')
        
        if element_text:
            explanation.append(f"Clicking on the previously targeted {element_type} '{element_text}'")
        else:
            explanation.append(f"Clicking on the previously targeted {element_type}")
    else:
        explanation.append("Clicking at the current position (reference to previous target)")
    
    # Add to command history
    update_command_history('click')
    
    return {
        'code': '\n'.join(code_lines),
        'explanation': '\n'.join(explanation)
    }

def extract_keys_from_step(step, key_mapping=None):
    """Extract key presses from a step"""
    if key_mapping is None:
        key_mapping = KEY_MAPPING
        
    detected_keys = set()
    
    # Look for explicit key press patterns
    for match in re.finditer(KEY_COMMAND_PATTERN, step.lower()):
        key = match.group(1)
        if key in key_mapping and key_mapping[key] not in detected_keys:
            detected_keys.add(key_mapping[key])
    
    # Special case for Enter which is commonly used
    if 'press enter' in step.lower() or 'hit enter' in step.lower():
        if 'enter' not in detected_keys:
            detected_keys.add('enter')
    
    return detected_keys

def is_keyboard_command(step):
    """Check if the step is a pure keyboard command like 'press enter'"""
    return re.search(KEY_COMMAND_PATTERN, step.lower()) is not None and (
        step.lower().startswith('press') or 
        step.lower().startswith('hit') or
        step.lower().startswith('push') or
        step.lower().startswith('stroke')
    )

def handle_keyboard_command(step):
    """Handle pure keyboard commands like 'press enter'"""
    code_lines = []
    explanation = []
    
    detected_keys = extract_keys_from_step(step)
    
    if detected_keys:
        for key in detected_keys:
            code_lines.append(f'pyautogui.press("{key}")')
            explanation.append(f"Pressing the {key.upper()} key")
        
        # Add to command history
        update_command_history('keyboard')
    
    return {
        'code': '\n'.join(code_lines),
        'explanation': '\n'.join(explanation)
    }

def is_typing_command(step):
    """Check if the step is a typing command like 'type hello'"""
    step_lower = step.lower()
    has_type = any(pattern in step_lower for pattern in ['type ', 'typing ', 'write ', 'enter '])
    
    return has_type or step_lower.startswith('type ')

def extract_typing_target(step, ui_description):
    """Extract target element to click before typing, if specified"""
    code_lines = []
    explanation = []
    target_found = False
    
    if 'in' in step.lower() or 'on' in step.lower() or 'the' in step.lower():
        # Create a modified query that only looks for the target element
        modified_query = step.lower()
        modified_query = re.sub(r'(?:type|typing|enter|write)\s+.*', '', modified_query, flags=re.IGNORECASE)
        modified_query = modified_query.strip()
        
        # Only look for a UI element if the modified query has meaningful content
        if len(modified_query) > 5:  # Arbitrary threshold to avoid overly short queries
            print(f"🔎 Looking for element to type in: '{modified_query}'")
            from llm_control.command_processing.finder import find_ui_element
            ui_element = find_ui_element(modified_query, ui_description)
            
            if ui_element:
                # If we found an element to type in, click it first
                x, y = ui_element['x'], ui_element['y']
                element_type = ui_element['element_type']
                element_text = ui_element['element_text']
                
                # Move to and click the element first
                code_lines.append(f"pyautogui.moveTo({x}, {y}, duration=0.5)")
                explanation.append(f"Moving to {element_type} '{element_text}' at coordinates ({x}, {y})")
                code_lines.append("pyautogui.click()")
                explanation.append(f"Clicking on the element to focus it")
                
                # Update command history with this element
                update_ui_element_history(ui_element['element'], (x, y))
                
                target_found = True
    
    return {
        'code_lines': code_lines,
        'explanation': explanation,
        'target_found': target_found
    }

def handle_typing_command(step, ui_description, original_step):
    """Handle typing commands like 'type hello'"""
    code_lines = []
    explanation = []
    
    # First check if we need to click on a specific element before typing
    target_info = extract_typing_target(step, ui_description)
    code_lines.extend(target_info['code_lines'])
    explanation.extend(target_info['explanation'])
    
    # Extract the text to type from the original step (not normalized)
    # to preserve the full context for the LLM
    text_to_type = extract_text_to_type_with_llm(original_step)
    
    # If LLM extraction failed, fall back to regex patterns
    if not text_to_type:
        print("📋 Using fallback text extraction for typing")
        # Pattern 1: quoted text after type/typing/etc.
        match = re.search(r'(?:type|typing|enter|write)\s*["\']([^"\']+)["\']', step, re.IGNORECASE)
        if match:
            text_to_type = match.group(1)
        else:
            # Pattern 2: Capture everything after type/write/etc. until the end or specific terminators
            # This is a much more aggressive pattern to get the full text
            match = re.search(r'(?:type|typing|enter|write)\s+(.*?)(?:$|\s+then\s+(?:press|hit))', step, re.IGNORECASE)
            if match:
                text_to_type = match.group(1).strip()
            else:
                # Pattern 3: If all else fails, just get everything after the command word
                for cmd_word in ['type', 'typing', 'enter', 'write']:
                    if f' {cmd_word} ' in step.lower() or step.lower().startswith(f'{cmd_word} '):
                        parts = re.split(rf'\b{cmd_word}\b', step, flags=re.IGNORECASE, maxsplit=1)
                        if len(parts) > 1:
                            text_to_type = parts[1].strip()
                            break
    
    # If we found text to type, add typing command and skip UI element detection
    if text_to_type:
        # Add the typing command
        safe_text = ensure_text_is_safe_for_typewrite(text_to_type)
        code_lines.append(f'pyautogui.typewrite("{safe_text}")')
        explanation.append(f"Typing '{text_to_type}'")
        
        # Add key press commands if specified in the step
        detected_keys = extract_keys_from_step(step)
        
        for key in detected_keys:
            code_lines.append(f'pyautogui.press("{key}")')
            explanation.append(f"Pressing the {key.upper()} key")
        
        # Add to command history
        update_command_history('type')
    
    return {
        'code': '\n'.join(code_lines),
        'explanation': '\n'.join(explanation)
    }

def handle_ui_element_command(step, ui_description):
    """Handle commands that target UI elements like 'click on button'"""
    code_lines = []
    explanation = []
    
    # Find potential UI elements referenced in the user input
    from llm_control.command_processing.finder import find_ui_element
    ui_element = find_ui_element(step, ui_description)
    
    if ui_element:
        # Element found, generate code to interact with it
        x, y = ui_element['x'], ui_element['y']
        element = ui_element['element']
        element_type = ui_element['element_type']
        element_display = ui_element['element_display']
        
        # Add move to element
        code_lines.append(f"pyautogui.moveTo({x}, {y}, duration=0.5)")
        explanation.append(f"Moving to {element_type} {element_display} at coordinates ({x}, {y})")
        
        # Update command history with this element
        update_ui_element_history(element, (x, y))
        
        # Check for sequence of actions in user input
        has_click = 'click' in step.lower()
        has_double_click = 'double' in step.lower() and 'click' in step.lower()
        has_right_click = 'right' in step.lower() and 'click' in step.lower()
        
        # Process actions in sequence
        if has_click or not (has_double_click or has_right_click):
            # Default action is click if no specific action is mentioned
            code_lines.append("pyautogui.click()")
            if element_type == 'button':
                explanation.append(f"Clicking on the button")
            elif element_type == 'checkbox':
                explanation.append(f"Clicking on the checkbox to toggle it")
            else:
                explanation.append(f"Clicking on the element")
            
            # Update command history
            update_command_history('click')
            
        elif has_double_click:
            code_lines.append("pyautogui.doubleClick()")
            explanation.append(f"Double-clicking on the element")
            
            # Update command history
            update_command_history('double_click')
            
        elif has_right_click:
            code_lines.append("pyautogui.rightClick()")
            explanation.append(f"Right-clicking on the element")
            
            # Update command history
            update_command_history('right_click')
        
        # Add key press commands if specified
        if 'press' in step.lower() or 'hit' in step.lower():
            detected_keys = extract_keys_from_step(step)
            
            for key in detected_keys:
                code_lines.append(f'pyautogui.press("{key}")')
                explanation.append(f"Pressing the {key.upper()} key")
        
        # Add match information for debugging - safely handle DEBUG_MODE
        match_info = ui_element.get('match_info', {})
        if match_info and logger.getEffectiveLevel() <= logging.DEBUG:
            explanation.append(f"\nMatch confidence: {match_info['score']:.1f}")
            explanation.append(f"Match reasons: {', '.join(match_info['reasons'])}")
    else:
        # No specific element found, generate a message explaining why
        elements_count = len(ui_description.get('elements', [])) if ui_description else 0
        
        if elements_count == 0:
            # No elements detected at all
            code_lines.append("# No UI elements were detected in the screenshot")
            explanation.append("Could not detect any UI elements in the screenshot")
        else:
            # Elements detected but none matched the query
            code_lines.append(f"# No matching UI element found for: '{step}'")
            explanation.append(f"Found {elements_count} UI elements, but none matched your request")
            
            # Try to handle generic key press actions when no element was matched
            if 'press' in step.lower() or 'hit' in step.lower():
                detected_keys = extract_keys_from_step(step)
                
                for key in detected_keys:
                    code_lines.append(f'pyautogui.press("{key}")')
                    explanation.append(f"Pressing the {key.upper()} key")
    
    return {
        'code': '\n'.join(code_lines),
        'explanation': '\n'.join(explanation)
    }

def process_single_step(step_input, ui_description, screenshot=None):
    """Process a single step of a potentially multi-step query"""
    print(f"🔎 Processing step: '{step_input}'")
    
    # Keep the original step for reference
    original_step = step_input
    
    # Normalize the step by removing prefixes like 'then'
    normalized_step = normalize_step(step_input)
    
    # Store the original step in the command history
    add_step_to_history(original_step, normalized_step)
    
    # Use a decision tree to determine the type of step and handle it appropriately
    if is_reference_command(normalized_step):
        print(f"🔍 Detected reference command: '{step_input}'")
        return handle_reference_command(normalized_step)
    
    if is_keyboard_command(normalized_step):
        print(f"⌨️ Processing keyboard command: '{step_input}'")
        return handle_keyboard_command(normalized_step)
    
    if is_typing_command(normalized_step):
        print(f"📝 Processing typing command: '{step_input}'")
        return handle_typing_command(normalized_step, ui_description, original_step)
    
    # If none of the above, assume it's a UI element command
    return handle_ui_element_command(normalized_step, ui_description)

def generate_pyautogui_code_with_ui_awareness(user_input, ui_description):
    """Generate PyAutoGUI code based on user input with awareness of UI elements"""
    logger.info(f"Generating PyAutoGUI code for: '{user_input}'")
    
    # Reset command history for a new session
    from llm_control.command_processing.history import reset_command_history
    reset_command_history()
    
    # Pre-process the query to ensure actions following a comma are recognized as steps
    from llm_control import ACTION_VERBS
    for verb in ACTION_VERBS:
        # Replace patterns like "something, click" with "something, then click"
        user_input = re.sub(rf',\s*({verb})', r', then \1', user_input, flags=re.IGNORECASE)
    
    # Check if this is a multi-step query
    from llm_control import STEP_SEPARATORS
    has_multiple_steps = any(separator in user_input for separator in STEP_SEPARATORS) or \
                         re.search(r'\b(then|and)\b', user_input) is not None
    
    code_lines = []
    explanation = []
    
    if has_multiple_steps:
        # Split the query into steps using the helper function
        from llm_control.command_processing.parser import split_user_input_into_steps, clean_and_normalize_steps
        steps = split_user_input_into_steps(user_input)
        
        # Clean and normalize the steps using the helper function
        steps = clean_and_normalize_steps(steps)
        
        # Include import for time module for sleep commands
        code_lines.append("import time  # For sleep between steps")
        
        # Process each step individually
        print(f"🔄 Processing multi-step query with {len(steps)} steps:")
        for i, step in enumerate(steps):
            print(f"  Step {i+1}: '{step}'")  # Add quotes to better see step boundaries
            
            # Process the individual step
            step_result = process_single_step(step, ui_description)
            
            # Add the commands from this step
            if step_result['code']:
                if i > 0:
                    code_lines.append("")  # Add a blank line between steps
                    code_lines.append(f"# Step {i+1}: {step}")
                
                for code_line in step_result['code'].split('\n'):
                    code_lines.append(code_line)
                
                # Add sleep between steps
                if i < len(steps) - 1:  # Don't add sleep after the last step
                    code_lines.append("time.sleep(1)  # Wait between steps")
                
                explanation.append(f"\nStep {i+1}: {step}")
                explanation.append(step_result['explanation'])
                if i < len(steps) - 1:
                    explanation.append("Waiting 1 second between steps")
            else:
                explanation.append(f"\nStep {i+1}: {step} (Failed: No matching elements found)")
    else:
        # Single step query - process as before
        single_result = process_single_step(user_input, ui_description)
        code_lines = single_result['code'].split('\n')
        explanation.append(single_result['explanation'])
    
    return {
        'code': '\n'.join(code_lines),
        'explanation': '\n'.join(explanation)
    }
