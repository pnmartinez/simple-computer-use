# LLM Control Refactor Plan

## Current System Analysis

### Database Structure

After analyzing the codebase, I noted that there is **no formal database structure** currently implemented. Data persistence appears to rely primarily on:

1. **In-memory storage**: Most state is kept in memory during server runtime
2. **Screenshot files**: Saved to disk for UI analysis and debugging
3. **JSON responses**: Used for API communication, but not persisted

The absence of a persistent database means there's no long-term storage for:
- Command history
- User preferences
- Performance metrics
- Training data for improving accuracy

### Code Structure Assessment

#### Main Components

1. **Voice Control Server** (`llm_control/voice_control_server.py`): Large monolithic server file (~2000 lines) handling voice command processing
2. **Server Implementation** (`llm_control/server.py`): Base server functionality
3. **UI Detection** (`llm_control/ui_detection/`): Logic for identifying UI elements
4. **Command Processing** (`llm_control/command_processing/`): Command parsing and execution

#### Major Inefficiencies

1. **Monolithic Design**: The voice control server file contains multiple responsibilities that should be separated
2. **No Persistence Layer**: Lack of database means no history or learning capabilities
3. **Duplicated Code**: Multiple implementations of similar functionality across files
4. **Manual PyAutoGUI Generation**: Commands are generated in a complex multi-step process

#### Redundant Code to Consider Dropping

1. **Legacy Scripts**: Multiple test and demo scripts with overlapping functionality
2. **Older Implementation Files**: `main.py` and `utils.py` in the root directory
3. **Duplicate Screenshots**: No cleanup mechanism for old screenshots
4. **Multiple Server Implementations**: Several variations of the same server

## Refactor Plan

### Phase 1: Database Implementation

1. **Create a SQLite Database Schema**

```sql
-- Command History Table
CREATE TABLE command_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    raw_command TEXT,               -- Original user command
    language_code TEXT,             -- Original language
    translated_command TEXT,        -- Translated command (if applicable)
    success BOOLEAN,                -- Whether execution succeeded
    execution_time REAL,            -- Time taken to execute
    screenshot_path TEXT            -- Path to associated screenshot
);

-- Command Steps Table
CREATE TABLE command_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id INTEGER,
    step_number INTEGER,
    step_description TEXT,
    step_type TEXT,                 -- click, type, scroll, etc.
    target_element TEXT,            -- Element description or coordinates
    pyautogui_cmd TEXT,             -- Generated PyAutoGUI command
    success BOOLEAN,
    error_message TEXT,
    FOREIGN KEY (command_id) REFERENCES command_history(id)
);

-- UI Elements Table
CREATE TABLE ui_elements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id INTEGER,
    element_type TEXT,              -- button, text_field, icon, etc.
    element_text TEXT,              -- Text content
    x1 INTEGER, y1 INTEGER,         -- Top-left coordinates
    x2 INTEGER, y2 INTEGER,         -- Bottom-right coordinates
    confidence REAL,                -- Detection confidence
    clicked BOOLEAN,                -- Whether element was clicked
    FOREIGN KEY (command_id) REFERENCES command_history(id)
);

-- User Preferences Table
CREATE TABLE user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    value TEXT
);

-- System Metrics Table
CREATE TABLE system_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    metric_name TEXT,
    metric_value REAL,
    description TEXT
);
```

2. **Create Database Models**

Implement Python classes for database interaction using SQLAlchemy:

```python
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import datetime

Base = declarative_base()

class CommandHistory(Base):
    __tablename__ = 'command_history'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    raw_command = Column(String)
    language_code = Column(String)
    translated_command = Column(String)
    success = Column(Boolean)
    execution_time = Column(Float)
    screenshot_path = Column(String)
    
    steps = relationship("CommandStep", back_populates="command")
    ui_elements = relationship("UIElement", back_populates="command")

class CommandStep(Base):
    __tablename__ = 'command_steps'
    
    id = Column(Integer, primary_key=True)
    command_id = Column(Integer, ForeignKey('command_history.id'))
    step_number = Column(Integer)
    step_description = Column(String)
    step_type = Column(String)
    target_element = Column(String)
    pyautogui_cmd = Column(String)
    success = Column(Boolean)
    error_message = Column(String)
    
    command = relationship("CommandHistory", back_populates="steps")

class UIElement(Base):
    __tablename__ = 'ui_elements'
    
    id = Column(Integer, primary_key=True)
    command_id = Column(Integer, ForeignKey('command_history.id'))
    element_type = Column(String)
    element_text = Column(String)
    x1 = Column(Integer)
    y1 = Column(Integer)
    x2 = Column(Integer)
    y2 = Column(Integer)
    confidence = Column(Float)
    clicked = Column(Boolean)
    
    command = relationship("CommandHistory", back_populates="ui_elements")

class UserPreference(Base):
    __tablename__ = 'user_preferences'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    value = Column(String)

class SystemMetric(Base):
    __tablename__ = 'system_metrics'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    metric_name = Column(String)
    metric_value = Column(Float)
    description = Column(String)
```

