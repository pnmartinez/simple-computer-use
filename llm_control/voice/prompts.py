"""
Prompts for Ollama LLM API calls.

This module contains all the prompts used for communicating with the Ollama API.
Each prompt is designed for a specific purpose in the voice control pipeline.
"""

# Translation prompt - used to translate text from other languages to English
TRANSLATION_PROMPT = """
        Translate the following text to English.
        
        CRITICAL: DO NOT translate any of the following:
        1. Proper nouns, UI element names, button labels, or technical terms
        2. Menu items, tabs, or buttons (like "Actividades", "Archivo", "Configuración")
        3. Application names (like "Firefox", "Chrome", "Terminal")
        4. Text inside quotes (e.g., "Hola mundo")
        5. Any word that might be a desktop element or application name
        
        EXAMPLES of words to KEEP in original language:
        - "actividades" should stay as "actividades" (NEVER translate to "activities")
        - "opciones" should stay as "opciones" (NEVER translate to "options")
        - "archivo" should stay as "archivo" (NEVER translate to "file")
        - "nueva pestaña" should stay as "nueva pestaña" (NEVER translate to "new tab")
        
        Spanish -> English examples with preserved text:
        - "haz clic en el botón Cancelar" -> "click on the Cancelar button"
        - "escribe 'Hola mundo' en el campo Mensaje" -> "type 'Hola mundo' in the Mensaje field"
        - "presiona enter en la ventana Configuración" -> "press enter in the Configuración window"
        - "selecciona Archivo desde el menú" -> "select Archivo from the menu"
        - "mueve el cursor a actividades" -> "move the cursor to actividades"
        
        ```
        {text}
        ```
        
        RETURN ONLY THE TRANSLATED TEXT - NOTHING ELSE. NO EXPLANATIONS. NO HEADERS. NO NOTES.
        """

# Command verification prompt - used to verify that parsed steps match the original command
VERIFICATION_PROMPT = """
            Your task is to verify that a step extracted from a voice command doesn't contain hallucinated text that wasn't in the original command.
            
            Original Voice Command: "{original_command}"
            
            Extracted Step: "{step}"
            
            Check if all parts of the extracted step are semantically present in the original command. If the step contains details not implied by the original command, remove those details.
            
            RULES:
            1. Keep all words and phrases that directly appear in or are strongly implied by the original command
            2. Remove details, explanations, or actions that aren't mentioned or strongly implied in the original
            3. Maintain the overall intent and instruction of the step
            4. Focus on removing just hallucinated content, not rewording the entire step
            
            EXAMPLES:
            
            Original: "Open Firefox and go to Gmail"
            Step: "Find and click on the Firefox icon on the desktop then wait 5 seconds for it to load"
            Result: "Find and click on the Firefox icon" 
            (Removed details about "on the desktop" and "wait 5 seconds" as those weren't in the original)
            
            Original: "Type Hello World in Notepad"
            Step: "Open Notepad application from the Start menu"
            Result: "Open Notepad application"
            (Removed "from the Start menu" as it wasn't specified in the original)
            
            Return only the verified or corrected step with no additional text or explanations.
            """

# Command splitting prompt - used to break down a natural language command into steps
SPLIT_COMMAND_PROMPT = """
        Split this command into separate steps, step by step. Format your response as a bulleted list, with each step on a new line starting with "- ".
        
        IMPORTANT RULES:
        1. Keep write/type commands together with their content. 
           For example: "escribe hello world" should be ONE step, not separated.
        2. If you see "escribe" or "type" followed by content, keep them together as one step. A lonely "escribe" or "write" should not exist: in that case you can even join a comma separated "write" witht the next one, if it makes sense.
        3. Identify actions clearly - click, type, press, etc.
        
        EXAMPLES:
        
        Input: "Open Firefox, go to Gmail and compose a new email"
        Output:
        "- Open Firefox
        - Go to Gmail
        - Compose a new email"
        
        Input: "Click Settings then change theme"
        Output:
        "- Click Settings
        - Change theme"
        
        Input: "Click compose, type hello world, press send"
        Output:
        "- Click compose
        - Type hello world
        - Press send"
        
        Input: "Clique en Composer, escribe haz una review general del código, presiona Enter"
        Output:
        "- Clique en Composer
        - Escribe haz una review general del código
        - Presiona Enter"

        Input "Clic Composer, escribe, revisa la aplicación, presiona Enter."
        Output:
        "- Clic Composer,
        - Escribe "revisa la aplicación",
        - Presiona Enter"
        
        Split this series of commands:
        ```
        {command}
        ```
        
        IMPORTANT: keep the original content, only reformat as bullet point list WITH NO ADDITIONAL TEXT. Each line should start with "- ".
        """

