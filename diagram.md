# LLM PC Control Architecture Diagram

## System Overview

```mermaid
graph TD
    subgraph "Client Layer"
        A1[Mobile App] -->|HTTP/WebSocket| B1
        A2[Browser Interface] -->|HTTP| B1
        A3[CLI Scripts<br>record_and_execute.py<br>test_voice_command.py] -->|HTTP| B1
    end
    
    subgraph "Server Layer"
        B1[Flask Server<br>server.py]
        B2[REST API Endpoints]
        B3[WebSocket Endpoints]
        B1 --> B2
        B1 --> B3
        
        B4[SSL/Security<br>Handling]
        B1 -.-> B4
    end
    
    subgraph "Audio Processing"
        C1[Whisper Model<br>Speech Recognition]
        C2[Audio Recording<br>sounddevice/soundfile]
        C3[Language Detection]
        
        B1 --> C1
        A3 --> C2
        C2 --> C1
        C1 --> C3
    end
    
    subgraph "Translation Layer"
        D1[Ollama LLM<br>Translation] 
        D2[Language Mapping]
        
        C3 -->|Non-English| D1
        D1 --> D2
    end
    
    subgraph "Command Processing"
        E1[Command Parser<br>parser.py]
        E2[Command Executor<br>executor.py]
        E3[UI Element Finder]
        E4[History Tracking]
        
        B1 --> E1
        E1 --> E2
        E2 --> E3
        E2 <--> E4
    end
    
    subgraph "Action Layer"
        F1[PyAutoGUI<br>Mouse/Keyboard Control]
        F2[Screenshot Processing]
        F3[System Integration]
        
        E2 --> F1
        E2 --> F2
        E2 --> F3
    end
    
    D2 -->|English Commands| E1
```

## Module Structure

```mermaid
classDiagram
    class server {
        +run_server()
        +transcribe_audio()
        +translate_with_ollama()
        +process_audio_command()
        +voice_command_endpoint()
        +command_endpoint()
        +transcribe_endpoint()
    }
    
    class main {
        +run_command()
        +process_user_command()
        +execute_actions()
        +setup()
    }
    
    class executor {
        +process_single_step()
        +handle_keyboard_command()
        +handle_typing_command()
        +handle_scroll_command()
        +handle_ui_element_command()
        +is_typing_command()
        +is_keyboard_command()
        +is_scroll_command()
        +extract_keys_from_step()
    }
    
    class parser {
        +split_user_input_into_steps()
        +clean_and_normalize_steps()
        +normalize_step()
    }
    
    class text_extraction {
        +extract_text_to_type_with_llm()
        +ensure_text_is_safe_for_typewrite()
    }
    
    class cli_server {
        +cli_server()
        +parse_args()
        +check_ssl_config()
        +generate_self_signed_cert()
    }
    
    class test_voice_command {
        +record_audio()
        +transcribe_audio()
        +translate_with_ollama()
        +execute_command()
        +main()
    }
    
    class record_and_execute {
        +record_audio()
        +send_to_server()
        +main()
    }
    
    server --> main
    main --> executor
    main --> parser
    executor --> text_extraction
    server --> test_voice_command
    server --> record_and_execute
    cli_server --> server
```

## Audio Processing Flow

```mermaid
sequenceDiagram
    participant User
    participant Client
    participant Server
    participant Whisper
    participant Ollama
    participant CommandProcessor
    participant PyAutoGUI
    
    User->>Client: Speak command
    Client->>Client: Record audio
    Client->>Server: Send audio file
    Server->>Server: Save to temp file
    Server->>Whisper: Transcribe audio
    Whisper->>Server: Return transcription
    Server->>Server: Check language
    
    alt Non-English detected
        Server->>Ollama: Translate to English
        Ollama->>Server: Return translation
    end
    
    Server->>CommandProcessor: Process command
    CommandProcessor->>CommandProcessor: Parse command
    CommandProcessor->>CommandProcessor: Generate code
    CommandProcessor->>PyAutoGUI: Execute actions
    PyAutoGUI->>Server: Return results
    Server->>Client: Return response
    Client->>User: Display results
```

## Data Flow Diagram

