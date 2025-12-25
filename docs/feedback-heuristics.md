# Feedback Heuristics Specification (TTS Screen Summary)

This document describes the logic used to generate TTS-friendly feedback summaries from
command execution and screen deltas. It is intended to be a complete, structured reference
for downstream LLMs or human reviewers.

Source implementation: `llm_control/voice/feedback.py`.

---

## 1) Inputs and Outputs

**Primary function**
- `summarize_screen_delta_v2(before, after, command, success, steps=None, code=None, verbosity="short")`

**Inputs**
- `before`: path to screenshot **before** execution (may be `None`).
- `after`: path to screenshot **after** execution (may be `None`).
- `command`: original command text.
- `success`: boolean from execution result.
- `steps`: optional list of pipeline steps.
- `code`: optional PyAutoGUI code executed (string).
- `verbosity`: `"short"` or `"long"`.

**Output**
- A single Spanish, TTS-friendly sentence or short paragraph describing:
  - Actions performed (from executed code, or steps fallback),
  - Whether changes were detected,
  - What likely changed (text/UI delta),
  - Any uncertainty due to OCR/YOLO failures.

---

## 2) Action Phrase Derivation (Source of Truth)

### 2.1 Primary: Executed Code (PyAutoGUI)
Action phrase is derived from **executed PyAutoGUI code**, not from the spoken command.

**Detection patterns** (regex over code string):
- Click:
  - `pyautogui.click`, `pyautogui.doubleClick`, `pyautogui.rightClick`
  - Phrase: `"hecho clic"`
  - If click coordinates can be inferred, append zone and OCR target text (see section 5).
- Type:
  - `pyautogui.write`, `pyautogui.typewrite`
  - Phrase: `"escrito el texto"`
- Press:
  - `pyautogui.press('enter'|'intro')` → `"pulsado Enter"`
  - `pyautogui.press('tab')` → `"pulsado Tab"`
  - `pyautogui.press('esc'|'escape')` → `"pulsado Escape"`
- Scroll:
  - `pyautogui.scroll(...)` → `"hecho scroll"`
- Drag:
  - `pyautogui.dragTo(...)`, `pyautogui.dragRel(...)` → `"arrastrado el elemento"`

**Final phrase construction**
- Single action: `"He {acción}"`
- Multiple actions: `"He {acción 1}, {acción 2} y {acción 3}"`

### 2.2 Fallback: Steps
If code is missing or yields no action phrase, use pipeline `steps`:
- Detects actions by keyword presence in the concatenated steps.
- Same verb set as above (click, type, press, scroll, drag).
  - Escape detection uses **word boundaries**: `\besc\b|\bescape\b`.

### 2.3 Last Resort: Command
If both code and steps fail, fall back to `_command_for_voice(command)`:
Produces a generic phrase such as `"He ejecutado la acción"`.

---

## 3) Visual Delta & Focused Analysis

### 3.1 Visual Diff (Fast)
Computes a normalized pixel difference score (`0..1`) between `before` and `after`:
- Uses downscaled RGB images for performance.
- `score` = mean absolute difference over all channels.

### 3.2 Change Boxes (Region-of-Change)
Identifies coarse regions of change to focus OCR/YOLO:
- Thresholds diff image and finds bounding boxes.
- Builds a set of coarse stripes, merges overlapping boxes.
- Keeps top 5 largest boxes.

These boxes are mapped back to the original screenshot resolution before OCR/YOLO.

### 3.3 Focus Strategy
If visual score is small, OCR/YOLO runs on the full image.
If changes are significant, OCR/YOLO is restricted to the change boxes to reduce noise.

---

## 4) OCR & YOLO Extraction

### 4.1 OCR
Uses `detect_text_regions(image_path)` and applies normalization:
- `_normalize_text` lowercases and redacts PII.
- `_is_noise_text` filters numeric-only, timestamps, dates, percents, and pagination.

### 4.2 YOLO
Uses `detect_ui_elements_with_yolo(image_path)` when enabled:
- Summarizes counts of UI element types.

