import os
import re
import logging
import ollama

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def extract_text_to_type_with_llm(query):
    """
    Use Ollama to extract text that should be typed from a user query.
    Returns the text to type as a string.
    """
    logger.info(f"Using LLM to extract text to type from: '{query}'")
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.1:latest')
    
    # Create a prompt that asks the LLM to extract the text to type
    system_prompt = """Your task is to analyze a UI interaction query and extract ONLY the text that should be typed.

For example:
- "Type 'Hello world' in the search field" → Hello world
- "Click on the textbox and enter admin@example.com" → admin@example.com
- "Type password123 and press Enter" → password123
- "Write 'This is a test message' in the composer" → This is a test message
- "Enter John Doe in the name field" → John Doe
- "Click the search box and type python tutorial" → python tutorial
- "Type 'C:\\Users\\Documents\\file.txt'" → C:\\Users\\Documents\\file.txt

IMPORTANT: Your response must ONLY contain the exact text that should be typed. No explanations, notes, formatting or additional text.
Keep the exact case, punctuation, and special characters as specified in the query.
Preserve any escape sequences like \\n, \\t, or \\\\ that might be in the text.
If the text to type is in quotes, extract only what's inside the quotes.
If the text to type is not in quotes, infer what text should be typed based on context.
If there's no text to type, respond with the single word: NONE"""
    
    user_prompt = f"Extract the text that should be typed from this query: {query}"
    
    try:
        print(f"📝 Extracting text to type using LLM...")
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
    
    # Map special key names that might be in the text to their properly escaped versions
    special_keys = {
        '{': '{{',  # PyAutoGUI uses { } for special keys
        '}': '}}',
    }
    
    # Replace any special keys
    for key, replacement in special_keys.items():
        text = text.replace(key, replacement)
        
    return text
