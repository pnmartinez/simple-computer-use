import os
import sys
import subprocess
import pkg_resources
import logging

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def check_and_install_package(package_name, install_cmd=None, downgrade_conflicts=False):
    """Check if a package is installed, and install it if it's not"""
    try:
        pkg_resources.get_distribution(package_name)
        return True
    except pkg_resources.DistributionNotFound:
        print(f"📦 Package '{package_name}' not found. Installing...")
        if install_cmd is None:
            install_cmd = f"pip install {package_name}"
        
        try:
            result = subprocess.run(install_cmd, shell=True, check=True, 
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(f"✅ Successfully installed {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {package_name}: {e}")
            logger.error(f"Failed to install {package_name}: {e}")
            print(f"Error output: {e.stderr.decode()}")
            
            # Check if it's a version conflict and fix it if requested
            if downgrade_conflicts and "VersionConflict" in e.stderr.decode():
                print(f"Detected version conflict. Attempting to resolve...")
                
                # Special handling for numpy conflicts with ultralytics
                if package_name == "ultralytics" and "numpy" in e.stderr.decode():
                    print("Downgrading numpy to be compatible with ultralytics...")
                    try:
                        numpy_cmd = "pip install numpy<=2.1.1"
                        subprocess.run(numpy_cmd, shell=True, check=True, 
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        print("✅ Downgraded numpy successfully, retrying ultralytics installation...")
                        
                        # Retry the original installation
                        result = subprocess.run(install_cmd, shell=True, check=True, 
                                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        print(f"✅ Successfully installed {package_name}")
                        return True
                    except subprocess.CalledProcessError as numpy_err:
                        print(f"❌ Failed to downgrade numpy: {numpy_err}")
                        return False
            
            return False

def check_and_install_dependencies():
    """Check and install all required dependencies"""
    logger.info("Checking and installing dependencies...")
    
    # Essential packages
    check_and_install_package("pyautogui")
    check_and_install_package("pillow")
    check_and_install_package("numpy")
    check_and_install_package("opencv-python")
    
    # OCR packages
    check_and_install_package("easyocr")
    check_and_install_package("paddleocr")
    
    # Vision and LLM packages
    check_and_install_package("ollama")
    
    # YOLO package - use special command if needed
    check_and_install_package("ultralytics", downgrade_conflicts=True)
    
    # Image processing packages
    check_and_install_package("scikit-image")
    
    # Utility packages
    check_and_install_package("requests")
    check_and_install_package("tqdm")
    
    logger.info("Dependency check complete")
