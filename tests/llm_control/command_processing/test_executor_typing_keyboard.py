"""
Tests for typing vs keyboard command detection and prioritization.

This test suite verifies that the system correctly distinguishes between
typing commands and keyboard commands, especially in edge cases where
both might be detected.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))

from llm_control.command_processing.executor import (
    is_typing_command,
    is_keyboard_command,
    process_single_step
)


class TestTypingKeyboardDetection(unittest.TestCase):
    """Test typing and keyboard command detection functions."""

    def test_is_typing_command_pure_typing(self):
        """Test that pure typing commands are detected correctly."""
        # Spanish typing commands
        self.assertTrue(is_typing_command("escribe hola mundo"))
        self.assertTrue(is_typing_command("Escribe, revisa los logs"))
        self.assertTrue(is_typing_command("teclea el texto"))
        self.assertTrue(is_typing_command("ingresa la contraseña"))
        
        # English typing commands
        self.assertTrue(is_typing_command("type hello world"))
        self.assertTrue(is_typing_command("write the text"))
        self.assertTrue(is_typing_command("enter the password"))
        self.assertTrue(is_typing_command("input data"))

    def test_is_typing_command_keyboard_false_positive(self):
        """Test that keyboard commands with 'enter' are NOT detected as typing."""
        # These should NOT be detected as typing commands
        self.assertFalse(is_typing_command("presiona enter"))
        self.assertFalse(is_typing_command("press enter"))
        self.assertFalse(is_typing_command("pulsa enter"))
        self.assertFalse(is_typing_command("Presiona Enter"))
        self.assertFalse(is_typing_command("Press Enter"))
        self.assertFalse(is_typing_command("presiona enter."))
        self.assertFalse(is_typing_command("press enter and continue"))

    def test_is_keyboard_command_pure_keyboard(self):
        """Test that pure keyboard commands are detected correctly."""
        # Spanish keyboard commands
        self.assertTrue(is_keyboard_command("presiona enter"))
        self.assertTrue(is_keyboard_command("pulsa tab"))
        self.assertTrue(is_keyboard_command("presiona escape"))
        self.assertTrue(is_keyboard_command("presiona abajo"))
        self.assertTrue(is_keyboard_command("presiona arriba"))
        
        # English keyboard commands
        self.assertTrue(is_keyboard_command("press enter"))
        self.assertTrue(is_keyboard_command("hit tab"))
        self.assertTrue(is_keyboard_command("press escape"))
        self.assertTrue(is_keyboard_command("press down"))
        self.assertTrue(is_keyboard_command("press up"))

    def test_is_keyboard_command_combinations(self):
        """Test keyboard command detection with key combinations."""
        self.assertTrue(is_keyboard_command("presiona control c"))
        self.assertTrue(is_keyboard_command("press ctrl c"))
        self.assertTrue(is_keyboard_command("presiona alt tab"))
        self.assertTrue(is_keyboard_command("press shift enter"))

    def test_is_keyboard_command_typing_false_positive(self):
        """Test that typing commands are NOT detected as keyboard."""
        # These should NOT be detected as keyboard commands
        self.assertFalse(is_keyboard_command("escribe hola"))
        self.assertFalse(is_keyboard_command("type hello"))
        self.assertFalse(is_keyboard_command("write text"))
        self.assertFalse(is_keyboard_command("enter the password"))


class TestCommandPrioritization(unittest.TestCase):
    """Test the prioritization logic in process_single_step."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock UI description (empty for most tests)
        self.ui_description = {"elements": []}
        
        # Mock structured_usage_log to avoid side effects
        self.structured_log_patcher = patch('llm_control.command_processing.executor.structured_usage_log')
        self.mock_structured_log = self.structured_log_patcher.start()
        
        # Mock command history
        self.history_patcher = patch('llm_control.command_processing.executor.command_history', {
            'last_command': None,
            'last_ui_element': None
        })
        self.history_patcher.start()
        
        # Mock history functions
        self.add_step_patcher = patch('llm_control.command_processing.executor.add_step_to_history')
        self.add_step_patcher.start()
        
        self.update_history_patcher = patch('llm_control.command_processing.executor.update_command_history')
        self.update_history_patcher.start()

    def tearDown(self):
        """Clean up after tests."""
        self.structured_log_patcher.stop()
        self.history_patcher.stop()
        self.add_step_patcher.stop()
        self.update_history_patcher.stop()

    @patch('llm_control.command_processing.executor.extract_text_to_type_with_llm')
    @patch('llm_control.command_processing.executor.extract_typing_target')
    def test_pure_keyboard_command(self, mock_extract_target, mock_extract_text):
        """Test Scenario 1: Pure keyboard command like 'Presiona Enter'."""
        mock_extract_target.return_value = {
            'code_lines': [],
            'explanation': [],
            'target_found': False
        }
        
        result = process_single_step("Presiona Enter", self.ui_description)
        
        # Should be processed as keyboard command
        self.assertIn('code', result)
        self.assertIn('description', result)
        # Should contain press("enter")
        self.assertIn('press("enter")', result['code'].lower() or '')
        # Should NOT try to extract text to type
        mock_extract_text.assert_not_called()

    @patch('llm_control.command_processing.executor.extract_text_to_type_with_llm')
    @patch('llm_control.command_processing.executor.extract_typing_target')
    def test_pure_typing_command(self, mock_extract_target, mock_extract_text):
        """Test Scenario 2: Pure typing command like 'Escribe hola'."""
        mock_extract_target.return_value = {
            'code_lines': [],
            'explanation': [],
            'target_found': False
        }
        mock_extract_text.return_value = "hola"
        
        result = process_single_step("Escribe hola", self.ui_description)
        
        # Should be processed as typing command
        self.assertIn('code', result)
        self.assertIn('description', result)
        # Should extract text to type
        mock_extract_text.assert_called_once()
        # Should contain typewrite
        self.assertIn('typewrite', result['code'].lower())

    @patch('llm_control.command_processing.executor.extract_text_to_type_with_llm')
    @patch('llm_control.command_processing.executor.extract_typing_target')
    @patch('llm_control.command_processing.executor.extract_keys_from_step')
    def test_typing_with_keyboard_sequence(self, mock_extract_keys, mock_extract_target, mock_extract_text):
        """Test Scenario 3: Sequence typing + keyboard in same step."""
        mock_extract_target.return_value = {
            'code_lines': [],
            'explanation': [],
            'target_found': False
        }
        mock_extract_text.return_value = "hola"
        mock_extract_keys.return_value = [['enter']]
        
        result = process_single_step("Escribe hola y presiona Enter", self.ui_description)
        
        # Should be processed (either as typing or keyboard depending on detection)
        self.assertIn('code', result)
        self.assertIn('description', result)
        
        # The command should be processed - check that it produces valid code
        # Note: The actual behavior depends on which pattern matches first
        # If sequence pattern matches, it should be typing; otherwise it may default to keyboard
        code_lower = result['code'].lower()
        # Should contain either typewrite or press (or both)
        self.assertTrue('typewrite' in code_lower or 'press' in code_lower)

    @patch('llm_control.command_processing.executor.extract_text_to_type_with_llm')
    @patch('llm_control.command_processing.executor.extract_typing_target')
    def test_enter_as_verb_typing(self, mock_extract_target, mock_extract_text):
        """Test Scenario 5: 'Enter the password' should be typing (English)."""
        mock_extract_target.return_value = {
            'code_lines': [],
            'explanation': [],
            'target_found': False
        }
        mock_extract_text.return_value = "the password"
        
        result = process_single_step("Enter the password", self.ui_description)
        
        # Should be processed as typing command
        self.assertIn('code', result)
        # Should extract text to type
        mock_extract_text.assert_called_once()

    @patch('llm_control.command_processing.executor.extract_text_to_type_with_llm')
    @patch('llm_control.command_processing.executor.extract_typing_target')
    def test_keyboard_after_typing_separate_steps(self, mock_extract_target, mock_extract_text):
        """Test Scenario 4: Separate steps - typing then keyboard."""
        mock_extract_target.return_value = {
            'code_lines': [],
            'explanation': [],
            'target_found': False
        }
        
        # First step: typing
        mock_extract_text.return_value = "hola"
        result1 = process_single_step("Escribe hola", self.ui_description)
        self.assertIn('typewrite', result1['code'].lower())
        
        # Second step: keyboard (should NOT be treated as typing)
        mock_extract_text.reset_mock()
        result2 = process_single_step("Presiona Enter", self.ui_description)
        
        # Should be processed as keyboard, not typing
        self.assertIn('code', result2)
        # Should NOT try to extract text
        mock_extract_text.assert_not_called()
        # Should contain press
        self.assertIn('press', result2['code'].lower())

    @patch('llm_control.command_processing.executor.extract_text_to_type_with_llm')
    @patch('llm_control.command_processing.executor.extract_typing_target')
    def test_multiple_keyboard_commands(self, mock_extract_target, mock_extract_text):
        """Test: Multiple keyboard commands in sequence."""
        mock_extract_target.return_value = {
            'code_lines': [],
            'explanation': [],
            'target_found': False
        }
        
        # First keyboard command
        result1 = process_single_step("Presiona abajo", self.ui_description)
        self.assertIn('press', result1['code'].lower())
        self.assertIn('down', result1['code'].lower())
        
        # Second keyboard command
        result2 = process_single_step("Presiona Enter", self.ui_description)
        self.assertIn('press', result2['code'].lower())
        self.assertIn('enter', result2['code'].lower())
        
        # Neither should try to extract text
        mock_extract_text.assert_not_called()


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and ambiguous scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.ui_description = {"elements": []}
        
        # Mock all external dependencies
        self.structured_log_patcher = patch('llm_control.command_processing.executor.structured_usage_log')
        self.structured_log_patcher.start()
        
        self.history_patcher = patch('llm_control.command_processing.executor.command_history', {
            'last_command': None,
            'last_ui_element': None
        })
        self.history_patcher.start()
        
        self.add_step_patcher = patch('llm_control.command_processing.executor.add_step_to_history')
        self.add_step_patcher.start()
        
        self.update_history_patcher = patch('llm_control.command_processing.executor.update_command_history')
        self.update_history_patcher.start()

    def tearDown(self):
        """Clean up after tests."""
        self.structured_log_patcher.stop()
        self.history_patcher.stop()
        self.add_step_patcher.stop()
        self.update_history_patcher.stop()

    @patch('llm_control.command_processing.executor.extract_text_to_type_with_llm')
    @patch('llm_control.command_processing.executor.extract_typing_target')
    def test_ambiguous_enter_command(self, mock_extract_target, mock_extract_text):
        """Test ambiguous command with 'enter' - should default to keyboard if has press verb."""
        mock_extract_target.return_value = {
            'code_lines': [],
            'explanation': [],
            'target_found': False
        }
        
        # Ambiguous but has explicit keyboard verb
        result = process_single_step("Presiona Enter.", self.ui_description)
        
        # Should default to keyboard
        self.assertIn('code', result)
        mock_extract_text.assert_not_called()

    def test_case_insensitive_detection(self):
        """Test that detection works case-insensitively."""
        # All these should be detected the same way
        self.assertTrue(is_keyboard_command("PRESIONA ENTER"))
        self.assertTrue(is_keyboard_command("Presiona Enter"))
        self.assertTrue(is_keyboard_command("presiona enter"))
        self.assertTrue(is_keyboard_command("Presiona ENTER"))
        
        self.assertTrue(is_typing_command("ESCRIBE HOLA"))
        self.assertTrue(is_typing_command("Escribe hola"))
        self.assertTrue(is_typing_command("escribe hola"))

    def test_spanish_and_english_mixed(self):
        """Test commands mixing Spanish and English."""
        # Spanish keyboard verb with English key name
        self.assertTrue(is_keyboard_command("presiona tab"))
        self.assertTrue(is_keyboard_command("pulsa escape"))
        
        # English keyboard verb with Spanish key name
        self.assertTrue(is_keyboard_command("press intro"))
        self.assertTrue(is_keyboard_command("press espacio"))


if __name__ == '__main__':
    # Configure logging to reduce noise during tests
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    unittest.main(verbosity=2)
