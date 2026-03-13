import os
import re
import logging
# Get the package logger
logger = logging.getLogger("llm-pc-control")

def extract_text_to_type_with_llm(query):
    """
    Use Ollama to extract text that should be typed from a user query.
    Returns the text to type as a string.
    """
    logger.info(f"Using LLM to extract text to type from: '{query}'")
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen3.5:4b')
    
    # Create a prompt that asks the LLM to extract the text to type
    system_prompt = """Your task is to analyze a UI interaction query and extract ONLY the text that should be typed.

CRITICAL RULE: When the command starts with "Escribe" (or "Write"/"Type"), extract EVERYTHING after the typing verb as literal text to type, even if it looks like an instruction or command. The user wants to type that exact text, not execute it as a command.

For example in English:
- "Type 'Hello world' in the search field" → Hello world
- "Click on the textbox and enter admin@example.com" → admin@example.com
- "Type password123 and press Enter" → password123
- "Write 'This is a test message' in the composer" → This is a test message
- "Enter John Doe in the name field" → John Doe
- "Write, execute this command" → execute this command
- "Type, for this you can examine the logs" → for this you can examine the logs

For example in Spanish:
- "Escribe 'Hola mundo' en el campo de búsqueda" → Hola mundo
- "Haz clic en el cuadro de texto e ingresa usuario@ejemplo.com" → usuario@ejemplo.com
- "Teclea contraseña123 y presiona Enter" → contraseña123
- "Escribir 'Este es un mensaje de prueba' en el editor" → Este es un mensaje de prueba
- "Ingresa Juan Pérez en el campo nombre" → Juan Pérez
- "Escribe, ejecuta este comando" → ejecuta este comando
- "Escribe el comando conflictivo, tiene oraciones con ejecución o ejecutar" → el comando conflictivo, tiene oraciones con ejecución o ejecutar
- "Escribe, para esto puedes examinar los logs de servicio en el journal" → para esto puedes examinar los logs de servicio en el journal

IMPORTANT RULES:
1. When the query starts with "Escribe," or "Write," (with comma), extract EVERYTHING after the comma as literal text.
2. When the query contains "Escribe [texto]" (without comma but with space), extract everything after "Escribe" as literal text.
3. Your response must ONLY contain the exact text that should be typed. No explanations, notes, formatting or additional text.
4. Keep the exact case, punctuation, and special characters as specified in the query.
5. Preserve any escape sequences like \\n, \\t, or \\\\ that might be in the text.
6. If the text to type is in quotes, extract only what's inside the quotes.
7. If the text to type is not in quotes, extract everything after the typing verb (Escribe/Write/Type) as literal text.
8. If there's no text to type, respond with the single word: NONE"""
    
    user_prompt = f"Extract the text that should be typed from this query: {query}"
    
    try:
        print(f"📝 Extracting text to type using LLM...")
        from llm_control.utils.ollama import ollama_chat
        success, content, error = ollama_chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            options={"temperature": 0.1},
            timeout=60,
        )
        if not success:
            raise RuntimeError(error or "Ollama API failed")
        extracted_text = (content or "").strip()
        
        # Clean up the extracted text - remove any explanatory notes or formatting
        extracted_text = re.sub(r'```.*?```', '', extracted_text, flags=re.DOTALL)  # Remove code blocks
        extracted_text = re.sub(r'^["\'`]|["\'`]$', '', extracted_text)  # Remove quotes at beginning/end
        
        # Handle the case where the LLM returns "NONE"
        if extracted_text.upper() == "NONE":
            logger.info("LLM couldn't identify any text to type")
            print("📝 No specific text to type identified")
            return None
            
        # Return the extracted text
        logger.info(f"LLM extracted text to type: '{extracted_text}'")
        print(f"📝 Extracted text to type: '{extracted_text}'")
        
        return extracted_text
    
    except Exception as e:
        logger.error(f"Error using Ollama for text extraction: {str(e)}")
        print(f"❌ Error extracting text to type: {str(e)}")
        return None

def ensure_text_is_safe_for_typewrite(text):
    """Ensure text is properly escaped for use with pyautogui.typewrite"""
    if not text:
        return ""
    
    # Map special characters with tildes to their ASCII equivalents
    special_chars = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
        'ñ': 'n', 'Ñ': 'N',
        'ü': 'u', 'Ü': 'U',
        '¿': '?', '¡': '!',
        '«': '"', '»': '"',
        '€': 'E', '£': 'L', '¥': 'Y',
        '©': '(c)', '®': '(r)', '™': '(tm)',
        '…': '...', '—': '-', '–': '-',
        '•': '*', '°': 'o',
        '{': '{{',  # PyAutoGUI uses { } for special keys
        '}': '}}',
    }
    
    # Replace special characters
    for char, replacement in special_chars.items():
        text = text.replace(char, replacement)
        
    return text

