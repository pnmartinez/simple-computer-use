"""
Command Line Interface for LLM PC Control.

This module provides a command-line interface for the LLM PC Control package,
allowing users to run commands from the terminal or enter an interactive mode.
"""

import argparse
import logging
import sys
from typing import List, Optional

from llm_control.main import setup, run_command

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Args:
        args: Command-line arguments (defaults to sys.argv[1:])
        
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="LLM PC Control - Control your computer with natural language commands"
    )
    
    # Add subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Set up the environment")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run a command")
    run_parser.add_argument(
        "user_input",
        nargs="+",
        help="The command to run (e.g., 'click on the button')"
    )
    
    # Interactive mode
    interactive_parser = subparsers.add_parser(
        "interactive", help="Run in interactive mode"
    )
    
    # Parse arguments
    return parser.parse_args(args)

def interactive_mode() -> None:
    """
    Run the CLI in interactive mode, accepting commands from the user.
    """
    print("LLM PC Control - Interactive Mode")
    print("Type 'exit' or 'quit' to exit")
    print("Type 'help' for help")
    
    # Set up the environment
    setup()
    
    while True:
        try:
            # Get user input
            user_input = input("\nEnter a command: ")
            
            # Check if the user wants to exit
            if user_input.lower() in ["exit", "quit"]:
                print("Exiting...")
                break
                
            # Check if the user wants help
            elif user_input.lower() == "help":
                print("\nLLM PC Control - Help")
                print("Commands:")
                print("  exit, quit - Exit the program")
                print("  help - Show this help message")
                print("\nExamples:")
                print("  click on the button")
                print("  type 'Hello, world!' in the text box")
                print("  press enter")
                
            # Process the command
            elif user_input.strip():
                run_command(user_input)
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
            
        except Exception as e:
            logger.error(f"Error: {str(e)}")

def main(args: Optional[List[str]] = None) -> None:
    """
    Main entry point for the CLI.
    
    Args:
        args: Command-line arguments (defaults to sys.argv[1:])
    """
    # Parse arguments
    parsed_args = parse_args(args)
    
    # Run the appropriate command
    if parsed_args.command == "setup":
        setup()
        
    elif parsed_args.command == "run":
        # Join the user input into a single string
        user_input = " ".join(parsed_args.user_input)
        
        # Set up the environment
        setup()
        
        # Run the command
        run_command(user_input)
        
    elif parsed_args.command == "interactive":
        interactive_mode()
        
    else:
        # Default to interactive mode if no command is specified
        interactive_mode()

if __name__ == "__main__":
    main() 