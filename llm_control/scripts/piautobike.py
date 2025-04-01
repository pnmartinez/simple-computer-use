"""
Piautobike scripts management module.

This module provides functionality to create, save, load, and execute Piautobike scripts.
"""

import os
import json
import time
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

# Configure logging
logger = logging.getLogger("piautobike-scripts")

# Define the scripts directory
SCRIPTS_DIR = os.environ.get("PIAUTOBIKE_SCRIPTS_DIR", os.path.join(os.path.expanduser("~"), ".piautobike", "scripts"))

# Ensure scripts directory exists
os.makedirs(SCRIPTS_DIR, exist_ok=True)

class PiautobikeScript:
    """Class representing a Piautobike script with metadata and commands."""
    
    def __init__(
        self, 
        name: str, 
        description: str, 
        commands: List[str], 
        pyautogui_code: Optional[str] = None,
        script_id: Optional[str] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        tags: Optional[List[str]] = None
    ):
        """
        Initialize a new Piautobike script.
        
        Args:
            name: Script name
            description: Script description
            commands: List of natural language commands
            pyautogui_code: Generated PyAutoGUI code
            script_id: Unique identifier for the script (generated if not provided)
            created_at: Creation timestamp (generated if not provided)
            updated_at: Last update timestamp (set to created_at if not provided)
            tags: List of tags for categorizing the script
        """
        self.name = name
        self.description = description
        self.commands = commands
        self.pyautogui_code = pyautogui_code or ""
        self.script_id = script_id or str(uuid.uuid4())
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or self.created_at
        self.tags = tags or []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert script to dictionary for serialization."""
        return {
            "script_id": self.script_id,
            "name": self.name,
            "description": self.description,
            "commands": self.commands,
            "pyautogui_code": self.pyautogui_code,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PiautobikeScript':
        """Create script instance from dictionary."""
        return cls(
            name=data.get("name", "Unnamed Script"),
            description=data.get("description", ""),
            commands=data.get("commands", []),
            pyautogui_code=data.get("pyautogui_code", ""),
            script_id=data.get("script_id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            tags=data.get("tags", [])
        )
    
    def save(self) -> str:
        """
        Save script to disk.
        
        Returns:
            Path to the saved script file
        """
        # Update timestamp
        self.updated_at = datetime.now().isoformat()
        
        # Create filename from script_id
        filename = f"{self.script_id}.json"
        filepath = os.path.join(SCRIPTS_DIR, filename)
        
        # Save to disk
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)
        
        logger.info(f"Saved script '{self.name}' to {filepath}")
        return filepath

def load_script(script_id: str) -> Optional[PiautobikeScript]:
    """
    Load a script by ID.
    
    Args:
        script_id: The unique identifier of the script
        
    Returns:
        The loaded script or None if not found
    """
    filepath = os.path.join(SCRIPTS_DIR, f"{script_id}.json")
    
    if not os.path.exists(filepath):
        logger.warning(f"Script with ID {script_id} not found at {filepath}")
        return None
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            script_data = json.load(f)
        
        return PiautobikeScript.from_dict(script_data)
    except Exception as e:
        logger.error(f"Error loading script {script_id}: {e}")
        return None

def list_scripts() -> List[Dict[str, Any]]:
    """
    List all available scripts with metadata.
    
    Returns:
        List of script metadata dictionaries
    """
    scripts = []
    
    # List all JSON files in scripts directory
    script_files = list(Path(SCRIPTS_DIR).glob("*.json"))
    
    for script_file in script_files:
        try:
            with open(script_file, 'r', encoding='utf-8') as f:
                script_data = json.load(f)
            
            # Include only metadata (exclude code)
            scripts.append({
                "script_id": script_data.get("script_id"),
                "name": script_data.get("name"),
                "description": script_data.get("description"),
                "created_at": script_data.get("created_at"),
                "updated_at": script_data.get("updated_at"),
                "tags": script_data.get("tags", []),
                "command_count": len(script_data.get("commands", []))
            })
        except Exception as e:
            logger.error(f"Error loading script from {script_file}: {e}")
    
    # Sort by updated_at (most recent first)
    scripts.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    
    return scripts

def delete_script(script_id: str) -> bool:
    """
    Delete a script by ID.
    
    Args:
        script_id: The unique identifier of the script
        
    Returns:
        True if deleted successfully, False otherwise
    """
    filepath = os.path.join(SCRIPTS_DIR, f"{script_id}.json")
    
    if not os.path.exists(filepath):
        logger.warning(f"Script with ID {script_id} not found at {filepath}")
        return False
    
    try:
        os.remove(filepath)
        logger.info(f"Deleted script {script_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting script {script_id}: {e}")
        return False

def execute_script(script: Union[str, PiautobikeScript]) -> Dict[str, Any]:
    """
    Execute a Piautobike script.
    
    Args:
        script: Either a script ID string or PiautobikeScript instance
        
    Returns:
        Dictionary with execution results
    """
    # Get script instance if ID is provided
    if isinstance(script, str):
        script_instance = load_script(script)
        if not script_instance:
            return {"success": False, "error": f"Script with ID {script} not found"}
    else:
        script_instance = script
    
    # Check if script has PyAutoGUI code
    if not script_instance.pyautogui_code:
        return {"success": False, "error": "Script doesn't contain executable PyAutoGUI code"}
    
    # Log execution
    logger.info(f"Executing script '{script_instance.name}' ({script_instance.script_id})")
    
    try:
        # Create local environment for script execution
        script_vars = {}
        exec_globals = {
            "pyautogui": __import__("pyautogui"),
            "time": __import__("time")
        }
        
        # Execute the script
        start_time = time.time()
        exec(script_instance.pyautogui_code, exec_globals, script_vars)
        execution_time = time.time() - start_time
        
        return {
            "success": True,
            "script_id": script_instance.script_id,
            "name": script_instance.name,
            "execution_time": execution_time
        }
    except Exception as e:
        logger.error(f"Error executing script '{script_instance.name}': {e}")
        return {
            "success": False,
            "script_id": script_instance.script_id,
            "name": script_instance.name,
            "error": str(e)
        }

def export_script(script_id: str, export_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Export a script to a specified directory or to a string.
    
    Args:
        script_id: The unique identifier of the script
        export_dir: Directory to save the exported script (if None, returns data without saving)
        
    Returns:
        Dictionary with export results
    """
    # Load the script
    script = load_script(script_id)
    if not script:
        return {"success": False, "error": f"Script with ID {script_id} not found"}
    
    # Convert to exportable format
    export_data = script.to_dict()
    
    # If export_dir is specified, save to file
    if export_dir:
        os.makedirs(export_dir, exist_ok=True)
        safe_name = "".join(c if c.isalnum() else "_" for c in script.name).lower()
        export_path = os.path.join(export_dir, f"{safe_name}_{script_id}.json")
        
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2)
            
            logger.info(f"Exported script '{script.name}' to {export_path}")
            
            return {
                "success": True,
                "script_id": script_id,
                "name": script.name,
                "export_path": export_path
            }
        except Exception as e:
            logger.error(f"Error exporting script '{script.name}': {e}")
            return {
                "success": False,
                "script_id": script_id,
                "name": script.name,
                "error": str(e)
            }
    
    # If no export_dir, just return the data
    return {
        "success": True,
        "script_id": script_id,
        "name": script.name,
        "export_data": export_data
    }

