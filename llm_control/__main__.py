"""
Main entry point for the llm_control package.
This allows running the package as a module via `python -m llm_control`.
"""

import sys
import os
import importlib
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("llm-pc-control")

if __name__ == "__main__":
    # Check if we have a specific command
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        # Remove the command from the arguments so the submodule doesn't see it
        sys.argv.pop(1)
        
        if command == "voice-server":
            # Run the voice control server
            try:
                # Import the module lazily to avoid issues with missing dependencies
                try:
                    from llm_control import voice_control_server
                except ModuleNotFoundError:
                    logger.error("Voice control server module not found")
                    sys.exit(1)
                except ImportError as e:
                    logger.error(f"Error importing voice control server: {e}")
                    sys.exit(1)
                # The module has its own argument parsing and app.run() call
            except Exception as e:
                logger.error(f"Error running voice control server: {e}")
                sys.exit(1)
        
        elif command == "simple-voice":
            # Run the simple voice command script
            simple_voice_path = os.path.join(os.path.dirname(__file__), "..", "simple_voice_command.py")
            if os.path.exists(simple_voice_path):
                # Execute the script directly
                try:
                    import subprocess
                    subprocess.run([sys.executable, simple_voice_path] + sys.argv[1:])
                except Exception as e:
                    logger.error(f"Error running simple voice command: {e}")
                    sys.exit(1)
            else:
                logger.error("Error: simple_voice_command.py not found")
                sys.exit(1)
        
        else:
            print(f"Unknown command: {command}")
            print("Available commands:")
            print("  voice-server - Run the voice control server")
            print("  simple-voice - Run the simple voice command script")
            sys.exit(1)
    else:
        # No command specified, show help
        print("LLM PC Control - Voice Command System")
        print("-------------------------------------")
        print("Usage: python -m llm_control <command> [options]")
        print("\nAvailable commands:")
        print("  voice-server - Run the voice control server")
        print("  simple-voice - Run the simple voice command script")
        print("\nExample:")
        print("  python -m llm_control voice-server --port 8080 --whisper-model medium")
        print("  python -m llm_control simple-voice --command \"click on the Firefox icon\"") 