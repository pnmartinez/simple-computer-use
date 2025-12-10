import re
import logging
import json
from llm_control.llm.intent_detection import extract_target_text_with_llm
from llm_control.ui_detection.element_finder import get_center_point
from llm_control import STRUCTURED_USAGE_LOGS_ENABLED

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def find_ui_element(query, ui_description):
    """Find the most likely UI element matching the query and return its screen coordinates"""
    try:
        print(f"element_query = {query}")
        
        # Structured logging: element search request
        if STRUCTURED_USAGE_LOGS_ENABLED:
            logger.info(json.dumps({
                "event": "ui_element_search_start",
                "query": query,
                "has_ui_description": ui_description is not None,
                "elements_count": len(ui_description.get('elements', [])) if ui_description else 0
            }))
        
        if not ui_description or 'elements' not in ui_description:
            logger.warning("No UI description or elements provided")
            if STRUCTURED_USAGE_LOGS_ENABLED:
                logger.info(json.dumps({
                    "event": "ui_element_search_failed",
                    "query": query,
                    "reason": "no_ui_description"
                }))
            return None
        
        elements = ui_description['elements']
        if not elements:
            logger.warning("Empty elements list in UI description")
            if STRUCTURED_USAGE_LOGS_ENABLED:
                logger.info(json.dumps({
                    "event": "ui_element_search_failed",
                    "query": query,
                    "reason": "empty_elements_list"
                }))
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
        
        # Helper function to check word boundary matches (defined once, used multiple times)
        def is_word_boundary_match(text, pattern):
            """Check if pattern matches at word boundaries in text, returns match type"""
            # Exact word match (highest priority)
            if re.search(rf'\b{re.escape(pattern)}\b', text, re.IGNORECASE):
                return 'exact_word'
            # Pattern at start of text
            if text.startswith(pattern):
                return 'starts_with'
            # Pattern at end of text
            if text.endswith(pattern):
                return 'ends_with'
            # Pattern within word (lowest priority, may be false positive)
            if pattern in text:
                return 'within_word'
            return None
        
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
                # Exact match with element text (case-insensitive)
                if elem_text == query:
                    score += 100
                    match_reason.append(f"Exact text match: '{elem_text}'")
                else:
                    # Check for partial text matches with improved logic
                    for fragment in potential_text_fragments:
                        fragment_lower = fragment.lower()
                        # Para frases multi-palabra (p.ej. "llm control" o "evolutionary troupe"),
                        # prueba también con cada palabra como palabra clave independiente.
                        fragments_to_try = [fragment_lower]
                        if " " in fragment_lower:
                            fragments_to_try.extend(
                                [w for w in fragment_lower.split() if len(w) > 2]
                            )

                        for frag in fragments_to_try:
                            # Check for word boundary matches
                            match_type = is_word_boundary_match(elem_text, frag)
                            
                            if match_type:
                                base_score = 0
                                match_desc = ""
                                
                                if match_type == 'exact_word':
                                    # Exact word match - highest score
                                    base_score = 90 if is_llm_extraction else 70
                                    match_desc = f"Exact word match: '{frag}'"
                                    
                                    # Bonus for plural/singular handling
                                    # Check if one is plural and other is singular
                                    fragment_words = frag.split()
                                    elem_words = elem_text.split()
                                    for fw in fragment_words:
                                        for ew in elem_words:
                                            # Simple plural/singular check
                                            if fw == ew[:-1] or ew == fw[:-1]:  # One ends with 's'
                                                if len(fw) > 3 and len(ew) > 3:  # Only for words longer than 3 chars
                                                    base_score += 5
                                                    match_desc += " (plural/singular match)"
                                                    break
                                    
                                elif match_type == 'starts_with':
                                    # Starts with pattern - good match
                                    base_score = 75 if is_llm_extraction else 60
                                    match_desc = f"Starts with: '{frag}'"
                                    
                                elif match_type == 'ends_with':
                                    # Ends with pattern - moderate match
                                    base_score = 65 if is_llm_extraction else 50
                                    match_desc = f"Ends with: '{frag}'"
                                    
                                elif match_type == 'within_word':
                                    # Within word - potential false positive, penalize
                                    # Only accept if the word is not too long (to avoid "plan" in "explanation")
                                    word_length = len(elem_text)
                                    fragment_length = len(frag)
                                    
                                    # Penalize if fragment is short and word is long (likely false positive)
                                    if fragment_length < 5 and word_length > fragment_length * 2:
                                        # Significant penalty for short fragments in long words
                                        base_score = 20 if is_llm_extraction else 15
                                        match_desc = f"Fragment within long word: '{frag}' (low confidence)"
                                    else:
                                        # Moderate score for reasonable matches
                                        base_score = 40 if is_llm_extraction else 30
                                        match_desc = f"Contains fragment: '{frag}'"
                                
                                if base_score > 0:
                                    score += base_score
                                    if is_llm_extraction:
                                        match_desc = f"LLM-extracted {match_desc}"
                                    match_reason.append(match_desc)
                                    break
            
            # 2. Check element description (from Phi-3 Vision) if available
            if elem_desc and not elem_text:  # Prioritize description for elements without text
                for fragment in potential_text_fragments:
                    fragment_lower = fragment.lower()
                    
                    # Use same word boundary matching logic
                    match_type = is_word_boundary_match(elem_desc, fragment_lower)
                    
                    if match_type:
                        base_score = 0
                        match_desc = ""
                        
                        if match_type == 'exact_word':
                            base_score = 60 if is_llm_extraction else 45
                            match_desc = f"Description exact word: '{fragment}'"
                        elif match_type == 'starts_with':
                            base_score = 50 if is_llm_extraction else 35
                            match_desc = f"Description starts with: '{fragment}'"
                        elif match_type == 'ends_with':
                            base_score = 40 if is_llm_extraction else 30
                            match_desc = f"Description ends with: '{fragment}'"
                        elif match_type == 'within_word':
                            # Penalize matches within words in descriptions too
                            word_length = len(elem_desc)
                            fragment_length = len(fragment_lower)
                            if fragment_length < 5 and word_length > fragment_length * 2:
                                base_score = 15 if is_llm_extraction else 10
                                match_desc = f"Description contains fragment (low confidence): '{fragment}'"
                            else:
                                base_score = 30 if is_llm_extraction else 20
                                match_desc = f"Description contains: '{fragment}'"
                        
                        if base_score > 0:
                            score += base_score
                            if is_llm_extraction:
                                match_desc = f"LLM-extracted {match_desc}"
                            match_reason.append(match_desc)
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
        # Increased threshold and added validation for close matches
        MIN_THRESHOLD = 25  # Increased from 20 to reduce false positives
        SCORE_DIFFERENCE_THRESHOLD = 10  # Minimum difference between 1st and 2nd match
        
        if matches and matches[0]['score'] > MIN_THRESHOLD:
            best_match = matches[0]['element']
            best_match_info = matches[0]
            best_score = matches[0]['score']
            
            # Additional validation: if there are multiple close matches, be more cautious
            if len(matches) > 1:
                second_score = matches[1]['score']
                score_difference = best_score - second_score
                
                # If scores are very close, prefer exact word matches or higher confidence
                if score_difference < SCORE_DIFFERENCE_THRESHOLD:
                    # Check if best match has "within_word" type (potential false positive)
                    best_reasons = best_match_info.get('reasons', [])
                    second_reasons = matches[1].get('reasons', [])
                    
                    best_has_within_word = any('within_word' in reason.lower() or 'within long word' in reason.lower() 
                                               for reason in best_reasons)
                    second_has_exact = any('exact word' in reason.lower() or 'exact text match' in reason.lower() 
                                          for reason in second_reasons)
                    
                    # If best match is "within_word" and second has exact match, prefer second
                    if best_has_within_word and second_has_exact:
                        logger.warning(f"Close scores detected ({best_score:.1f} vs {second_score:.1f}), "
                                     f"preferring exact match over within-word match")
                        best_match = matches[1]['element']
                        best_match_info = matches[1]
                        best_score = second_score
            
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
            
            # Structured logging: successful match
            if STRUCTURED_USAGE_LOGS_ENABLED:
                top_matches = []
                for i, match in enumerate(matches[:3]):  # Top 3 matches
                    top_matches.append({
                        "rank": i + 1,
                        "score": round(match['score'], 2),
                        "type": match['element'].get('type', 'unknown'),
                        "text": match['element'].get('text', ''),
                        "reasons": match['reasons']
                    })
                
                logger.info(json.dumps({
                    "event": "ui_element_search_success",
                    "query": query,
                    "selected_match": {
                        "type": best_match.get('type', 'unknown'),
                        "text": best_match.get('text', ''),
                        "coordinates": {"x": int(center[0]), "y": int(center[1])},
                        "score": round(best_match_info['score'], 2),
                        "reasons": best_match_info['reasons']
                    },
                    "top_matches": top_matches,
                    "total_matches": len(matches)
                }))
            
            return {
                'x': int(center[0]),
                'y': int(center[1]),
                'element': best_match,
                'element_type': best_match.get('type', 'unknown'),
                'element_text': best_match.get('text', ''),
                'element_display': best_match.get('text', best_match.get('description', '')),
                'match_info': best_match_info
            }
        
        # Structured logging: no match found
        if STRUCTURED_USAGE_LOGS_ENABLED:
            logger.info(json.dumps({
                "event": "ui_element_search_no_match",
                "query": query,
                "elements_analyzed": len(elements),
                "matches_found": len(matches),
                "top_match_score": round(matches[0]['score'], 2) if matches else 0,
                "threshold": 25  # MIN_THRESHOLD value
            }))
        
        return None
    except Exception as e:
        logger.error(f"Error in find_ui_element: {str(e)}")
        print(f"❌ Error finding UI element: {str(e)}")
        
        # Structured logging: error
        if STRUCTURED_USAGE_LOGS_ENABLED:
            logger.info(json.dumps({
                "event": "ui_element_search_error",
                "query": query,
                "error": str(e)
            }))
        
        return None 