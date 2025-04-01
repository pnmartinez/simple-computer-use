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

## Piautobike Scripts Endpoints

These endpoints allow you to create, manage, and execute Piautobike scripts.

### List All Scripts

**Endpoint:** `/scripts`

**Method:** `GET`

**Description:** Retrieves a list of all available Piautobike scripts with their metadata.

**Response Example:**
```json
{
  "status": "success",
  "scripts": [
    {
      "script_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "name": "Open browser and search",
      "description": "Opens the default browser and searches for a query",
      "created_at": "2023-06-15T10:30:00",
      "updated_at": "2023-06-15T10:30:00",
      "tags": ["browser", "search"],
      "command_count": 2
    }
  ],
  "count": 1
}
```

### Get Script Details

**Endpoint:** `/scripts/{script_id}`

**Method:** `GET`

**Description:** Retrieves detailed information about a specific script, including the PyAutoGUI code.

**Parameters:**
- `script_id` (path parameter): The unique identifier of the script to retrieve

**Response Example:**
```json
{
  "status": "success",
  "script": {
    "script_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "Open browser and search",
    "description": "Opens the default browser and searches for a query",
    "commands": [
      "Open Firefox",
      "Search for LLM PC Control"
    ],
    "pyautogui_code": "import pyautogui\nimport time\n\n# Command: Open Firefox\npyautogui.hotkey('win', 'r')\ntime.sleep(0.5)\npyautogui.write('firefox')\ntime.sleep(0.1)\npyautogui.press('enter')\ntime.sleep(2)\n\n# Command: Search for LLM PC Control\npyautogui.write('LLM PC Control')\ntime.sleep(0.1)\npyautogui.press('enter')",
    "created_at": "2023-06-15T10:30:00",
    "updated_at": "2023-06-15T10:30:00",
    "tags": ["browser", "search"]
  }
}
```

### Create New Script

**Endpoint:** `/scripts`

**Method:** `POST`

**Description:** Creates a new Piautobike script. If PyAutoGUI code is not provided, it will be generated automatically from the commands.

**Request Body:**
```json
{
  "name": "Open browser and search",
  "description": "Opens the default browser and searches for a query",
  "commands": [
    "Open Firefox",
    "Search for LLM PC Control"
  ],
  "tags": ["browser", "search"],
  "pyautogui_code": "import pyautogui\nimport time\n\n# Command: Open Firefox\npyautogui.hotkey('win', 'r')\n..."
}
```

**Note:** The `pyautogui_code` field is optional. If not provided, the code will be generated from the commands.

**Response Example:**
```json
{
  "status": "success",
  "message": "Script 'Open browser and search' created successfully",
  "script": {
    "script_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "Open browser and search",
    "description": "Opens the default browser and searches for a query",
    "commands": [
      "Open Firefox",
      "Search for LLM PC Control"
    ],
    "pyautogui_code": "import pyautogui\nimport time\n\n# Command: Open Firefox\npyautogui.hotkey('win', 'r')\n...",
    "created_at": "2023-06-15T10:30:00",
    "updated_at": "2023-06-15T10:30:00",
    "tags": ["browser", "search"]
  }
}
```

### Update Script

**Endpoint:** `/scripts/{script_id}`

**Method:** `PUT`

**Description:** Updates an existing script with new information.

**Parameters:**
- `script_id` (path parameter): The unique identifier of the script to update

**Request Body:**
```json
{
  "name": "Updated script name",
  "description": "Updated description",
  "commands": [
    "Open Chrome",
    "Search for LLM PC Control"
  ],
  "tags": ["browser", "chrome", "search"]
}
```

**Note:** All fields are optional. Only provided fields will be updated.

**Response Example:**
```json
{
  "status": "success",
  "message": "Script 'Updated script name' updated successfully",
  "script": {
    "script_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "Updated script name",
    "description": "Updated description",
    "commands": [
      "Open Chrome",
      "Search for LLM PC Control"
    ],
    "pyautogui_code": "import pyautogui\nimport time\n\n# Command: Open Chrome\npyautogui.hotkey('win', 'r')\n...",
    "created_at": "2023-06-15T10:30:00",
    "updated_at": "2023-06-15T11:45:00",
    "tags": ["browser", "chrome", "search"]
  }
}
```

### Delete Script

**Endpoint:** `/scripts/{script_id}`

**Method:** `DELETE`

**Description:** Deletes a script.

**Parameters:**
- `script_id` (path parameter): The unique identifier of the script to delete

**Response Example:**
```json
{
  "status": "success",
  "message": "Script with ID 3fa85f64-5717-4562-b3fc-2c963f66afa6 deleted successfully"
}
```

### Execute Script

**Endpoint:** `/scripts/{script_id}/execute`

**Method:** `POST`

