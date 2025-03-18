#!/usr/bin/env python3
"""
UI Detection Diagnostic Tool

This script helps diagnose issues with the UI detection module.
It checks for required dependencies, tests screenshot functionality,
and provides detailed feedback about any errors encountered.
"""

import os
import sys
import logging
import traceback
import importlib
import subprocess
from typing import Dict, List, Any, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("ui-detection-diagnostics")

def check_python_version() -> Dict[str, Any]:
    """Check the Python version."""
    logger.info(f"Python version: {sys.version}")
    version_info = {
        "major": sys.version_info.major,
        "minor": sys.version_info.minor,
        "micro": sys.version_info.micro,
        "full": sys.version,
    }
    
    # Check if Python version is >= 3.8
    if sys.version_info < (3, 8):
        logger.warning("Python version < 3.8 may cause issues with some dependencies")
    
    return version_info

def check_package(package_name: str) -> Dict[str, Any]:
    """Check if a package is installed and get its version."""
    logger.info(f"Checking package: {package_name}")
    result = {
        "name": package_name,
        "installed": False,
        "version": None,
        "error": None
    }
    
    try:
        package = importlib.import_module(package_name)
        result["installed"] = True
        
        # Try to get version in different ways
        if hasattr(package, "__version__"):
            result["version"] = package.__version__
        elif hasattr(package, "version"):
            result["version"] = package.version
        elif hasattr(package, "VERSION"):
            result["version"] = package.VERSION
        
        logger.info(f"{package_name} is installed, version: {result['version']}")
    except ImportError as e:
        logger.warning(f"{package_name} is not installed: {str(e)}")
        result["error"] = str(e)
    except Exception as e:
        logger.error(f"Error checking {package_name}: {str(e)}")
        result["error"] = str(e)
    
    return result

def check_required_dependencies() -> Dict[str, Any]:
    """Check all required dependencies for UI detection."""
    logger.info("Checking required dependencies...")
    
    packages = [
        "PIL", "numpy", "cv2", "pyautogui", "easyocr", "torch", 
        "torchvision", "ultralytics", "imagehash"
    ]
    
    results = {}
    for package in packages:
        results[package] = check_package(package)
    
    missing_packages = [p for p, r in results.items() if not r["installed"]]
    
    return {
        "all_installed": len(missing_packages) == 0,
        "missing_packages": missing_packages,
        "results": results
    }

def test_screenshot_functionality() -> Dict[str, Any]:
    """Test taking a screenshot."""
    logger.info("Testing screenshot functionality...")
    
    try:
        # Import our screenshot module
        from llm_control.screenshot import take_screenshot
        
        # Try to take a screenshot
        screenshot_info = take_screenshot()
        
        if screenshot_info.get("success", False):
            logger.info(f"Screenshot taken successfully: {screenshot_info.get('path')}")
            return {
                "success": True,
                "screenshot_info": screenshot_info
            }
        else:
            logger.error(f"Failed to take screenshot: {screenshot_info.get('error')}")
            return {
                "success": False,
                "error": screenshot_info.get("error")
            }
    except Exception as e:
        logger.error(f"Error testing screenshot functionality: {str(e)}")
        logger.error(traceback.format_exc())
        
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

def test_ocr_functionality() -> Dict[str, Any]:
    """Test OCR functionality if available."""
    logger.info("Testing OCR functionality...")
    
    try:
        # Import dependencies for OCR
        try:
            import easyocr
            from llm_control.ui_detection.ocr import detect_text_regions
        except ImportError as e:
            logger.warning(f"OCR dependencies not available: {str(e)}")
            return {
                "success": False,
                "error": f"OCR dependencies not available: {str(e)}"
            }
        
        # First take a screenshot to use for OCR testing
        from llm_control.screenshot import take_screenshot
        screenshot_info = take_screenshot()
        
        if not screenshot_info.get("success", False):
            logger.error(f"Failed to take screenshot for OCR testing: {screenshot_info.get('error')}")
            return {
                "success": False,
                "error": f"Failed to take screenshot for OCR testing: {screenshot_info.get('error')}"
            }
        
        # Try OCR on the screenshot
        screenshot_path = screenshot_info.get("path")
        try:
            text_regions = detect_text_regions(screenshot_path)
            
            if text_regions:
                logger.info(f"OCR detected {len(text_regions)} text regions")
                # Log the first few detected texts
                for i, region in enumerate(text_regions[:3]):
                    logger.info(f"  Text {i+1}: {region.get('text', 'N/A')}")
                
                return {
                    "success": True,
                    "regions_count": len(text_regions),
                    "sample_regions": text_regions[:3]
                }
            else:
                logger.warning("OCR completed but no text regions detected")
                return {
                    "success": True,
                    "regions_count": 0,
                    "warning": "No text regions detected"
                }
        except Exception as e:
            logger.error(f"Error during OCR processing: {str(e)}")
            logger.error(traceback.format_exc())
            
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    except Exception as e:
        logger.error(f"Error testing OCR functionality: {str(e)}")
        logger.error(traceback.format_exc())
        
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

