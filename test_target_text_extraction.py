#!/usr/bin/env python3
"""
Test script to verify that target text extraction correctly preserves original language.
This is critical for OCR operations where we need the exact text as it appears on screen.
"""

import os
import sys
import logging
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Get the logger
logger = logging.getLogger("test-extraction")

# Try to import from the package first
try:
    from llm_control.llm.intent_detection import extract_target_text_with_llm
    print("Successfully imported from llm_control package!")
except ImportError:
    print("Could not import from package, defining function here")
    
    # If we can't import from the package, define a minimal version here
    # This should match the function in llm_control/llm/intent_detection.py
    import os
    import re
    import logging
    
    try:
        import ollama
    except ImportError:
        print("Error: Ollama package not found. Please install with: pip install ollama")
        sys.exit(1)
    
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
        OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.1:latest')
        
        # Create a prompt that asks the LLM to identify the target text
        system_prompt = """Your task is to analyze a UI interaction query and extract ONLY the single most important target text that the user wants to find on the screen.

For example:
- "Click the Submit button" → Submit
- "Move mouse to the Profile icon in the top right" → Profile
- "Type 'Hello' in the search field" → search
- "Find and click on the COMPOSE button" → COMPOSE

Spanish examples (keep original language):
- "Haz clic en el botón Enviar" → Enviar
- "Mueve el cursor al icono de Perfil" → Perfil
- "Escribe 'Hola' en el campo de búsqueda" → búsqueda

IMPORTANT: Your response must ONLY contain the single most important target word or phrase for this step. No explanations, notes, quotes, formatting or additional text.
Keep the original letter case. Extract ONLY the most important UI element that needs to be found on screen.
DO NOT TRANSLATE the target text - keep it in the EXACT same language as it appears in the user's query.
Do NOT include keyboard keys (like Enter, Tab, Escape) as the target - these will be handled separately.
If there's no clear target text, respond with the single word: NONE"""
        
        user_prompt = f"Extract the single most important target text from this query: {query}"
        
        print(f"🔍 Extracting target text using LLM...")
        
        try:
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
            extracted_text = re.sub(r'```.*?```', '', extracted_text, flags=re.DOTALL)
            extracted_text = re.sub(r'\(.*?\)', '', extracted_text)
            extracted_text = re.sub(r'\n.*', '', extracted_text, flags=re.DOTALL)
            extracted_text = re.sub(r'["`\'*_]', '', extracted_text)
            extracted_text = re.sub(r',.*', '', extracted_text)
            
            if extracted_text.upper() == "NONE":
                print("🔍 No specific target text identified")
                return []
                
            target_text = extracted_text.strip()
            print(f"🔍 Extracted target text: {target_text}")
            
            # Verify target text appears in original query
            if preserve_original_language:
                if target_text.lower() not in query.lower():
                    print(f"⚠️ Extracted text '{target_text}' not found in original query, attempting to match")
                    words = [word.strip('.,;:!?"\'()[]{}') for word in query.split()]
                    best_match = None
                    best_match_similarity = 0
                    
                    for word in words:
                        if len(word) < 3 or word.lower() in ['click', 'clic', 'on', 'the', 'el', 'la', 'en', 'on', 'to']:
                            continue
                        
                        # Calculate string similarity
                        similarity = 0
                        target_lower = target_text.lower()
                        word_lower = word.lower()
                        
                        # Common prefix length
                        for i in range(min(len(target_lower), len(word_lower))):
                            if target_lower[i] == word_lower[i]:
                                similarity += 1
                            else:
                                break
                        
                        if similarity > best_match_similarity:
                            best_match = word
                            best_match_similarity = similarity
                    
                    if best_match and best_match_similarity >= 2:
                        print(f"🔄 Using original language match: '{best_match}' instead of '{target_text}'")
                        target_text = best_match
            
            return [target_text] if target_text else []
        
        except Exception as e:
            print(f"❌ Error extracting target text: {str(e)}")
            return []

def test_extraction(query, expected_language="original"):
    """Test extraction with the given query"""
    print("\n" + "="*70)
    print(f"Testing extraction with query: '{query}'")
    print("="*70)
    
    # Call the extraction function
    result = extract_target_text_with_llm(query)
    
    # Print the result
    if result:
        print(f"✅ Extracted text: '{result[0]}'")
        
        # Check if result appears in original query (case insensitive)
        if result[0].lower() in query.lower():
            print(f"✅ MATCH: Text found in original query")
        else:
            print(f"❌ NOT FOUND: Text not found in original query")
        
        # For Spanish queries, make sure we didn't get an English translation
        if "haz clic" in query.lower() or "escribe" in query.lower() or "mueve" in query.lower():
            english_terms = ["click", "type", "move", "search", "button", "icon"]
            if any(term in result[0].lower() for term in english_terms):
                print(f"❌ WARNING: Possibly translated to English: '{result[0]}'")
            else:
                print(f"✅ Text appears to be in original Spanish language")
    else:
        print("❌ No text extracted")
    
    print("-"*70)

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Test target text extraction with language preservation"
    )
    
    parser.add_argument(
        "--query",
        type=str,
        help="Custom query to test extraction with"
    )
    
    return parser.parse_args()

def main():
    """Main entry point"""
    args = parse_args()
    
    print("Testing Target Text Extraction Language Preservation")
    print("="*70)
    
    # If a custom query is provided, test only that
    if args.query:
        test_extraction(args.query)
        return
    
    # Otherwise, test with predefined examples
    test_cases = [
        # English test cases
        "Click on the Submit button",
        "Move to the Settings icon in the top right",
        "Find and click on the LOGIN button",
        "Type 'Hello world' in the search field",
        
        # Spanish test cases
        "Haz clic en el botón Cancelar",
        "Mueve el cursor al icono de Perfil",
        "Busca y haz clic en ACEPTAR",
        "Escribe 'Hola mundo' en el campo de búsqueda",
        
        # Mixed language test cases
        "Click on the Configuración button",
        "Haz clic en el botón Settings",
    ]
    
    for query in test_cases:
        test_extraction(query)
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    main() 