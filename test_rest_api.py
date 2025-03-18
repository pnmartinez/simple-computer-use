#!/usr/bin/env python3
"""
Test script for the LLM PC Control REST API.
This script demonstrates how to interact with the various REST API endpoints.
"""

import os
import sys
import time
import argparse
import json
import requests
from urllib.parse import urljoin
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_health_endpoint(base_url):
    """Test the health check endpoint"""
    url = urljoin(base_url, '/health')
    logger.info(f"Testing health endpoint: {url}")
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        print("\n✅ Health Endpoint Test")
        print("-" * 60)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Health Endpoint Test Failed: {str(e)}")
        return False

def test_api_info_endpoint(base_url):
    """Test the API info endpoint"""
    url = urljoin(base_url, '/api/info')
    logger.info(f"Testing API info endpoint: {url}")
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        print("\n✅ API Info Endpoint Test")
        print("-" * 60)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        # Save discovered endpoints for later use
        info = response.json()
        endpoints = info.get('endpoints', {})
        capabilities = info.get('capabilities', {})
        
        print("\nDiscovered Capabilities:")
        for capability, enabled in capabilities.items():
            print(f"  • {capability}: {'✅ Enabled' if enabled else '❌ Disabled'}")
        
        print("\nDiscovered Endpoints:")
        for name, endpoint_url in endpoints.items():
            print(f"  • {name}: {endpoint_url}")
        
        return endpoints
    except requests.exceptions.RequestException as e:
        print(f"\n❌ API Info Endpoint Test Failed: {str(e)}")
        return {}

def test_system_info_endpoint(base_url):
    """Test the system info endpoint"""
    url = urljoin(base_url, '/api/system-info')
    logger.info(f"Testing system info endpoint: {url}")
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        print("\n✅ System Info Endpoint Test")
        print("-" * 60)
        print(f"Status Code: {response.status_code}")
        
        # Pretty print the system info
        system_info = response.json()
        
        print("\nPlatform Information:")
        platform = system_info.get('platform', {})
        print(f"  • System: {platform.get('system')}")
        print(f"  • Release: {platform.get('release')}")
        print(f"  • Machine: {platform.get('machine')}")
        
        print("\nServer Information:")
        server = system_info.get('server', {})
        print(f"  • Uptime: {server.get('uptime')}")
        print(f"  • Started: {server.get('started')}")
        
        # Print CPU, memory, and disk info if available
        if 'cpu' in system_info:
            cpu = system_info['cpu']
            print("\nCPU Information:")
            print(f"  • Usage: {cpu.get('percent')}%")
            print(f"  • Cores: {cpu.get('cores')}")
            print(f"  • Threads: {cpu.get('threads')}")
        
        if 'memory' in system_info:
            memory = system_info['memory']
            print("\nMemory Information:")
            total_gb = memory.get('total', 0) / (1024 * 1024 * 1024)
            available_gb = memory.get('available', 0) / (1024 * 1024 * 1024)
            print(f"  • Total: {total_gb:.2f} GB")
            print(f"  • Available: {available_gb:.2f} GB")
            print(f"  • Usage: {memory.get('percent')}%")
        
        if 'disk' in system_info:
            disk = system_info['disk']
            print("\nDisk Information:")
            total_gb = disk.get('total', 0) / (1024 * 1024 * 1024)
            free_gb = disk.get('free', 0) / (1024 * 1024 * 1024)
            print(f"  • Total: {total_gb:.2f} GB")
            print(f"  • Free: {free_gb:.2f} GB")
            print(f"  • Usage: {disk.get('percent')}%")
        
        return True
    except requests.exceptions.RequestException as e:
        print(f"\n❌ System Info Endpoint Test Failed: {str(e)}")
        return False

def test_command_endpoint(base_url):
    """Test the command endpoint"""
    url = urljoin(base_url, '/command')
    logger.info(f"Testing command endpoint: {url}")
    
    test_command = "click on the button"
    
    try:
        response = requests.post(
            url, 
            json={"command": test_command},
            timeout=10
        )
        response.raise_for_status()
        
        print("\n✅ Command Endpoint Test")
        print("-" * 60)
        print(f"Command: {test_command}")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Command Endpoint Test Failed: {str(e)}")
        return False

def run_test_suite(base_url, include_command=True):
    """Run all tests"""
    print("=" * 60)
    print(f"🔍 Testing LLM PC Control REST API at {base_url}")
    print("=" * 60)
    
    # Start with the health endpoint
    if not test_health_endpoint(base_url):
        print("\n⚠️ Health endpoint test failed, but continuing with other tests...")
    
    # Test the API info endpoint
    endpoints = test_api_info_endpoint(base_url)
    
    # Test system info endpoint
    test_system_info_endpoint(base_url)
    
    # Test command endpoint if requested
    if include_command:
        test_command_endpoint(base_url)
    
    print("\n" + "=" * 60)
    print("✅ Test suite completed")
    print("=" * 60)

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Test the LLM PC Control REST API"
    )
    
    parser.add_argument(
        "--url", 
        type=str, 
        default="http://localhost:5000",
        help="Base URL of the LLM PC Control server (default: http://localhost:5000)"
    )
    
    parser.add_argument(
        "--no-command", 
        action="store_true",
        help="Skip testing the command endpoint"
    )
    
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose logging"
    )
    
    return parser.parse_args()

def main():
    """Main entry point"""
    args = parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Ensure URL has a trailing slash
    base_url = args.url
    if not base_url.endswith('/'):
        base_url += '/'
    
    # Run the test suite
    run_test_suite(base_url, not args.no_command)

if __name__ == "__main__":
    main() 