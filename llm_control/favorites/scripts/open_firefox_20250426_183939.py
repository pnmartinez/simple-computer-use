#!/usr/bin/env python3
# Favorite command: Open Firefox and go to github.com
# Created: 2025-04-26T18:39:39.023421
# Original timestamp: 2025-04-26T18:39:39.023378
# Success: True

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
