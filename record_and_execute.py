#!/usr/bin/env python3
"""
Record audio from the microphone, send it to the server, and execute the resulting command.
This is a simple client for testing the voice command functionality.
"""

import os
import sys
import time
import argparse
import tempfile
import logging
import requests
import sounddevice as sd
import soundfile as sf
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Get the logger
logger = logging.getLogger("voice-command-client")

def check_dependencies():
    """Check if required packages are installed"""
    try:
        # First try to import the packages
        import sounddevice
        import soundfile
        import requests
        import numpy
    except ImportError as e:
        print(f"Missing required dependency: {e}")
        print("Please install the required packages:")
        print("pip install sounddevice soundfile requests numpy")
        sys.exit(1)
    except OSError as e:
        if "PortAudio" in str(e):
            print("❌ PortAudio library not found")
            print("This is a system dependency required for audio recording.")
            print("\nPlease install PortAudio on your system:")
            print("- Ubuntu/Debian: sudo apt-get install portaudio19-dev")
            print("- Fedora/RHEL: sudo dnf install portaudio-devel")
            print("- Arch Linux: sudo pacman -S portaudio")
            print("- macOS: brew install portaudio")
            print("\nAfter installing PortAudio, reinstall sounddevice:")
            print("pip uninstall -y sounddevice && pip install sounddevice")
            sys.exit(1)
        else:
            # Re-raise if it's not a PortAudio issue
            raise

def list_audio_devices():
    """List available audio input devices"""
    print("\nAvailable audio input devices:")
    print("-" * 60)
    print(f"{'ID':<5} {'Name':<30} {'Channels':<10} {'Sample Rate':<15}")
    print("-" * 60)
    
    devices = sd.query_devices()
    
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            name = device['name']
            channels = device['max_input_channels']
            sample_rate = device['default_samplerate']
            print(f"{i:<5} {name[:30]:<30} {channels:<10} {sample_rate:<15.0f}")
    
    print("\nUse --device <ID> to select a specific device")

def record_audio(device=None, duration=5, sample_rate=16000, channels=1):
    """
    Record audio from the microphone
    
    Args:
        device: Audio device ID or name
        duration: Recording duration in seconds
        sample_rate: Sample rate in Hz
        channels: Number of channels
        
    Returns:
        Path to the recorded audio file
    """
    print(f"\n🎙️ Recording audio for {duration} seconds...")
    print("Speak your command now")
    
    # Create countdown
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(0.5)
    
    print("Recording...")
    
    # Record audio
    recording = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=channels,
        device=device,
        dtype='float32'
    )
    
    # Wait for the recording to finish
    sd.wait()
    
    print("Recording finished!")
    
    # Normalize the recording
    recording = recording / np.max(np.abs(recording))
    
    # Create a temporary file for the audio
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_path = temp_file.name
    
    # Save the recording to a WAV file
    sf.write(temp_path, recording, sample_rate)
    
    print(f"Audio saved to {temp_path}")
    
    return temp_path

def send_to_server(audio_file, server_url, model_size="base", endpoint="/voice-command", translate=True):
    """
    Send the audio file to the server
    
    Args:
        audio_file: Path to the audio file
        server_url: URL of the server
        model_size: Whisper model size
        endpoint: Server endpoint
        translate: Whether to request translation (default: True)
        
    Returns:
        Server response
    """
    url = f"{server_url.rstrip('/')}{endpoint}"
    
    print(f"\n📡 Sending audio to server at {url}")
    
    with open(audio_file, 'rb') as f:
        files = {'audio_file': f}
        data = {
            'model_size': model_size,
            'translate': 'true' if translate else 'false'
        }
        
        try:
            response = requests.post(url, files=files, data=data, timeout=60)
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending audio to server: {str(e)}")
            return None

def print_response(response):
    """Print the server response"""
    if response is None:
        print("\n❌ Failed to get response from server")
        return
    
    if response.status_code != 200:
        print(f"\n❌ Server error: {response.status_code}")
        print(response.text)
        return
    
    try:
        data = response.json()
        
        print("\n🔊 Voice Command Result:")
        print("-" * 60)
        
        if "transcription" in data:
            print(f"📝 Transcription: {data['transcription']}")
        
        if "translated" in data and data["translated"]:
            print(f"🇪🇸 Translated to: {data['translation']}")
        
        if "language" in data:
            print(f"🌐 Detected Language: {data['language']}")
        
        if "steps" in data:
            print(f"🔢 Command Steps: {data['steps']}")
        
        if "result" in data:
            print(f"✅ Result: {data['result']}")
        
        if "error" in data:
            print(f"❌ Error: {data['error']}")
            
        print("-" * 60)
    except Exception as e:
        print(f"\n❌ Error parsing response: {str(e)}")
        print(response.text)

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Record audio and send it to the LLM PC Control server"
    )
    
    parser.add_argument(
        "--server", 
        type=str, 
        default="http://localhost:5000",
        help="Server URL (default: http://localhost:5000)"
    )
    
    parser.add_argument(
        "--duration", 
        type=int, 
        default=5,
        help="Recording duration in seconds (default: 5)"
    )
    
    parser.add_argument(
        "--device", 
        type=int,
        help="Audio input device ID"
    )
    
    parser.add_argument(
        "--list-devices", 
        action="store_true",
        help="List available audio input devices"
    )
    
    parser.add_argument(
        "--sample-rate", 
        type=int, 
        default=16000,
        help="Sample rate in Hz (default: 16000)"
    )
    
    parser.add_argument(
        "--transcribe-only", 
        action="store_true",
        help="Only transcribe the audio, don't execute the command"
    )
    
    parser.add_argument(
        "--whisper-model", 
        type=str, 
        choices=["tiny", "base", "small", "medium", "large"],
        default="base",
        help="Whisper model size (default: base)"
    )
    
    # Add translation options
    parser.add_argument(
        "--no-translate", 
        action="store_true",
        help="Disable automatic translation of non-English languages to English (enabled by default)"
    )
    
    return parser.parse_args()

def main():
    """Main entry point"""
    # Check dependencies
    check_dependencies()
    
    # Parse arguments
    args = parse_args()
    
    # List audio devices if requested
    if args.list_devices:
        list_audio_devices()
        sys.exit(0)
    
    # Record audio
    audio_file = record_audio(
        device=args.device,
        duration=args.duration,
        sample_rate=args.sample_rate
    )
    
    # Determine the endpoint
    endpoint = "/transcribe" if args.transcribe_only else "/voice-command"
    
    # Send to server
    response = send_to_server(
        audio_file=audio_file,
        server_url=args.server,
        model_size=args.whisper_model,
        endpoint=endpoint,
        translate=not args.no_translate
    )
    
    # Print response
    print_response(response)
    
    # Clean up
    os.unlink(audio_file)

if __name__ == "__main__":
    main() 