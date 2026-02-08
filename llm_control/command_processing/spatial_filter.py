"""
Spatial filtering module for UI element selection based on grid zones.

This module provides functions to extract spatial specifications from commands
and filter UI elements based on their position in a 3x3 grid, matching the
same grid system used in feedback generation.
"""

import re
import logging
from typing import List, Tuple, Dict, Optional

logger = logging.getLogger("llm-pc-control")

# Mapping of spatial keywords to canonical terms
SPATIAL_KEYWORDS = {
    # Spanish
    'arriba': 'arriba',
    'abajo': 'abajo',
    'izquierda': 'izquierda',
    'derecha': 'derecha',
    'centro': 'centro',
    'superior': 'arriba',
    'inferior': 'abajo',
    # English
    'top': 'arriba',
    'bottom': 'abajo',
    'left': 'izquierda',
    'right': 'derecha',
    'center': 'centro',
    'middle': 'centro',
}

# Grid zone definitions (row, col)
GRID_ZONES = {
    'arriba-izquierda': (0, 0),
    'arriba-centro': (0, 1),
    'arriba-derecha': (0, 2),
    'centro-izquierda': (1, 0),
    'centro-centro': (1, 1),
    'centro-derecha': (1, 2),
    'abajo-izquierda': (2, 0),
    'abajo-centro': (2, 1),
    'abajo-derecha': (2, 2),
}


def extract_spatial_specs(command: str) -> List[str]:
    """
    Extract spatial specifications from a command string.
    
    Args:
        command: The command string to analyze
        
    Returns:
        List of canonical spatial specifications found (e.g., ['arriba'], ['arriba', 'izquierda'])
    """
    if not command:
        return []
    
    command_lower = command.lower()
    found_specs = []
    
    # Check for each spatial keyword
    for keyword, canonical in SPATIAL_KEYWORDS.items():
        # Use word boundaries to avoid matching within words
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, command_lower):
            if canonical not in found_specs:
                found_specs.append(canonical)
    
    return found_specs


def normalize_spatial_spec(specs: List[str]) -> Optional[str]:
    """
    Normalize a list of spatial specifications into a single canonical spec.
    
    Args:
        specs: List of spatial specifications (e.g., ['arriba', 'izquierda'])
        
    Returns:
        Canonical spec string (e.g., 'arriba-izquierda') or None if invalid
    """
    if not specs:
        return None
    
    # Remove duplicates while preserving order
    unique_specs = []
    for spec in specs:
        if spec not in unique_specs:
            unique_specs.append(spec)
    
    # Single spec cases
    if len(unique_specs) == 1:
        spec = unique_specs[0]
        # For single specs like "arriba", "derecha", etc., return as-is
        # The filtering logic will handle expanding to multiple zones
        return spec
    
    # Two specs: combine them
    if len(unique_specs) == 2:
        # Order: row first, then column
        row_specs = ['arriba', 'centro', 'abajo']
        col_specs = ['izquierda', 'centro', 'derecha']
        
        row_spec = None
        col_spec = None
        
        has_centro = 'centro' in unique_specs

        for spec in unique_specs:
            if spec == 'centro':
                continue
            if spec in row_specs:
                row_spec = spec
            elif spec in col_specs:
                col_spec = spec

        if has_centro:
            if row_spec is None and col_spec is not None:
                row_spec = 'centro'
            elif col_spec is None and row_spec is not None:
                col_spec = 'centro'
            elif row_spec is None and col_spec is None:
                row_spec = 'centro'
        
        if row_spec and col_spec:
            return f"{row_spec}-{col_spec}"
        elif row_spec:
            return row_spec
        elif col_spec:
            return col_spec
    
    # More than 2 specs: invalid, return None
    return None


