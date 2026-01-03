"""
Utility functions for managing favorite commands.
"""
import os
import json
import logging
from datetime import datetime
import tempfile
import subprocess
import sys

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def get_favorites_dir():
    """
    Get the path to the favorites directory.
    
    Returns:
        str: Path to the favorites directory
    """
    from llm_control import is_packaged
    
    # Create a directory for storing favorites data
    favorites_dir = os.environ.get("FAVORITES_DIR")
    
    if not favorites_dir:
        # Use is_packaged() for cross-platform detection
        if is_packaged():
            # Running from packaged executable
            # Use user's home directory for favorites
            favorites_dir = os.path.join(os.path.expanduser("~"), ".llm-control", "favorites")
        else:
            # Development mode: use subdirectory in the project directory
            favorites_dir = os.path.join(os.getcwd(), "llm_control", "favorites", "scripts")
    
    # If it's a relative path, make it relative to the current working directory
    if not os.path.isabs(favorites_dir):
        if not is_packaged():
            # Only use getcwd() in development mode
            favorites_dir = os.path.join(os.getcwd(), favorites_dir)
    
    # Ensure the directory exists
    os.makedirs(favorites_dir, exist_ok=True)
    
    return favorites_dir

def save_as_favorite(command_data, name=None):
    """
    Save a command execution as a favorite Python script.
    
    Args:
        command_data: Dictionary containing command execution data with keys:
            - timestamp: ISO format timestamp
            - command: Original command text
            - steps: List of command steps
            - code: Generated code
            - success: Boolean indicating success status
        name: Optional name for the favorite script. If not provided,
              a name will be generated based on the command.
    
    Returns:
        dict: Information about the saved favorite including file path
    """
    try:
        # Get the favorites directory
        favorites_dir = get_favorites_dir()
        
        # Generate a filename if not provided
        if not name:
            # Use first few words of command (max 5 words)
            command_words = command_data.get('command', '').split()[:5]
            name = '_'.join(word.lower() for word in command_words if word.isalnum())
            
            # Fallback if name is empty or not valid
            if not name:
                name = f"favorite_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Sanitize the filename
        name = name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        
        # Add timestamp to ensure uniqueness
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{name}_{timestamp}.py"
        
        # Full path for the file
        filepath = os.path.join(favorites_dir, filename)
        
        # Get the code to save
        code = command_data.get('code', '')
        
        # If no code is available, create a simple script
        if not code:
            steps_str = "\\n".join([f"# {step}" for step in command_data.get('steps', [])])
            code = f"""#!/usr/bin/env python3
# Favorite command: {command_data.get('command', 'Unknown')}
# Created: {datetime.now().isoformat()}
# Steps:
{steps_str}

print("This is a saved favorite command, but no executable code was available.")
"""
        else:
            # Add a header to the code with information about the command
            header = f"""#!/usr/bin/env python3
# Favorite command: {command_data.get('command', 'Unknown')}
# Created: {datetime.now().isoformat()}
# Original timestamp: {command_data.get('timestamp', 'Unknown')}
# Success: {command_data.get('success', False)}
"""
            code = header + code
        
        # Write the script file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # Make the script executable
        os.chmod(filepath, 0o755)
        
        # Create a metadata file with the same name but .json extension
        metadata_file = os.path.splitext(filepath)[0] + ".json"
        
        # Save metadata
        metadata = {
            'name': name,
            'command': command_data.get('command', ''),
            'timestamp': datetime.now().isoformat(),
            'original_timestamp': command_data.get('timestamp', ''),
            'steps': command_data.get('steps', []),
            'success': command_data.get('success', False),
            'script_path': filepath
        }
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Saved favorite command to {filepath}")
        
        return {
            'status': 'success',
            'name': name,
            'filepath': filepath,
            'metadata_path': metadata_file,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error saving favorite: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'status': 'error',
            'error': str(e)
        }

