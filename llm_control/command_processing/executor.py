"""
Command executor module.

This module processes and executes user commands, generating PyAutoGUI actions
based on the user's intent and the current UI state.
"""

import re
import logging
import time
from typing import Dict, Any, List, Optional, Tuple, Union

# Import from the main package
from llm_control import (
    KEY_MAPPING,
    KEY_COMMAND_PATTERN,
    REFERENCE_WORDS,
    command_history,
    structured_usage_log,
)

# Import from command processing submodules
from llm_control.command_processing.parser import normalize_step
from llm_control.command_processing.history import (
    update_ui_element_history, update_command_history, 
    add_step_to_history, get_last_ui_element, get_last_coordinates
)
from llm_control.command_processing.finder import find_ui_element

# Import from LLM submodules
from llm_control.llm.text_extraction import extract_text_to_type_with_llm, ensure_text_is_safe_for_typewrite
from llm_control.llm.intent_detection import extract_target_text_with_llm

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def is_reference_command(step):
    """Check if the step is a reference command like 'click it' or standalone 'click'"""
    step_lower = step.lower()
    
    # Only consider as reference if it's a standalone action or explicitly uses reference words
    
    # Check for standalone "click" - but only if it's truly standalone
    if step_lower == 'click' or step_lower == 'click on':
        return True
    
    # Check for explicit reference words like "click it", "click on that", etc.
    # But don't match if there's specific content after "click on" 
    
    # First, check if the step has a click command followed by a reference word
    for ref_word in REFERENCE_WORDS:
        ref_pattern = rf'\b(click|click\s+on)\s+{ref_word}\b'
        if re.search(ref_pattern, step_lower):
            return True
    
    # Not a reference command if it has a specific target after "click on"
    # For example, "click on button" is not a reference command
    if re.match(r'click\s+on\s+\w+', step_lower) and not any(ref in step_lower for ref in REFERENCE_WORDS):
        return False
        
    return False

def handle_reference_command(step):
    """Handle reference commands that refer to previous elements or positions"""
    code_lines = []
    explanation = []
    description = "Reference Click"
    
    # Get the last UI element and coordinates
    last_element = get_last_ui_element()
    last_coordinates = get_last_coordinates()
    
    if last_element and last_coordinates:
        # If we have both the element and coordinates, use them
        x, y = last_coordinates
        element_type = last_element.get('type', 'unknown')
        element_text = last_element.get('text', '')
        
        # First move to the position (in case the cursor has moved)
        code_lines.append(f"pyautogui.moveTo({x}, {y}, duration=0.3)")
        
        # Then click
        code_lines.append("pyautogui.click()")
        
        if element_text:
            explanation.append(f"Moving to previously targeted {element_type} '{element_text}' at ({x}, {y})")
            explanation.append(f"Clicking on the element")
            description = f"Click on {element_type}: {element_text}"
        else:
            explanation.append(f"Moving to previously targeted {element_type} at ({x}, {y})")
            explanation.append(f"Clicking on the element")
            description = f"Click on {element_type}"
    else:
        # No element history available, just click at the current position
        code_lines.append("pyautogui.click()")
        explanation.append("Clicking at the current position (no element history available)")
    
    # Add to command history
    update_command_history('click')
    
    structured_usage_log(
        "command.reference_action",
        used_history=bool(last_element and last_coordinates),
        coordinates=list(last_coordinates) if last_coordinates else None,
        element_type=last_element.get('type') if last_element else None,
        element_text=last_element.get('text') if last_element else None,
        description=description,
    )

    return {
        'code': '\n'.join(code_lines),
        'explanation': '\n'.join(explanation),
        'description': description
    }