def get_grid_zones_for_spec(spec: str, screen_size: Tuple[int, int]) -> List[Tuple[int, int, int, int]]:
    """
    Get the bounding boxes for grid zones matching a spatial specification.
    
    Args:
        spec: Spatial specification (e.g., 'arriba', 'derecha', 'arriba-izquierda')
        screen_size: Tuple of (width, height) of the screen
        
    Returns:
        List of bounding boxes (left, top, right, bottom) for matching zones
    """
    if not spec or not screen_size:
        return []
    
    width, height = screen_size
    if width <= 0 or height <= 0:
        return []
    
    # Calculate grid boundaries (same as in _click_zone_description)
    third_width = width / 3
    third_height = height / 3
    
    zones = []
    
    # Handle combined specs (e.g., "arriba-izquierda")
    if '-' in spec:
        parts = spec.split('-')
        if len(parts) == 2:
            row_spec, col_spec = parts
            zone_key = f"{row_spec}-{col_spec}"
            if zone_key in GRID_ZONES:
                row, col = GRID_ZONES[zone_key]
                left = int(col * third_width)
                top = int(row * third_height)
                right = int((col + 1) * third_width) if col < 2 else width
                bottom = int((row + 1) * third_height) if row < 2 else height
                zones.append((left, top, right, bottom))
        return zones
    
    # Handle single row specs (e.g., "arriba" = all 3 cells in top row)
    if spec == 'arriba':
        for col in range(3):
            left = int(col * third_width)
            top = 0
            right = int((col + 1) * third_width) if col < 2 else width
            bottom = int(third_height)
            zones.append((left, top, right, bottom))
        return zones
    
    if spec == 'abajo':
        for col in range(3):
            left = int(col * third_width)
            top = int(2 * third_height)
            right = int((col + 1) * third_width) if col < 2 else width
            bottom = height
            zones.append((left, top, right, bottom))
        return zones
    
    # Handle single column specs (e.g., "derecha" = all 3 cells in right column)
    if spec == 'izquierda':
        for row in range(3):
            left = 0
            top = int(row * third_height)
            right = int(third_width)
            bottom = int((row + 1) * third_height) if row < 2 else height
            zones.append((left, top, right, bottom))
        return zones
    
    if spec == 'derecha':
        for row in range(3):
            left = int(2 * third_width)
            top = int(row * third_height)
            right = width
            bottom = int((row + 1) * third_height) if row < 2 else height
            zones.append((left, top, right, bottom))
        return zones
    
    # Handle center (single cell)
    if spec == 'centro':
        left = int(third_width)
        top = int(third_height)
        right = int(2 * third_width)
        bottom = int(2 * third_height)
        zones.append((left, top, right, bottom))
        return zones
    
    return zones


def is_point_in_zones(x: float, y: float, zones: List[Tuple[int, int, int, int]]) -> bool:
    """
    Check if a point is within any of the given zones.
    
    Args:
        x: X coordinate of the point
        y: Y coordinate of the point
        zones: List of bounding boxes (left, top, right, bottom)
        
    Returns:
        True if point is in any zone, False otherwise
    """
    for left, top, right, bottom in zones:
        if left <= x < right and top <= y < bottom:
            return True
    return False


def filter_elements_by_spatial_spec(
    elements: List[Dict],
    spec: str,
    screen_size: Tuple[int, int]
) -> List[Dict]:
    """
    Filter UI elements based on a spatial specification.
    
    Args:
        elements: List of UI element dictionaries with 'bbox' keys
        spec: Spatial specification (e.g., 'arriba', 'derecha', 'arriba-izquierda')
        screen_size: Tuple of (width, height) of the screen
        
    Returns:
        Filtered list of elements that are in the specified zones
    """
    if not spec or not elements or not screen_size:
        return elements
    
    # Get zones for the spec
    zones = get_grid_zones_for_spec(spec, screen_size)
    if not zones:
        # If no zones match, return all elements (fallback)
        return elements
    
    filtered = []
    for elem in elements:
        bbox = elem.get('bbox')
        if not bbox or len(bbox) != 4:
            # If element has no valid bbox, include it (fallback)
            filtered.append(elem)
            continue
        
        x1, y1, x2, y2 = bbox
        # Use center point of the element
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        
        if is_point_in_zones(center_x, center_y, zones):
            filtered.append(elem)
    
    return filtered


