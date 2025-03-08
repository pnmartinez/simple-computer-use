# LLM PC Control

Control your computer with natural language commands using Large Language Models (LLMs).

## Features

- **Natural Language Commands**: Control your computer using everyday language
- **UI Element Detection**: Automatically detects UI elements on your screen
- **Multi-Step Commands**: Execute complex sequences of actions with a single command
- **OCR Integration**: Reads text from your screen to better understand the context
- **Keyboard and Mouse Control**: Simulates keyboard and mouse actions

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/llm-pc-control.git
cd llm-pc-control

# Install the package
pip install -e .
```

## Requirements

- Python 3.8 or higher
- Ollama (for local LLM inference)
- EasyOCR and PaddleOCR (for text recognition)
- PyAutoGUI (for keyboard and mouse control)

## Usage

### Command Line Interface

```bash
# Set up the environment (download models, check dependencies)
llm-pc-control setup

# Run a single command
llm-pc-control run "click on the button"

# Run in interactive mode
llm-pc-control interactive
```

### Python API

```python
from llm_control.main import setup, run_command

# Set up the environment
setup()

# Run a command
run_command("click on the button")
```

## Examples

Here are some examples of commands you can use:

- "Click on the Submit button"
- "Type 'Hello, world!' in the search box"
- "Press Enter"
- "Move to the top-right corner of the screen"
- "Double-click on the file icon"
- "Right-click on the image"
- "Scroll down"
- "Click on the button, then type 'Hello', then press Enter"

## How It Works

1. **Screenshot Analysis**: Takes a screenshot of your screen
2. **UI Detection**: Analyzes the screenshot to detect UI elements
3. **Command Parsing**: Parses your natural language command into steps
4. **Action Generation**: Generates the corresponding actions for each step
5. **Execution**: Executes the actions using PyAutoGUI

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.