# OCR target identification prompt - used to identify UI elements that need OCR
IDENTIFY_OCR_TARGETS_PROMPT = """
            Your task is to identify text that needs to be visually detected on screen (OCR targets) in this UI automation step:

            ```
            {step}
            ```
            
            For any UI element that needs to be located visually by text (like buttons, menu items, labels, icons), wrap ONLY that text in double quotes.
            
            EXAMPLES:
            
            Input: Find and click on the Settings button
            Output: Find and click on the "Settings" button
            
            Input: Click on the Compose button in Gmail
            Output: Click on the "Compose" button in Gmail
            
            Input: Type hello world this is me
            Output: Type "hello world this is me"
            
            Input: Press Alt+F4 to close the window
            Output: Press Alt+F4 to close the window
            (Note: No quotes needed as there's no text to find visually)

            Input: haz clic.
            Output: haz clic.
            (Note: No change or quotes needed as there's no text to find visually)
            
            ONLY add quotes around specific text that would be seen on screen that needs to be located.
            DO NOT add quotes around general descriptions or actions, such as "click"
            Return only the modified step with NO additional explanations or boilerplate.
            """

# PyAutoGUI code generation prompt - used to generate automation code
GENERATE_PYAUTOGUI_ACTIONS_PROMPT = """
            Generate a PyAutoGUI command for this UI automation step:
            
            ```
            {step}
            ```
            
            Your response should be in JSON format with these fields:
            1. "pyautogui_cmd": A Python command that uses PyAutoGUI to execute this step
            2. "target": The primary OCR target (if any) that would be visually detected on screen
            3. "description": A short description of this action
            
            IMPORTANT: ONLY use the following PyAutoGUI functions - DO NOT use any other functions:
            
            1. Mouse operations:
               - pyautogui.moveTo(x, y) - Move mouse to absolute position
               - pyautogui.move(x, y) - Move mouse relative to current position
               - pyautogui.click(x, y) - Click at position
               - pyautogui.doubleClick(x, y) - Double-click at position
               - pyautogui.rightClick(x, y) - Right-click at position
               - pyautogui.dragTo(x, y) - Drag to position
            
            2. Keyboard operations:
               - pyautogui.write('text') - Type text
               - pyautogui.press('key') - Press a key (e.g., 'enter', 'tab', 'escape')
               - pyautogui.hotkey('key1', 'key2', ...) - Press keys together (e.g., 'ctrl', 'c')
            
            3. Scrolling operations:
               - pyautogui.scroll(amount) - Scroll up (positive) or down (negative)
            
            4. Screenshot operations:
               - pyautogui.screenshot() - Take a screenshot
            
            For UI element detection, use these patterns:
            - For finding elements: Simple string search approach mentioning the target
            - For multi-step operations: Use multiple basic PyAutoGUI commands separated by semicolons
            
            For hotkey combinations:
            - "Ctrl-L" -> pyautogui.hotkey('ctrl', 'l')
            - "Alt-Tab" -> pyautogui.hotkey('alt', 'tab')
            - "Shift-Enter" -> pyautogui.hotkey('shift', 'enter')
            - "Ctrl-Alt-Delete" -> pyautogui.hotkey('ctrl', 'alt', 'delete')
            
            EXAMPLES:
            
            Step: Find and click on the "Settings" button
            Response:
            {
              "pyautogui_cmd": "# Find and click on Settings\\npyautogui.click(x, y)  # Coordinates would be determined at runtime",
              "target": "Settings",
              "description": "Click on Settings button"
            }
            
            Step: Type hello in the "search" field
            Response:
            {
              "pyautogui_cmd": "# Click on search field\\npyautogui.click(x, y);  # Coordinates for search field\\npyautogui.write('hello')",
              "target": "search",
              "description": "Type hello in search field"
            }
            
            Step: Press Alt+F4 to close the window
            Response:
            {
              "pyautogui_cmd": "pyautogui.hotkey('alt', 'f4')",
              "target": null,
              "description": "Close window with Alt+F4"
            }
            
            Step: Press Ctrl-L
            Response:
            {
              "pyautogui_cmd": "pyautogui.hotkey('ctrl', 'l')",
              "target": null, 
              "description": "Focus address bar with Ctrl-L"
            }
            
            Step: Scroll down to see more content
            Response:
            {
              "pyautogui_cmd": "pyautogui.scroll(-10)  # Negative values scroll down",
              "target": null,
              "description": "Scroll down"
            }
            
            Step: Right-click on the "image" and select Save
            Response:
            {
              "pyautogui_cmd": "# Right-click on image\\npyautogui.rightClick(x, y);  # Coordinates for image\\n# Then click on Save option\\npyautogui.move(0, 50);  # Move down to Save option\\npyautogui.click()",
              "target": "image",
              "description": "Right-click image and select Save"
            }
            
            IMPORTANT: 
            1. Return valid JSON with no additional explanation or text
            2. If there is no specific target, set "target" to null
            3. Use ONLY the PyAutoGUI functions listed above
            4. Do not attempt to use coordinates directly - use placeholders and comments
            5. For locating screen elements, keep it simple and reference the target - don't use locateOnScreen()
            6. Use comments to explain the steps where appropriate
            7. For hotkey combinations, always use pyautogui.hotkey() with lowercase key names
            """ 