#!/usr/bin/env python3
"""
Android Client Example for LLM PC Control REST API

This script demonstrates how an Android client would interact with the
LLM PC Control server using the REST API. While this example is in Python,
the concepts and HTTP requests can be directly translated to Android/Java/Kotlin.

For Android implementation:
- Use Retrofit or OkHttp for REST API calls
- Use coroutines or RxJava for asynchronous operations
- Implement SSL certificate pinning for security
"""

import os
import sys
import time
import json
import argparse
import logging
import requests
from urllib.parse import urljoin
import base64
import tempfile
import threading
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AndroidClientSimulation:
    """
    Simulates an Android client connecting to the LLM PC Control REST API
    
    This class demonstrates the basic flow and API calls that would be made
    from an Android application.
    """
    
    def __init__(self, base_url):
        """Initialize the client with the server URL"""
        self.base_url = base_url if base_url.endswith('/') else base_url + '/'
        self.session = requests.Session()
        self.server_info = None
        self.endpoints = {}
        self.capabilities = {}
        self.command_history = []
    
    def discover_api(self):
        """
        Discover API endpoints and capabilities
        
        This is typically done when the app first connects to the server.
        """
        print("📱 Android client: Discovering API endpoints...")
        
        try:
            url = urljoin(self.base_url, '/api/info')
            response = self.session.get(url, timeout=5)
            response.raise_for_status()
            
            self.server_info = response.json()
            self.endpoints = self.server_info.get('endpoints', {})
            self.capabilities = self.server_info.get('capabilities', {})
            
            print("✅ Connected to server successfully")
            print(f"Server: {self.server_info.get('server', {}).get('name')}")
            print(f"API Version: {self.server_info.get('server', {}).get('api_version')}")
            
            print("\nServer Capabilities:")
            for capability, enabled in self.capabilities.items():
                print(f"  • {capability}: {'✅ Enabled' if enabled else '❌ Disabled'}")
            
            print("\nAvailable Endpoints:")
            for name, endpoint_url in self.endpoints.items():
                print(f"  • {name}: {endpoint_url}")
            
            return True
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to connect to server: {str(e)}")
            return False
    
    def check_server_health(self):
        """
        Check if the server is healthy
        
        Android apps would typically do this before making other requests.
        """
        if 'health' not in self.endpoints:
            print("❌ Health endpoint not available")
            return False
        
        try:
            response = self.session.get(self.endpoints['health'], timeout=5)
            response.raise_for_status()
            
            health_data = response.json()
            print(f"✅ Server is healthy")
            print(f"Timestamp: {health_data.get('timestamp')}")
            
            return True
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Server health check failed: {str(e)}")
            return False
    
    def get_system_info(self):
        """
        Get system information from the server
        
        Android apps might display this in a dashboard or settings screen.
        """
        if 'system_info' not in self.endpoints:
            print("❌ System info endpoint not available")
            return None
        
        try:
            response = self.session.get(self.endpoints['system_info'], timeout=5)
            response.raise_for_status()
            
            system_info = response.json()
            print("✅ Retrieved system information")
            
            # On Android, you might display this in a formatted UI
            platform = system_info.get('platform', {})
            server = system_info.get('server', {})
            
            print(f"System: {platform.get('system')} {platform.get('release')}")
            print(f"Server Uptime: {server.get('uptime')}")
            
            if 'cpu' in system_info:
                print(f"CPU Usage: {system_info['cpu'].get('percent')}%")
            
            if 'memory' in system_info:
                memory = system_info['memory']
                memory_percent = memory.get('percent', 0)
                print(f"Memory Usage: {memory_percent}%")
            
            return system_info
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to get system info: {str(e)}")
            return None
    
    def send_command(self, command_text):
        """
        Send a text command to the server
        
        This simulates typing a command in the Android app and sending it.
        """
        if 'command' not in self.endpoints:
            print("❌ Command endpoint not available")
            return None
        
        try:
            print(f"📱 Sending command: '{command_text}'")
            
            response = self.session.post(
                self.endpoints['command'],
                json={'command': command_text},
                timeout=10
            )
            response.raise_for_status()
            
            result = response.json()
            print("✅ Command processed successfully")
            
            # Save to command history
            self.command_history.append({
                'command': command_text,
                'result': result,
                'timestamp': time.time()
            })
            
            # Android would display this result in the UI
            print(f"Status: {result.get('status')}")
            print(f"Result: {result.get('result')}")
            
            return result
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Command failed: {str(e)}")
            return None
    
    def send_voice_command(self, audio_file_path):
        """
        Send a voice command to the server
        
        This simulates recording audio on Android and sending it for transcription
        and command execution.
        """
        if 'voice_command' not in self.endpoints:
            print("❌ Voice command endpoint not available")
            return None
        
        if not self.capabilities.get('transcription', False):
            print("❌ Server does not support transcription")
            return None
        
        try:
            print(f"📱 Sending voice command audio file: {audio_file_path}")
            
            with open(audio_file_path, 'rb') as audio_file:
                files = {'audio_file': audio_file}
                
                # In Android, you would use MultipartBody for this
                response = self.session.post(
                    self.endpoints['voice_command'],
                    files=files,
                    data={'model_size': 'base'},
                    timeout=30  # Voice commands can take longer
                )
                response.raise_for_status()
                
                result = response.json()
                print("✅ Voice command processed successfully")
                
                # Save to command history
                self.command_history.append({
                    'command': f"Voice: {result.get('transcription', 'Unknown')}",
                    'result': result,
                    'timestamp': time.time()
                })
                
                # Android would display these details in the UI
                print(f"Transcription: {result.get('transcription')}")
                if result.get('translated', False):
                    print(f"Translation: {result.get('translation')}")
                print(f"Steps: {result.get('steps')}")
                print(f"Result: {result.get('result')}")
                
                return result
        
        except FileNotFoundError:
            print(f"❌ Audio file not found: {audio_file_path}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Voice command failed: {str(e)}")
            return None
    
    def send_audio_data(self, audio_data_base64):
        """
        Send base64-encoded audio data to the server
        
        This simulates sending raw audio data from Android without saving to a file.
        """
        if 'voice_command' not in self.endpoints:
            print("❌ Voice command endpoint not available")
            return None
        
        try:
            print(f"📱 Sending base64 audio data (length: {len(audio_data_base64)} chars)")
            
            # In Android, you would use RequestBody for this
            response = self.session.post(
                self.endpoints['voice_command'],
                data={
                    'audio_data': audio_data_base64,
                    'model_size': 'base'
                },
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            print("✅ Audio data processed successfully")
            
            # Display result (would be shown in Android UI)
            print(f"Transcription: {result.get('transcription')}")
            
            return result
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Audio data processing failed: {str(e)}")
            return None
    
    def simulate_android_app(self):
        """
        Simulate the full flow of an Android application
        
        This method ties together all the individual API calls in a realistic flow.
        """
        print("\n" + "=" * 60)
        print("📱 Starting Android Client Simulation")
        print("=" * 60)
        
        # Step 1: Connect to server and discover API
        if not self.discover_api():
            print("❌ Failed to connect to server. Exiting.")
            return False
        
        # Step 2: Check server health
        if not self.check_server_health():
            print("⚠️ Server health check failed, but continuing...")
        
        # Step 3: Get system information
        system_info = self.get_system_info()
        
        # Step 4: Send a few text commands
        print("\n" + "-" * 60)
        print("📱 Simulating user typing commands")
        print("-" * 60)
        
        commands = [
            "click on the start button",
            "type 'hello world'",
            "press enter"
        ]
        
        for command in commands:
            result = self.send_command(command)
            time.sleep(1)  # Simulate delay between commands
        
        # Step 5: Show command history
        print("\n" + "-" * 60)
        print("📱 Command History")
        print("-" * 60)
        
        for i, entry in enumerate(self.command_history):
            print(f"{i+1}. {entry['command']}")
            print(f"   Result: {entry['result'].get('result', 'No result')}")
            print()
        
        print("\n" + "=" * 60)
        print("✅ Android Client Simulation Completed")
        print("=" * 60)
        
        return True

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Android Client Example for LLM PC Control REST API"
    )
    
    parser.add_argument(
        "--url", 
        type=str, 
        default="http://localhost:5000",
        help="Base URL of the LLM PC Control server (default: http://localhost:5000)"
    )
    
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--audio-file",
        type=str,
        help="Path to an audio file for voice command testing"
    )
    
    return parser.parse_args()

def main():
    """Main entry point"""
    args = parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and run the Android client simulation
    client = AndroidClientSimulation(args.url)
    client.simulate_android_app()
    
    # Test voice command if audio file is provided
    if args.audio_file:
        print("\n" + "-" * 60)
        print("📱 Testing Voice Command with Audio File")
        print("-" * 60)
        
        client.send_voice_command(args.audio_file)

if __name__ == "__main__":
    main() 