def extract_keys_from_step(step, key_mapping=None):
    """Extract key presses from a step"""
    if key_mapping is None:
        key_mapping = KEY_MAPPING
        
    detected_keys = []
    
    # Verbs que indican pulsación de tecla (para limpiarlos si aparecen como "tecla" al tokenizar)
    press_verbs = {
        "press", "hit", "push", "stroke",
        "pulsa", "presiona", "oprime", "teclea",
        "presionar", "oprimir", "teclear"
    }
    
    # Look for explicit key press patterns with English and Spanish verbs
    for match in re.finditer(KEY_COMMAND_PATTERN, step.lower()):
        # Extract the key name after the press/pulsa/etc. verb
        command_verb = match.group(1)  # e.g., "press", "pulsa"
        key_name = match.group(2) or match.group(3) or match.group(4)  # e.g., "ctrl-l", "control l"
        
        if not key_name:
            continue
            
        # Split on any combination of space, hyphen, or plus
        keys = re.split(r'[-+\s]+', key_name)
        # Map each key in the combination, ignorando verbos tipo "presiona", "pulsa", etc.
        mapped_keys = []
        for k in keys:
            k = k.strip().lower()
            if not k:
                continue
            # Descarta palabras que son en realidad verbos de pulsación
            if k in press_verbs:
                continue
            if k in key_mapping:
                mapped_keys.append(key_mapping[k])
            else:
                mapped_keys.append(k)

        if not mapped_keys:
            continue

        # Si tenemos varias teclas y todas son iguales (p.ej. "abajo abajo abajo"),
        # interprétalo como varias pulsaciones secuenciales en lugar de una sola combinación.
        unique_keys = set(mapped_keys)
        if len(mapped_keys) > 1 and len(unique_keys) == 1:
            single_key = mapped_keys[0]
            for _ in mapped_keys:
                detected_keys.append([single_key])
        else:
            detected_keys.append(mapped_keys)
    
    return detected_keys

def is_keyboard_command(step):
    """Check if the step is a keyboard command"""
    return bool(re.search(KEY_COMMAND_PATTERN, step.lower()))

def handle_keyboard_command(step):
    """Handle pure keyboard commands like 'press enter'"""
    code_lines = []
    explanation = []
    description = "Keyboard Command"
    
    detected_keys = extract_keys_from_step(step)
    
    if detected_keys:
        key_names = []
        for key_combo in detected_keys:
            if len(key_combo) > 1:
                # Key combination - use hotkey
                formatted_keys = ", ".join([f'"{k}"' for k in key_combo])
                code_lines.append(f'pyautogui.hotkey({formatted_keys})')
                explanation.append(f"Pressing {'+'.join(k.upper() for k in key_combo)}")
                key_names.append('+'.join(k.upper() for k in key_combo))
            else:
                # Single key - use press
                key = key_combo[0]
                code_lines.append(f'pyautogui.press("{key}")')
                explanation.append(f"Pressing the {key.upper()} key")
                key_names.append(key.upper())
        
        # Create a descriptive title for the action
        if len(key_names) == 1:
            description = f"Press {key_names[0]}"
        else:
            description = f"Press Keys: {', '.join(key_names)}"
        
        # Add to command history
        update_command_history('keyboard')

    structured_usage_log(
        "command.keyboard_action",
        keys=detected_keys,
        success=bool(code_lines),
        description=description,
    )

    return {
        'code': '\n'.join(code_lines),
        'explanation': '\n'.join(explanation),
        'description': description
    }

def is_scroll_command(step):
    """Check if the step is a scroll command"""
    scroll_patterns = [
        r'\bscroll\s+(up|down|to\s+top|to\s+bottom|page\s+up|page\s+down)\b',
        r'\bscroll\b',
        r'\b(up|down)scroll\b',
        r'\bmove\s+(up|down)\b',
        r'\b(page\s+up|page\s+down)\b'
    ]
    
    for pattern in scroll_patterns:
        if re.search(pattern, step.lower()):
            return True
    
    return False

