import unittest
import os
import sys

# Add the parent directory to the path so we can import the package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from llm_control.command_processing.parser import (
    normalize_step,
    split_user_input_into_steps,
    clean_and_normalize_steps
)

class TestCommandProcessing(unittest.TestCase):
    """Test the command processing functionality."""
    
    def test_normalize_step(self):
        """Test the normalize_step function."""
        # Test removing prefixes
        self.assertEqual(normalize_step("then click the button"), "click the button")
        self.assertEqual(normalize_step("and type hello"), "type hello")
        self.assertEqual(normalize_step("next press enter"), "press enter")
        
        # Test with no prefix
        self.assertEqual(normalize_step("click the button"), "click the button")
        
        # Test with whitespace
        self.assertEqual(normalize_step("  click the button  "), "click the button")
    
    def test_split_user_input_into_steps(self):
        """Test the split_user_input_into_steps function."""
        # Test splitting by comma
        self.assertEqual(
            split_user_input_into_steps("click the button, type hello, press enter"),
            ["click the button", "type hello", "press enter"]
        )
        
        # Test splitting by 'then'
        self.assertEqual(
            split_user_input_into_steps("click the button then type hello then press enter"),
            ["click the button", "type hello", "press enter"]
        )
        
        # Test splitting by 'and'
        self.assertEqual(
            split_user_input_into_steps("click the button and type hello and press enter"),
            ["click the button", "type hello", "press enter"]
        )
        
        # Test with mixed delimiters
        self.assertEqual(
            split_user_input_into_steps("click the button, type hello then press enter"),
            ["click the button", "type hello", "press enter"]
        )
        
        # Test with quoted text
        self.assertEqual(
            split_user_input_into_steps("click the button, type 'hello, world', press enter"),
            ["click the button", "type 'hello, world'", "press enter"]
        )
    
    def test_clean_and_normalize_steps(self):
        """Test the clean_and_normalize_steps function."""
        # Test basic normalization
        self.assertEqual(
            clean_and_normalize_steps(["then click the button", "and type hello", "next press enter"]),
            ["click the button", "type hello", "press enter"]
        )
        
        # Test with empty steps
        self.assertEqual(
            clean_and_normalize_steps(["click the button", "", "press enter"]),
            ["click the button", "press enter"]
        )
        
        # Test with whitespace
        self.assertEqual(
            clean_and_normalize_steps(["  click the button  ", "  type hello  ", "  press enter  "]),
            ["click the button", "type hello", "press enter"]
        )

if __name__ == "__main__":
    unittest.main() 