def get_favorites(limit=None):
    """
    Get the list of favorite commands.
    
    Args:
        limit: Maximum number of favorites to return (default: all)
    
    Returns:
        List of dictionaries containing favorite command data
    """
    try:
        # Get the favorites directory
        favorites_dir = get_favorites_dir()
        
        # Check if the directory exists
        if not os.path.exists(favorites_dir):
            return []
        
        # List all JSON files in the directory
        metadata_files = [f for f in os.listdir(favorites_dir) if f.endswith('.json')]
        
        # Sort by modification time (newest first)
        metadata_files.sort(key=lambda x: os.path.getmtime(os.path.join(favorites_dir, x)), reverse=True)
        
        # Apply limit if specified
        if limit is not None and limit > 0:
            metadata_files = metadata_files[:limit]
        
        # Read metadata for each favorite
        favorites = []
        for metadata_file in metadata_files:
            try:
                with open(os.path.join(favorites_dir, metadata_file), 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    favorites.append(metadata)
            except Exception as e:
                logger.error(f"Error reading favorite metadata {metadata_file}: {str(e)}")
        
        return favorites
        
    except Exception as e:
        logger.error(f"Error getting favorites: {str(e)}")
        return []

def delete_favorite(script_id):
    """
    Delete a favorite command script.
    
    Args:
        script_id: Script ID (filename without extension)
    
    Returns:
        dict: Information about the deletion status
    """
    try:
        # Get the favorites directory
        favorites_dir = get_favorites_dir()
        
        # Check if the directory exists
        if not os.path.exists(favorites_dir):
            return {
                'status': 'error',
                'error': f"Favorites directory not found: {favorites_dir}"
            }
        
        # Create paths for script and metadata files
        script_path = os.path.join(favorites_dir, f"{script_id}.py")
        metadata_path = os.path.join(favorites_dir, f"{script_id}.json")
        
        # Check if files exist
        script_exists = os.path.exists(script_path)
        metadata_exists = os.path.exists(metadata_path)
        
        if not script_exists and not metadata_exists:
            return {
                'status': 'error',
                'error': f"Favorite script not found: {script_id}"
            }
        
        # Delete the files
        deleted_files = []
        
        if script_exists:
            os.remove(script_path)
            deleted_files.append(script_path)
        
        if metadata_exists:
            os.remove(metadata_path)
            deleted_files.append(metadata_path)
        
        logger.info(f"Deleted favorite script: {script_id}")
        
        return {
            'status': 'success',
            'message': f"Favorite script deleted: {script_id}",
            'deleted_files': deleted_files
        }
        
    except Exception as e:
        logger.error(f"Error deleting favorite: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'status': 'error',
            'error': str(e)
        }

def run_favorite(script_id):
    """
    Run a favorite command script.
    
    Args:
        script_id: Script ID (filename without extension)
    
    Returns:
        dict: Information about the execution result
    """
    try:
        # Get the favorites directory
        favorites_dir = get_favorites_dir()
        
        # Create path for script file
        script_path = os.path.join(favorites_dir, f"{script_id}.py")
        
        # Check if script exists
        if not os.path.exists(script_path):
            return {
                'status': 'error',
                'error': f"Favorite script not found: {script_path}"
            }
        
        # Execute the script
        logger.info(f"Running favorite script: {script_path}")
        process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for the process to complete (with timeout)
        try:
            stdout, stderr = process.communicate(timeout=30)
            exit_code = process.returncode
            
            # Check if the script executed successfully
            if exit_code == 0:
                logger.info(f"Favorite script executed successfully: {script_id}")
                return {
                    'status': 'success',
                    'message': f"Favorite script executed successfully: {script_id}",
                    'stdout': stdout,
                    'stderr': stderr,
                    'exit_code': exit_code
                }
            else:
                logger.error(f"Favorite script failed with exit code {exit_code}: {script_id}")
                return {
                    'status': 'error',
                    'message': f"Favorite script failed with exit code {exit_code}",
                    'stdout': stdout,
                    'stderr': stderr,
                    'exit_code': exit_code
                }
                
        except subprocess.TimeoutExpired:
            # Kill the process if it times out
            process.kill()
            logger.error(f"Favorite script execution timed out: {script_id}")
            return {
                'status': 'error',
                'error': f"Script execution timed out after 30 seconds: {script_id}"
            }
        
    except Exception as e:
        logger.error(f"Error running favorite: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'status': 'error',
            'error': str(e)
        } 