def import_script(import_data: Dict[str, Any], replace_existing: bool = False) -> Dict[str, Any]:
    """
    Import a script from a dictionary or JSON file.
    
    Args:
        import_data: Dictionary with script data or path to JSON file
        replace_existing: Whether to replace if a script with the same ID exists
        
    Returns:
        Dictionary with import results
    """
    try:
        # Check if import_data is a file path
        if isinstance(import_data, str) and os.path.exists(import_data):
            with open(import_data, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
        
        # Create script instance from imported data
        script = PiautobikeScript.from_dict(import_data)
        
        # Check if script with this ID already exists
        existing_script = load_script(script.script_id)
        if existing_script and not replace_existing:
            return {
                "success": False,
                "script_id": script.script_id,
                "name": script.name,
                "error": f"Script with ID {script.script_id} already exists"
            }
        
        # Save the imported script
        script.save()
        
        logger.info(f"Imported script '{script.name}' successfully")
        
        return {
            "success": True,
            "script_id": script.script_id,
            "name": script.name,
            "message": "Script imported successfully"
        }
    except Exception as e:
        logger.error(f"Error importing script: {e}")
        return {
            "success": False,
            "error": f"Error importing script: {str(e)}"
        }

def batch_import_scripts(import_dir: str, replace_existing: bool = False) -> Dict[str, Any]:
    """
    Import multiple scripts from a directory.
    
    Args:
        import_dir: Directory containing script JSON files
        replace_existing: Whether to replace existing scripts
        
    Returns:
        Dictionary with import results
    """
    if not os.path.exists(import_dir) or not os.path.isdir(import_dir):
        return {
            "success": False,
            "error": f"Import directory {import_dir} does not exist or is not a directory"
        }
    
    imported = []
    failed = []
    
    # Find all JSON files in the directory
    json_files = list(Path(import_dir).glob("*.json"))
    
    for json_file in json_files:
        try:
            result = import_script(str(json_file), replace_existing)
            if result.get("success", False):
                imported.append({
                    "script_id": result["script_id"],
                    "name": result["name"]
                })
            else:
                failed.append({
                    "file": str(json_file),
                    "error": result.get("error", "Unknown error")
                })
        except Exception as e:
            failed.append({
                "file": str(json_file),
                "error": str(e)
            })
    
    return {
        "success": len(failed) == 0,
        "imported_count": len(imported),
        "failed_count": len(failed),
        "imported": imported,
        "failed": failed
    } 