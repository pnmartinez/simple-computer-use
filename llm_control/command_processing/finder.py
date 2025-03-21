import re
import logging
from llm_control.llm.intent_detection import extract_target_text_with_llm
from llm_control.ui_detection.element_finder import get_center_point

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def find_ui_element(query, ui_description):
    """Find the most likely UI element matching the query and return its screen coordinates"""
    try:
        print(f"element_query = {query}")
        if not ui_description or 'elements' not in ui_description:
            logger.warning("No UI description or elements provided")
            return None
        
        elements = ui_description['elements']
        if not elements:
            logger.warning("Empty elements list in UI description")
            return None
            
        query = query.lower()
        matches = []
        
        # Parse query to identify potential position keywords
        position_keywords = {
            'top': {'priority': 'y', 'compare': min, 'filter': lambda e, all_e: e['bbox'][1] < sum(x['bbox'][1] for x in all_e) / len(all_e)},
            'bottom': {'priority': 'y', 'compare': max, 'filter': lambda e, all_e: e['bbox'][1] > sum(x['bbox'][1] for x in all_e) / len(all_e)},
            'left': {'priority': 'x', 'compare': min, 'filter': lambda e, all_e: e['bbox'][0] < sum(x['bbox'][0] for x in all_e) / len(all_e)},
            'right': {'priority': 'x', 'compare': max, 'filter': lambda e, all_e: e['bbox'][0] > sum(x['bbox'][0] for x in all_e) / len(all_e)},
            'center': {'priority': None, 'filter': lambda e, all_e: True},  # Special case handled separately
        }
        
        # Check for position keywords in query
        active_position_filters = []
        for keyword, config in position_keywords.items():
            if keyword in query:
                active_position_filters.append(config['filter'])
                print(f"Detected position keyword: {keyword}")
                logger.debug(f"Detected position keyword: {keyword}")
        
        # Common element types and their synonyms
        element_type_keywords = {
            'button': ['button', 'btn', 'submit', 'ok', 'cancel', 'send', 'add', 'save', 'continue'],
            'input_field': ['input', 'field', 'textbox', 'text field', 'text box', 'textarea', 'edit', 'entry'],
            'menu_item': ['menu', 'option', 'dropdown', 'list item'],
            'checkbox': ['checkbox', 'check', 'tick'],
            'link': ['link', 'hyperlink', 'url', 'href'],
            'icon': ['icon', 'image', 'symbol', 'glyph'],
            'tab': ['tab', 'page'],
        }
        
        # Extract key phrases from the query using LLM
        potential_text_fragments = extract_target_text_with_llm(query)
        
        # If the LLM extraction failed or returned nothing, fall back to the old method
        if not potential_text_fragments:
            logger.debug("Using fallback text extraction method")
            print("📋 Using traditional text extraction method")
            
            # Extract text in quotes as exact matches (highest priority)
            quoted_text = re.findall(r'"([^"]+)"', query)
            if quoted_text:
                # Quoted text is most important, so it gets preferential treatment
                # Use only the first quoted text for single-word focus
                potential_text_fragments = [quoted_text[0]]
                logger.debug(f"Found quoted text: {quoted_text[0]}")
                print(f"🔍 Found quoted text: {quoted_text[0]}")
            else:
                # Try to extract actionable nouns and verbs (excluding common verbs)
                common_verbs = ['click', 'type', 'press', 'move', 'drag', 'scroll', 'find', 'locate', 'go', 'select']
                common_prepositions = ['to', 'on', 'at', 'in', 'by', 'for', 'with', 'from', 'about', 'the', 'and', 'then']
                query_words = query.split()
                
                # Filter out common words that are unlikely to be part of element text
                filtered_words = [word for word in query_words 
                                if word not in common_verbs
                                and word not in common_prepositions
                                and len(word) > 1]  # Skip single-character words
                
                # Add individual words if they pass our filters - only the most likely one
                if filtered_words:
                    # Simply take the first filtered word as the target
                    potential_text_fragments = [filtered_words[0]]
                    logger.debug(f"Extracted main word: {filtered_words[0]}")
                    print(f"🔍 Extracted main word: {filtered_words[0]}")
                else:
                    # If no words passed our filters, use just the first non-common word as last resort
                    for word in query_words:
                        if len(word) > 1 and word not in common_prepositions:
                            potential_text_fragments = [word]
                            print(f"🔍 Using fallback word: {word}")
                            break
        else:
            print("🧠 Using LLM-extracted target text")
        
        logger.debug(f"Analyzing {len(elements)} elements for match with query: '{query}'")
        logger.debug(f"Potential text fragments: {potential_text_fragments}")
        
        # Score each element
        for elem in elements:
            score = 0
            match_reason = []
            
            # Get element properties
            elem_text = elem.get('text', '').lower()
            elem_desc = elem.get('description', '').lower()
            elem_type = elem.get('type', 'unknown').lower()
            
            # Check if we used LLM-based extraction - simpler check based on potential_text_fragments 
            is_llm_extraction = len(potential_text_fragments) > 0 and not (len(potential_text_fragments) > 10)
            
            # 1. Check for text matches (highest priority)
            if elem_text:
                # Exact match with element text
                if elem_text == query:
                    score += 100
                    match_reason.append(f"Exact text match: '{elem_text}'")
                else:
                    # Check for partial text matches
                    for fragment in potential_text_fragments:
                        fragment_lower = fragment.lower()
                        if fragment_lower in elem_text:
                            # Give higher score to LLM-extracted text matches
                            if is_llm_extraction:
                                score += 80  # Higher score for LLM-extracted text
                                match_reason.append(f"LLM-extracted text match: '{fragment}'")
                            else:
                                score += 50
                                match_reason.append(f"Text contains fragment: '{fragment}'")
                            break
            
            # 2. Check element description (from Phi-3 Vision) if available
            if elem_desc and not elem_text:  # Prioritize description for elements without text
                for fragment in potential_text_fragments:
                    fragment_lower = fragment.lower()
                    if fragment_lower in elem_desc:
                        # Give higher score to LLM-extracted text matches
                        if is_llm_extraction:
                            score += 60  # Higher score for LLM-extracted text
                            match_reason.append(f"Description contains LLM-extracted: '{fragment}'")
                        else:
                            score += 40
                            match_reason.append(f"Description contains: '{fragment}'")
                        break
            
            # 3. Check element type
            for type_name, synonyms in element_type_keywords.items():
                if any(synonym in query for synonym in synonyms) and elem_type == type_name:
                    score += 30
                    match_reason.append(f"Element type '{elem_type}' matches query")
                    break
            
            # 4. Apply position filters
            if active_position_filters:
                position_score = 0
                position_match = True
                for filter_func in active_position_filters:
                    if not filter_func(elem, elements):
                        position_match = False
                        break
                
                if position_match:
                    position_score = 30  # Give stronger weight to position matching
                    match_reason.append("Position matches specified direction")
                else:
                    # If position doesn't match, significantly reduce the score
                    score *= 0.3  # Reduce score for elements not matching position
                
                score += position_score
            
            # 5. Small bonus for buttons (as they're common click targets)
            if elem_type == 'button':
                score += 5
                match_reason.append("Button type bonus")
            
            # 6. Boost score for higher confidence elements
            confidence = elem.get('confidence', 0)
            score = score * (0.7 + confidence * 0.3)  # Scale from 0.7-1.0 based on confidence
            
            if score > 0:
                matches.append({
                    'element': elem,
                    'score': score,
                    'reasons': match_reason
                })
        
        # Sort matches by score (highest first)
        matches.sort(key=lambda x: x['score'], reverse=True)
        
        # Log match information for debugging
        if matches:
            logger.debug(f"Found {len(matches)} potential matches")
            for i, match in enumerate(matches[:3]):  # Log top 3 matches
                elem = match['element']
                logger.debug(f"Match #{i+1}: Score {match['score']:.1f} - " + 
                           f"Type: {elem.get('type', 'unknown')}, " +
                           f"Text: '{elem.get('text', '')}', " + 
                           f"Reasons: {', '.join(match['reasons'])}")
        else:
            logger.warning(f"No matches found for query: '{query}'")
            # Log some examples of what was available
            sample_elements = elements[:5] if len(elements) > 5 else elements
            logger.debug("Sample of available elements:")
            for i, elem in enumerate(sample_elements):
                logger.debug(f"Element #{i+1}: Type: {elem.get('type', 'unknown')}, " +
                           f"Text: '{elem.get('text', '')}'")
        
        # Return the best match if score exceeds threshold
        if matches and matches[0]['score'] > 20:  # Minimum threshold to consider it a valid match
            best_match = matches[0]['element']
            best_match_info = matches[0]
            bbox = best_match['bbox']
            center = get_center_point(bbox)
            
            # Improved logging
            match_log = f"Selected best match: {best_match.get('type', 'unknown')} - '{best_match.get('text', '')}'"
            logger.info(match_log)
            print(f"🎯 {match_log}")
            
            # Print detailed match reasons
            print(f"   Score: {best_match_info['score']:.1f}")
            print(f"   Match reasons: {', '.join(best_match_info['reasons'])}")
            
            # Print next best match if available
            if len(matches) > 1:
                second_match = matches[1]['element']
                print(f"   Next best match: {second_match.get('type', 'unknown')} - '{second_match.get('text', '')}' (Score: {matches[1]['score']:.1f})")
            
            return {
                'x': int(center[0]),
                'y': int(center[1]),
                'element': best_match,
                'element_type': best_match.get('type', 'unknown'),
                'element_text': best_match.get('text', ''),
                'element_display': best_match.get('text', best_match.get('description', '')),
                'match_info': best_match_info
            }
        
        return None
    except Exception as e:
        logger.error(f"Error in find_ui_element: {str(e)}")
        print(f"❌ Error finding UI element: {str(e)}")
        return None 