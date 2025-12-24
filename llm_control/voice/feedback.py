"""
Utilities for generating screen-change summaries after command execution.
"""

import logging
from collections import Counter
from typing import Iterable, List, Set

from llm_control.ui_detection.ocr import detect_text_regions
from llm_control.ui_detection.element_finder import detect_ui_elements_with_yolo

logger = logging.getLogger("voice-control-feedback")


def _normalize_text(text: str) -> str:
    return " ".join(text.strip().split()).lower()


def _extract_texts(image_path: str) -> Set[str]:
    texts: Set[str] = set()
    try:
        for region in detect_text_regions(image_path):
            text = region.get("text", "")
            if text:
                normalized = _normalize_text(text)
                if normalized:
                    texts.add(normalized)
    except Exception as exc:
        logger.warning(f"Failed to extract OCR text from {image_path}: {exc}")
    return texts


def _extract_element_types(image_path: str) -> Counter:
    counts: Counter = Counter()
    try:
        for element in detect_ui_elements_with_yolo(image_path):
            element_type = element.get("type")
            if element_type:
                counts[element_type] += 1
    except Exception as exc:
        logger.warning(f"Failed to detect UI elements from {image_path}: {exc}")
    return counts


def _truncate_items(items: Iterable[str], limit: int = 5, max_len: int = 40) -> List[str]:
    trimmed: List[str] = []
    for item in items:
        if len(trimmed) >= limit:
            break
        trimmed.append(item[:max_len] + ("…" if len(item) > max_len else ""))
    return trimmed


def summarize_screen_delta(before: str, after: str, command: str, success: bool) -> str:
    """
    Build a concise summary describing what changed between two screenshots.

    Args:
        before: Path to the screenshot captured before execution.
        after: Path to the screenshot captured after execution.
        command: Original command text.
        success: Whether the command execution succeeded.

    Returns:
        A short, user-facing summary string.
    """
    status_phrase = "parece haber surtido efecto" if success else "no parece haber surtido efecto"

    if not before or not after:
        return f"Comando '{command}' {status_phrase}, sin capturas disponibles para comparar."

    before_texts = _extract_texts(before)
    after_texts = _extract_texts(after)
    added_texts = sorted(after_texts - before_texts)
    removed_texts = sorted(before_texts - after_texts)

    before_elements = _extract_element_types(before)
    after_elements = _extract_element_types(after)

    total_before = sum(before_elements.values())
    total_after = sum(after_elements.values())

    change_parts: List[str] = []
    if added_texts:
        change_parts.append(f"Texto nuevo: {', '.join(_truncate_items(added_texts))}")
    if removed_texts:
        change_parts.append(f"Texto removido: {', '.join(_truncate_items(removed_texts))}")

    if total_before != total_after:
        change_parts.append(f"Elementos UI: {total_before} → {total_after}")

    type_deltas = []
    for element_type in sorted(set(before_elements) | set(after_elements)):
        delta = after_elements.get(element_type, 0) - before_elements.get(element_type, 0)
        if delta:
            sign = "+" if delta > 0 else ""
            type_deltas.append(f"{sign}{delta} {element_type}")

    if type_deltas:
        change_parts.append(f"Cambios por tipo: {', '.join(type_deltas[:4])}")

    if not change_parts:
        change_parts.append("No se detectaron cambios visibles.")

    return f"Comando '{command}' {status_phrase}. " + " ".join(change_parts)
