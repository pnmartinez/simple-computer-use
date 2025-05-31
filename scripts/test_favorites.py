#!/usr/bin/env python3
"""
Test script for favorites functionality.
"""

import os
import sys
import json
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the required modules
from llm_control.favorites.utils import save_as_favorite, get_favorites

def main():
    """Test the favorites functionality."""
    
    print("Testing favorites functionality...")
    
    # Create some example command data
    command1 = {
        'timestamp': datetime.now().isoformat(),
        'command': 'Open Firefox and go to github.com',
        'steps': ['Open Firefox', 'Go to github.com'],
        'code': '''
import pyautogui
import time

# Open Firefox
pyautogui.hotkey('win', 'r')
time.sleep(0.5)
pyautogui.write('firefox')
pyautogui.press('enter')
time.sleep(2)

# Go to github.com
pyautogui.write('github.com')
pyautogui.press('enter')
''',
        'success': True
    }
    
    command2 = {
        'timestamp': datetime.now().isoformat(),
        'command': 'Take screenshot and save to desktop',
        'steps': ['Take screenshot', 'Save to desktop'],
        'code': '''
import pyautogui
import time
from datetime import datetime

# Take screenshot
screenshot = pyautogui.screenshot()

# Save to desktop
desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
filename = f'screenshot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
filepath = os.path.join(desktop, filename)
screenshot.save(filepath)
print(f"Screenshot saved to {filepath}")
''',
        'success': True
    }
    
    # Save commands as favorites
    print("\nSaving example command 1 as favorite...")
    result1 = save_as_favorite(command1, "open_firefox")
    
    if result1['status'] == 'success':
        print(f"  Success! Saved to: {result1['filepath']}")
    else:
        print(f"  Error: {result1.get('error', 'Unknown error')}")
    
    print("\nSaving example command 2 as favorite...")
    result2 = save_as_favorite(command2)
    
    if result2['status'] == 'success':
        print(f"  Success! Saved to: {result2['filepath']}")
    else:
        print(f"  Error: {result2.get('error', 'Unknown error')}")
    
    # Get all favorites
    print("\nRetrieving favorites...")
    favorites = get_favorites()
    
    # Print the favorites
    print(f"\nFound {len(favorites)} favorites:")
    for i, fav in enumerate(favorites):
        print(f"\nFavorite {i+1}:")
        print(f"  Name: {fav.get('name', 'Unknown')}")
        print(f"  Command: {fav.get('command', 'Unknown')}")
        print(f"  Timestamp: {fav.get('timestamp', 'Unknown')}")
        print(f"  Script Path: {fav.get('script_path', 'Unknown')}")
    
    print("\nTest completed successfully!")

if __name__ == "__main__":
    main() 