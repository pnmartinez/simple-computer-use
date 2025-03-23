#!/usr/bin/env python3

import sys
import importlib.util
import subprocess
import os
from dotenv import load_dotenv

def check_package(package_name):
    """Check if a Python package is installed"""
    package_spec = importlib.util.find_spec(package_name)
    if package_spec is None:
        print(f"❌ {package_name} is not installed")
        return False
    print(f"✅ {package_name} is installed")
    return True

def check_ollama():
    """Check if Ollama is running and accessible"""
    try:
        # Simple check to see if we can import ollama
        import ollama
        
        # Try to list models to confirm connection
        try:
            models = ollama.list()
            print(f"✅ Ollama is running and accessible")
            
            # Load model name from .env if it exists
            load_dotenv()
            model_name = os.getenv('OLLAMA_MODEL', 'llama3.1')
            
            # Check if the model is installed
            model_names = [model['name'] for model in models['models']]
            if model_name in model_names:
                print(f"✅ Model '{model_name}' is installed")
            else:
                print(f"❌ Model '{model_name}' is not installed")
                print(f"   You can install it with: ollama pull {model_name}")
                
            return True
        except Exception as e:
            print(f"❌ Ollama is installed but not accessible: {str(e)}")
            print("   Make sure the Ollama server is running")
            return False
    except ImportError:
        print("❌ Ollama Python library is not installed")
        return False

def check_pyautogui():
    """Check if PyAutoGUI is working properly"""
    try:
        import pyautogui
        
        # Get screen size to verify basic functionality
        screen_width, screen_height = pyautogui.size()
        print(f"✅ PyAutoGUI is working (Screen resolution: {screen_width}x{screen_height})")
        return True
    except Exception as e:
        print(f"❌ PyAutoGUI is installed but not working: {str(e)}")
        return False

def main():
    print("=== LLM PC Control - Setup Check ===\n")
    
    # Check required packages
    packages = ['pyautogui', 'PIL', 'dotenv', 'ollama']
    all_packages_installed = all(check_package(pkg) for pkg in packages)
    
    print("\n=== Checking Ollama ===")
    ollama_working = check_ollama()
    
    print("\n=== Checking PyAutoGUI ===")
    pyautogui_working = check_pyautogui()
    
    print("\n=== Summary ===")
    if all_packages_installed and ollama_working and pyautogui_working:
        print("✅ All checks passed! You can run the application with: python main.py")
    else:
        print("❌ Some checks failed. Please fix the issues above before running the application.")

if __name__ == "__main__":
    main() 