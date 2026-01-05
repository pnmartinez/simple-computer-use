#!/usr/bin/env python3
# Favorite command: Clic Actividades. Escribe Gestor de Archivos. Presiona Enter. Presiona Control Shift N.
# Created: 2025-07-09T20:02:16.980407
# Original timestamp: Unknown
# Success: True
import pyautogui
import time

# Generated from multiple steps
import time

# Step 1
pyautogui.moveTo(58, 15, duration=0.5)
pyautogui.click()
time.sleep(0.5)  # Pause between steps

# Step 2
pyautogui.typewrite("Gestor de Archivos")
time.sleep(0.5)  # Pause between steps

# Step 3
pyautogui.press("enter")
time.sleep(0.5)  # Pause between steps

# Step 4
pyautogui.hotkey("ctrl", "shift", "n")
