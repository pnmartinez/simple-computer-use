import os
import re
import logging
import ollama

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def extract_target_text_with_llm(query):
    """
    Use Ollama to extract target text from a user query.
    Returns the single most relevant target word/phrase for the current step.
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
- "Minimize the current opened app" → minimize
- "Click LOGIN then press Enter" → LOGIN
- "Type my password then hit Tab" → password

IMPORTANT: Your response must ONLY contain the single most important target word or phrase for this step. No commas, explanations, notes, quotes, formatting or additional text.
Keep the original letter case. Extract ONLY the most important UI element that needs to be found on screen.
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
        
        return [target_text] if target_text else []
    
    except Exception as e:
        logger.error(f"Error using Ollama for target text extraction: {str(e)}")
        print(f"❌ Error extracting target text: {str(e)}")
        # Fall back to empty list, which will trigger the old method
        return []