def handle_scroll_command(step):
    """Handle scroll commands to scroll up or down"""
    code_lines = []
    explanation = []
    description = ""
    
    step_lower = step.lower()
    
    # Extract direction and amount (if specified)
    direction = "down"  # Default direction
    amount = 3  # Default number of scroll actions
    scroll_amount = 100  # Default scroll amount per action
    
    # Check for specific command types
    if re.search(r'\bpage\s+up\b', step_lower) or re.search(r'\bscroll\s+page\s+up\b', step_lower):
        direction = "up"
        scroll_amount = 500  # Larger scroll amount for page up
        description = "Page Up Scroll"
        explanation.append("Scrolling page up (equivalent to pressing Page Up key)")
        explanation.append(f"Using pyautogui.scroll({scroll_amount}) with positive value for upward scrolling")
        code_lines.append("pyautogui.scroll(500)")  # Positive for up
        
    elif re.search(r'\bpage\s+down\b', step_lower) or re.search(r'\bscroll\s+page\s+down\b', step_lower):
        direction = "down"
        scroll_amount = 500  # Larger scroll amount for page down
        description = "Page Down Scroll"
        explanation.append("Scrolling page down (equivalent to pressing Page Down key)")
        explanation.append(f"Using pyautogui.scroll(-{scroll_amount}) with negative value for downward scrolling")
        code_lines.append("pyautogui.scroll(-500)")  # Negative for down
        
    elif re.search(r'\bto\s+top\b', step_lower):
        direction = "up"
        amount = 20  # Multiple scrolls to likely reach the top
        description = "Scroll to Top"
        explanation.append(f"Scrolling to the top of the content with {amount} scroll operations")
        explanation.append("Using multiple small scrolls with delays for smoother operation")
        code_lines.append("# Scroll multiple times to reach the top")
        code_lines.append(f"for _ in range({amount}):")
        code_lines.append(f"    pyautogui.scroll(300)")
        code_lines.append(f"    time.sleep(0.2)")  # Increased delay for smoother scrolling
        
    elif re.search(r'\bto\s+bottom\b', step_lower):
        direction = "down"
        amount = 20  # Multiple scrolls to likely reach the bottom
        description = "Scroll to Bottom"
        explanation.append(f"Scrolling to the bottom of the content with {amount} scroll operations")
        explanation.append("Using multiple small scrolls with delays for smoother operation")
        code_lines.append("# Scroll multiple times to reach the bottom")
        code_lines.append(f"for _ in range({amount}):")
        code_lines.append(f"    pyautogui.scroll(-300)")
        code_lines.append(f"    time.sleep(0.2)")  # Increased delay for smoother scrolling
        
    else:
        # Check for direction in normal scroll commands
        if re.search(r'\bup\b', step_lower):
            direction = "up"
        
        # Check for specific amount
        amount_match = re.search(r'(\d+)\s+(lines|times|clicks)', step_lower)
        if amount_match:
            amount = int(amount_match.group(1))
        
        # Generate code for normal scrolling
        if direction == "up":
            description = f"Scroll Up {amount} Times"
            explanation.append(f"Scrolling up {amount} times with {scroll_amount} units per scroll")
            explanation.append("Using multiple small scrolls with delays for smoother operation")
            code_lines.append(f"for _ in range({amount}):")
            code_lines.append(f"    pyautogui.scroll({scroll_amount})")  # Positive for up
            code_lines.append(f"    time.sleep(0.2)")  # Increased delay for smoother scrolling
        else:
            description = f"Scroll Down {amount} Times"
            explanation.append(f"Scrolling down {amount} times with {scroll_amount} units per scroll")
            explanation.append("Using multiple small scrolls with delays for smoother operation")
            code_lines.append(f"for _ in range({amount}):")
            code_lines.append(f"    pyautogui.scroll(-{scroll_amount})")  # Negative for down
            code_lines.append(f"    time.sleep(0.2)")  # Increased delay for smoother scrolling
    
    # Add to command history
    update_command_history(f'scroll {direction}')
    
    structured_usage_log(
        "command.scroll_action",
        direction=direction,
        iterations=amount,
        description=description,
        code_generated=bool(code_lines),
    )

    return {
        'code': '\n'.join(code_lines),
        'explanation': '\n'.join(explanation),
        'description': description
    }

def is_typing_command(step):
    """Check if the step is a typing command"""
    step_lower = step.lower()
    
    # More specific patterns with word boundaries to avoid false matches
    # English commands
    english_patterns = [r'\btype\b', r'\benter\b', r'\bwrite\b', r'\binput\b']
    # Spanish commands
    spanish_patterns = [r'\bescribe\b', r'\bescribir\b', r'\bteclea\b', r'\bteclear\b', 
                        r'\bingresa\b', r'\bingresar\b']
    
    # Check for any pattern in either language with regex for more precision
    for pattern in english_patterns + spanish_patterns:
        if re.search(pattern, step_lower):
            return True
            
    return False

