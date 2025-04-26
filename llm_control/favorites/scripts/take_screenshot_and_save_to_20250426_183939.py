#!/usr/bin/env python3
# Favorite command: Take screenshot and save to desktop
# Created: 2025-04-26T18:39:39.023602
# Original timestamp: 2025-04-26T18:39:39.023383
# Success: True

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
