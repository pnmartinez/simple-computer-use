#!/usr/bin/env python3
"""
Test script for favorites run and delete functionality.
"""

import os
import sys
import json
from datetime import datetime
import time

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the required modules
from llm_control.favorites.utils import save_as_favorite, get_favorites, delete_favorite, run_favorite

def main():
    """Test the favorites run and delete functionality."""
    
    print("Testing favorites run and delete functionality...")
    
    # Create a simple example command for testing
    test_command = {
        'timestamp': datetime.now().isoformat(),
        'command': 'Print hello world',
        'steps': ['Print hello world'],
        'code': '''
# Simple hello world script
from datetime import datetime
import os

print("Hello, World!")
print("This is a test script.")
print("Current time:", datetime.now().isoformat())
''',
        'success': True
    }
    
    # Save command as favorite with a unique name
    unique_name = f"test_hello_{int(time.time())}"
    print(f"\nSaving test command as favorite with name: {unique_name}")
    result = save_as_favorite(test_command, unique_name)
    
    if result['status'] != 'success':
        print(f"Error saving favorite: {result.get('error', 'Unknown error')}")
        return
    
    script_path = result['filepath']
    script_id = os.path.splitext(os.path.basename(script_path))[0]
    print(f"Successfully saved favorite script: {script_id}")
    
    # Run the script
    print("\nRunning the favorite script...")
    run_result = run_favorite(script_id)
    
    if run_result['status'] == 'success':
        print("Script executed successfully!")
        print("Output:")
        print("-" * 40)
        print(run_result.get('stdout', ''))
        print("-" * 40)
        if run_result.get('stderr'):
            print("Errors:")
            print(run_result['stderr'])
    else:
        print(f"Error running script: {run_result.get('error', 'Unknown error')}")
    
    # Delete the script
    print("\nDeleting the favorite script...")
    delete_result = delete_favorite(script_id)
    
    if delete_result['status'] == 'success':
        print(f"Successfully deleted: {script_id}")
        print(f"Deleted files: {delete_result.get('deleted_files', [])}")
    else:
        print(f"Error deleting script: {delete_result.get('error', 'Unknown error')}")
    
    # Verify deletion
    print("\nVerifying deletion...")
    favorites = get_favorites()
    
    # Check if our script is still in the list
    found = False
    for fav in favorites:
        if fav.get('name', '').startswith(unique_name):
            found = True
            print(f"WARNING: Script still exists: {fav.get('script_path', '')}")
    
    if not found:
        print("Verification successful: Script was properly deleted.")
    
    print("\nTest completed successfully!")

if __name__ == "__main__":
    main() 