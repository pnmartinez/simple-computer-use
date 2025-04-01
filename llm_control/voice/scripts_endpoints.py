"""
Scripts endpoints module.

This module provides Flask endpoints for managing Piautobike scripts.
"""

import os
import logging
import time
import json
from flask import request, jsonify, Blueprint
from typing import Dict, Any, List, Optional

# Configure logging
logger = logging.getLogger("scripts-endpoints")

# Import from our own modules
from llm_control.scripts.piautobike import (
    PiautobikeScript,
    load_script,
    list_scripts,
    delete_script,
    execute_script,
    export_script,
    import_script,
    batch_import_scripts
)

from llm_control.voice.utils import error_response, cors_preflight
from llm_control.voice.commands import (
    process_command_pipeline,
    validate_pyautogui_cmd,
    OLLAMA_MODEL,
    OLLAMA_HOST
)

# Define local version of sanitize_for_json to avoid circular imports
def sanitize_for_json(obj):
    """
    Recursively sanitize an object for JSON serialization, converting NumPy types to native Python types.
    
    Args:
        obj: The object to sanitize
        
    Returns:
        The sanitized object safe for JSON serialization
    """
    try:
        import numpy as np
        
        if isinstance(obj, dict):
            return {k: sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [sanitize_for_json(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(sanitize_for_json(item) for item in obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        else:
            return obj
    except ImportError:
        # If numpy isn't available, just return the object as is
        return obj

# Create scripts blueprint
scripts_bp = Blueprint('scripts', __name__)

@scripts_bp.route('/scripts', methods=['GET'])
@cors_preflight
def list_scripts_endpoint():
    """Endpoint to list all available scripts."""
    try:
        scripts = list_scripts()
        # Sanitize for JSON serialization
        sanitized_scripts = sanitize_for_json(scripts)
        return jsonify({
            "status": "success",
            "scripts": sanitized_scripts,
            "count": len(sanitized_scripts)
        })
    except Exception as e:
        logger.error(f"Error listing scripts: {e}")
        return error_response(f"Error listing scripts: {str(e)}", 500)

@scripts_bp.route('/scripts/<script_id>', methods=['GET'])
@cors_preflight
def get_script_endpoint(script_id):
    """Endpoint to get a specific script by ID."""
    try:
        script = load_script(script_id)
        if not script:
            return error_response(f"Script with ID {script_id} not found", 404)
        
        # Sanitize for JSON serialization
        script_dict = sanitize_for_json(script.to_dict())
        return jsonify({
            "status": "success",
            "script": script_dict
        })
    except Exception as e:
        logger.error(f"Error getting script {script_id}: {e}")
        return error_response(f"Error getting script: {str(e)}", 500)

@scripts_bp.route('/scripts', methods=['POST'])
@cors_preflight
def create_script_endpoint():
    """Endpoint to create a new script."""
    try:
        # Get request data
        logger.info(f"Received create script request. Content type: {request.content_type}")
        if not request.is_json:
            logger.error(f"Request is not JSON. Content type: {request.content_type}")
            return error_response("Request must be JSON", 400)
        
        try:
            data = request.get_json()
            logger.debug(f"Parsed request data: {data}")
        except Exception as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            return error_response(f"Invalid JSON data: {str(e)}", 400)
        
        if not data:
            logger.error("Request contained empty JSON data")
            return error_response("No JSON data provided", 400)
        
        # Validate required fields
        required_fields = ['name', 'description', 'commands']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.error(f"Missing required fields: {missing_fields}. Request data: {data}")
            return error_response(f"Missing required field(s): {', '.join(missing_fields)}", 400)
        
        # Log validation success and data structure
        logger.info(f"Creating script '{data['name']}' with {len(data.get('commands', []))} commands")
        logger.debug(f"Script data: {json.dumps(data, indent=2)}")
        
        # Create script instance
        script = PiautobikeScript(
            name=data['name'],
            description=data['description'],
            commands=data['commands'],
            pyautogui_code=data.get('pyautogui_code', ''),
            tags=data.get('tags', [])
        )
        
        # If PyAutoGUI code is provided, validate it
        if script.pyautogui_code:
            logger.info("Validating provided PyAutoGUI code")
            is_valid, disallowed = validate_pyautogui_cmd(script.pyautogui_code)
            if not is_valid:
                logger.error(f"Invalid PyAutoGUI code, contains disallowed functions: {disallowed}")
                return error_response(
                    f"Invalid PyAutoGUI code, contains disallowed functions: {', '.join(disallowed)}",
                    400
                )
        
        # If no PyAutoGUI code is provided but commands are, generate code
        if not script.pyautogui_code and script.commands:
            logger.info(f"Generating PyAutoGUI code for {len(script.commands)} commands")
            try:
                # Generate PyAutoGUI code for each command
                all_code = []
                for i, command in enumerate(script.commands):
                    logger.info(f"Processing command {i+1}/{len(script.commands)}: '{command}'")
                    # Use command pipeline to generate PyAutoGUI code
                    result = process_command_pipeline(command, model=OLLAMA_MODEL)
                    
                    if not result.get('success', False):
                        logger.warning(f"Command pipeline failed for command: '{command}', error: {result.get('error', 'Unknown error')}")
                        continue
                        
                    if 'pyautogui_actions' in result:
                        # Extract code from actions
                        actions = result['pyautogui_actions']
                        logger.debug(f"Command result actions: {actions}")
                        
                        # Comment with original command
                        all_code.append(f"# Command: {command}")
                        
                        # Handle older format (dict with steps)
                        if isinstance(actions, dict) and 'steps' in actions:
                            logger.debug(f"Processing dictionary format with {len(actions['steps'])} steps")
                            for step in actions['steps']:
                                if 'code' in step:
                                    all_code.append(step['code'])
                                    all_code.append("# Wait for action to complete")
                                    all_code.append("time.sleep(0.5)")
                        # Handle newer format (list of actions)
                        elif isinstance(actions, list):
                            logger.debug(f"Processing list format with {len(actions)} actions")
                            for action in actions:
                                if 'pyautogui_cmd' in action:
                                    all_code.append(action['pyautogui_cmd'])
                                    all_code.append("# Wait for action to complete")
                                    all_code.append("time.sleep(0.5)")
                    else:
                        logger.warning(f"No pyautogui_actions found in result for command: '{command}'")
                
                # Create complete script with imports
                if all_code:
                    script.pyautogui_code = "import pyautogui\nimport time\n\n" + "\n".join(all_code)
                    logger.info(f"Generated {len(all_code)} lines of PyAutoGUI code")
                else:
                    logger.warning("No PyAutoGUI code was generated for any commands")
            except Exception as e:
                logger.error(f"Error generating PyAutoGUI code: {str(e)}", exc_info=True)
                # Continue without PyAutoGUI code
        
        # Save script
        logger.info(f"Saving script '{script.name}' to persistent storage")
        script.save()
        
        # Sanitize for JSON serialization
        script_dict = sanitize_for_json(script.to_dict())
        
        logger.info(f"Script '{script.name}' created successfully with ID {script.script_id}")
        return jsonify({
            "status": "success",
            "message": f"Script '{script.name}' created successfully",
            "script": script_dict
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating script: {str(e)}", exc_info=True)
        return error_response(f"Error creating script: {str(e)}", 500)

@scripts_bp.route('/scripts/<script_id>', methods=['PUT'])
@cors_preflight
def update_script_endpoint(script_id):
    """Endpoint to update an existing script."""
    try:
        # Load existing script
        script = load_script(script_id)
        if not script:
            return error_response(f"Script with ID {script_id} not found", 404)
        
        # Get request data
        data = request.get_json()
        if not data:
            return error_response("No JSON data provided", 400)
        
        # Update script fields
        if 'name' in data:
            script.name = data['name']
        if 'description' in data:
            script.description = data['description']
        if 'commands' in data:
            script.commands = data['commands']
        if 'pyautogui_code' in data:
            # Validate PyAutoGUI code if provided
            is_valid, disallowed = validate_pyautogui_cmd(data['pyautogui_code'])
            if not is_valid:
                return error_response(
                    f"Invalid PyAutoGUI code, contains disallowed functions: {', '.join(disallowed)}",
                    400
                )
            script.pyautogui_code = data['pyautogui_code']
        if 'tags' in data:
            script.tags = data['tags']
        
        # Save updated script
        script.save()
        
        # Sanitize for JSON serialization
        script_dict = sanitize_for_json(script.to_dict())
        
        return jsonify({
            "status": "success",
            "message": f"Script '{script.name}' updated successfully",
            "script": script_dict
        })
    
    except Exception as e:
        logger.error(f"Error updating script {script_id}: {e}")
        return error_response(f"Error updating script: {str(e)}", 500)

@scripts_bp.route('/scripts/<script_id>', methods=['DELETE'])
@cors_preflight
def delete_script_endpoint(script_id):
    """Endpoint to delete a script."""
    try:
        # Delete script
        success = delete_script(script_id)
        if not success:
            return error_response(f"Script with ID {script_id} not found", 404)
        
        return jsonify({
            "status": "success",
            "message": f"Script with ID {script_id} deleted successfully"
        })
    
    except Exception as e:
        logger.error(f"Error deleting script {script_id}: {e}")
        return error_response(f"Error deleting script: {str(e)}", 500)

@scripts_bp.route('/scripts/<script_id>/execute', methods=['POST'])
@cors_preflight
def execute_script_endpoint(script_id):
    """Endpoint to execute a script."""
    try:
        # Load script
        script = load_script(script_id)
        if not script:
            return error_response(f"Script with ID {script_id} not found", 404)
        
        # Execute script
        start_time = time.time()
        result = execute_script(script)
        execution_time = time.time() - start_time
        
        # Sanitize result for JSON serialization
        sanitized_result = sanitize_for_json(result)
        
        # Prepare response
        response = {
            "status": "success" if sanitized_result.get("success", False) else "error",
            "script_id": script_id,
            "name": script.name,
            "execution_time": execution_time
        }
        
        # Add error if execution failed
        if not sanitized_result.get("success", False):
            response["error"] = sanitized_result.get("error", "Unknown error")
            logger.error(f"Script execution failed: {response['error']}")
            return jsonify(response), 500
        
        logger.info(f"Script '{script.name}' executed successfully in {execution_time:.2f} seconds")
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error executing script {script_id}: {e}")
        return error_response(f"Error executing script: {str(e)}", 500)

@scripts_bp.route('/scripts/generate', methods=['POST'])
@cors_preflight
def generate_script_endpoint():
    """Endpoint to generate a script from commands without saving it."""
    try:
        # Get request data
        data = request.get_json()
        if not data:
            logger.error("No JSON data provided in request")
            return error_response("No JSON data provided", 400)
        
        # Validate required fields
        if 'commands' not in data or not isinstance(data['commands'], list):
            logger.error(f"Missing or invalid 'commands' field in data: {data}")
            return error_response("Missing or invalid 'commands' field", 400)
        
        # Log the commands received
        logger.info(f"Generating script for {len(data['commands'])} commands: {data['commands']}")
        
        # Generate PyAutoGUI code for each command
        all_code = []
        actions_results = []
        
        for command in data['commands']:
            # Use command pipeline to generate PyAutoGUI code
            logger.info(f"Processing command: '{command}'")
            try:
                result = process_command_pipeline(command, model=OLLAMA_MODEL)
                # Sanitize result for JSON serialization
                sanitized_result = sanitize_for_json(result)
                actions_results.append(sanitized_result)
                
                # Check if command was successful
                if sanitized_result.get('success', False):
                    # Add command as comment
                    all_code.append(f"# Command: {command}")
                    
                    # Try to extract code in different formats based on the response structure
                    code_added = False
                    
                    # Format 1: pyautogui_actions is a list with pyautogui_cmd
                    if 'pyautogui_actions' in sanitized_result and isinstance(sanitized_result['pyautogui_actions'], list):
                        for action in sanitized_result['pyautogui_actions']:
                            if isinstance(action, dict) and 'pyautogui_cmd' in action:
                                all_code.append(action['pyautogui_cmd'])
                                all_code.append("# Wait for action to complete")
                                all_code.append("time.sleep(0.5)")
                                code_added = True
                    
                    # Format 2: pyautogui_actions has steps with code
                    elif 'pyautogui_actions' in sanitized_result and isinstance(sanitized_result['pyautogui_actions'], dict) and 'steps' in sanitized_result['pyautogui_actions']:
                        for step in sanitized_result['pyautogui_actions']['steps']:
                            if 'code' in step:
                                all_code.append(step['code'])
                                all_code.append("# Wait for action to complete")
                                all_code.append("time.sleep(0.5)")
                                code_added = True
                    
                    # Format 3: actions is a list with pyautogui_cmd
                    elif 'actions' in sanitized_result and isinstance(sanitized_result['actions'], list):
                        for action in sanitized_result['actions']:
                            if isinstance(action, dict) and 'pyautogui_cmd' in action:
                                all_code.append(action['pyautogui_cmd'])
                                all_code.append("# Wait for action to complete")
                                all_code.append("time.sleep(0.5)")
                                code_added = True
                    
                    # Format 4: code is a dictionary with raw code
                    elif 'code' in sanitized_result and isinstance(sanitized_result['code'], dict) and 'raw' in sanitized_result['code']:
                        all_code.append(sanitized_result['code']['raw'])
                        code_added = True
                    
                    # If no code was added from the formats, add a comment
                    if not code_added:
                        all_code.append(f"# No PyAutoGUI code was generated for: {command}")
                        logger.warning(f"No PyAutoGUI code found in the result for command: {command}")
                else:
                    # Command failed, add a comment
                    error_msg = sanitized_result.get('error', 'Unknown error')
                    all_code.append(f"# Command failed: {command}")
                    all_code.append(f"# Error: {error_msg}")
                    logger.warning(f"Command failed: {command} - Error: {error_msg}")
            except Exception as cmd_error:
                # Handle errors in the command pipeline
                logger.error(f"Error processing command '{command}': {cmd_error}", exc_info=True)
                all_code.append(f"# Error processing command: {command}")
                all_code.append(f"# Error: {str(cmd_error)}")
        
        # Create complete script with imports
        pyautogui_code = ""
        if all_code:
            pyautogui_code = "import pyautogui\nimport time\n\n" + "\n".join(all_code)
        else:
            pyautogui_code = "# No code was generated for the provided commands"
        
        # Log the generated code length
        logger.info(f"Generated PyAutoGUI code with {len(pyautogui_code)} characters")
        if len(pyautogui_code) < 100:
            logger.warning(f"Very short code generated: '{pyautogui_code}'")
        
        # Create simplified response without potentially problematic nested objects
        response = {
            "status": "success",
            "pyautogui_code": pyautogui_code,
            "commands_processed": len(data['commands']),
            "code_length": len(pyautogui_code)
        }
        
        # Log the final response size
        logger.info(f"Returning response with {len(str(response))} characters")
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error generating script: {e}", exc_info=True)
        return error_response(f"Error generating script: {str(e)}", 500)

@scripts_bp.route('/scripts/generate-ui', methods=['GET'])
def generate_script_ui_endpoint():
    """Endpoint that provides a simple HTML UI for script generation and management."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Piautobike Script Generator</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                line-height: 1.6;
            }
            h1, h2, h3 {
                color: #333;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                display: flex;
                gap: 20px;
            }
            .panel {
                flex: 1;
                padding: 20px;
                background-color: #f9f9f9;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .form-group {
                margin-bottom: 15px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
            }
            input, textarea, select {
                width: 100%;
                padding: 8px;
                box-sizing: border-box;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            button {
                background-color: #4CAF50;
                color: white;
                padding: 10px 15px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
            }
            button:hover {
                background-color: #45a049;
            }
            #commandsList {
                margin-bottom: 15px;
            }
            .command-item {
                display: flex;
                margin-bottom: 5px;
            }
            .command-item input {
                flex-grow: 1;
                margin-right: 5px;
            }
            .command-item button {
                background-color: #f44336;
                padding: 5px 10px;
            }
            #resultCode {
                white-space: pre-wrap;
                overflow-x: auto;
                background-color: #f5f5f5;
                padding: 15px;
                border-radius: 4px;
                font-family: monospace;
            }
            #scriptsList {
                list-style: none;
                padding: 0;
            }
            .script-item {
                padding: 10px;
                background-color: #fff;
                margin-bottom: 10px;
                border-radius: 4px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            .script-item h3 {
                margin-top: 0;
            }
            .script-actions {
                display: flex;
                gap: 10px;
            }
            .btn-delete {
                background-color: #f44336;
            }
            .btn-edit {
                background-color: #2196F3;
            }
            .btn-execute {
                background-color: #FF9800;
            }
            .loading {
                display: none;
                margin-top: 10px;
            }
            .spinner {
                border: 4px solid #f3f3f3;
                border-top: 4px solid #3498db;
                border-radius: 50%;
                width: 20px;
                height: 20px;
                animation: spin 2s linear infinite;
                display: inline-block;
                vertical-align: middle;
                margin-right: 10px;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        </style>
    </head>
    <body>
        <h1>Piautobike Script Generator</h1>
        
        <div class="container">
            <div class="panel">
                <h2>Create New Script</h2>
                
                <div class="form-group">
                    <label for="scriptName">Script Name:</label>
                    <input type="text" id="scriptName" placeholder="Enter script name">
                </div>
                
                <div class="form-group">
                    <label for="scriptDescription">Description:</label>
                    <textarea id="scriptDescription" placeholder="Enter script description" rows="2"></textarea>
                </div>
                
                <div class="form-group">
                    <label>Commands:</label>
                    <div id="commandsList">
                        <div class="command-item">
                            <input type="text" placeholder="Enter a command (e.g., 'Click on Firefox icon')">
                            <button onclick="removeCommand(this)">-</button>
                        </div>
                    </div>
                    <button onclick="addCommand()">Add Command</button>
                </div>
                
                <div class="form-group">
                    <label for="scriptTags">Tags (comma separated):</label>
                    <input type="text" id="scriptTags" placeholder="browser, automation, ...">
                </div>
                
                <button onclick="generateCode()">Generate Code</button>
                <button onclick="saveScript()">Save Script</button>
                
                <div class="loading" id="generateLoading">
                    <div class="spinner"></div> Generating code...
                </div>
                <div class="loading" id="saveLoading">
                    <div class="spinner"></div> Saving script...
                </div>
                
                <h3>Generated PyAutoGUI Code:</h3>
                <pre id="resultCode">// Code will appear here after generation</pre>
            </div>
            
            <div class="panel">
                <h2>Saved Scripts</h2>
                <button onclick="loadScripts()">Refresh List</button>
                <button onclick="showImportDialog()">Import Script</button>
                
                <div class="loading" id="listLoading">
                    <div class="spinner"></div> Loading scripts...
                </div>
                
                <ul id="scriptsList">
                    <!-- Scripts will be loaded here -->
                </ul>
            </div>
        </div>
        
        <!-- Import Dialog -->
        <div id="importDialog" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5); z-index: 1000;">
            <div style="background-color: white; max-width: 500px; margin: 100px auto; padding: 20px; border-radius: 5px; box-shadow: 0 0 10px rgba(0,0,0,0.3);">
                <h2>Import Script</h2>
                <p>Import a script from a JSON file:</p>
                
                <form id="importForm" enctype="multipart/form-data">
                    <div class="form-group">
                        <label for="importFile">Select script file:</label>
                        <input type="file" id="importFile" name="file" accept=".json">
                    </div>
                    
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="replaceExisting" name="replace">
                            Replace if script ID already exists
                        </label>
                    </div>
                    
                    <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px;">
                        <button type="button" onclick="hideImportDialog()" style="background-color: #ccc; color: black;">Cancel</button>
                        <button type="button" onclick="importScript()">Import</button>
                    </div>
                </form>
                
                <div class="loading" id="importLoading" style="display: none; margin-top: 10px;">
                    <div class="spinner"></div> Importing script...
                </div>
            </div>
        </div>
        
        <script>
            // Load scripts when page loads
            document.addEventListener('DOMContentLoaded', function() {
                loadScripts();
            });
            
            function addCommand() {
                const commandsList = document.getElementById('commandsList');
                const commandItem = document.createElement('div');
                commandItem.className = 'command-item';
                commandItem.innerHTML = `
                    <input type="text" placeholder="Enter a command (e.g., 'Click on Firefox icon')">
                    <button onclick="removeCommand(this)">-</button>
                `;
                commandsList.appendChild(commandItem);
            }
            
            function removeCommand(button) {
                const commandItem = button.parentElement;
                commandItem.remove();
            }
            
            function collectCommands() {
                const commandInputs = document.querySelectorAll('#commandsList .command-item input');
                const commands = [];
                commandInputs.forEach(input => {
                    if (input.value.trim()) {
                        commands.push(input.value.trim());
                    }
                });
                return commands;
            }
            
            function generateCode() {
                const commands = collectCommands();
                if (commands.length === 0) {
                    alert('Please add at least one command');
                    return;
                }
                
                // Show loading indicator
                document.getElementById('generateLoading').style.display = 'block';
                
                // Call the API to generate code
                fetch('/scripts/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ commands })
                })
                .then(response => response.json())
                .then(data => {
                    // Hide loading indicator
                    document.getElementById('generateLoading').style.display = 'none';
                    
                    if (data.status === 'success') {
                        document.getElementById('resultCode').textContent = data.pyautogui_code;
                    } else {
                        alert('Error generating code: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    // Hide loading indicator
                    document.getElementById('generateLoading').style.display = 'none';
                    alert('Error: ' + error);
                });
            }
            
            function saveScript() {
                const name = document.getElementById('scriptName').value.trim();
                const description = document.getElementById('scriptDescription').value.trim();
                const commands = collectCommands();
                const tagsInput = document.getElementById('scriptTags').value.trim();
                const tags = tagsInput ? tagsInput.split(',').map(tag => tag.trim()) : [];
                const pyautogui_code = document.getElementById('resultCode').textContent;
                
                if (!name) {
                    alert('Please enter a script name');
                    return;
                }
                
                if (!description) {
                    alert('Please enter a script description');
                    return;
                }
                
                if (commands.length === 0) {
                    alert('Please add at least one command');
                    return;
                }
                
                // Show loading indicator
                document.getElementById('saveLoading').style.display = 'block';
                
                // Call the API to save the script
                fetch('/scripts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name,
                        description,
                        commands,
                        tags,
                        pyautogui_code: pyautogui_code !== '// Code will appear here after generation' ? pyautogui_code : ''
                    })
                })
                .then(response => response.json())
                .then(data => {
                    // Hide loading indicator
                    document.getElementById('saveLoading').style.display = 'none';
                    
                    if (data.status === 'success') {
                        alert('Script saved successfully!');
                        loadScripts();  // Refresh the scripts list
                    } else {
                        alert('Error saving script: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    // Hide loading indicator
                    document.getElementById('saveLoading').style.display = 'none';
                    alert('Error: ' + error);
                });
            }
            
            function loadScripts() {
                // Show loading indicator
                document.getElementById('listLoading').style.display = 'block';
                
                // Clear current list
                document.getElementById('scriptsList').innerHTML = '';
                
                // Call the API to get scripts
                fetch('/scripts')
                .then(response => response.json())
                .then(data => {
                    // Hide loading indicator
                    document.getElementById('listLoading').style.display = 'none';
                    
                    if (data.status === 'success') {
                        const scriptsList = document.getElementById('scriptsList');
                        
                        if (data.scripts.length === 0) {
                            scriptsList.innerHTML = '<p>No scripts found. Create your first script!</p>';
                            return;
                        }
                        
                        data.scripts.forEach(script => {
                            const scriptItem = document.createElement('li');
                            scriptItem.className = 'script-item';
                            
                            const tagsList = script.tags && script.tags.length > 0 
                                ? `<p><strong>Tags:</strong> ${script.tags.join(', ')}</p>` 
                                : '';
                            
                            scriptItem.innerHTML = `
                                <h3>${script.name}</h3>
                                <p>${script.description}</p>
                                ${tagsList}
                                <p><strong>Commands:</strong> ${script.command_count}</p>
                                <p><strong>Last updated:</strong> ${new Date(script.updated_at).toLocaleString()}</p>
                                <div class="script-actions">
                                    <button class="btn-execute" onclick="executeScript('${script.script_id}')">Execute</button>
                                    <button class="btn-edit" onclick="editScript('${script.script_id}')">Edit</button>
                                    <button class="btn-delete" onclick="deleteScript('${script.script_id}')">Delete</button>
                                    <button class="btn-export" onclick="exportScript('${script.script_id}')" style="background-color: #2962FF;">Export</button>
                                </div>
                            `;
                            
                            scriptsList.appendChild(scriptItem);
                        });
                    } else {
                        alert('Error loading scripts: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    // Hide loading indicator
                    document.getElementById('listLoading').style.display = 'none';
                    alert('Error: ' + error);
                });
            }
            
            function executeScript(scriptId) {
                if (!confirm('Are you sure you want to execute this script? It will perform automated actions on your system.')) {
                    return;
                }
                
                fetch(`/scripts/${scriptId}/execute`, {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        alert(`Script executed successfully in ${data.execution_time.toFixed(2)} seconds!`);
                    } else {
                        alert('Error executing script: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    alert('Error: ' + error);
                });
            }
            
            function editScript(scriptId) {
                // Fetch script details
                fetch(`/scripts/${scriptId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        const script = data.script;
                        
                        // Fill form fields
                        document.getElementById('scriptName').value = script.name;
                        document.getElementById('scriptDescription').value = script.description;
                        document.getElementById('scriptTags').value = script.tags.join(', ');
                        document.getElementById('resultCode').textContent = script.pyautogui_code;
                        
                        // Clear and add commands
                        const commandsList = document.getElementById('commandsList');
                        commandsList.innerHTML = '';
                        
                        script.commands.forEach(command => {
                            const commandItem = document.createElement('div');
                            commandItem.className = 'command-item';
                            commandItem.innerHTML = `
                                <input type="text" value="${command}" placeholder="Enter a command">
                                <button onclick="removeCommand(this)">-</button>
                            `;
                            commandsList.appendChild(commandItem);
                        });
                        
                        // Scroll to top of page
                        window.scrollTo(0, 0);
                        
                        // Add data attribute for update mode
                        document.getElementById('scriptName').dataset.scriptId = scriptId;
                        
                        // Change button text
                        const saveButton = document.querySelector('button[onclick="saveScript()"]');
                        saveButton.textContent = 'Update Script';
                        saveButton.onclick = function() { updateScript(scriptId); };
                    } else {
                        alert('Error loading script: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    alert('Error: ' + error);
                });
            }
            
            function updateScript(scriptId) {
                const name = document.getElementById('scriptName').value.trim();
                const description = document.getElementById('scriptDescription').value.trim();
                const commands = collectCommands();
                const tagsInput = document.getElementById('scriptTags').value.trim();
                const tags = tagsInput ? tagsInput.split(',').map(tag => tag.trim()) : [];
                const pyautogui_code = document.getElementById('resultCode').textContent;
                
                if (!name || !description || commands.length === 0) {
                    alert('Please fill in all required fields');
                    return;
                }
                
                // Show loading indicator
                document.getElementById('saveLoading').style.display = 'block';
                
                // Call the API to update the script
                fetch(`/scripts/${scriptId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name,
                        description,
                        commands,
                        tags,
                        pyautogui_code: pyautogui_code !== '// Code will appear here after generation' ? pyautogui_code : ''
                    })
                })
                .then(response => response.json())
                .then(data => {
                    // Hide loading indicator
                    document.getElementById('saveLoading').style.display = 'none';
                    
                    if (data.status === 'success') {
                        alert('Script updated successfully!');
                        
                        // Reset the form
                        document.getElementById('scriptName').value = '';
                        document.getElementById('scriptDescription').value = '';
                        document.getElementById('scriptTags').value = '';
                        document.getElementById('resultCode').textContent = '// Code will appear here after generation';
                        
                        // Reset commands to just one empty field
                        const commandsList = document.getElementById('commandsList');
                        commandsList.innerHTML = `
                            <div class="command-item">
                                <input type="text" placeholder="Enter a command (e.g., 'Click on Firefox icon')">
                                <button onclick="removeCommand(this)">-</button>
                            </div>
                        `;
                        
                        // Reset the button
                        const saveButton = document.querySelector('button[onclick="updateScript(\'' + scriptId + '\')"]');
                        saveButton.textContent = 'Save Script';
                        saveButton.onclick = saveScript;
                        
                        // Refresh the scripts list
                        loadScripts();
                    } else {
                        alert('Error updating script: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    // Hide loading indicator
                    document.getElementById('saveLoading').style.display = 'none';
                    alert('Error: ' + error);
                });
            }
            
            function deleteScript(scriptId) {
                if (!confirm('Are you sure you want to delete this script? This action cannot be undone.')) {
                    return;
                }
                
                fetch(`/scripts/${scriptId}`, {
                    method: 'DELETE'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        alert('Script deleted successfully!');
                        loadScripts();  // Refresh the scripts list
                    } else {
                        alert('Error deleting script: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    alert('Error: ' + error);
                });
            }
            
            function exportScript(scriptId) {
                // Simple export that downloads the script file
                window.location.href = `/scripts/${scriptId}/export?download=true`;
            }
            
            function showImportDialog() {
                document.getElementById('importDialog').style.display = 'block';
            }
            
            function hideImportDialog() {
                document.getElementById('importDialog').style.display = 'none';
                // Reset the form
                document.getElementById('importForm').reset();
            }
            
            function importScript() {
                const fileInput = document.getElementById('importFile');
                
                if (!fileInput.files || fileInput.files.length === 0) {
                    alert('Please select a file to import');
                    return;
                }
                
                const file = fileInput.files[0];
                if (!file.name.endsWith('.json')) {
                    alert('Please select a JSON file');
                    return;
                }
                
                const formData = new FormData();
                formData.append('file', file);
                formData.append('replace', document.getElementById('replaceExisting').checked);
                
                // Show loading indicator
                document.getElementById('importLoading').style.display = 'block';
                
                fetch('/scripts/import', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    // Hide loading indicator
                    document.getElementById('importLoading').style.display = 'none';
                    
                    if (data.status === 'success') {
                        alert('Script imported successfully!');
                        hideImportDialog();
                        loadScripts();  // Refresh the scripts list
                    } else {
                        alert('Error importing script: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    // Hide loading indicator
                    document.getElementById('importLoading').style.display = 'none';
                    alert('Error: ' + error);
                });
            }
        </script>
    </body>
    </html>
    """
    
    return html 

@scripts_bp.route('/scripts/<script_id>/export', methods=['GET'])
@cors_preflight
def export_script_endpoint(script_id):
    """Endpoint to export a script."""
    try:
        # Export the script without saving to file
        result = export_script(script_id)
        if not result.get("success", False):
            return error_response(result.get("error", "Unknown error"), 404)
        
        # Sanitize result for JSON serialization
        sanitized_result = sanitize_for_json(result)
        
        # Format the response
        response = {
            "status": "success",
            "script_id": script_id,
            "name": sanitized_result.get("name", ""),
            "export_data": sanitized_result.get("export_data", {})
        }
        
        # Set Content-Disposition header for download if requested
        download = request.args.get('download', 'false').lower() == 'true'
        if download:
            safe_name = "".join(c if c.isalnum() else "_" for c in sanitized_result.get("name", "script")).lower()
            from flask import Response
            json_data = json.dumps(sanitized_result.get("export_data", {}), indent=2)
            response = Response(
                json_data,
                mimetype='application/json',
                headers={
                    'Content-Disposition': f'attachment; filename={safe_name}_{script_id}.json'
                }
            )
            return response
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error exporting script {script_id}: {e}")
        return error_response(f"Error exporting script: {str(e)}", 500)

@scripts_bp.route('/scripts/import', methods=['POST'])
@cors_preflight
def import_script_endpoint():
    """Endpoint to import a script."""
    try:
        # Check if it's a JSON file upload or JSON data
        if 'file' in request.files:
            # Get the uploaded file
            script_file = request.files['file']
            
            # Save to temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp:
                temp_path = temp.name
                script_file.save(temp_path)
            
            # Import from file
            replace_existing = request.form.get('replace', 'false').lower() == 'true'
            result = import_script(temp_path, replace_existing)
            
            # Delete temporary file
            import os
            try:
                os.unlink(temp_path)
            except:
                pass
        else:
            # Get JSON data
            data = request.get_json()
            if not data:
                return error_response("No script data provided", 400)
            
            # Import from data
            replace_existing = request.args.get('replace', 'false').lower() == 'true'
            result = import_script(data, replace_existing)
        
        # Check result
        if not result.get("success", False):
            return error_response(result.get("error", "Unknown error"), 400)
        
        # Sanitize result for JSON serialization
        result_sanitized = sanitize_for_json(result)
        
        # Return success response
        return jsonify({
            "status": "success",
            "message": "Script imported successfully",
            "script_id": result_sanitized.get("script_id", ""),
            "name": result_sanitized.get("name", "")
        })
    
    except Exception as e:
        logger.error(f"Error importing script: {e}")
        return error_response(f"Error importing script: {str(e)}", 500)

@scripts_bp.route('/scripts/batch-import', methods=['POST'])
@cors_preflight
def batch_import_scripts_endpoint():
    """Endpoint to import multiple scripts from a directory."""
    try:
        # Get request data
        data = request.get_json()
        if not data or 'directory' not in data:
            return error_response("No import directory specified", 400)
        
        # Get directory and replace flag
        import_dir = data['directory']
        replace_existing = data.get('replace', False)
        
        # Validate directory
        if not os.path.exists(import_dir) or not os.path.isdir(import_dir):
            return error_response(f"Import directory {import_dir} does not exist or is not a directory", 400)
        
        # Import scripts
        result = batch_import_scripts(import_dir, replace_existing)
        
        # Sanitize result for JSON serialization
        sanitized_result = sanitize_for_json(result)
        
        # Return response
        return jsonify({
            "status": "success" if sanitized_result.get("success", False) else "partial" if sanitized_result.get("imported_count", 0) > 0 else "error",
            "imported_count": sanitized_result.get("imported_count", 0),
            "failed_count": sanitized_result.get("failed_count", 0),
            "imported": sanitized_result.get("imported", []),
            "failed": sanitized_result.get("failed", [])
        })
    
    except Exception as e:
        logger.error(f"Error batch importing scripts: {e}")
        return error_response(f"Error batch importing scripts: {str(e)}", 500)

@scripts_bp.route('/scripts/generate-test', methods=['POST'])
@cors_preflight
def generate_script_test_endpoint():
    """Test endpoint that returns a fixed script for testing the Android client."""
    try:
        # Get request data to log it
        data = request.get_json()
        logger.info(f"Received test script generation request: {data}")
        
        # Fixed test PyAutoGUI code
        pyautogui_code = """import pyautogui
import time

# Command: Click on Firefox
pyautogui.moveTo(100, 100)
# Wait for action to complete
time.sleep(0.5)
pyautogui.click()
# Wait for action to complete
time.sleep(0.5)

# Command: Type "Hello World"
pyautogui.write("Hello World")
# Wait for action to complete
time.sleep(0.5)
pyautogui.press("enter")
# Wait for action to complete
time.sleep(0.5)
"""
        
        # Log the code length
        logger.info(f"Test code has {len(pyautogui_code)} characters")
        
        # Create response
        response = {
            "status": "success",
            "pyautogui_code": pyautogui_code,
            "action_results": [
                {
                    "success": True,
                    "command": "Click on Firefox",
                    "pyautogui_actions": [
                        {"description": "Move to Firefox icon", "pyautogui_cmd": "pyautogui.moveTo(100, 100)"},
                        {"description": "Click", "pyautogui_cmd": "pyautogui.click()"}
                    ]
                },
                {
                    "success": True,
                    "command": "Type Hello World",
                    "pyautogui_actions": [
                        {"description": "Type text", "pyautogui_cmd": "pyautogui.write(\"Hello World\")"},
                        {"description": "Press Enter", "pyautogui_cmd": "pyautogui.press(\"enter\")"}
                    ]
                }
            ]
        }
        
        # Log response size
        logger.info(f"Test response has {len(str(response))} characters")
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error in test endpoint: {e}", exc_info=True)
        return error_response(f"Error in test endpoint: {str(e)}", 500) 