### Phase 2: Core Refactoring

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
├── database/
│   ├── __init__.py
│   ├── models.py              # SQLAlchemy models
│   ├── session.py             # Database session management
│   └── repository.py          # Data access layer
└── llm/
    ├── __init__.py
    ├── client.py              # LLM client implementation
    ├── prompts.py             # LLM prompting templates
    └── parsers.py             # Response parsing utilities
```

2. **Implement Repository Pattern for Data Access**

Create a cleaner data access layer:

```python
# llm_control/database/repository.py
from sqlalchemy.orm import Session
from typing import List, Optional
from . import models

class CommandRepository:
    def __init__(self, session: Session):
        self.session = session
    
    def add_command(self, command_data):
        """Add a new command to the history"""
        command = models.CommandHistory(**command_data)
        self.session.add(command)
        self.session.commit()
        return command
    
    def get_command_history(self, limit=10) -> List[models.CommandHistory]:
        """Get recent command history"""
        return self.session.query(models.CommandHistory).order_by(
            models.CommandHistory.timestamp.desc()
        ).limit(limit).all()
    
    def get_successful_commands(self) -> List[models.CommandHistory]:
        """Get commands that completed successfully"""
        return self.session.query(models.CommandHistory).filter(
            models.CommandHistory.success == True
        ).order_by(models.CommandHistory.timestamp.desc()).all()
    
    def add_command_step(self, command_id, step_data):
        """Add a step to an existing command"""
        step = models.CommandStep(command_id=command_id, **step_data)
        self.session.add(step)
        self.session.commit()
        return step
    
    def add_ui_element(self, command_id, element_data):
        """Add a UI element to an existing command"""
        element = models.UIElement(command_id=command_id, **element_data)
        self.session.add(element)
        self.session.commit()
        return element
```

### Phase 3: Improve PyAutoGUI Command Generation

1. **Create a Dedicated PyAutoGUI Command Generator**

```python
# llm_control/voice_server/action_generator.py
from typing import List, Dict, Any
import json
import re
from llm_control.database.repository import CommandRepository

class PyAutoGUIGenerator:
    def __init__(self, llm_client, command_repository: CommandRepository = None):
        self.llm_client = llm_client
        self.command_repository = command_repository
        
    def generate_from_natural_language(self, command: str, steps: List[str], 
                                       ui_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate PyAutoGUI commands from natural language steps"""
        
        # First, check history for similar commands if repository exists
        if self.command_repository:
            similar_commands = self._find_similar_commands(command)
            if similar_commands:
                # Use the most successful similar command as reference
                return self._adapt_from_similar_command(similar_commands[0], steps)
        
        # If no similar commands or no repository, generate from scratch
        return self._generate_new_commands(steps, ui_elements)
    
    def _find_similar_commands(self, command: str) -> List[Dict[str, Any]]:
        """Find similar commands in history"""
        # This would use the database to find commands with similar text
        # Could implement fuzzy matching or embedding-based similarity
        if not self.command_repository:
            return []
        
        # Query DB for similar commands that succeeded
        # This is a placeholder for actual implementation
        return []
    
    def _adapt_from_similar_command(self, similar_command, new_steps: List[str]) -> List[Dict[str, Any]]:
        """Adapt commands from a similar historical command"""
        # This would use a successful historical command as a template
        # and adapt it to the new context
        # Placeholder implementation
        return []
    
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

### Phase 4: Code to Drop

1. **Legacy Files to Remove**
   - `utils.py` (root directory)
   - `main.py` (root directory)
   - `struct.json`
   - All test_*.py files that duplicate functionality

2. **Consolidate Server Implementations**
   - Remove redundant server implementations
   - Standardize on a single server architecture
   - Create clear separation between REST and WebSocket endpoints

3. **Screenshot Management**
   - Implement a screenshot cleanup policy
   - Store screenshots in database references
   - Add timestamp-based cleanup for old screenshots

### Phase 5: Implementation Timeline

1. **Week 1-2: Setup Database Infrastructure**
   - Create SQLite schema
   - Implement SQLAlchemy models
   - Add migration script for existing data

2. **Week 3-4: Core Refactoring**
   - Split monolithic server into modules
   - Implement repository pattern
   - Update API endpoints to use the new structure

3. **Week 5-6: Improve PyAutoGUI Generation**
   - Implement dedicated generator
   - Add command validation
   - Create test cases for validation

4. **Week 7-8: Clean-up and Documentation**
   - Remove deprecated code
   - Add comprehensive documentation
   - Create migration guides for users

## Benefits of the Refactor

1. **Improved Maintainability**: Smaller, focused modules are easier to update
2. **Better Data Persistence**: Database storage enables learning from past actions
3. **Enhanced Security**: Validation prevents dangerous commands
4. **Cleaner Codebase**: Dropping redundant code reduces confusion
5. **Command Learning**: The system can improve by learning from successful commands
6. **Performance Tracking**: Metrics stored in the database enable analysis
7. **Incremental Enhancement**: The modular design allows for progressive improvements 