### 4.3 Caching & Timeouts
OCR/YOLO calls are cached via LRU using `(path, mtime, focus boxes)`.
Execution runs in a thread pool with timeouts.

---

## 5) Click Zone + OCR Target Text

### 5.1 Coordinate Extraction
When click actions are detected:
- Parses `pyautogui.click(...)` or uses the most recent `pyautogui.moveTo(...)`.
- Supports named args (`x=`, `y=`) or positional args.

### 5.2 Zone Mapping (3×3 grid)
Screen is divided into a 3×3 grid (left/center/right × top/center/bottom).
Examples:
- `zona central`
- `zona de arriba izquierda`
- `zona de abajo derecha`

### 5.3 OCR Target Text
If a click position is found:
- Searches OCR regions from the **before** screenshot.
- If the click falls inside a text box, attaches normalized text:
  - Example: `"hecho clic en la zona de arriba izquierda sobre actividades"`

---

## 6) Change-Type Heuristics

### 6.1 Modal Detection
If newly added text contains CTA words **as full tokens**:
```
CTA_WORDS = aceptar, cancelar, permitir, denegar, guardar, continuar, ok
```
Then:
- If change area is localized (<35% of screen):
  - Hypothesis: `modal`
  - Summary: `"Parece que apareció un diálogo."`
  - If CTA words detected: `"Parece que apareció un diálogo con {CTAs}."`

### 6.2 Large Content Change (Scroll-like)
If there is heavy text churn and large region change:
- If steps/code indicate scroll → `"Parece que se ha hecho scroll."`
- Else → `"Hubo un cambio grande en la lista o el contenido."`

### 6.3 Navigation
If change is global or very large:
- `"La pantalla cambió bastante."`

### 6.4 Localized Change
If change is moderate/local:
- If new text exists: `"Veo texto nuevo como {texto}."`
- Else: `"Veo un cambio localizado."`

---

## 7) Status & Confidence Messaging

Combines execution success + visual score:
- Success + low visual change: `"Se ejecutó, pero no detecto cambios visibles."`
- Success + change: `"Se ejecutó y detecto cambios en pantalla."`
- Failure + change: `"La acción reportó fallo, pero veo cambios en pantalla."`
- Failure + low change: `"La acción reportó fallo y no detecto cambios claros."`

If OCR/YOLO fail or time out:
- Adds a brief limitation message (short mode).

---

## 8) PII Redaction

Before text output:
- URLs → `[enlace]`
- Emails → `[correo]`
- Phone-like → `[teléfono]`
- Token-like → `[token]`
- IBAN → `[iban]`

---

## 9) TTS-Friendly Formatting

- No visual symbols (e.g., avoids `→`).
- Truncates long text by words and character cap.
- Natural list formatting: `A y B`, or `A, B y C`.

---

## 10) Behavior Without Screenshots

If `before`/`after` are missing:
- Summary still describes actions based on executed code.
- Acknowledges lack of screenshots:
  - `"Se ejecutó, pero no tengo capturas para comparar."`
  - or `"La acción reportó fallo y no tengo capturas para comparar."`

---

## 11) Example Output Patterns

1) **Click with OCR target**
> "He hecho clic en la zona de arriba izquierda sobre actividades. Se ejecutó y detecto cambios en pantalla."

2) **Typing + Enter (no screenshots)**
> "He escrito el texto y pulsado Enter. Se ejecutó, pero no tengo capturas para comparar."

3) **Modal with CTA**
> "He hecho clic. Parece que apareció un diálogo con aceptar y cancelar."

4) **Large content change without scroll**
> "He hecho clic. Hubo un cambio grande en la lista o el contenido."

---

## 12) Where This Is Wired In

- Execution entry point: `llm_control/voice/commands.py:execute_command_with_logging`
  - Captures `before`/`after` if not typing-only.
  - Passes `steps` and executed code into `summarize_screen_delta_v2`.
- History persistence: `llm_control/voice/utils.py:add_to_command_history`
  - Stores `screen_summary`.
- API: `GET /command-summary/latest` (returns `screen_summary` for TTS).