def extract_typing_target(step, ui_description):
    """Extract target element to click before typing, if specified"""
    code_lines = []
    explanation = []
    target_found = False
    
    # Updated to recognize English and Spanish prepositions
    if any(prep in step.lower() for prep in ['in', 'on', 'the', 'en', 'el', 'la', 'los', 'las']):
        # Create a modified query that only looks for the target element
        modified_query = step.lower()
        
        # Remove typing commands in both English and Spanish
        typing_pattern = r'(?:type|typing|enter|write|escribe|escribir|teclea|teclear|ingresa|ingresar)\s+.*'
        modified_query = re.sub(typing_pattern, '', modified_query, flags=re.IGNORECASE)
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

                structured_usage_log(
                    "command.typing.target_focus",
                    element_type=element_type,
                    element_text=element_text,
                    coordinates=[x, y],
                )

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
    description = "Type Text"
    extra_key_sequences = []
    
    # First check if we need to click on a specific element before typing
    target_info = extract_typing_target(step, ui_description)
    code_lines.extend(target_info['code_lines'])
    explanation.extend(target_info['explanation'])
    
    # Extract the text to type from the original step (not normalized)
    # to preserve the full context for the LLM
    text_to_type = extract_text_to_type_with_llm(original_step)
    
    # If LLM extraction failed, fall back to regex/heuristics (incluye inglés y español)
    if not text_to_type:
        print("📋 Using fallback text extraction for typing")
        # Pattern 1: quoted text after typing verbs (English + Spanish)
        match = re.search(
            r'(?:type|typing|enter|write|escribe|escribir|teclea|teclear|ingresa|ingresar)\s*["\']([^"\']+)["\']',
            step,
            re.IGNORECASE,
        )
        if match:
            text_to_type = match.group(1)
        else:
            # Pattern 2: Capture everything after typing verbs until the end or an explicit next action
            match = re.search(
                r'(?:type|typing|enter|write|escribe|escribir|teclea|teclear|ingresa|ingresar)\s+(.*?)(?:$|\s+then\s+(?:press|hit|pulsa|presiona))',
                step,
                re.IGNORECASE,
            )
            if match:
                text_to_type = match.group(1).strip()
            else:
                # Pattern 3: If all else fails, just get everything after the command word
                for cmd_word in [
                    "type",
                    "typing",
                    "enter",
                    "write",
                    "escribe",
                    "escribir",
                    "teclea",
                    "teclear",
                    "ingresa",
                    "ingresar",
                ]:
                    step_lower = step.lower()
                    if f" {cmd_word} " in step_lower or step_lower.startswith(f"{cmd_word} "):
                        parts = re.split(rf"\b{cmd_word}\b", step, flags=re.IGNORECASE, maxsplit=1)
                        if len(parts) > 1:
                            text_to_type = parts[1].strip()
                            break

        # Heurística extra: si seguimos sin texto, intenta usar el original_step completo tras el verbo principal.
        if not text_to_type:
            original_lower = original_step.lower()
            for cmd_word in [
                "escribe",
                "escribir",
                "teclea",
                "teclear",
                "ingresa",
                "ingresar",
                "type",
                "typing",
                "enter",
                "write",
            ]:
                idx = original_lower.find(cmd_word)
                if idx != -1:
                    # Todo lo que venga después del verbo
                    tail = original_step[idx + len(cmd_word) :].strip()
                    # Quita conectores iniciales tipo ",", "y", "and"
                    tail = re.sub(r'^[\s,\.]*(y\s+|and\s+)?', "", tail, flags=re.IGNORECASE)
                    if tail:
                        text_to_type = tail
                    break
    
    # If we found text to type, add typing command and skip UI element detection
    if text_to_type:
        # Create a more descriptive action name
        description = f"Type: '{text_to_type}'"
        if len(text_to_type) > 30:
            # Truncate very long texts in the description
            description = f"Type: '{text_to_type[:27]}...'"
        
        # Add the typing command
        safe_text = ensure_text_is_safe_for_typewrite(text_to_type)
        code_lines.append(f'pyautogui.typewrite("{safe_text}")')
        explanation.append(f"Typing '{text_to_type}'")
        
        # Add key press commands if specified in the step
        detected_keys = extract_keys_from_step(step)
        extra_key_sequences = detected_keys
        
        if detected_keys:
            key_names = []
            for key in detected_keys:
                code_lines.append(f'pyautogui.press("{key}")')
                explanation.append(f"Pressing the {key.upper()} key")
                key_names.append(key.upper())
            
            # Update description to include key presses
            if len(key_names) == 1:
                description += f" and Press {key_names[0]}"
            else:
                description += f" and Press Keys: {', '.join(key_names)}"
        
        # Add to command history
        update_command_history('type')

    structured_usage_log(
        "command.typing_action",
        text=text_to_type,
        text_length=len(text_to_type) if text_to_type else 0,
        target_found=target_info['target_found'],
        extra_keys=extra_key_sequences,
        success=bool(code_lines),
        description=description,
    )

    return {
        'code': '\n'.join(code_lines),
        'explanation': '\n'.join(explanation),
        'description': description
    }

