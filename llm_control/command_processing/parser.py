import re
import logging
from llm_control import STEP_SEPARATORS, ACTION_VERBS, structured_usage_log

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def normalize_step(step_input):
    """Normalize the step input by removing prefixes like 'then'"""
    normalized_step = step_input
    if normalized_step.lower().startswith('then '):
        normalized_step = normalized_step[5:].strip()
    return normalized_step

def split_user_input_into_steps(user_input):
    """
    Split a user input string into individual steps
    Returns a list of step strings
    """
    # Remove trailing period if present (to prevent it from being treated as a separate step)
    if user_input.endswith('.'):
        user_input = user_input[:-1].strip()
        
    steps = []
    
    # First, check if the input is a single operation (no need to split)
    # Common patterns for single operations that should not be split
    single_operation_patterns = [
        r'^click\s+(on\s+)?[a-zA-Z0-9\s]+$',  # Simple click commands (click on X)
        r'^move\s+to\s+[a-zA-Z0-9\s]+$',      # Simple move commands (move to X)
        r'^type\s+["\'][^"\']+["\']$',        # Type with quoted text
        r'^press\s+[a-zA-Z0-9\s]+$',          # Press key commands
    ]
    
    # Check if the input matches any single operation pattern
    if any(re.match(pattern, user_input.lower()) for pattern in single_operation_patterns):
        return [user_input]
    
    # Special handling for "Escribe, [texto]" pattern - should be treated as single typing step
    # Check if command starts with typing verb followed by comma and text (not another action)
    typing_verbs = ['escribe', 'type', 'write', 'teclea', 'enter']
    user_input_lower = user_input.lower()
    
    # Detect "Escribe, [texto]" pattern - don't split if comma is after typing verb and followed by text
    should_preserve_typing = False
    for verb in typing_verbs:
        # Pattern: "Escribe, [texto sin verbo de acción]"
        pattern = rf'^{verb}\s*,\s+'
        if re.match(pattern, user_input_lower):
            # Check if what comes after the comma is text (not an action verb)
            after_comma = user_input[user_input.find(',') + 1:].strip()
            after_comma_lower = after_comma.lower()
            
            # If after comma doesn't start with an action verb, it's text to type
            if not any(after_comma_lower.startswith(action) for action in ACTION_VERBS):
                should_preserve_typing = True
                break
    
    # Try comma splitting first for cases like "move to X, click"
    # BUT: Skip if it's a "Escribe, [texto]" pattern
    if "," in user_input and not should_preserve_typing:
        # Split by comma but ensure we don't break quoted text
        in_quotes = False
        current_step = ""
        for char in user_input:
            if char in ['"', "'"]:
                in_quotes = not in_quotes
            
            if char == ',' and not in_quotes:
                if current_step.strip():
                    steps.append(current_step.strip())
                current_step = ""
            else:
                current_step += char
        
        # Add the last step if there's anything left
        if current_step.strip():
            steps.append(current_step.strip())
    
    # If comma splitting didn't work or found only one step, try other separators
    if len(steps) <= 1:
        steps = []  # Reset steps
        remaining_input = user_input
        
        # Start with the most specific separators (longest first)
        for separator in sorted(STEP_SEPARATORS, key=len, reverse=True):
            if separator in remaining_input:
                parts = remaining_input.split(separator)
                for i, part in enumerate(parts):
                    if i == 0:
                        steps.append(part.strip())
                    else:
                        steps.append(part.strip())
                
                # If we've successfully split the query, stop trying other separators
                if len(steps) > 1:
                    break
        
    # If no specific separators were found but "then" or "and" is in the query
    if not steps:
        for word in ['then', 'and']:
            if word in user_input.lower():
                # Make sure we're dealing with "then" or "and" as separators, not part of words
                # For example "backend" contains "and" but should not be split
                parts = re.split(rf'\b{word}\b', user_input, flags=re.IGNORECASE)
                steps = [s.strip() for s in parts if s.strip()]
                if len(steps) > 1:
                    break
    
    # If we still don't have multiple steps, just use the whole query
    if len(steps) <= 1:
        steps = [user_input]
    
    # Post-process steps to merge adjacent ones that might be part of the same operation
    # BUT: Don't merge if they were separated by a comma and represent different actions
    final_steps = []
    i = 0
    comma_separated = "," in user_input  # Track if original input had commas
    
    while i < len(steps):
        current = steps[i]
        
        # If this is just "click" or "click on" and there's a next step that's not a verb
        if i < len(steps) - 1:
            next_step = steps[i+1]
            current_lower = current.lower()
            next_lower = next_step.lower()
            
            # Check if current step is a standalone action verb
            is_standalone_verb = current_lower in ['click', 'click on', 'move to', 'press']
            
            # Check if current step is a typing/writing command
            is_typing_command = any(current_lower.startswith(cmd) for cmd in ['type', 'write', 'escribe', 'teclea', 'enter'])
            
            # Check if next step doesn't start with an action verb
            next_has_no_verb = not any(next_lower.startswith(verb) for verb in ACTION_VERBS)
            
            # Check if next step starts with an action verb (different action)
            next_has_verb = any(next_lower.startswith(verb) for verb in ACTION_VERBS)
            
            # Don't merge if:
            # 1. They were separated by comma AND next step is a different action
            # 2. Current is typing command AND next step starts with action verb (definitely different action)
            # BUT: If current is "Escribe," or "type," and next is text (not an action), merge them (it's "Escribe, [texto]")
            should_not_merge = False
            should_merge_typing = False
            
            if comma_separated:
                # Special case: "Escribe, [texto]" - should merge
                if is_typing_command and len(current.split()) <= 2 and not next_has_verb:
                    # Current is just "Escribe," and next is text without action verb - merge them
                    should_merge_typing = True
                # If comma-separated and next step is a different action, don't merge
                elif next_has_verb:
                    should_not_merge = True
            
            # Merge typing commands with their text: "Escribe, [texto]"
            if should_merge_typing:
                # Merge "Escribe," with the following text
                final_steps.append(f"{current} {next_step}")
                i += 2  # Skip both steps
                continue
            
            if is_standalone_verb and next_has_no_verb and not should_not_merge:
                # Merge the two steps
                final_steps.append(f"{current} {next_step}")
                i += 2  # Skip both steps
                continue
        
        final_steps.append(current)
        i += 1
    
    # Additional parsing for keyboard actions
    refined_steps = []
    
    # Regex patterns for keyboard actions that should be split
    keyboard_patterns = [
        # Modified pattern to handle Spanish "escribe a" and similar constructs
        (r'(\btype\s+[^\s]+.*|\bteclea\s+[^\s]+.*|\bescribe\s+[^\s]+.*|\bwrite\s+[^\s]+.*|\benter\s+[^\s]+.*)', 'type'),
        (r'(\bpress\s+\w+|\bpulsa\s+\w+|\bpresiona\s+\w+|\bhit\s+\w+|\boprime\s+\w+)', 'press')
    ]
    
    for step in final_steps:
        # Check if this is already a simple step
        if any(re.match(f'^{pattern[0]}$', step.lower()) for pattern in keyboard_patterns):
            refined_steps.append(step)
            continue
        
        # Check if we need to split this step for keyboard actions
        matches = []
        for pattern, action_type in keyboard_patterns:
            for match in re.finditer(pattern, step, re.IGNORECASE):
                matches.append((match.start(), match.end(), match.group(), action_type))
        
        # Sort matches by position
        matches.sort(key=lambda x: x[0])
        
        if matches:
            # Process step with keyboard action patterns
            last_end = 0
            for start, end, matched_text, action_type in matches:
                # Add text before this match if it's not just whitespace
                prefix = step[last_end:start].strip()
                if prefix and not any(prefix.lower().endswith(f" {verb}") for verb in ["y", "luego", "then", "and"]):
                    refined_steps.append(prefix)
                
                # Add the matched action
                refined_steps.append(matched_text)
                last_end = end
            
            # Add any remaining text after the last match
            suffix = step[last_end:].strip()
            if suffix and not suffix.lower().startswith(("y ", "luego ", "then ", "and ")):
                refined_steps.append(suffix)
        else:
            # No keyboard actions to split, keep the step as is
            refined_steps.append(step)
    
    # Final cleanup - Remove any standalone punctuation steps
    refined_steps = [step for step in refined_steps if step.strip() not in ['.', ',', ';']]
    
    # Log the initial step splitting for debugging
    print(f"🔄 Initial step splitting: {refined_steps}")
    structured_usage_log(
        "command.steps_split",
        raw=user_input,
        total_steps=len(refined_steps),
        steps=refined_steps,
    )
    
    return refined_steps

