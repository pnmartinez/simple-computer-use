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
    system_prompt = """Your task is to analyze a UI interaction query and extract ONLY the single most important target text that the user wants to find on the screen.

For example:
- "Click the Submit button" → Submit
- "Move mouse to the Profile icon in the top right" → Profile
- "Type 'Hello' in the search field" → search
- "Find and click on the COMPOSE button" → COMPOSE
- "Minimize the current opened app" → minimize
- "Click LOGIN then press Enter" → LOGIN
- "Type my password then hit Tab" → password

Spanish examples (keep original language):
- "Haz clic en el botón Enviar" → Enviar
- "Mueve el cursor al icono de Perfil" → Perfil
- "Escribe 'Hola' en el campo de búsqueda" → búsqueda
- "Busca y haz clic en REDACTAR" → REDACTAR

IMPORTANT: Your response must ONLY contain the single most important target word or phrase for this step. No explanations, notes, quotes, formatting or additional text.
Keep the original letter case. Extract ONLY the most important UI element that needs to be found on screen.
DO NOT TRANSLATE the target text - keep it in the EXACT same language as it appears in the user's query.
Do NOT include keyboard keys (like Enter, Tab, Escape) as the target - these will be handled separately.
If there's no clear target text, respond with the single word: NONE"""
    
    user_prompt = f"Extract the single most important target text from this query: {query}"
    
    try:
        print(f"🔍 Extracting target text using LLM...")
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            options={"temperature": 0.1}  # Lower temperature for more consistent formatting
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
        
        # Log the extracted text
        logger.info(f"LLM extracted target text: {target_text}")
        print(f"🔍 Extracted target text: {target_text}")
        
        # Verify the target text appears in the original query (preserve language)
        # This ensures we're using a term from the original language
        if preserve_original_language:
            # If extracted text doesn't appear in the original query, try finding similar text
            if target_text.lower() not in query.lower():
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
                    similarity = 0
                    target_lower = target_text.lower()
                    word_lower = word.lower()
                    
                    # Length of common prefix
                    for i in range(min(len(target_lower), len(word_lower))):
                        if target_lower[i] == word_lower[i]:
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