```mermaid
flowchart LR
    subgraph Inputs
        AudioIn[Audio Data]
        TextIn[Text Commands]
    end
    
    subgraph Processing
        SR[Speech Recognition]
        Lang[Language Detection]
        Trans[Translation]
        Pres[Target Text Preservation]
        Parse[Command Parsing]
        Exec[Command Execution]
    end
    
    subgraph Actions
        Mouse[Mouse Movement]
        Keys[Keypresses]
        Type[Text Entry]
        Scroll[Scrolling]
    end
    
    subgraph History
        UIHist[UI Element History]
        CmdHist[Command History]
        CoordHist[Coordinate History]
    end
    
    AudioIn --> SR
    SR --> Lang
    Lang --> Trans
    Trans --> Pres
    Pres --> Parse
    TextIn --> Parse
    
    Parse --> Exec
    Exec --> Mouse
    Exec --> Keys
    Exec --> Type
    Exec --> Scroll
    
    Exec --> UIHist
    Exec --> CmdHist
    Exec --> CoordHist
    
    UIHist --> Exec
    CmdHist --> Exec
    CoordHist --> Exec
```

## Target Text Preservation

```mermaid
sequenceDiagram
    participant Input as "Spanish Command"
    participant Trans as "Translation Process"
    participant Parser as "Command Parser"
    participant UI as "UI Element Finder"

    Input->>Trans: "Haz clic en el botón Cancelar"
    Note over Trans: Identifies quoted text<br/>and UI element references
    Trans->>Parser: "Click on the Cancelar button"
    Note over Parser: Command structure in English<br/>Target label in original language
    Parser->>UI: Find element with label "Cancelar"
    Note over UI: Matches against actual<br/>UI text in the interface
```

A critical aspect of multilingual command processing is preserving target text elements in their original language. When a user references UI elements in their commands, those references must remain untranslated to match what actually appears on screen.

### Examples:
| Original Command | Incorrect Translation | Correct Translation |
|------------------|------------------------|---------------------|
| "Haz clic en Guardar" | "Click on Save" | "Click on Guardar" |
| "Escribir 'Hola' en Mensaje" | "Type 'Hello' in Message" | "Type 'Hola' in Mensaje" |
| "Selecciona Archivo" | "Select File" | "Select Archivo" |

This requirement is implemented in the translation process by:
1. Instructing the LLM translator to preserve quoted text
2. Preserving UI element names, button labels, and menu items
3. Maintaining file paths and technical terms in their original form

## File Organization

```
llm-control/
├── llm_control/                     # Main package
│   ├── __init__.py                  # Constants and configurations
│   ├── server.py                    # Main server functionality
│   ├── main.py                      # Core command processing
│   ├── cli_server.py                # CLI server entry point
│   ├── command_processing/          # Command processing modules
│   │   ├── executor.py              # Execute user commands
│   │   ├── parser.py                # Parse user input
│   │   ├── finder.py                # Find UI elements
│   │   └── history.py               # Track command history
│   ├── llm/                         # LLM integration modules
│   │   ├── text_extraction.py       # Extract text for typing
│   │   └── intent_detection.py      # Detect user intent
│   └── utils/                       # Utility modules
│       ├── dependencies.py          # Dependency management
│       └── screenshot.py            # Screenshot handling
├── record_and_execute.py            # Record & send to server
├── test_voice_command.py            # Standalone testing tool
├── start_android_server_rest.py     # Android REST API server
└── README.md                        # Documentation
```

## Key Interfaces

### REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/transcribe` | POST | Audio transcription only |
| `/command` | POST | Execute text command |
| `/voice-command` | POST | Process voice command |
| `/api/info` | GET | Server capabilities |
| `/api/system-info` | GET | System information |

### Command Line Arguments

| Argument | Description |
|----------|-------------|
| `--whisper-model` | Whisper model size (tiny/base/small/medium/large) |
| `--language` | Expected language (default: es) |
| `--disable-translation` | Disable automatic translation |
| `--ollama-model` | Ollama model for translation |
| `--ollama-host` | Ollama API host |

## Areas for Potential Refactoring

1. **Separation of Concerns**
   - Server functionality is tightly coupled with audio processing
   - Command execution mixed with UI detection

2. **Code Duplication**
   - Audio recording logic duplicated across files
   - Translation logic appears in multiple places

3. **Configuration Management**
   - Environment variables, command-line args, and constants spread across files
   - No central configuration system

4. **Error Handling**
   - Inconsistent error handling patterns
   - Some functions return None on error, others raise exceptions

5. **Testing Infrastructure**
   - Limited unit testing
   - Manual test scripts that could be automated

6. **Language Support**
   - Spanish support added in multiple places
   - Could be centralized into language modules

7. **Documentation**
   - Scattered across various files
   - No centralized API documentation

8. **Dependency Management**
   - Manual checks for dependencies
   - No formal dependency specification (requirements.txt/pyproject.toml) 