def test_yolo_functionality() -> Dict[str, Any]:
    """Test YOLO detection functionality if available."""
    logger.info("Testing YOLO UI detection functionality...")
    
    try:
        # Import dependencies for YOLO
        try:
            from ultralytics import YOLO
            from llm_control.ui_detection.element_finder import detect_ui_elements_with_yolo
        except ImportError as e:
            logger.warning(f"YOLO dependencies not available: {str(e)}")
            return {
                "success": False,
                "error": f"YOLO dependencies not available: {str(e)}"
            }
        
        # First take a screenshot to use for YOLO testing
        from llm_control.screenshot import take_screenshot
        screenshot_info = take_screenshot()
        
        if not screenshot_info.get("success", False):
            logger.error(f"Failed to take screenshot for YOLO testing: {screenshot_info.get('error')}")
            return {
                "success": False,
                "error": f"Failed to take screenshot for YOLO testing: {screenshot_info.get('error')}"
            }
        
        # Try YOLO detection on the screenshot
        screenshot_path = screenshot_info.get("path")
        try:
            ui_elements = detect_ui_elements_with_yolo(screenshot_path)
            
            if ui_elements:
                logger.info(f"YOLO detected {len(ui_elements)} UI elements")
                # Log the first few detected elements
                for i, element in enumerate(ui_elements[:3]):
                    logger.info(f"  Element {i+1}: type={element.get('type', 'N/A')}, confidence={element.get('confidence', 0):.2f}")
                
                return {
                    "success": True,
                    "elements_count": len(ui_elements),
                    "sample_elements": ui_elements[:3]
                }
            else:
                logger.warning("YOLO completed but no UI elements detected")
                return {
                    "success": True,
                    "elements_count": 0,
                    "warning": "No UI elements detected"
                }
        except Exception as e:
            logger.error(f"Error during YOLO processing: {str(e)}")
            logger.error(traceback.format_exc())
            
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    except Exception as e:
        logger.error(f"Error testing YOLO functionality: {str(e)}")
        logger.error(traceback.format_exc())
        
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

def generate_installation_recommendations(dep_results: Dict[str, Any]) -> List[str]:
    """Generate pip installation recommendations for missing packages."""
    recommendations = []
    
    if not dep_results["all_installed"]:
        # Basic packages first
        basic_packages = ["Pillow", "numpy", "opencv-python", "pyautogui", "imagehash"]
        missing_basic = [p for p in basic_packages if p.lower().replace("-", "") in [pkg.lower() for pkg in dep_results["missing_packages"]]]
        
        if missing_basic:
            recommendations.append(f"pip install {' '.join(missing_basic)}")
        
        # PyTorch separate (with CUDA if available)
        if "torch" in dep_results["missing_packages"] or "torchvision" in dep_results["missing_packages"]:
            recommendations.append("# For PyTorch with CUDA (recommended for GPU support):")
            recommendations.append("pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118")
            recommendations.append("# OR, for CPU-only PyTorch:")
            recommendations.append("pip install torch torchvision")
        
        # EasyOCR separate
        if "easyocr" in dep_results["missing_packages"]:
            recommendations.append("pip install easyocr")
        
        # Ultralytics (YOLO) separate
        if "ultralytics" in dep_results["missing_packages"]:
            recommendations.append("pip install ultralytics")
        
        # Final recommendation - install everything at once with LLM Control's UI option
        recommendations.append("\n# Alternatively, you can install all UI detection dependencies at once:")
        recommendations.append("pip install -e .[ui]")
    
    return recommendations

def main():
    """Run all diagnostic tests and output results."""
    print("\n========================================================")
    print("      UI DETECTION MODULE DIAGNOSTIC TOOL")
    print("========================================================\n")
    
    print("This tool will check for required dependencies and test")
    print("the functionality of the UI detection module components.\n")
    
    # Check Python version
    print("\n--- Python Environment ---")
    python_version = check_python_version()
    
    # Check dependencies
    print("\n--- Dependency Check ---")
    dep_results = check_required_dependencies()
    
    if dep_results["all_installed"]:
        print("✅ All required dependencies are installed.")
    else:
        print(f"❌ Missing dependencies: {', '.join(dep_results['missing_packages'])}")
    
    # Test screenshot functionality
    print("\n--- Screenshot Functionality Test ---")
    screenshot_result = test_screenshot_functionality()
    
    if screenshot_result["success"]:
        print("✅ Screenshot functionality is working.")
    else:
        print(f"❌ Screenshot functionality failed: {screenshot_result.get('error', 'Unknown error')}")
    
    # Test OCR functionality if possible
    print("\n--- OCR Functionality Test ---")
    ocr_result = test_ocr_functionality()
    
    if ocr_result["success"]:
        print(f"✅ OCR functionality is working. Detected {ocr_result.get('regions_count', 0)} text regions.")
    else:
        print(f"❌ OCR functionality failed: {ocr_result.get('error', 'Unknown error')}")
    
    # Test YOLO functionality if possible
    print("\n--- YOLO UI Detection Test ---")
    yolo_result = test_yolo_functionality()
    
    if yolo_result["success"]:
        print(f"✅ YOLO UI detection is working. Detected {yolo_result.get('elements_count', 0)} UI elements.")
    else:
        print(f"❌ YOLO UI detection failed: {yolo_result.get('error', 'Unknown error')}")
    
    # Summary and recommendations
    print("\n========================================================")
    print("                      SUMMARY")
    print("========================================================\n")
    
    # Count passed/failed tests
    tests = [
        ("Screenshot", screenshot_result["success"]),
        ("OCR", ocr_result.get("success", False)),
        ("YOLO UI Detection", yolo_result.get("success", False))
    ]
    
    passed = sum(1 for _, success in tests if success)
    total = len(tests)
    
    print(f"Tests passed: {passed}/{total}")
    
    for name, success in tests:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} - {name}")
    
    # Installation recommendations if needed
    if not dep_results["all_installed"]:
        print("\n--- Installation Recommendations ---")
        print("To install missing dependencies, run the following commands:")
        print()
        
        for recommendation in generate_installation_recommendations(dep_results):
            print(recommendation)
    
    print("\n========================================================")
    print("If UI detection is still not working after installing dependencies,")
    print("check for circular imports or other issues in the codebase.")
    print("========================================================\n")

if __name__ == "__main__":
    main() 