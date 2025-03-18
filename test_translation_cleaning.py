#!/usr/bin/env python3
"""
Test script to verify translation cleaning and preservation of UI element names.
"""

import os
import sys
import logging
import re
import argparse
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Get the logger
logger = logging.getLogger("test-cleaning")

def clean_llm_response(response, original_text):
    """Clean the LLM response to remove unnecessary explanations"""
    if not response:
        return ""
    
    # List of common prefixes that LLMs might add
    prefixes = [
        "Here is the translation of the given sequence of interactions with a PC:",
        "Here is the translation of the sequence:",
        "Here is the translation:",
        "Here's the translation:",
        "Translation:",
        "The translation is:",
        "Translated text:",
        "Translating to English:",
    ]
    
    # Clean up response by removing common prefixes
    cleaned = response
    
    # Try to remove prefixes
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    
    # Also try to remove less exact matches at the start
    lines = cleaned.split('\n')
    if lines and any(line.lower().startswith(('here', 'translation', 'translated')) for line in [lines[0]]):
        # If the first line looks like a header, remove it
        cleaned = '\n'.join(lines[1:]).strip()
    
    # Remove explanatory notes often found at the end
    explanatory_markers = [
        "Note:",
        "Please note:",
        "I've preserved",
        "I have preserved",
        "I kept",
        "I maintained",
    ]
    
    for marker in explanatory_markers:
        if marker in cleaned:
            # Get the text before the marker
            parts = cleaned.split(marker, 1)
            cleaned = parts[0].strip()
    
    # Remove triple backticks (used in code blocks)
    cleaned = re.sub(r'```.*?```', '', cleaned, flags=re.DOTALL)
    if cleaned.startswith('```') and '```' in cleaned[3:]:
        cleaned = cleaned.split('```', 2)[1].strip()
    
    # Sanity check - if we've removed too much, revert to original response
    if len(cleaned) < len(response) * 0.5 and len(cleaned.split()) < 3:
        logger.warning(f"Cleaning may have removed too much content. Using original response.")
        return response
    
    # If we have multiple paragraphs, the first one is likely the translation
    paragraphs = cleaned.split("\n\n")
    if len(paragraphs) > 1:
        # Check if the first paragraph could be a complete command
        first_para = paragraphs[0].strip()
        # A command should include action verbs
        action_verbs = ['click', 'move', 'type', 'press', 'select', 'open', 'close']
        if any(verb in first_para.lower() for verb in action_verbs) and len(first_para.split()) >= 3:
            cleaned = first_para
    
    # Remove any trailing colon, period or comma
    cleaned = re.sub(r'[:.;,]+$', '', cleaned).strip()
    
    return cleaned

def test_with_sample_responses():
    """Test the cleaning function with sample LLM responses"""
    test_cases = [
        # Test case 1: Simple prefix removal
        {
            "original": "haz clic en actividades, then type firefox",
            "response": "Here is the translation of the given sequence of interactions with a PC:\n\nClick on activities, then type firefox",
            "expected": "Click on actividades, then type firefox"
        },
        # Test case 2: With explanatory note
        {
            "original": "mueve el ratón a opciones",
            "response": "Move the mouse to options\n\nNote: I've preserved the original command structure while translating it to English.",
            "expected": "Move the mouse to opciones"
        },
        # Test case 3: With code block
        {
            "original": "abre la aplicación configuración",
            "response": "```\nOpen the settings application\n```",
            "expected": "Open the configuración application"
        },
        # Test case 4: With multiple paragraphs
        {
            "original": "haz clic en actividades, luego escribe firefox y presiona enter",
            "response": "Click on activities, then type Firefox and press Enter.\n\nThis translation preserves the proper noun 'Firefox' while translating the command from Spanish to English.",
            "expected": "Click on actividades, then type Firefox and press Enter"
        },
        # Test case 5: Minimal response
        {
            "original": "clic en el botón Archivo",
            "response": "Click on the File button",
            "expected": "Click on the Archivo button"
        },
        # Test case 6: Another actividades case
        {
            "original": "mueve el ratón a actividades",
            "response": "Move the mouse to activities",
            "expected": "Move the mouse to actividades"
        }
    ]
    
    print("\nTesting with sample responses:")
    print("="*70)
    
    passed = 0
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest case {i}:")
        print(f"Original text: '{test['original']}'")
        print(f"LLM response: '{test['response']}'")
        
        # Clean the response
        cleaned = clean_llm_response(test['response'], test['original'])
        print(f"Cleaned text: '{cleaned}'")
        
        # Post-process to fix specific terms
        # This is the additional step from our enhanced translation function
        specific_terms = [
            {"spanish": "actividades", "english": "activities"},
            {"spanish": "archivo", "english": "file"},
            {"spanish": "configuración", "english": "settings"},
            {"spanish": "opciones", "english": "options"}
        ]
        
        for term in specific_terms:
            if term["spanish"] in test["original"].lower() and term["english"] in cleaned.lower():
                pattern = re.compile(re.escape(term["english"]), re.IGNORECASE)
                cleaned = pattern.sub(term["spanish"], cleaned)
        
        print(f"Final text: '{cleaned}'")
        print(f"Expected: '{test['expected']}'")
        
        # Check if the result matches the expected output
        if cleaned.lower() == test['expected'].lower():
            print("✅ PASSED")
            passed += 1
        else:
            print("❌ FAILED")
        
        print("-"*70)
    
    print(f"\nResults: {passed}/{len(test_cases)} tests passed")
    return passed, len(test_cases)

