#!/usr/bin/env python3
"""
Test script for the command history functionality.
This script adds some example commands to the history and then retrieves them.
"""

import os
import sys
import datetime
import json

# Add the project root to the path to allow importing from llm_control
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    # Import our command history functions
    from llm_control.voice.utils import add_to_command_history, get_command_history
except ImportError:
    print("Error: Could not import command history functions.")
    print("Make sure you're running this script from the project root directory.")
    sys.exit(1)

def main():
    """Test the command history functionality."""
    print("\nCommand History Test")
    print("===================\n")
    
    print("Adding example commands to history...")
    
    # Example command 1
    command1 = {
        'timestamp': datetime.datetime.now().isoformat(),
        'command': 'click on the Firefox icon',
        'steps': ['move the cursor to the Firefox icon', 'click'],
        'code': 'import pyautogui\n\n# move the cursor to the Firefox icon\npyautogui.moveTo(100, 100)\n\n# click\npyautogui.click()',
        'success': True
    }
    
    # Example command 2
    command2 = {
        'timestamp': datetime.datetime.now().isoformat(),
        'command': 'type "hello world" and press enter',
        'steps': ['type "hello world"', 'press enter'],
        'code': 'import pyautogui\n\n# type "hello world"\npyautogui.typewrite("hello world")\n\n# press enter\npyautogui.press("enter")',
        'success': True
    }
    
    # Example command 3 (failed)
    command3 = {
        'timestamp': datetime.datetime.now().isoformat(),
        'command': 'click on non-existent button',
        'steps': ['find non-existent button', 'click on non-existent button'],
        'code': 'import pyautogui\n\n# This command would fail as the button does not exist\npyautogui.click(1000, 1000)',
        'success': False
    }
    
    # Add commands to history
    add_to_command_history(command1)
    add_to_command_history(command2)
    add_to_command_history(command3)
    
    print("Added 3 example commands to history.")
    print("\nRetrieving command history...")
    
    # Get all command history
    history = get_command_history()
    
    # Print the history
    print(f"\nFound {len(history)} commands in history:")
    for i, cmd in enumerate(history):
        print(f"\nCommand {i+1}:")
        print(f"  Timestamp: {cmd['timestamp']}")
        print(f"  Command: {cmd['command']}")
        print(f"  Steps: {cmd['steps']}")
        print(f"  Success: {cmd['success']}")
        print(f"  Code: {cmd['code'][:50]}..." if len(cmd['code']) > 50 else f"  Code: {cmd['code']}")
    
    # Get the history file path
    from llm_control.voice.utils import get_command_history_file
    history_file = get_command_history_file()
    
    print(f"\nCommand history is stored in: {history_file}")
    print("\nTest completed successfully!")

if __name__ == "__main__":
    main() 