"""
Passive diagnostic sampler for the UI detection pipeline.

With a configurable probability, captures the full detection state
(screenshot + YOLO boxes + OCR regions + merged elements) so that
non-deterministic OCR behaviour can be diagnosed later.

When triggered, enters a "burst" mode that captures several consecutive
detections to allow before/after comparison of the same screen area.

Configuration via environment variables:
    DIAGNOSTIC_SAMPLE_RATE   - probability per detection (0.0-1.0, default 0.03 = 3%)
    DIAGNOSTIC_BURST_LENGTH  - consecutive captures after a trigger (default 3)
    DIAGNOSTIC_DIR           - output directory (default ./diagnostic_samples)
"""

import json
import logging
import os
import random
import shutil
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("llm-pc-control")

_SAMPLE_RATE = float(os.environ.get("DIAGNOSTIC_SAMPLE_RATE", "0.20"))
_BURST_LENGTH = int(os.environ.get("DIAGNOSTIC_BURST_LENGTH", "3"))
_OUTPUT_DIR = os.environ.get("DIAGNOSTIC_DIR", os.path.join(os.getcwd(), "diagnostic_samples"))

_lock = threading.Lock()
_burst_remaining = 0
_session_id: str | None = None


def _new_session_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{random.randint(1000,9999)}"


def should_capture() -> bool:
    """Decide whether the current detection should be captured.

    Returns True if we are inside a burst, or if the random dice
    triggers a new burst.
    """
    global _burst_remaining, _session_id

    with _lock:
        if _burst_remaining > 0:
            _burst_remaining -= 1
            return True

        if random.random() < _SAMPLE_RATE:
            _burst_remaining = max(0, _BURST_LENGTH - 1)
            _session_id = _new_session_id()
            return True

    return False


def capture_detection_state(
    image_path: str | None,
    yolo_elements: list,
    ocr_regions: list,
    merged_elements: list,
    extra_context: dict | None = None,
):
    """Save a snapshot of the full detection pipeline to disk.

    Called from the detection pipeline only when ``should_capture()``
    returned True, so the cost is near-zero for normal operation.
    """
    global _session_id

    with _lock:
        session = _session_id or _new_session_id()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    sample_dir = os.path.join(_OUTPUT_DIR, session)

    try:
        os.makedirs(sample_dir, exist_ok=True)

        if image_path and os.path.isfile(image_path):
            ext = os.path.splitext(image_path)[1] or ".png"
            shutil.copy2(image_path, os.path.join(sample_dir, f"{ts}_screenshot{ext}"))

        payload = {
            "timestamp": ts,
            "session": session,
            "image_path": str(image_path) if image_path else None,
            "yolo_elements": _serialise_elements(yolo_elements),
            "ocr_regions": _serialise_elements(ocr_regions),
            "merged_elements": _serialise_elements(merged_elements),
        }
        if extra_context:
            payload["context"] = extra_context

        json_path = os.path.join(sample_dir, f"{ts}_detection.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        logger.debug(f"Diagnostic sample saved: {json_path}")
    except Exception as exc:
        logger.debug(f"Diagnostic sampler write error (non-fatal): {exc}")


def _serialise_elements(elements: list) -> list:
    """Make element dicts JSON-safe (convert numpy/torch types)."""
    safe = []
    for elem in elements:
        entry = {}
        for k, v in elem.items():
            try:
                json.dumps(v)
                entry[k] = v
            except (TypeError, ValueError):
                entry[k] = str(v)
        safe.append(entry)
    return safe