def test_with_ollama(text, model="llama3.1"):
    """Test the actual Ollama translation with a real query"""
    try:
        import requests
        
        print("\nTesting with Ollama:")
        print("="*70)
        print(f"Text to translate: '{text}'")
        
        # Common Spanish desktop UI terms that should never be translated
        desktop_terms = ["actividades", "Actividades", "aplicaciones", "Aplicaciones", 
                        "escritorio", "Escritorio", "configuración", "Configuración",
                        "archivo", "Archivo", "editar", "Editar", "ver", "Ver",
                        "ventana", "Ventana", "ayuda", "Ayuda", "herramientas", "Herramientas"]
        
        # Pre-process to identify exact words to preserve
        specific_preserve_terms = []
        
        # Extract quoted strings - these should never be translated
        quoted_strings = re.findall(r'"([^"]+)"|\'([^\']+)\'', text)
        for quoted_match in quoted_strings:
            for group in quoted_match:
                if group:  # Non-empty group
                    specific_preserve_terms.append(group)
        
        # Look for desktop terms to preserve
        for term in desktop_terms:
            if term in text:
                specific_preserve_terms.append(term)
                
        # Look for potential app names and UI elements (capital first letter words)
        potential_app_names = re.findall(r'\b([A-Z][a-zA-Z0-9]+)\b', text)
        specific_preserve_terms.extend(potential_app_names)
        
        # Prepare the prompt for translation
        preserve_examples = "\n".join([f"- \"{term}\" must remain as \"{term}\"" for term in specific_preserve_terms[:5]])
        if not preserve_examples and specific_preserve_terms:
            preserve_examples = f"- \"{specific_preserve_terms[0]}\" must remain as \"{specific_preserve_terms[0]}\""
        
        prompt = f"""
        Translate the following sequence of interactions with a PC to English.
        
        CRITICAL: DO NOT translate any of the following:
        1. Proper nouns, UI element names, button labels, or technical terms
        2. Menu items, tabs, or buttons (like "Actividades", "Archivo", "Configuración")
        3. Application names (like "Firefox", "Chrome", "Terminal")
        4. Text inside quotes (e.g., "Hola mundo")
        5. Any word that might be a desktop element or application name
        
        ESPECIALLY PRESERVE THESE EXACT TERMS (DO NOT TRANSLATE THEM):
        {preserve_examples}
        {'- ALL OTHER WORDS listed in quotes or UI element references' if specific_preserve_terms else ''}
        
        EXAMPLES of words to KEEP in original language:
        - "actividades" should stay as "actividades" (NEVER translate to "activities")
        - "opciones" should stay as "opciones" (NEVER translate to "options")
        - "archivo" should stay as "archivo" (NEVER translate to "file")
        - "nueva pestaña" should stay as "nueva pestaña" (NEVER translate to "new tab")
        
        Spanish → English examples with preserved text:
        - "haz clic en el botón Cancelar" → "click on the Cancelar button"
        - "escribe 'Hola mundo' en el campo Mensaje" → "type 'Hola mundo' in the Mensaje field"
        - "presiona enter en la ventana Configuración" → "press enter in the Configuración window"
        - "selecciona Archivo desde el menú" → "select Archivo from the menu"
        - "mueve el cursor a actividades" → "move the cursor to actividades"
        
        Now translate this text:
        ```
        {text}
        ```
        
        RETURN ONLY THE TRANSLATED TEXT - NOTHING ELSE. NO EXPLANATIONS. NO HEADERS. NO NOTES.
        """
        
        print(f"Terms to preserve: {specific_preserve_terms}")
        
        # Ensure Ollama is running
        try:
            ollama_host = "http://localhost:11434"
            response = requests.get(f"{ollama_host}/api/tags", timeout=2)
            if response.status_code != 200:
                print(f"❌ Ollama server not responding at {ollama_host}")
                return False
        except:
            print(f"❌ Ollama server not available at {ollama_host}")
            return False
        
        # Make API request to Ollama
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Error from Ollama API: {response.status_code}")
            return False
        
        # Parse response
        result = response.json()
        translated_text = result["response"].strip()
        
        print(f"Raw translation: '{translated_text}'")
        
        # Clean the response
        cleaned = clean_llm_response(translated_text, text)
        print(f"Cleaned text: '{cleaned}'")
        
        # Post-process to ensure preservation of specific terms
        for term in specific_preserve_terms:
            # Convert the term to lowercase for English equivalents
            term_lower = term.lower()
            english_equivalent = ""
            
            # Map common Spanish terms to their English equivalents
            if term_lower == "actividades": english_equivalent = "activities"
            elif term_lower == "archivo": english_equivalent = "file"
            elif term_lower == "configuración": english_equivalent = "settings"
            elif term_lower == "opciones": english_equivalent = "options"
            elif term_lower == "herramientas": english_equivalent = "tools"
            elif term_lower == "ayuda": english_equivalent = "help"
            elif term_lower == "editar": english_equivalent = "edit"
            elif term_lower == "ver": english_equivalent = "view"
            elif term_lower == "ventana": english_equivalent = "window"
            
            # If we know the English equivalent, replace it with the original term
            if english_equivalent and english_equivalent in cleaned.lower():
                # Find the correct case version of the English term
                pattern = re.compile(re.escape(english_equivalent), re.IGNORECASE)
                cleaned = pattern.sub(term, cleaned)
        
        print(f"Final text: '{cleaned}'")
        
        # Check for terms that should have been preserved
        for term in specific_preserve_terms:
            if term.lower() not in cleaned.lower() and term.lower() in text.lower():
                possible_translation = ""
                # Try to guess what it might have been translated to
                if term.lower() == "actividades": possible_translation = "activities"
                elif term.lower() == "archivo": possible_translation = "file"
                elif term.lower() == "configuración": possible_translation = "settings"
                
                if possible_translation and possible_translation in cleaned.lower():
                    print(f"❌ '{term}' was translated to '{possible_translation}' but should have been preserved")
                else:
                    print(f"❌ '{term}' may not have been preserved in the translation")
            else:
                print(f"✅ '{term}' was preserved correctly")
        
        return True
    except Exception as e:
        print(f"❌ Error testing with Ollama: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Test translation cleaning and preservation of UI element names"
    )
    
    parser.add_argument(
        "--sample-tests",
        action="store_true",
        help="Run tests with sample responses"
    )
    
    parser.add_argument(
        "--ollama-test",
        type=str,
        help="Test the Ollama translation with a custom query"
    )
    
    parser.add_argument(
        "--actividades-test",
        action="store_true",
        help="Test the critical 'actividades' case specifically"
    )
    
    return parser.parse_args()

def main():
    """Main entry point"""
    args = parse_args()
    
    print("Testing Translation Cleaning and UI Element Preservation")
    print("="*70)
    
    # Run sample tests
    if args.sample_tests or not (args.ollama_test or args.actividades_test):
        test_with_sample_responses()
    
    # Test with Ollama
    if args.ollama_test:
        test_with_ollama(args.ollama_test)
    
    # Test the critical 'actividades' case
    if args.actividades_test or not (args.sample_tests or args.ollama_test):
        print("\nSpecific test for the 'actividades' issue:")
        print("="*70)
        test_with_ollama("mueve el ratón a actividades, haz clic")
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    main() 