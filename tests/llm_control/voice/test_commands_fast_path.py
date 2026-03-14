"""Tests for fast path parsing in commands (no LLM)."""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))

from llm_control.voice.commands import _fast_path_parse_step


class TestFastPathParseStep(unittest.TestCase):
    """Test _fast_path_parse_step for keyboard and typing commands."""

    def test_keyboard_press_enter(self):
        r = _fast_path_parse_step("Presiona Enter")
        self.assertIsNotNone(r)
        self.assertEqual(r["type"], "keyboard")
        self.assertIn('pyautogui.press("enter")', r["code"])

    def test_keyboard_press_tab(self):
        r = _fast_path_parse_step("Presiona Tab")
        self.assertIsNotNone(r)
        self.assertIn('pyautogui.press("tab")', r["code"])

    def test_keyboard_hotkey(self):
        r = _fast_path_parse_step("Presiona control R")
        self.assertIsNotNone(r)
        self.assertIn("pyautogui.hotkey", r["code"])
        self.assertIn("ctrl", r["code"])
        self.assertIn("r", r["code"])

    def test_typing_simple(self):
        r = _fast_path_parse_step("Escribe hola")
        self.assertIsNotNone(r)
        self.assertEqual(r["type"], "typing")
        self.assertIn('pyautogui.typewrite("hola")', r["code"])

    def test_typing_english(self):
        r = _fast_path_parse_step("Type hello")
        self.assertIsNotNone(r)
        self.assertIn('pyautogui.typewrite("hello")', r["code"])

    def test_typing_and_key(self):
        r = _fast_path_parse_step("Escribe hola y presiona Enter")
        self.assertIsNotNone(r)
        self.assertIn('pyautogui.typewrite("hola")', r["code"])
        self.assertIn('pyautogui.press("enter")', r["code"])

    def test_unknown_returns_none(self):
        r = _fast_path_parse_step("Clic en Aceptar")
        self.assertIsNone(r)

    def test_empty_returns_none(self):
        self.assertIsNone(_fast_path_parse_step(""))
        self.assertIsNone(_fast_path_parse_step(None))