**Description:** Executes a script, running the PyAutoGUI commands.

**Parameters:**
- `script_id` (path parameter): The unique identifier of the script to execute

**Response Example:**
```json
{
  "status": "success",
  "script_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "Open browser and search",
  "execution_time": 3.542
}
```

### Generate Script (Without Saving)

**Endpoint:** `/scripts/generate`

**Method:** `POST`

**Description:** Generates PyAutoGUI code from a list of commands without saving it as a script.

**Request Body:**
```json
{
  "commands": [
    "Open Firefox",
    "Search for LLM PC Control"
  ]
}
```

**Response Example:**
```json
{
  "status": "success",
  "pyautogui_code": "import pyautogui\nimport time\n\n# Command: Open Firefox\npyautogui.hotkey('win', 'r')\ntime.sleep(0.5)\npyautogui.write('firefox')\ntime.sleep(0.1)\npyautogui.press('enter')\ntime.sleep(2)\n\n# Command: Search for LLM PC Control\npyautogui.write('LLM PC Control')\ntime.sleep(0.1)\npyautogui.press('enter')",
  "action_results": [
    {
      "success": true,
      "command": "Open Firefox",
      "pyautogui_actions": [
        {
          "description": "Press Win+R to open Run dialog",
          "pyautogui_cmd": "pyautogui.hotkey('win', 'r')"
        },
        {
          "description": "Type firefox",
          "pyautogui_cmd": "pyautogui.write('firefox')"
        },
        {
          "description": "Press Enter",
          "pyautogui_cmd": "pyautogui.press('enter')"
        }
      ]
    },
    {
      "success": true,
      "command": "Search for LLM PC Control",
      "pyautogui_actions": [
        {
          "description": "Type search query",
          "pyautogui_cmd": "pyautogui.write('LLM PC Control')"
        },
        {
          "description": "Press Enter to search",
          "pyautogui_cmd": "pyautogui.press('enter')"
        }
      ]
    }
  ]
}
```

### Export Script

**Endpoint:** `/scripts/{script_id}/export`

**Method:** `GET`

**Description:** Exports a script as JSON, either returning the data in the response or downloading as a file.

**Parameters:**
- `script_id` (path parameter): The unique identifier of the script to export
- `download` (query parameter, optional): Set to "true" to download as a file, default is "false"

**Response Example (JSON):**
```json
{
  "status": "success",
  "script_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "Open browser and search",
  "export_data": {
    "script_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "Open browser and search",
    "description": "Opens the default browser and searches for a query",
    "commands": [
      "Open Firefox",
      "Search for LLM PC Control"
    ],
    "pyautogui_code": "import pyautogui\nimport time\n\n# Command: Open Firefox\npyautogui.hotkey('win', 'r')\ntime.sleep(0.5)\npyautogui.write('firefox')\ntime.sleep(0.1)\npyautogui.press('enter')\ntime.sleep(2)\n\n# Command: Search for LLM PC Control\npyautogui.write('LLM PC Control')\ntime.sleep(0.1)\npyautogui.press('enter')",
    "created_at": "2023-06-15T10:30:00",
    "updated_at": "2023-06-15T10:30:00",
    "tags": ["browser", "search"]
  }
}
```

**Response Example (Download):**  
When using `?download=true`, the response will be a file download with the script data.

### Import Script

**Endpoint:** `/scripts/import`

**Method:** `POST`

**Description:** Imports a script from a JSON file or data.

**Request Options:**
1. **File Upload:**
   - `file` (form data): JSON file containing the script data
   - `replace` (form data, optional): Set to "true" to replace existing script with the same ID, default is "false"

2. **JSON Data:**
   - Request body should contain the script data in JSON format
   - `replace` (query parameter, optional): Set to "true" to replace existing script with the same ID, default is "false"

**Response Example:**
```json
{
  "status": "success",
  "message": "Script imported successfully",
  "script_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "Open browser and search"
}
```

### Batch Import Scripts

**Endpoint:** `/scripts/batch-import`

**Method:** `POST`

**Description:** Imports multiple scripts from a directory.

**Request Body:**
```json
{
  "directory": "/path/to/scripts",
  "replace": false
}
```

**Response Example:**
```json
{
  "status": "success",
  "imported_count": 3,
  "failed_count": 1,
  "imported": [
    {
      "script_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "name": "Open browser and search"
    },
    {
      "script_id": "7bc94e12-9dab-4ef2-a76c-1d956f3e8901",
      "name": "Take screenshot and save"
    },
    {
      "script_id": "c48e2f10-5b3a-4c1d-8f9e-6a8b7c9d0e12",
      "name": "Find and click button"
    }
  ],
  "failed": [
    {
      "file": "/path/to/scripts/invalid.json",
      "error": "Invalid JSON format"
    }
  ]
}
``` 