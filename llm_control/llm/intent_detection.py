import os
import re
import logging
import ollama

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def extract_target_text_with_llm(query, preserve_original_language=True):
    """
    Use Ollama to extract target text from a user query.
    Returns the single most relevant target word/phrase for the current step.
    
    Args:
        query: The user query to extract target text from
        preserve_original_language: If True, ensures the extracted text is in 
                                   the original language of the query
    
    Returns:
        A list containing the extracted target text, or an empty list if none found
    """
    logger.info(f"Using LLM to extract target text from: '{query}'")
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'gemma3:12b')
    
    # Record the query language for later use
    query_language = query  # We'll use the original query for preservation
    
    # Create a prompt that asks the LLM to identify the target text
    # Improved prompt for handling long commands - extract only the UI element target
    system_prompt = """Your task is to analyze a UI interaction query and extract ONLY the single most important target text that the user wants to find on the screen.

For short commands:
- "Click the Submit button" → Submit
- "Move mouse to the Profile icon in the top right" → Profile
- "Type 'Hello' in the search field" → search
- "Find and click on the COMPOSE button" → COMPOSE
- "Click LOGIN then press Enter" → LOGIN

For LONG commands with additional context, extract ONLY the UI element target, ignoring instructions:
- "Asegúrate de que en el 'Compost' también tenemos un servicio..." → Compost
- "Click on 'View Plans' and then check the status" → View Plans
- "Haz clic en 'Descargas' para abrir la carpeta" → Descargas
- "I need to click '4 comandos' to see the options" → 4 comandos

Spanish examples (keep original language):
- "Haz clic en el botón Enviar" → Enviar
- "Mueve el cursor al icono de Perfil" → Perfil
- "Escribe 'Hola' en el campo de búsqueda" → búsqueda
- "Busca y haz clic en REDACTAR" → REDACTAR

IMPORTANT RULES:
1. Extract ONLY the UI element name/text that appears on screen (usually in quotes or after action verbs)
2. For long commands, ignore all instructions and context - extract ONLY the target element
3. If text appears in quotes, that's usually the target - extract it exactly as written
4. Your response must ONLY contain the target word or phrase. No explanations, notes, quotes, formatting or additional text.
5. Keep the original letter case exactly as it appears
6. DO NOT TRANSLATE - keep it in the EXACT same language as in the query
7. Do NOT include keyboard keys (Enter, Tab, Escape) - these are handled separately
8. If there's no clear UI target text (e.g. imperative verbal commands without a screen object), respond with: NONE

Commands that should return NONE (no UI element target):
- "Comitea" → NONE  (git commit action, no UI element)
- "Puchea" → NONE  (git push action, no UI element)
- "ejecútalo" → NONE  (run/execute action, no UI element)
- "Si ya existe el script simplemente ejecútalo" → NONE
- "Abre una terminal" → NONE  (system action, not a UI element to click)"""
    
    user_prompt = f"Extract the single most important target text from this query: {query}"
    
    try:
        print(f"🔍 Extracting target text using LLM...")
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            options={"temperature": 0}  # Zero temperature for maximum reproducibility
        )
        
        # Extract the response text and clean it
        extracted_text = response['message']['content'].strip()
        
        # Clean up the extracted text - remove any explanatory notes or formatting
        # Remove any markdown formatting, notes in parentheses, etc.
        extracted_text = re.sub(r'```.*?```', '', extracted_text, flags=re.DOTALL)  # Remove code blocks
        extracted_text = re.sub(r'\(.*?\)', '', extracted_text)  # Remove parenthetical notes
        extracted_text = re.sub(r'\n.*', '', extracted_text, flags=re.DOTALL)  # Keep only first line
        extracted_text = re.sub(r'["`\'*_]', '', extracted_text)  # Remove quotes and formatting chars
        extracted_text = re.sub(r',.*', '', extracted_text)  # Keep only text before any comma
        
        # Handle the case where the LLM returns "NONE"
        if extracted_text.upper() == "NONE":
            logger.info("LLM couldn't identify any target text")
            print("🔍 No specific target text identified")
            return []
            
        # Return a single-item list with the extracted text
        target_text = extracted_text.strip()
        
        # Log the extracted text (preservar original para logging)
        logger.info(f"LLM extracted target text: {target_text}")
        print(f"🔍 Extracted target text: {target_text}")
        
        # Normalizar el texto extraído para matching consistente
        # Importar función de normalización desde finder
        try:
            from llm_control.command_processing.finder import normalize_text_for_matching
            has_normalize_func = True
            target_text_normalized = normalize_text_for_matching(target_text)
        except ImportError:
            # Fallback si no se puede importar (no debería pasar)
            has_normalize_func = False
            target_text_normalized = target_text.lower().strip()
        
        # Verify the target text appears in the original query (preserve language)
        # This ensures we're using a term from the original language
        if preserve_original_language:
            # Comparar versiones normalizadas para verificar si aparece
            if has_normalize_func:
                query_normalized = normalize_text_for_matching(query)
            else:
                query_normalized = query.lower()
            if target_text_normalized not in query_normalized:
                print(f"⚠️ Extracted text '{target_text}' not found in original query, attempting to match")
                
                # Try to find the correct version in the original query
                words = [word.strip('.,;:!?"\'()[]{}') for word in query.split()]
                best_match = None
                best_match_similarity = 0
                
                for word in words:
                    # Skip common words and very short ones
                    if len(word) < 3 or word.lower() in ['click', 'clic', 'on', 'the', 'el', 'la', 'en', 'on', 'to']:
                        continue
                    
                    # Calculate string similarity (simple algorithm)
                    # Usar versiones normalizadas para comparación consistente
                    similarity = 0
                    target_normalized = target_text_normalized
                    if has_normalize_func:
                        word_normalized = normalize_text_for_matching(word)
                    else:
                        word_normalized = word.lower()
                    
                    # Length of common prefix
                    for i in range(min(len(target_normalized), len(word_normalized))):
                        if target_normalized[i] == word_normalized[i]:
                            similarity += 1
                        else:
                            break
                    
                    # Check if this is better than our previous best match
                    if similarity > best_match_similarity:
                        best_match = word
                        best_match_similarity = similarity
                
                # Use the best match if it's good enough
                if best_match and best_match_similarity >= 2:
                    print(f"🔄 Using original language match: '{best_match}' instead of '{target_text}'")
                    target_text = best_match
        
        return [target_text] if target_text else []
    
    except Exception as e:
        logger.error(f"Error using Ollama for target text extraction: {str(e)}")
        print(f"❌ Error extracting target text: {str(e)}")
        # Fall back to empty list, which will trigger the old method
        return []
