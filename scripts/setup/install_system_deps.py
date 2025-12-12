#!/usr/bin/env python3
"""
System Dependency Installer for LLM PC Control

This script helps users install the required system dependencies.

Note: PortAudio installation functions are kept for legacy support but are
no longer required as pyaudio and sounddevice have been removed from the project.
Audio is received via HTTP from the Electron GUI, not recorded directly.
"""

import os
import sys
import platform
import subprocess
import argparse

def check_root_privileges():
    """Check if the script is running with root/admin privileges"""
    if platform.system().lower() == "windows":
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    else:
        return os.geteuid() == 0

def get_distribution_info():
    """Get information about the Linux distribution"""
    if not os.path.exists("/etc/os-release"):
        return "unknown", "unknown"
    
    distro_id = ""
    version = ""
    
    with open("/etc/os-release") as f:
        for line in f:
            if line.startswith("ID="):
                distro_id = line.split("=")[1].strip().strip('"')
            elif line.startswith("VERSION_ID="):
                version = line.split("=")[1].strip().strip('"')
    
    return distro_id, version

def install_portaudio():
    """Install PortAudio based on the detected operating system"""
    system = platform.system().lower()
    
    print(f"Detected operating system: {platform.system()} {platform.release()}")
    
    if system == "linux":
        distro, version = get_distribution_info()
        print(f"Detected Linux distribution: {distro} {version}")
        
        # Check for common Linux distribution families
        is_debian_based = distro in ["debian", "ubuntu", "mint", "pop", "kali", "elementary", "zorin"]
        is_fedora_based = distro in ["fedora", "rhel", "centos", "almalinux", "rocky"]
        is_arch_based = distro in ["arch", "manjaro", "endeavouros", "garuda"]
        is_suse_based = distro in ["opensuse", "suse", "sles"]
        
        if is_debian_based:
            print("\n📦 Installing PortAudio for Debian-based systems...")
            result = subprocess.run(
                ["apt-get", "update"], 
                check=False
            )
            if result.returncode != 0:
                print("❌ Failed to update package lists. Please run 'sudo apt-get update' manually.")
            
            result = subprocess.run(
                ["apt-get", "install", "-y", "portaudio19-dev"], 
                check=False
            )
            if result.returncode != 0:
                print("❌ Failed to install portaudio19-dev. Please run 'sudo apt-get install portaudio19-dev' manually.")
            else:
                print("✅ Successfully installed PortAudio!")
        
        elif is_fedora_based:
            print("\n📦 Installing PortAudio for Fedora-based systems...")
            result = subprocess.run(
                ["dnf", "install", "-y", "portaudio-devel"], 
                check=False
            )
            if result.returncode != 0:
                print("❌ Failed to install portaudio-devel. Please run 'sudo dnf install portaudio-devel' manually.")
            else:
                print("✅ Successfully installed PortAudio!")
        
        elif is_arch_based:
            print("\n📦 Installing PortAudio for Arch-based systems...")
            result = subprocess.run(
                ["pacman", "-S", "--noconfirm", "portaudio"], 
                check=False
            )
            if result.returncode != 0:
                print("❌ Failed to install portaudio. Please run 'sudo pacman -S portaudio' manually.")
            else:
                print("✅ Successfully installed PortAudio!")
        
        elif is_suse_based:
            print("\n📦 Installing PortAudio for openSUSE systems...")
            result = subprocess.run(
                ["zypper", "install", "-y", "portaudio-devel"], 
                check=False
            )
            if result.returncode != 0:
                print("❌ Failed to install portaudio-devel. Please run 'sudo zypper install portaudio-devel' manually.")
            else:
                print("✅ Successfully installed PortAudio!")
        
        else:
            print("\n❌ Unsupported Linux distribution.")
            print("Please install PortAudio manually for your distribution.")
            print("Common packages to look for: portaudio-devel, portaudio19-dev, or portaudio")
    
    elif system == "darwin":  # macOS
        print("\n📦 Installing PortAudio for macOS...")
        
        # Check if Homebrew is installed
        try:
            subprocess.run(["brew", "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ Homebrew not found. Please install Homebrew first:")
            print("    /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
            return
        
        # Install PortAudio with Homebrew
        result = subprocess.run(
            ["brew", "install", "portaudio"], 
            check=False
        )
        if result.returncode != 0:
            print("❌ Failed to install portaudio. Please run 'brew install portaudio' manually.")
        else:
            print("✅ Successfully installed PortAudio!")
    
    elif system == "windows":
        print("\n📦 Windows systems:")
        print("PortAudio is included in the Windows wheels for sounddevice.")
        print("If you encounter issues, try reinstalling the sounddevice package:")
        print("    pip uninstall -y sounddevice")
        print("    pip install sounddevice")
    
    else:
        print(f"\n❌ Unsupported operating system: {system}")
        print("Please install PortAudio manually for your system.")

def reinstall_sounddevice():
    """Reinstall the sounddevice package"""
    print("\n📦 Reinstalling sounddevice package...")
    
    # Uninstall first
    result = subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", "sounddevice"], 
        check=False
    )
    
    # Then install again
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "sounddevice"], 
        check=False
    )
    
    if result.returncode != 0:
        print("❌ Failed to reinstall sounddevice. Please run 'pip install sounddevice' manually.")
    else:
        print("✅ Successfully reinstalled sounddevice!")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Install system dependencies for LLM PC Control"
    )
    
    parser.add_argument(
        "--no-reinstall", 
        action="store_true",
        help="Skip reinstalling sounddevice package"
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("🔧 System Dependency Installer for LLM PC Control")
    print("=" * 70)
    
    # Check for root privileges
    if not check_root_privileges() and platform.system().lower() != "windows":
        print("❌ This script needs to be run with administrator privileges.")
        print("Please run it again with 'sudo' (Linux/macOS) or as Administrator (Windows).")
        sys.exit(1)
    
    # Install PortAudio
    install_portaudio()
    
    # Reinstall sounddevice package
    if not args.no_reinstall:
        reinstall_sounddevice()
    
    print("\n" + "=" * 70)
    print("✅ Installation complete!")
    print("You should now be able to use the voice command functionality.")
    print("=" * 70)

if __name__ == "__main__":
    main() 