def remove_spatial_specs_from_command(command: str) -> str:
    """
    Remove spatial specifications from a command string to prevent them
    from being included in target extraction.
    
    This function is careful to preserve spatial keywords when they appear
    to be part of the target (e.g., in quotes or after "en"/"on" without
    another spatial spec before it).
    
    Args:
        command: The command string
        
    Returns:
        Command string with spatial keywords removed (but preserved when part of target)
    """
    if not command:
        return command
    
    # First, protect text in quotes
    protected_parts = []
    quote_pattern = r'(["\'])([^"\']*)\1'
    
    def protect_quoted(match):
        quote_char = match.group(1)
        content = match.group(2)
        placeholder = f"__QUOTED_{len(protected_parts)}__"
        protected_parts.append((placeholder, quote_char + content + quote_char))
        return placeholder
    
    # Replace quoted text with placeholders
    result = re.sub(quote_pattern, protect_quoted, command)
    
    # Find positions of spatial keywords in the command (case-insensitive)
    command_lower = result.lower()
    keyword_positions = []
    
    for keyword in SPATIAL_KEYWORDS.keys():
        pattern = r'\b' + re.escape(keyword) + r'\b'
        for match in re.finditer(pattern, command_lower):
            keyword_positions.append((match.start(), match.end(), keyword))
    
    # Sort by position
    keyword_positions.sort(key=lambda x: x[0])
    
    # Check which keywords should be preserved (part of target)
    preserved_ranges = set()  # Store (start, end) tuples to preserve
    
    for start, end, keyword in keyword_positions:
        # Check what comes before this keyword (don't strip to preserve spaces)
        before = command_lower[:start]
        
        # If keyword is after "en" or "on" and there's no other spatial spec before "en"/"on"
        # then it's likely part of the target
        # Look for "en" or "on" followed by optional whitespace
        en_on_pattern = r'\b(en|on)(?:\s+|$)'
        en_on_matches = list(re.finditer(en_on_pattern, before))
        
        if en_on_matches:
            # Get the last "en"/"on" before this keyword
            last_en_on = en_on_matches[-1]
            text_before_en_on = before[:last_en_on.start()].strip()
            text_after_en_on = command_lower[last_en_on.end():start].strip()
            
            # Check if there's a spatial spec before "en"/"on"
            has_spatial_before = any(
                re.search(r'\b' + re.escape(k) + r'\b', text_before_en_on, re.IGNORECASE)
                for k in SPATIAL_KEYWORDS.keys()
            )
            
            # If there's a spatial spec before "en"/"on", then anything after "en"/"on"
            # (including spatial keywords) is likely part of the target → preserve
            if has_spatial_before:
                preserved_ranges.add((start, end))
            # If there's NO spatial spec before "en"/"on", check if this keyword
            # appears immediately after "en"/"on" (no other words in between)
            # In that case, it's likely the target name → preserve
            elif not text_after_en_on or len(text_after_en_on.split()) == 0:
                preserved_ranges.add((start, end))
    
    # Build result by removing non-preserved keywords
    # Mark all character positions: True = keep, False = remove
    keep_chars = [True] * len(result)
    
    for start, end, keyword in keyword_positions:
        if (start, end) not in preserved_ranges:
            # Mark this range for removal
            for i in range(start, end):
                keep_chars[i] = False
    
    # Build new result keeping only marked characters
    new_result_parts = []
    i = 0
    while i < len(result):
        if keep_chars[i]:
            # Find the next range of characters to keep
            start = i
            while i < len(result) and keep_chars[i]:
                i += 1
            new_result_parts.append(result[start:i])
        else:
            i += 1
    
    result = ''.join(new_result_parts)
    
    # Restore protected quoted text
    for placeholder, original in protected_parts:
        result = result.replace(placeholder, original)
    
    # Clean up extra whitespace (but preserve spaces around quotes)
    result = re.sub(r'\s+', ' ', result).strip()
    
    return result