def handle_ui_element_command(step, ui_description):
    """Handle commands that target UI elements like 'click on button'"""
    code_lines = []
    explanation = []
    description = "UI Interaction"
    performed_actions = []
    no_element_reason = None
    elements_count = len(ui_description.get('elements', [])) if ui_description else 0
    
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
        performed_actions.append("move")
        
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
                description = f"Click Button: {element_display}"
            elif element_type == 'checkbox':
                explanation.append(f"Clicking on the checkbox to toggle it")
                description = f"Toggle Checkbox: {element_display}"
            else:
                explanation.append(f"Clicking on the element")
                description = f"Click {element_type}: {element_display}"
            
            # Update command history
            update_command_history('click')
            performed_actions.append("click")
            
        elif has_double_click:
            code_lines.append("pyautogui.doubleClick()")
            explanation.append(f"Double-clicking on the element")
            description = f"Double-Click: {element_display}"
            
            # Update command history
            update_command_history('double_click')
            performed_actions.append("double_click")
            
        elif has_right_click:
            code_lines.append("pyautogui.rightClick()")
            explanation.append(f"Right-clicking on the element")
            description = f"Right-Click: {element_display}"
            
            # Update command history
            update_command_history('right_click')
            performed_actions.append("right_click")
        
        # Add key press commands if specified
        if 'press' in step.lower() or 'hit' in step.lower():
            detected_keys = extract_keys_from_step(step)
            
            if detected_keys:
                key_names = []
                for key in detected_keys:
                    code_lines.append(f'pyautogui.press("{key}")')
                    explanation.append(f"Pressing the {key.upper()} key")
                    key_names.append(key.upper())
                    combo_label = key.upper() if isinstance(key, str) else '+'.join(part.upper() for part in key)
                    performed_actions.append(f"press:{combo_label}")
                
                # Update description to include key presses
                if len(key_names) == 1:
                    description += f" & Press {key_names[0]}"
                else:
                    description += f" & Press Keys: {', '.join(key_names)}"
        
        # Add match information for debugging - safely handle DEBUG_MODE
        match_info = ui_element.get('match_info', {})
        if match_info and logger.getEffectiveLevel() <= logging.DEBUG:
            explanation.append(f"\nMatch confidence: {match_info['score']:.1f}")
            explanation.append(f"Match reasons: {', '.join(match_info['reasons'])}")
    else:
        # No specific element found, generate a message explaining why
        
        if elements_count == 0:
            # No elements detected at all
            code_lines.append("# No UI elements were detected in the screenshot")
            code_lines.append("# This may be due to:")
            code_lines.append("# - YOLO model not available or not loaded")
            code_lines.append("# - OCR not finding any text in the screenshot")
            code_lines.append("# - Screenshot capture issues")
            explanation.append("Could not detect any UI elements in the screenshot. This may indicate:")
            explanation.append("- YOLO/Ultralytics model is not available or failed to load")
            explanation.append("- OCR (EasyOCR) did not find any text in the screenshot")
            explanation.append("- Screenshot may be blank or corrupted")
            explanation.append("Check logs for more details about detection failures.")
            description = "No UI Elements Detected"
            no_element_reason = "no_elements_detected"
        else:
            # Elements detected but none matched the query
            code_lines.append(f"# No matching UI element found for: '{step}'")
            explanation.append(f"Found {elements_count} UI elements, but none matched your request")
            description = f"No Matching Element: '{step}'"
            no_element_reason = "no_match_found"
            
            # Try to handle generic key press actions when no element was matched
            if 'press' in step.lower() or 'hit' in step.lower():
                detected_keys = extract_keys_from_step(step)
                
                if detected_keys:
                    key_names = []
                    for key in detected_keys:
                        code_lines.append(f'pyautogui.press("{key}")')
                        explanation.append(f"Pressing the {key.upper()} key")
                        key_names.append(key.upper())
                        combo_label = key.upper() if isinstance(key, str) else '+'.join(part.upper() for part in key)
                        performed_actions.append(f"press:{combo_label}")
                    
                    # Update description for key presses
                    if len(key_names) == 1:
                        description = f"Press {key_names[0]} Key"
                    else:
                        description = f"Press Keys: {', '.join(key_names)}"
    
    # Log structured event for UI element action
    if ui_element:
        structured_usage_log(
            "command.ui_element_action",
            element_type=ui_element.get('element_type'),
            element_text=ui_element.get('element_text'),
            coordinates=[ui_element['x'], ui_element['y']],
            actions=performed_actions,
            success=True,
            description=description,
        )
    else:
        structured_usage_log(
            "command.ui_element_action",
            element_type=None,
            element_text=None,
            coordinates=None,
            actions=performed_actions,
            success=False,
            description=description,
            reason=no_element_reason if no_element_reason else "element_not_found",
            available_elements=elements_count,
        )
    
    return {
        'code': '\n'.join(code_lines),
        'explanation': '\n'.join(explanation),
        'description': description
    }

