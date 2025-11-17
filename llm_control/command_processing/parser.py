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
    
    # Try comma splitting first for cases like "move to X, click"
    if "," in user_input:
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
    final_steps = []
    i = 0
    while i < len(steps):
        current = steps[i]
        
        # If this is just "click" or "click on" and there's a next step that's not a verb
        if i < len(steps) - 1:
            next_step = steps[i+1]
            current_lower = current.lower()
            next_lower = next_step.lower()
            
            # Check if current step is a standalone action verb
            is_standalone_verb = current_lower in ['click', 'click on', 'move to', 'press']
            
            # Check if next step doesn't start with an action verb
            next_has_no_verb = not any(next_lower.startswith(verb) for verb in ACTION_VERBS)
            
            if is_standalone_verb and next_has_no_verb:
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
            # Try to infer the action from context
            if 'type' in clean_steps[-1].lower() or 'write' in clean_steps[-1].lower():
                # Previous step was about typing, this is likely the text to type
                clean_steps[-1] = f"{clean_steps[-1]} {step}"
            else:
                # Add an implied action based on the previous step
                if 'click' in clean_steps[-1].lower():
                    prefix = 'click on '
                elif 'move' in clean_steps[-1].lower():
                    prefix = 'move to '
                else:
                    prefix = 'interact with '
                
                clean_steps.append(f"{prefix}{step}")
        else:
            clean_steps.append(step)
    
    return clean_steps
