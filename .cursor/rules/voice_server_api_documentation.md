# LLM Control Voice Server API - Endpoint Reference

## Base URL
`https://{server-ip}:{port}`

## Endpoints Overview

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/` | Main page with server info and API documentation |
| `GET`  | `/health` | Server health check |
| `POST` | `/transcribe` | Transcribe audio to text |
| `POST` | `/translate` | Translate text to English |
| `POST` | `/command` | Execute a text command |
| `POST` | `/voice-command` | Process and execute voice command |
| `GET`  | `/screenshots` | List all available screenshots |
| `GET`  | `/screenshots/latest` | Get most recent screenshots |
| `GET`  | `/screenshots/<filename>` | Retrieve specific screenshot |
| `GET`  | `/screenshots/view` | View screenshots gallery |
| `GET/POST` | `/screenshot/capture` | Capture new screenshot |

## Detailed Specifications

### `GET /`
**Description:** Main page showing server information and available endpoints

**Response:** HTML page with server configuration and API documentation
- Content-Type: `text/html`

### `GET /health`
**Description:** Check server health status

**Response:**
```json
{
    "status": "ok",
    "message": "Voice control server is running",
    "timestamp": "2024-03-21T12:34:56.789Z"
}
```

### `POST /transcribe`
**Description:** Transcribe audio to text using Whisper

**Parameters:**
- `audio` (file, required): Audio file to transcribe (WAV, MP3, OGG)
- `language` (string, optional): Language code (default: server config)
- `model` (string, optional): Whisper model size (tiny, base, small, medium, large)

**Response:**
```json
{
    "status": "success",
    "text": "transcribed text",
    "language": "detected_language"
}
```

### `POST /translate`
**Description:** Translate text from any language to English using Ollama

**Request Body:**
```json
{
    "text": "text to translate",
    "model": "llama3.1",  // optional
    "ollama_host": "http://localhost:11434"  // optional
}
```

**Response:**
```json
{
    "status": "success",
    "original": "original text",
    "translated": "translated text"
}
```

### `POST /command`
**Description:** Execute a text command using LLM processing

**Request Body:**
```json
{
    "command": "command to execute",
    "model": "llama3.1",  // optional
    "capture_screenshot": true  // optional
}
```

**Response:**
```json
{
    "status": "success",
    "command": "executed command",
    "steps": 2,
    "result": "Command executed successfully",
    "screenshot": {  // if requested
        "filename": "screenshot.png",
        "filepath": "/path/to/screenshot.png",
        "url": "/screenshots/screenshot.png"
    }
}
```

### `POST /voice-command`
**Description:** Process and execute a voice command from audio

**Parameters:**
- `audio` (file, required): Audio file containing voice command (WAV, MP3, OGG)
- `language` (string, optional): Language code (default: server config)
- `model` (string, optional): Whisper model size (default: server config)
- `capture_screenshot` (boolean, optional): Whether to capture screenshot (default: true)

**Response:**
```json
{
    "status": "success",
    "transcription": {
        "text": "original transcribed text",
        "language": "detected_language",
        "translated": true,
        "translated_text": "translated command"
    },
    "steps": 2,
    "result": "Command executed successfully",
    "screenshot": {
        "filename": "screenshot.png",
        "filepath": "/path/to/screenshot.png",
        "url": "/screenshots/screenshot.png"
    }
}
```

### `GET /screenshots`
**Description:** List all available screenshots

**Response:**
```json
{
    "status": "success",
    "count": 10,
    "screenshots": [
        {
            "filename": "screenshot.png",
            "created": "2024-03-21T12:34:56.789Z",
            "size": 12345
        }
    ]
}
```

### `GET /screenshots/latest`
**Description:** Get information about the latest screenshots

**Parameters:**
- `limit` (integer, optional): Number of screenshots to return (default: 10)

**Response:** Same as `/screenshots`

### `GET /screenshots/<filename>`
**Description:** Serve a specific screenshot file

**Parameters:**
- `filename` (string, required): Name of the screenshot file

**Response:** Image file
- Content-Type: `image/png`

### `GET /screenshots/view`
**Description:** View screenshots in a gallery format

**Response:** HTML page with screenshot gallery
- Content-Type: `text/html`

### `GET/POST /screenshot/capture`
**Description:** Capture a screenshot on demand

**Parameters:**
- `format` (string, optional): Response format ('json' or 'redirect', default: 'redirect')

**Response (JSON format):**
```json
{
    "status": "success",
    "message": "Screenshot captured successfully",
    "filename": "screenshot.png",
    "filepath": "/path/to/screenshot.png",
    "url": "/screenshots/screenshot.png",
    "size": 12345,
    "timestamp": 1679401234,
    "image_data": "base64_encoded_image"  // if requested
}
```

**Response (redirect format):** Redirects to `/screenshots/<filename>`

## Error Responses

All endpoints may return the following error responses:

```json
{
    "error": "Error message describing what went wrong",
    "status": "error"
}
```

Common HTTP status codes:
- `400`: Bad Request - Missing or invalid parameters
- `404`: Not Found - Resource not found
- `422`: Unprocessable Entity - Valid request but failed to process
- `500`: Internal Server Error - Server-side error 