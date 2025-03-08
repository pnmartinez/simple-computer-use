import re
import logging
from llm_control import STEP_SEPARATORS, ACTION_VERBS

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
    steps = []
    
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
                # Split but preserve words like "backend" that contain "and"
                parts = re.split(rf'\b{word}\b', user_input, flags=re.IGNORECASE)
                steps = [s.strip() for s in parts if s.strip()]
                if len(steps) > 1:
                    break
    
    # If we still don't have multiple steps, just use the whole query
    if len(steps) <= 1:
        steps = [user_input]
    
    # Log the initial step splitting for debugging
    print(f"🔄 Initial step splitting: {steps}")
    
    return steps

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
