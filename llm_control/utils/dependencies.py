import os
import sys
import subprocess
import pkg_resources
import logging
import platform

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

def check_and_install_system_dependencies():
    """Check and install system dependencies required for the package"""
    logger.info("Checking system dependencies...")
    
    # Check the operating system
    system = platform.system().lower()
    
    # Note: PortAudio installation removed - pyaudio and sounddevice are no longer used
    # Audio is received via HTTP from the Electron GUI, not recorded directly
    # PortAudio installation code kept for reference but not executed
    if False and system == "linux":  # Disabled - no longer needed
        # Check for specific Linux distributions
        try:
            with open("/etc/os-release") as f:
                os_info = f.read()
            
            is_debian_based = "debian" in os_info.lower() or "ubuntu" in os_info.lower()
            is_fedora_based = "fedora" in os_info.lower() or "redhat" in os_info.lower()
            is_arch_based = "arch" in os_info.lower() or "manjaro" in os_info.lower()
            
            # Install PortAudio based on the distribution
            if is_debian_based:
                logger.info("Detected Debian/Ubuntu-based system")
                print("📦 Installing PortAudio for sound recording...")
                subprocess.run(
                    "sudo apt-get update && sudo apt-get install -y portaudio19-dev",
                    shell=True, check=False
                )
            elif is_fedora_based:
                logger.info("Detected Fedora/RedHat-based system")
                print("📦 Installing PortAudio for sound recording...")
                subprocess.run(
                    "sudo dnf install -y portaudio-devel",
                    shell=True, check=False
                )
            elif is_arch_based:
                logger.info("Detected Arch-based system")
                print("📦 Installing PortAudio for sound recording...")
                subprocess.run(
                    "sudo pacman -S --noconfirm portaudio",
                    shell=True, check=False
                )
            else:
                logger.warning("Unknown Linux distribution. Please install PortAudio manually.")
                print("⚠️ Please install PortAudio manually for your Linux distribution.")
                print("For example, on Ubuntu/Debian: sudo apt-get install portaudio19-dev")
                print("On Fedora/RHEL: sudo dnf install portaudio-devel")
                print("On Arch Linux: sudo pacman -S portaudio")
        
        except Exception as e:
            logger.error(f"Error checking Linux distribution: {str(e)}")
            print("⚠️ Could not determine Linux distribution. Please install PortAudio manually.")
    
    elif system == "darwin":  # macOS
        logger.info("Detected macOS system")
        print("📦 Installing PortAudio for sound recording...")
        subprocess.run(
            "brew install portaudio",
            shell=True, check=False
        )
    
    elif system == "windows":
        # PortAudio is included in the Windows wheels for sounddevice
        logger.info("Windows detected. PortAudio should be included in the sounddevice package.")
    
    else:
        logger.warning(f"Unknown operating system: {system}. Please install PortAudio manually.")
        print(f"⚠️ Unknown operating system: {system}. Please install PortAudio manually.")
    
    logger.info("System dependency check complete")

def check_and_install_dependencies():
    """Check and install all required dependencies"""
    logger.info("Checking and installing dependencies...")
    
    # Check system dependencies first
    check_and_install_system_dependencies()
    
    # Essential packages
    check_and_install_package("pyautogui")
    check_and_install_package("pillow")
    check_and_install_package("numpy")
    check_and_install_package("opencv-python")
    
    # OCR packages
    check_and_install_package("easyocr")
    # paddleocr removed - not used in current codebase (see ANALISIS_PADDLEPADDLE.md)
    
    # Vision and LLM packages
    check_and_install_package("ollama")
    
    # YOLO package - use special command if needed
    check_and_install_package("ultralytics", downgrade_conflicts=True)
    
    # Image processing packages
    check_and_install_package("scikit-image")
    
    # Server packages
    check_and_install_package("flask")
    check_and_install_package("flask-socketio", "pip install -U flask-socketio")
    
    # Speech recognition packages
    check_and_install_package("openai-whisper", "pip install -U openai-whisper")
    # Note: pyaudio, sounddevice, and soundfile removed - not used in codebase
    # Audio is received via HTTP, not recorded directly by the server
    
    # Utility packages
    check_and_install_package("requests")
    check_and_install_package("tqdm")
    
    # WebSocket and server packages
    check_and_install_package("socketio", "pip install -U python-socketio")
    check_and_install_package("eventlet")
    check_and_install_package("cryptography")
    check_and_install_package("ipaddress")
    check_and_install_package("qrcode", "pip install -U qrcode[pil]")
    try:
        import netifaces
    except ImportError:
        check_and_install_package("netifaces", "pip install -U netifaces")
    
    logger.info("Dependency check complete")