def parse_shell_command_with_llm(user_text):
    """
    Use Ollama to parse natural language text into a proper shell/terminal command.
    Returns the parsed command as a string, typically in lowercase.
    
    Examples:
    - "listar archivos" → "ls"
    - "listar archivos con detalles" → "ls -la"
    - "mostrar el contenido del archivo config" → "cat config"
    - "buscar texto en archivos" → "grep"
    """
    logger.info(f"Using LLM to parse shell command from: '{user_text}'")
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen3.5:4b')
    
    # Create a prompt that asks the LLM to convert natural language to shell command
    system_prompt = """Your task is to convert natural language text into a proper shell/terminal command.

CRITICAL RULES:
1. Convert the natural language description to the actual shell command that would accomplish the task
2. Use standard Unix/Linux commands (ls, cat, grep, find, etc.)
3. Output the command in lowercase (unless the command requires specific case)
4. Include appropriate flags and arguments when the description implies them
5. Your response must ONLY contain the command. No explanations, notes, formatting, or additional text.
6. Do NOT include the word "shell" or "terminal" in your response - just the command itself
7. If the text is already a valid command, return it as-is (but in lowercase if appropriate)
8. For commands with pipes or redirections, preserve them exactly
9. For file paths or arguments, keep them as specified in the original text

English examples:
- "list files" → ls
- "list files with details" → ls -la
- "show file content" → cat
- "show content of config file" → cat config
- "search for text in files" → grep
- "find files named test" → find . -name test
- "list files and filter by txt" → ls | grep txt
- "change to home directory" → cd ~
- "show current directory" → pwd
- "list all processes" → ps aux
- "check disk usage" → df -h

Spanish examples:
- "listar archivos" → ls
- "listar archivos con detalles" → ls -la
- "mostrar contenido del archivo" → cat
- "mostrar contenido del archivo config" → cat config
- "buscar texto en archivos" → grep
- "buscar archivos llamados test" → find . -name test
- "listar archivos y filtrar por txt" → ls | grep txt
- "cambiar al directorio home" → cd ~
- "mostrar directorio actual" → pwd
- "listar todos los procesos" → ps aux
- "verificar uso de disco" → df -h

If the input is already a valid command (like "ls -la" or "cat file.txt"), return it as-is but in lowercase if it's a simple command.

Your response must be ONLY the command, nothing else."""
    
    user_prompt = f"Convert this to a shell command: {user_text}"
    
    try:
        print(f"💻 Parsing shell command using LLM...")
        from llm_control.utils.ollama import ollama_chat
        success, content, error = ollama_chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            options={"temperature": 0.1},
            timeout=60,
        )
        if not success:
            raise RuntimeError(error or "Ollama API failed")
        parsed_command = (content or "").strip()
        
        # Clean up the parsed command - remove any explanatory notes or formatting
        parsed_command = re.sub(r'```.*?```', '', parsed_command, flags=re.DOTALL)  # Remove code blocks
        parsed_command = re.sub(r'^["\'`]|["\'`]$', '', parsed_command)  # Remove quotes at beginning/end
        parsed_command = re.sub(r'^shell\s+|^terminal\s+', '', parsed_command, flags=re.IGNORECASE)  # Remove shell/terminal prefix if LLM added it
        
        # Convert to lowercase for simple commands (but preserve case for file paths, etc.)
        # This is a heuristic: if it looks like a simple command (no paths, no special chars), lowercase it
        if not re.search(r'[/~$]', parsed_command) and not re.search(r'[|&<>]', parsed_command):
            # Simple command - lowercase the first word (the command itself)
            parts = parsed_command.split(maxsplit=1)
            if len(parts) > 0:
                parts[0] = parts[0].lower()
                parsed_command = ' '.join(parts)
        
        # Return the parsed command
        logger.info(f"LLM parsed shell command: '{parsed_command}'")
        print(f"💻 Parsed shell command: '{parsed_command}'")
        
        return parsed_command
    
    except Exception as e:
        logger.error(f"Error using Ollama for shell command parsing: {str(e)}")
        print(f"❌ Error parsing shell command: {str(e)}")
        return None