def process_single_step(step_input, ui_description):
    """Process a single step of a potentially multi-step query"""
    print(f"🔎 Processing step: '{step_input}'")
    
    # Keep the original step for reference
    original_step = step_input
    
    # Normalize the step by removing prefixes like 'then'
    normalized_step = normalize_step(step_input)
    
    # Check if this is a potential duplicate of the previous action
    # This is to prevent cases where "click on X" is followed by a "click" reference
    # that actually refers to the same element
    last_command = command_history.get('last_command')
    last_element = command_history.get('last_ui_element')
    last_element_type = last_element.get('type') if isinstance(last_element, dict) else None
    potential_duplicate = last_command == 'click' and normalized_step.lower() in ['click', 'click on', 'click it']

    def log_step_result(handler_name, action_result, success=None):
        if success is None:
            code = action_result.get('code', '')
            success = bool(code and not code.strip().startswith('#'))
        structured_usage_log(
            "command.step.result",
            step_original=original_step,
            handler=handler_name,
            description=action_result.get('description'),
            success=success,
        )

    structured_usage_log(
        "command.step.start",
        step_original=original_step,
        step_normalized=normalized_step,
        last_command=last_command,
        last_element_type=last_element_type,
        potential_duplicate=potential_duplicate,
    )
    
    if potential_duplicate:
        print(f"⚠️ Detected likely duplicate reference command, skipping: '{step_input}'")
        result = {
            'code': '# Skipping duplicate reference action',
            'explanation': 'Skipping redundant click action that references the previous element',
            'description': 'Skip Redundant Action'
        }
        log_step_result("duplicate_skip", result, success=False)
        return result
    
    # Store the original step in the command history
    add_step_to_history(original_step, normalized_step)
    
    # Use a decision tree to determine the type of step and handle it appropriately
    if is_reference_command(normalized_step):
        print(f"🔍 Detected reference command: '{step_input}'")
        result = handle_reference_command(normalized_step)
        log_step_result("reference", result)
        return result
    
    if is_keyboard_command(normalized_step):
        print(f"⌨️ Processing keyboard command: '{step_input}'")
        result = handle_keyboard_command(normalized_step)
        log_step_result("keyboard", result)
        return result
    
    if is_scroll_command(normalized_step):
        print(f"📜 Processing scroll command: '{step_input}'")
        result = handle_scroll_command(normalized_step)
        log_step_result("scroll", result)
        return result
    
    if is_typing_command(normalized_step):
        print(f"📝 Processing typing command: '{step_input}'")
        result = handle_typing_command(normalized_step, ui_description, original_step)
        log_step_result("typing", result)
        return result
    
    # If none of the above, assume it's a UI element command
    result = handle_ui_element_command(normalized_step, ui_description)
    log_step_result("ui_element", result)
    return result

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
        
        # Log the steps that will be processed
        logger.info(f"Command '{user_input}' was segmented into {len(steps)} steps")
        for i, step in enumerate(steps, 1):
            logger.info(f"Step {i}: - {step}")
        
        # Track which steps are processed
        processed_steps = []
        skipped_steps = []
        
        # Include import for time module for sleep commands
        code_lines.append("import time  # For sleep between steps")
        
        # Process each step individually
        print(f"🔄 Processing multi-step query with {len(steps)} steps:")
        for i, step in enumerate(steps):
            print(f"  Step {i+1}: '{step}'")  # Add quotes to better see step boundaries
            
            try:
                # Process the individual step
                step_result = process_single_step(step, ui_description)
                
                # Track that this step was processed
                processed_steps.append({
                    'step_number': i + 1,
                    'step': step,
                    'has_code': bool(step_result.get('code')),
                    'success': bool(step_result.get('code') and not step_result.get('code', '').strip().startswith('#'))
                })
                
                # Add the commands from this step
                if step_result['code']:
                    if i > 0:
                        code_lines.append("")  # Add a blank line between steps
                        code_lines.append(f"# Step {i+1}: {step}")
                    
                    for code_line in step_result['code'].split('\n'):
                        code_lines.append(code_line)
                    
                    # Add sleep between steps
                    if i < len(steps) - 1:  # Don't add sleep after the last step
                        code_lines.append("time.sleep(0.5)  # Wait between steps")
                    
                    explanation.append(f"\nStep {i+1}: {step}")
                    explanation.append(step_result['explanation'])
                    if i < len(steps) - 1:
                        explanation.append("Waiting 1 second between steps")
                else:
                    skipped_steps.append({
                        'step_number': i + 1,
                        'step': step,
                        'reason': 'no_code_generated'
                    })
                    explanation.append(f"\nStep {i+1}: {step} (Failed: No matching elements found)")
                    logger.warning(f"Step {i+1} ('{step}') did not generate any code")
                    
                    # Log structured event for skipped step
                    structured_usage_log(
                        "command.step.skipped",
                        step_original=step,
                        step_number=i + 1,
                        total_steps=len(steps),
                        reason="no_code_generated"
                    )
            except Exception as e:
                skipped_steps.append({
                    'step_number': i + 1,
                    'step': step,
                    'reason': f'error: {str(e)}'
                })
                logger.error(f"Error processing step {i+1} ('{step}'): {str(e)}")
                explanation.append(f"\nStep {i+1}: {step} (Error: {str(e)})")
                
                # Log structured event for skipped step due to error
                structured_usage_log(
                    "command.step.skipped",
                    step_original=step,
                    step_number=i + 1,
                    total_steps=len(steps),
                    reason=f"error: {str(e)}"
                )
        
        # Log summary of processed vs skipped steps
        if skipped_steps:
            logger.warning(f"Some steps were skipped: {len(skipped_steps)}/{len(steps)} steps had issues")
            for skipped in skipped_steps:
                logger.warning(f"  - Step {skipped['step_number']}: '{skipped['step']}' - {skipped['reason']}")
        
        # Verify all steps were processed
        if len(processed_steps) + len(skipped_steps) != len(steps):
            logger.error(f"Step count mismatch: Expected {len(steps)} steps, processed {len(processed_steps)}, skipped {len(skipped_steps)}")
            missing_steps = set(range(1, len(steps) + 1)) - set(s['step_number'] for s in processed_steps + skipped_steps)
            if missing_steps:
                logger.error(f"Missing steps: {missing_steps}")
                for step_num in missing_steps:
                    structured_usage_log(
                        "command.step.skipped",
                        step_original=steps[step_num - 1],
                        step_number=step_num,
                        total_steps=len(steps),
                        reason="never_processed"
                    )
    else:
        # Single step query - process as before
        single_result = process_single_step(user_input, ui_description)
        code_lines = single_result['code'].split('\n')
        explanation.append(single_result['explanation'])
    
    return {
        'code': '\n'.join(code_lines),
        'explanation': '\n'.join(explanation)
    }