def clean_and_normalize_steps(steps):
    """
    Process a list of steps to handle continuations and normalize step text
    Returns a list of cleaned steps
    """
    clean_steps = []
    
    for i, step in enumerate(steps):
        step_lower = step.lower()
        
        # Check if this step starts with an action verb
        has_action_verb = any(step_lower.startswith(verb) for verb in ACTION_VERBS)
        
        # If not the first step and doesn't start with an action verb, it might be a continuation
        if i > 0 and not has_action_verb and not step_lower.startswith('then') and not step_lower.startswith('and'):
            prev_step_lower = clean_steps[-1].lower()
            
            # Check if previous step is JUST a typing verb (e.g., "escribe", "type") without text
            # Special case: "Escribe, [texto]" should be merged (comma indicates continuation of typing command)
            prev_is_just_typing_verb = (
                (prev_step_lower in ['escribe', 'type', 'write', 'teclea', 'enter'] or
                 prev_step_lower.startswith('escribe ') and len(clean_steps[-1].split()) <= 2 or
                 prev_step_lower.startswith('type ') and len(clean_steps[-1].split()) <= 2) and
                len(step.split()) > 3  # Next step is substantial text
            )
            
            # Check if previous step ends with comma (indicates "Escribe, [texto]" pattern)
            prev_ends_with_comma = clean_steps[-1].rstrip().endswith(',')
            
            # Try to infer the action from context
            if 'type' in prev_step_lower or 'write' in prev_step_lower or 'escribe' in prev_step_lower:
                # Previous step was about typing
                # If previous step ends with comma, merge it (it's "Escribe, [texto]")
                if prev_ends_with_comma:
                    # Merge "Escribe," with the following text
                    clean_steps[-1] = f"{clean_steps[-1].rstrip(',')} {step}"
                elif prev_is_just_typing_verb:
                    # Don't merge - they were separated for a reason (likely comma-separated but not "Escribe, [texto]")
                    # Add implied action to current step
                    clean_steps.append(step)
                else:
                    # Previous step already has text, this is likely continuation
                    clean_steps[-1] = f"{clean_steps[-1]} {step}"
            else:
                # Add an implied action based on the previous step
                if 'click' in prev_step_lower:
                    prefix = 'click on '
                elif 'move' in prev_step_lower:
                    prefix = 'move to '
                else:
                    prefix = 'interact with '
                
                clean_steps.append(f"{prefix}{step}")
        else:
            clean_steps.append(step)
    
    return clean_steps
