# LLM Control Refactor Plan

## ✅ Completed Tasks

### Directory Structure Reorganization
- ✅ Created an organized directory structure:
  ```
  llm-control/
  ├── llm_control/         # Main Python package
  ├── scripts/             # Utility scripts
  │   ├── docker/          # Docker-related scripts
  │   ├── setup/           # Installation scripts
  │   └── tools/           # Utility tools
  ├── examples/            # Example scripts
  ├── docs/                # Documentation
  ├── tests/               # Test suite
  ├── data/                # Data files
  ├── logs/                # Log files
  └── screenshots/         # Screenshots directory
  ```
- ✅ Updated path references in all scripts
- ✅ Updated the README.md to reflect the new structure
- ✅ Updated .gitignore to match the new organization
- ✅ Verified the voice server works after restructuring

## Remaining Tasks

### Phase 1: Core Refactoring

1. **Modularize the Voice Control Server**

Split the monolithic voice_control_server.py into smaller, focused modules:

```
llm_control/
├── __init__.py
├── voice_server/
│   ├── __init__.py
│   ├── server.py              # Main server implementation
│   ├── transcription.py       # Audio transcription functions
│   ├── translation.py         # Language translation 
│   ├── command_processor.py   # Command parsing
│   └── action_generator.py    # PyAutoGUI command generation
└── llm/
    ├── __init__.py
    ├── client.py              # LLM client implementation
    ├── prompts.py             # LLM prompting templates
    └── parsers.py             # Response parsing utilities
```

### Phase 2: Improve PyAutoGUI Command Generation

1. **Create a Dedicated PyAutoGUI Command Generator**

```python
# llm_control/voice_server/action_generator.py
from typing import List, Dict, Any
import json
import re

class PyAutoGUIGenerator:
    def __init__(self, llm_client):
        self.llm_client = llm_client
        
    def generate_from_natural_language(self, command: str, steps: List[str], 
                                       ui_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate PyAutoGUI commands from natural language steps"""
        
        # Generate from scratch
        return self._generate_new_commands(steps, ui_elements)
    
    def _generate_new_commands(self, steps: List[str], ui_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate PyAutoGUI commands from scratch using LLM"""
        actions = []
        
        # Prepare context with UI elements for LLM
        ui_context = json.dumps(ui_elements, indent=2)
        
        for step in steps:
            # Formulate prompt for the LLM
            prompt = f"""
            Based on the following UI elements detected on screen:
            {ui_context}
            
            Generate a Python PyAutoGUI command to execute this step: "{step}"
            
            Return ONLY valid Python code that can be executed, with no additional explanation.
            Use the most precise PyAutoGUI function for the task, such as click(), moveTo(), typewrite(), etc.
            """
            
            # Get response from LLM
            response = self.llm_client.generate(prompt)
            
            # Clean up the response to get just the PyAutoGUI command
            pyautogui_cmd = self._extract_code(response)
            
            actions.append({
                "description": step,
                "pyautogui_cmd": pyautogui_cmd,
                "generated_from": "llm"
            })
            
        return actions
    
    def _extract_code(self, text: str) -> str:
        """Extract code from LLM response"""
        # Remove markdown code blocks if present
        if "```python" in text:
            match = re.search(r"```python\n(.*?)\n```", text, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        # Otherwise return the cleaned text
        return text.strip()
```

2. **Implement Action Validation and Safety**

```python
# llm_control/voice_server/action_validator.py
import re
from typing import Dict, Any, Tuple, List

class ActionValidator:
    """Validates and sanitizes PyAutoGUI commands for safety"""
    
    # Define dangerous patterns or commands to block
    DANGEROUS_PATTERNS = [
        r"subprocess\.(?:Popen|call|run)",
        r"os\.(?:system|popen|spawn|exec)",
        r"eval\(",
        r"exec\(",
        r"import (?:(?!pyautogui|time|re|json).)*$",  # Block imports except safe ones
        r"open\([^)]*,\s*['\"]\s*w",  # Open files in write mode
        r"hotkey\(['\"](alt|ctrl|cmd|win)['\"],\s*['\"](f4|q)['\"]"  # Alt+F4, Ctrl+Q, etc.
    ]
    
    # Define allowed PyAutoGUI functions
    ALLOWED_FUNCTIONS = [
        "click", "rightClick", "doubleClick", "tripleClick",
        "moveTo", "moveRel", "dragTo", "dragRel",
        "scroll", "hscroll", "vscroll",
        "typewrite", "write", "press", "keyDown", "keyUp",
        "screenshot", "locateOnScreen", "locateCenterOnScreen",
        "position", "size", "onScreen",
        "PAUSE", "FAILSAFE"
    ]
    
    def validate_action(self, action: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate a PyAutoGUI action for safety
        
        Returns:
            (is_valid, error_message)
        """
        cmd = action.get("pyautogui_cmd", "")
        
        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, cmd, re.IGNORECASE):
                return False, f"Command contains dangerous pattern: {pattern}"
        
        # Ensure command only uses allowed PyAutoGUI functions
        function_match = re.findall(r"(?:pyautogui|pg)\.(\w+)\(", cmd)
        for func in function_match:
            if func not in self.ALLOWED_FUNCTIONS:
                return False, f"Command uses disallowed function: {func}"
        
        return True, ""
    
    def sanitize_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sanitize a list of actions, replacing any invalid ones with safe versions"""
        sanitized = []
        
        for action in actions:
            is_valid, error = self.validate_action(action)
            
            if is_valid:
                sanitized.append(action)
            else:
                # Replace with safe no-op action
                sanitized.append({
                    "description": action.get("description", "") + f" [BLOCKED: {error}]",
                    "pyautogui_cmd": "# Command was blocked for security reasons\nprint('Command was blocked: Security violation')",
                    "error": error,
                    "original_cmd": action.get("pyautogui_cmd", "")
                })
                
        return sanitized
```

### Phase 3: Code to Drop

1. **Legacy Files to Remove**
   - `t.json` (cleanup already started)
   - Redundant test scripts that duplicate functionality

2. **Consolidate Server Implementations**
   - Remove redundant server implementations
   - Standardize on a single server architecture
   - Create clear separation between REST and WebSocket endpoints

3. **Screenshot Management**
   - Implement a screenshot cleanup policy
   - Add timestamp-based cleanup for old screenshots

### Phase 4: Implementation Timeline

1. **Week 1: Complete File Structure Work**
   - ✅ Reorganize directory structure (COMPLETED)
   - ✅ Update imports in all files to match new structure
   - Create comprehensive package initialization files

2. **Week 2-3: Core Refactoring**
   - Split monolithic server into modules
   - Update API endpoints to use the new structure

3. **Week 4-5: Improve PyAutoGUI Generation**
   - Implement dedicated generator
   - Add command validation
   - Create test cases for validation

4. **Week 6: Clean-up and Documentation**
   - Remove deprecated code
   - Add comprehensive documentation
   - Create migration guides for users

## Benefits of the Refactor

1. **Improved Maintainability**: Smaller, focused modules are easier to update
2. **Enhanced Security**: Validation prevents dangerous commands
3. **Cleaner Codebase**: Dropping redundant code reduces confusion
4. **Incremental Enhancement**: The modular design allows for progressive improvements
5. **Better PyAutoGUI Command Generation**: More accurate commands from natural language
6. **Organized File Structure**: ✅ A clear, intuitive project organization (COMPLETED)

## Next Steps

1. Update imports in Python files to reflect the new directory structure
2. Begin implementing the voice server modularization
3. Focus on implementing the PyAutoGUI command generator with safety checks 