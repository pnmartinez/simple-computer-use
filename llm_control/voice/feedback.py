"""
Utilities for generating TTS-friendly screen-change summaries after command execution.

Key improvements vs. naive OCR/YOLO set-diff:
- Visual change score (fast pixel diff) to modulate feedback and skip heavy analysis when appropriate.
- Region-of-change detection to focus OCR/YOLO on changed areas (reduces noise + latency).
- Fuzzy matching + anti-noise filters for OCR texts to reduce spurious deltas.
- TTS-friendly phrasing (no symbols like "→", natural lists, word-based truncation).
- Privacy redaction for commands and OCR (emails/tokens/phones/URLs/IBAN-like strings).
- Uncertainty reporting when OCR/YOLO fail or time out.
- Caching by (path, mtime, focus boxes) and concurrent execution with timeouts.
- Heuristics for change type (modal/scroll/navigation/localized) to produce actionable feedback.

Public API:
- summarize_screen_delta_v2(before, after, command, success, verbosity="short")

Note: This module depends on PIL (Pillow). OCR/YOLO functions are imported from your project.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from typing import List, Optional, Sequence, Tuple, Literal

from PIL import Image, ImageChops, ImageStat

from llm_control.ui_detection.ocr import detect_text_regions
from llm_control.ui_detection.element_finder import detect_ui_elements_with_yolo

logger = logging.getLogger("voice-control-feedback")

Verbosity = Literal["short", "long"]


# -----------------------------
# Privacy / redaction
# -----------------------------

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_URL_RE = re.compile(r"\bhttps?://\S+\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"\b(\+?\d[\d\s().-]{7,}\d)\b")
# Rough token-like strings: long alnum/base64-ish
_TOKEN_RE = re.compile(r"\b[A-Z0-9_\-]{16,}\b", re.IGNORECASE)
# Rough IBAN pattern
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b", re.IGNORECASE)


def _redact_pii(text: str) -> str:
    if not text:
        return text
    t = text
    t = _URL_RE.sub("[enlace]", t)
    t = _EMAIL_RE.sub("[correo]", t)
    t = _IBAN_RE.sub("[iban]", t)
    t = _PHONE_RE.sub("[teléfono]", t)
    t = _TOKEN_RE.sub("[token]", t)
    return t


def _command_for_voice(command: str) -> str:
    """
    Avoid speaking the raw command (may contain secrets). Try to infer an action verb.
    """
    if not command:
        return "He ejecutado la acción"

    cmd = command.strip().lower()
    cmd = _redact_pii(cmd)

    # Heuristics: customize to your command grammar.
    if any(k in cmd for k in ("haz clic", "click", "pincha", "pulsa el botón", "toca")):
        return "He hecho clic"
    if any(k in cmd for k in ("escribe", "teclea", "type", "introduce texto", "pega")):
        return "He escrito el texto"
    if any(k in cmd for k in ("enter", "intro", "return")):
        return "He pulsado Enter"
    if any(k in cmd for k in ("tab",)):
        return "He pulsado Tab"
    if any(k in cmd for k in ("escape", "esc")):
        return "He pulsado Escape"
    if any(k in cmd for k in ("sube", "baja", "scroll")):
        return "He hecho scroll"
    if any(k in cmd for k in ("arrastra", "drag")):
        return "He arrastrado el elemento"
    if any(k in cmd for k in ("abre", "open")):
        return "He intentado abrirlo"
    if any(k in cmd for k in ("cierra", "close")):
        return "He intentado cerrarlo"
    return "He ejecutado la acción"


def _action_phrase_from_steps(steps: Optional[Sequence[str]], command: str) -> str:
    if not steps:
        return _command_for_voice(command)

    steps_text = " ".join(step.lower() for step in steps)
    phrases = []

    if any(k in steps_text for k in ("clic", "click", "pincha", "toca", "pulsa el botón", "doble clic", "double click")):
        phrases.append("hecho clic")
    if any(k in steps_text for k in ("escribe", "teclea", "type", "introduce texto", "pega")):
        phrases.append("escrito el texto")
    if any(k in steps_text for k in ("enter", "intro")):
        phrases.append("pulsado Enter")
    if "tab" in steps_text:
        phrases.append("pulsado Tab")
    if any(k in steps_text for k in ("escape", "esc")):
        phrases.append("pulsado Escape")
    if any(k in steps_text for k in ("scroll", "sube", "baja", "desplaza")):
        phrases.append("hecho scroll")
    if any(k in steps_text for k in ("arrastra", "drag")):
        phrases.append("arrastrado el elemento")

    if not phrases:
        return _command_for_voice(command)

    return f"He {', '.join(phrases[:-1])} y {phrases[-1]}" if len(phrases) > 1 else f"He {phrases[0]}"


# -----------------------------
# Normalization + OCR filtering
# -----------------------------

def _normalize_text(text: str) -> str:
    # Normalize whitespace and lowercase; redact PII early.
    t = " ".join(text.strip().split()).lower()
    return _redact_pii(t)


# Common low-value OCR noise patterns
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")
_DATE_RE = re.compile(r"^\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?$")
_PERCENT_RE = re.compile(r"^\d{1,3}%$")
_NUMERIC_RE = re.compile(r"^\d+$")
_PAGINATION_RE = re.compile(r"^\d+\s*/\s*\d+$")


def _is_noise_text(t: str) -> bool:
    if not t:
        return True
    if len(t) <= 2:
        return True
    if _NUMERIC_RE.match(t):
        return True
    if _TIME_RE.match(t) or _DATE_RE.match(t):
        return True
    if _PERCENT_RE.match(t) or _PAGINATION_RE.match(t):
        return True
    return False


def _similarity(a: str, b: str) -> float:
    # Standard lib fuzzy ratio (0..1).
    return SequenceMatcher(None, a, b).ratio()


def _fuzzy_delta(
    before: Sequence[str],
    after: Sequence[str],
    threshold: float = 0.90,
) -> Tuple[List[str], List[str]]:
    """
    Return (added, removed) with fuzzy matching to reduce OCR jitter.
    Greedy match: each after tries to match one before.
    """
    before_list = list(before)
    after_list = list(after)

    matched_before = set()
    matched_after = set()

    # Precompute candidates (O(n^2) but usually small)
    for i, a in enumerate(after_list):
        best_j = None
        best_s = 0.0
        for j, b in enumerate(before_list):
            if j in matched_before:
                continue
            s = _similarity(a, b)
            if s > best_s:
                best_s = s
                best_j = j
        if best_j is not None and best_s >= threshold:
            matched_after.add(i)
            matched_before.add(best_j)

    added = [after_list[i] for i in range(len(after_list)) if i not in matched_after]
    removed = [before_list[j] for j in range(len(before_list)) if j not in matched_before]
    return added, removed


# -----------------------------
# TTS-friendly formatting
# -----------------------------

def _truncate_for_voice(s: str, max_words: int = 6, max_chars: int = 48) -> str:
    s = s.strip()
    if not s:
        return s
    # Prefer word truncation, but also cap chars.
    words = s.split()
    if len(words) > max_words:
        s = " ".join(words[:max_words]) + "…"
    if len(s) > max_chars:
        s = s[: max_chars - 1].rstrip() + "…"
    return s


def _natural_list(items: Sequence[str], limit: int = 3) -> str:
    items2 = [it for it in items if it]
    items2 = items2[:limit]
    if not items2:
        return ""
    if len(items2) == 1:
        return items2[0]
    if len(items2) == 2:
        return f"{items2[0]} y {items2[1]}"
    return f"{', '.join(items2[:-1])} y {items2[-1]}"


def _localize_element_type(t: str) -> str:
    # Extend based on your YOLO labels.
    mapping = {
        "button": "botón",
        "textbox": "campo de texto",
        "input": "campo de entrada",
        "icon": "icono",
        "menu": "menú",
        "dropdown": "desplegable",
        "checkbox": "casilla",
        "radiobutton": "opción",
        "dialog": "diálogo",
        "window": "ventana",
        "tab": "pestaña",
        "link": "enlace",
        "image": "imagen",
        "label": "etiqueta",
    }
    return mapping.get(t, t)


def _describe_count_delta(delta: int, element_type: str) -> str:
    et = _localize_element_type(element_type)
    if delta > 0:
        return f"aparecieron {delta} {et}{'' if delta == 1 else 's'}"
    return f"desaparecieron {abs(delta)} {et}{'' if abs(delta) == 1 else 's'}"


# -----------------------------
# Visual change detection
# -----------------------------

Box = Tuple[int, int, int, int]  # left, top, right, bottom


def _load_image_rgb(path: str, max_side: int = 900) -> Image.Image:
    img = Image.open(path).convert("RGB")
    # Downscale for speed in diff computations.
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)))
    return img


def _diff_score(before_img: Image.Image, after_img: Image.Image) -> float:
    # Mean absolute difference normalized [0..1]
    diff = ImageChops.difference(before_img, after_img)
    stat = ImageStat.Stat(diff)
    # stat.mean is per-channel 0..255
    mean = sum(stat.mean) / (len(stat.mean) * 255.0)
    return float(mean)


def _changed_boxes(before_img: Image.Image, after_img: Image.Image) -> List[Box]:
    """
    Compute coarse bounding boxes of changed regions.
    Returns boxes in the resized image coordinate system.
    """
    diff = ImageChops.difference(before_img, after_img).convert("L")
    # Simple threshold
    diff = diff.point(lambda p: 255 if p > 25 else 0)
    bbox = diff.getbbox()
    if not bbox:
        return []

    # Split into a few coarse boxes by scanning stripes (cheap approximation).
    w, h = diff.size
    boxes: List[Box] = []
    # Horizontal stripes
    stripe_h = max(24, h // 10)
    for y0 in range(0, h, stripe_h):
        y1 = min(h, y0 + stripe_h)
        stripe = diff.crop((0, y0, w, y1))
        b = stripe.getbbox()
        if b:
            # Expand bbox into full image coords
            l, t, r, btm = b
            boxes.append((l, y0 + t, r, y0 + btm))

    # Merge overlapping/nearby boxes
    boxes = _merge_boxes(boxes, pad=12)
    # Keep top-K largest boxes
    boxes.sort(key=_box_area, reverse=True)
    return boxes[:5]


def _box_area(b: Box) -> int:
    return max(0, b[2] - b[0]) * max(0, b[3] - b[1])


def _merge_boxes(boxes: List[Box], pad: int = 8) -> List[Box]:
    if not boxes:
        return []
    merged: List[Box] = []

    def expanded(b: Box) -> Box:
        l, t, r, bt = b
        return (l - pad, t - pad, r + pad, bt + pad)

    for b in boxes:
        b2 = expanded(b)
        placed = False
        for i, m in enumerate(merged):
            if _boxes_overlap(b2, m):
                merged[i] = (
                    min(m[0], b2[0]),
                    min(m[1], b2[1]),
                    max(m[2], b2[2]),
                    max(m[3], b2[3]),
                )
                placed = True
                break
        if not placed:
            merged.append(b2)

    # One extra pass for transitive merges
    changed = True
    while changed:
        changed = False
        out: List[Box] = []
        for b in merged:
            merged_into = False
            for j, m in enumerate(out):
                if _boxes_overlap(b, m):
                    out[j] = (
                        min(m[0], b[0]),
                        min(m[1], b[1]),
                        max(m[2], b[2]),
                        max(m[3], b[3]),
                    )
                    merged_into = True
                    changed = True
                    break
            if not merged_into:
                out.append(b)
        merged = out

    return merged


def _boxes_overlap(a: Box, b: Box) -> bool:
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


@dataclass
class VisualDelta:
    score: float  # 0..1
    boxes_resized: List[Box]
    resized_size: Tuple[int, int]
    original_size: Tuple[int, int]


def _compute_visual_delta(before_path: str, after_path: str) -> VisualDelta:
    before_img = _load_image_rgb(before_path)
    after_img = _load_image_rgb(after_path)
    # Ensure same size
    if before_img.size != after_img.size:
        after_img = after_img.resize(before_img.size)

    score = _diff_score(before_img, after_img)
    boxes = _changed_boxes(before_img, after_img)
    # For original size mapping we need original sizes too
    original_before = Image.open(before_path)
    return VisualDelta(
        score=score,
        boxes_resized=boxes,
        resized_size=before_img.size,
        original_size=original_before.size,
    )


def _map_box_to_original(vd: VisualDelta, b: Box) -> Box:
    rw, rh = vd.resized_size
    ow, oh = vd.original_size
    sx = ow / max(1, rw)
    sy = oh / max(1, rh)
    l, t, r, bt = b
    l2 = int(max(0, l * sx))
    t2 = int(max(0, t * sy))
    r2 = int(min(ow, r * sx))
    bt2 = int(min(oh, bt * sy))
    # Clamp
    return (max(0, l2), max(0, t2), max(0, r2), max(0, bt2))


def _changed_boxes_original(vd: VisualDelta) -> List[Box]:
    return [_map_box_to_original(vd, b) for b in vd.boxes_resized]


# -----------------------------
# OCR + YOLO extraction (with focus boxes)
# -----------------------------

@dataclass
class AnalysisResult:
    texts: List[str]
    element_counts: Counter
    ocr_ok: bool
    yolo_ok: bool


def _boxes_signature(boxes: Sequence[Box]) -> Tuple[Tuple[int, int, int, int], ...]:
    return tuple((int(l), int(t), int(r), int(b)) for (l, t, r, b) in boxes)


def _mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


@lru_cache(maxsize=128)
def _extract_texts_cached(
    image_path: str,
    mtime: float,
    boxes_sig: Tuple[Box, ...],
) -> Tuple[List[str], bool]:
    try:
        if not boxes_sig:
            regions = detect_text_regions(image_path)
            texts = []
            for region in regions:
                text = region.get("text", "")
                if text:
                    nt = _normalize_text(text)
                    if nt and not _is_noise_text(nt):
                        texts.append(nt)
            # Deduplicate while preserving order
            texts = list(dict.fromkeys(texts))
            return texts, True

        # Focus: crop and run OCR per box
        img = Image.open(image_path).convert("RGB")
        texts_all: List[str] = []
        for b in boxes_sig[:3]:
            crop = img.crop(b)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
                crop.save(tmp.name)
                for region in detect_text_regions(tmp.name):
                    text = region.get("text", "")
                    if text:
                        nt = _normalize_text(text)
                        if nt and not _is_noise_text(nt):
                            texts_all.append(nt)
        texts_all = list(dict.fromkeys(texts_all))
        return texts_all, True
    except Exception as exc:
        logger.warning(f"Failed to extract OCR text from {image_path}: {exc}")
        return [], False


@lru_cache(maxsize=128)
def _extract_element_types_cached(
    image_path: str,
    mtime: float,
    boxes_sig: Tuple[Box, ...],
) -> Tuple[Counter, bool]:
    counts: Counter = Counter()
    try:
        if not boxes_sig:
            for element in detect_ui_elements_with_yolo(image_path):
                et = element.get("type")
                if et:
                    counts[str(et)] += 1
            return counts, True

        # Focus: crop and run YOLO per box (trade-off: may miss context; good for delta cues)
        img = Image.open(image_path).convert("RGB")
        for b in boxes_sig[:3]:
            crop = img.crop(b)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
                crop.save(tmp.name)
                for element in detect_ui_elements_with_yolo(tmp.name):
                    et = element.get("type")
                    if et:
                        counts[str(et)] += 1
        return counts, True
    except Exception as exc:
        logger.warning(f"Failed to detect UI elements from {image_path}: {exc}")
        return Counter(), False


def _analyze_image(
    image_path: str,
    focus_boxes: Sequence[Box],
    run_yolo: bool,
    timeout_s: float,
) -> AnalysisResult:
    boxes_sig = _boxes_signature(focus_boxes)
    mt = _mtime(image_path)

    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_ocr = ex.submit(_extract_texts_cached, image_path, mt, boxes_sig)
        fut_yolo = ex.submit(_extract_element_types_cached, image_path, mt, boxes_sig) if run_yolo else None

        texts: List[str] = []
        element_counts: Counter = Counter()
        ocr_ok = True
        yolo_ok = True

        try:
            texts, ocr_ok = fut_ocr.result(timeout=timeout_s)
        except TimeoutError:
            logger.warning(f"OCR timed out for {image_path}")
            ocr_ok = False
        except Exception as exc:
            logger.warning(f"OCR failed for {image_path}: {exc}")
            ocr_ok = False

        if fut_yolo is not None:
            try:
                element_counts, yolo_ok = fut_yolo.result(timeout=timeout_s)
            except TimeoutError:
                logger.warning(f"YOLO timed out for {image_path}")
                yolo_ok = False
            except Exception as exc:
                logger.warning(f"YOLO failed for {image_path}: {exc}")
                yolo_ok = False
        else:
            element_counts = Counter()
            yolo_ok = True

    return AnalysisResult(texts=texts, element_counts=element_counts, ocr_ok=ocr_ok, yolo_ok=yolo_ok)


# -----------------------------
# Change-type heuristics
# -----------------------------

_MODAL_KEYWORDS = ("aceptar", "cancelar", "permitir", "denegar", "ok", "sí", "no", "guardar", "continuar")
_ERROR_KEYWORDS = ("error", "fallo", "incorrect", "inválid", "no se pudo", "denegad", "rechazad")


@dataclass
class ChangeHypothesis:
    kind: str  # "modal" | "scroll" | "navigation" | "localized" | "none"
    confidence: float
    highlights: List[str]


def _hypothesize_change(
    vd: VisualDelta,
    added_texts: Sequence[str],
    removed_texts: Sequence[str],
    type_deltas: Sequence[Tuple[str, int]],
    has_scroll_action: bool,
) -> ChangeHypothesis:
    score = vd.score
    boxes = _changed_boxes_original(vd)
    total_changed_area = 0
    ow, oh = vd.original_size
    for b in boxes:
        total_changed_area += _box_area(b)
    total_area = max(1, ow * oh)
    area_ratio = total_changed_area / total_area

    added_join = " ".join(added_texts[:10])
    modal_hits = [kw for kw in _MODAL_KEYWORDS if kw in added_join]
    error_hits = [kw for kw in _ERROR_KEYWORDS if kw in added_join]

    # None / very low change
    if score < 0.005 and area_ratio < 0.01:
        return ChangeHypothesis(kind="none", confidence=0.8, highlights=[])

    # Modal: moderate localized change + modal-like keywords
    if modal_hits and area_ratio < 0.35:
        hl = ["apareció un diálogo"]
        if error_hits:
            hl.append("con un posible mensaje de error")
        return ChangeHypothesis(kind="modal", confidence=0.75, highlights=hl)

    # Scroll: lots of texts churn + medium area ratio (often bands)
    if (len(added_texts) + len(removed_texts) >= 10) and area_ratio >= 0.15 and score >= 0.01:
        if has_scroll_action:
            return ChangeHypothesis(kind="scroll", confidence=0.65, highlights=["parece que se ha hecho scroll"])
        return ChangeHypothesis(
            kind="content_change",
            confidence=0.55,
            highlights=["hubo un cambio grande en la lista o el contenido"]
        )

    # Navigation: high global change
    if score >= 0.08 or area_ratio >= 0.55:
        return ChangeHypothesis(kind="navigation", confidence=0.6, highlights=["la pantalla cambió bastante"])

    # Localized change
    return ChangeHypothesis(kind="localized", confidence=0.6, highlights=["hubo un cambio localizado"])


# -----------------------------
# Summary builder
# -----------------------------

def summarize_screen_delta_v2(
    before: str,
    after: str,
    command: str,
    success: bool,
    steps: Optional[Sequence[str]] = None,
    verbosity: Verbosity = "short",
    timeout_s: float = 3.0,
) -> str:
    """
    Build a TTS-friendly summary describing what likely changed between two screenshots.

    Args:
        before: Path to screenshot captured before execution.
        after: Path to screenshot captured after execution.
        command: Original command text (will NOT be spoken literally; redacted).
        success: Whether the command execution succeeded.
        verbosity: "short" (default) or "long".
        timeout_s: Per-detector timeout.

    Returns:
        A short, user-facing summary string suitable for voice.
    """
    action_phrase = _action_phrase_from_steps(steps, command)

    if not before or not after:
        base = f"{action_phrase}. "
        if success:
            return base + "Se ejecutó, pero no tengo capturas para comparar."
        return base + "La acción reportó fallo y no tengo capturas para comparar."

    # Visual delta first (fast) to decide focus and wording
    try:
        vd = _compute_visual_delta(before, after)
    except Exception as exc:
        logger.warning(f"Visual delta failed: {exc}")
        vd = VisualDelta(score=0.0, boxes_resized=[], resized_size=(1, 1), original_size=(1, 1))

    focus_boxes = _changed_boxes_original(vd)
    # If change is tiny or boxes empty, avoid focusing (crop overhead may outweigh benefits)
    use_focus = bool(focus_boxes) and (vd.score >= 0.008)
    focus = focus_boxes if use_focus else []

    # Decide how much heavy lifting to do
    # - short mode: YOLO only if there's a meaningful visual change
    # - long mode: YOLO always (but with focus if available)
    run_yolo = (verbosity == "long") or (vd.score >= 0.02)

    before_res = _analyze_image(before, focus, run_yolo=run_yolo, timeout_s=timeout_s)
    after_res = _analyze_image(after, focus, run_yolo=run_yolo, timeout_s=timeout_s)

    # Fuzzy delta on OCR texts
    before_texts = before_res.texts
    after_texts = after_res.texts
    added_texts, removed_texts = _fuzzy_delta(before_texts, after_texts, threshold=0.90)

    # Prefer action-like new texts for highlights (buttons/CTAs)
    def actiony(t: str) -> bool:
        return any(k in t for k in _MODAL_KEYWORDS) or any(t.startswith(k) for k in ("guardar", "enviar", "continuar", "iniciar"))

    added_sorted = sorted(added_texts, key=lambda t: (not actiony(t), -len(t)))
    removed_sorted = sorted(removed_texts, key=len, reverse=True)

    added_voice = [_truncate_for_voice(t) for t in added_sorted if not _is_noise_text(t)]
    removed_voice = [_truncate_for_voice(t) for t in removed_sorted if not _is_noise_text(t)]

    # YOLO deltas
    type_deltas: List[Tuple[str, int]] = []
    if run_yolo and before_res.yolo_ok and after_res.yolo_ok:
        all_types = set(before_res.element_counts) | set(after_res.element_counts)
        for t in all_types:
            delta = after_res.element_counts.get(t, 0) - before_res.element_counts.get(t, 0)
            if delta:
                type_deltas.append((t, delta))
        type_deltas.sort(key=lambda x: abs(x[1]), reverse=True)

    # Hypothesize change type
    steps_text = " ".join(step.lower() for step in (steps or []))
    has_scroll_action = any(k in steps_text for k in ("scroll", "sube", "baja", "desplaza"))
    hypothesis = _hypothesize_change(vd, added_sorted, removed_sorted, type_deltas, has_scroll_action)

    # Compose status with evidence
    # Combine reported success + visual score to avoid contradictions
    if success and vd.score < 0.005:
        status = "Se ejecutó, pero no detecto cambios visibles."
    elif success:
        status = "Se ejecutó y detecto cambios en pantalla."
    elif (not success) and vd.score >= 0.02:
        status = "La acción reportó fallo, pero veo cambios en pantalla."
    else:
        status = "La acción reportó fallo y no detecto cambios claros."

    # Mention analysis limitations (but keep short by default)
    limitations: List[str] = []
    if not before_res.ocr_ok or not after_res.ocr_ok:
        limitations.append("no he podido leer bien el texto de la pantalla")
    if run_yolo and (not before_res.yolo_ok or not after_res.yolo_ok):
        limitations.append("no he podido detectar bien los elementos de la interfaz")

    # Short summary: 1–2 highlights max
    parts: List[str] = [f"{action_phrase}. {status}"]

    if limitations and verbosity == "short":
        parts.append(f"Además, {limitations[0]}.")
        return " ".join(parts)

    # Prefer hypothesis highlight
    if hypothesis.kind == "modal":
        # Mention likely dialog and key actions if present
        modal_actions = [t for t in added_voice if any(k in t for k in _MODAL_KEYWORDS)]
        if modal_actions:
            parts.append(f"Parece que apareció un diálogo con { _natural_list(modal_actions, limit=3) }.")
        else:
            parts.append("Parece que apareció un diálogo.")
    elif hypothesis.kind == "scroll":
        parts.append("Parece que se ha hecho scroll.")
    elif hypothesis.kind == "content_change":
        parts.append("Hubo un cambio grande en la lista o el contenido.")
    elif hypothesis.kind == "navigation":
        parts.append("La pantalla cambió bastante.")
    elif hypothesis.kind == "localized" and vd.score >= 0.01:
        # Try to mention the most informative new text
        if added_voice:
            parts.append(f"Veo texto nuevo como { _natural_list(added_voice, limit=2) }.")
        else:
            parts.append("Veo un cambio localizado.")
    else:
        # none/low: rely on added_voice if any
        if added_voice:
            parts.append(f"Veo texto nuevo como { _natural_list(added_voice, limit=2) }.")

    if verbosity == "short":
        if limitations:
            parts.append(f"Nota: { _natural_list(limitations, limit=2) }.")
        return " ".join(parts)

    # Long summary: include more details (still TTS-friendly)
    # Text changes
    if added_voice:
        parts.append(f"Texto nuevo (muestra): { _natural_list(added_voice, limit=3) }.")
    if removed_voice:
        parts.append(f"Texto eliminado (muestra): { _natural_list(removed_voice, limit=2) }.")

    # UI deltas (top 3)
    if type_deltas:
        deltas_desc = [_describe_count_delta(d, t) for (t, d) in type_deltas[:3]]
        parts.append(f"Cambios en la interfaz: { _natural_list(deltas_desc, limit=3) }.")

    # Visual score hint (spoken in qualitative terms)
    if vd.score < 0.01:
        parts.append("El cambio visual parece pequeño.")
    elif vd.score < 0.05:
        parts.append("El cambio visual es moderado.")
    else:
        parts.append("El cambio visual es grande.")

    if limitations:
        parts.append(f"Limitaciones: { _natural_list(limitations, limit=3) }.")

    return " ".join(parts)
