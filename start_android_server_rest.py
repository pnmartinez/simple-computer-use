#!/usr/bin/env python3
"""
Quick start script for the LLM PC Control server with Android configuration.
This script provides a simple way to start the server with settings
optimized for Android clients using REST API endpoints.
"""

import os
import sys
import argparse
import logging
import subprocess
import tempfile
import webbrowser
import datetime

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try importing QR code module, install if needed
try:
    import qrcode
except ImportError:
    logger.info("Installing qrcode package...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "qrcode[pil]"])
    import qrcode

def verify_ssl_certificate(cert_path):
    """Verify an SSL certificate and return key information"""
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        print("⚠️ Cryptography module not installed. Cannot verify SSL certificate.")
        return None
    
    try:
        with open(cert_path, 'rb') as f:
            cert_data = f.read()
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
        
        # Get certificate details
        subject = cert.subject.rfc4514_string()
        issuer = cert.issuer.rfc4514_string()
        
        # Get validity period
        not_before = cert.not_valid_before
        not_after = cert.not_valid_after
        
        # Check if self-signed
        is_self_signed = (issuer == subject)
        
        # Calculate days remaining until expiry
        days_remaining = (not_after - datetime.datetime.now()).days
        
        # Get the SAN extension for alternative names
        alt_names = []
        for ext in cert.extensions:
            if ext.oid.dotted_string == '2.5.29.17':  # Subject Alternative Name
                sans = ext.value
                for san in sans:
                    if isinstance(san, x509.DNSName):
                        alt_names.append(f"DNS:{san.value}")
                    elif isinstance(san, x509.IPAddress):
                        alt_names.append(f"IP:{san.value}")
        
        return {
            "subject": subject,
            "issuer": issuer,
            "valid_from": not_before.strftime("%Y-%m-%d"),
            "valid_until": not_after.strftime("%Y-%m-%d"),
            "days_remaining": days_remaining,
            "is_self_signed": is_self_signed,
            "alt_names": alt_names
        }
    except Exception as e:
        print(f"⚠️ Error verifying SSL certificate: {str(e)}")
        return None

def generate_qr_code(url, save_path=None):
    """Generate a QR code for the given URL and display or save it"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    if save_path:
        img.save(save_path)
        return save_path
    else:
        # Create a temporary file to save the QR code
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        img.save(temp_file.name)
        return temp_file.name

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Start LLM PC Control server for Android clients with REST API"
    )
    
    parser.add_argument(
        "--port", 
        type=int, 
        default=5000,
        help="Port to bind the server to (default: 5000)"
    )
    
    parser.add_argument(
        "--whisper-model", 
        type=str, 
        choices=["tiny", "base", "small", "medium", "large"],
        default="base",
        help="Whisper model size to use for transcription (default: base)"
    )
    
    parser.add_argument(
        "--language", 
        type=str, 
        default="es",
        help="Expected language for voice recognition (default: es - Spanish)"
    )
    
    parser.add_argument(
        "--disable-translation", 
        action="store_true",
        help="Disable automatic translation of non-English languages to English (enabled by default)"
    )
    
    parser.add_argument(
        "--no-ssl", 
        action="store_true",
        help="Disable SSL/TLS (not recommended for production)"
    )
    
    parser.add_argument(
        "--ssl-cert", 
        type=str, 
        help="Path to custom SSL certificate file (.crt or .pem)"
    )
    
    parser.add_argument(
        "--ssl-key", 
        type=str, 
        help="Path to custom SSL private key file (.key)"
    )
    
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="Run the server in debug mode with verbose logging"
    )
    
    parser.add_argument(
        "--qr", 
        action="store_true",
        help="Generate QR code for easy connection"
    )
    
    parser.add_argument(
        "--qr-file", 
        type=str, 
        help="Save QR code to this file path (PNG format)"
    )
    
    return parser.parse_args()

def get_local_ip():
    """Get the local IP address"""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't need to be reachable
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def main():
    """Main entry point"""
    args = parse_args()
    
    # Check for required dependencies
    try:
        # Check for the most essential packages
        print("📦 Installing essential dependencies...")
        
        # Install REST API dependencies
        print("🔄 Installing REST API dependencies...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", 
                              "flask>=2.0.0", "Werkzeug>=2.0.0", 
                              "cryptography>=42.0.0", "ipaddress>=1.0.23", 
                              "qrcode[pil]>=7.4.0"])
        
        print("✅ Essential dependencies installed")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Could not install all dependencies: {e}")
        print("Some server features may not work properly")
    
    # Build the command to start the server
    cmd = [sys.executable, "-m", "llm_control.cli_server"]
    
    # Add common parameters
    cmd.extend(["--host", "0.0.0.0"])  # Listen on all interfaces
    cmd.extend(["--port", str(args.port)])
    cmd.extend(["--whisper-model", args.whisper_model])
    cmd.extend(["--android-compat"])  # Keep for backward compatibility
    cmd.extend(["--use-rest-api"])  # Use REST API instead of WebSockets
    
    # Add SSL parameters
    use_ssl = not args.no_ssl
    if use_ssl:
        cmd.extend(["--ssl"])
        
        # If custom certificates are provided, use them
        if args.ssl_cert and args.ssl_key:
            cmd.extend(["--ssl-cert", args.ssl_cert])
            cmd.extend(["--ssl-key", args.ssl_key])
            
            # Verify SSL certificate
            print("\n🔒 Verifying provided SSL certificate...")
            cert_info = verify_ssl_certificate(args.ssl_cert)
            if cert_info:
                print(f"  • Subject: {cert_info['subject']}")
                print(f"  • Issuer: {cert_info['issuer']}")
                print(f"  • Valid from: {cert_info['valid_from']} to {cert_info['valid_until']}")
                print(f"  • Days remaining: {cert_info['days_remaining']}")
                if cert_info['is_self_signed']:
                    print("  • ⚠️ Self-signed certificate detected")
                    print("    Android clients will need to add a security exception")
                print("  • Alternative names:")
                for name in cert_info['alt_names']:
                    print(f"    - {name}")
        else:
            # Otherwise, use self-signed certificates
            cmd.extend(["--self-signed-ssl"])
            
            # Check for existing self-signed certificates in the default location
            ssl_dir = os.path.expanduser("~/.llm-pc-control/ssl")
            cert_path = os.path.join(ssl_dir, "server.crt")
            if os.path.exists(cert_path):
                print("\n🔒 Checking existing self-signed certificate...")
                cert_info = verify_ssl_certificate(cert_path)
                if cert_info:
                    print(f"  • Valid until: {cert_info['valid_until']}")
                    print(f"  • Days remaining: {cert_info['days_remaining']}")
                    print("  • Alternative names:")
                    for name in cert_info['alt_names']:
                        print(f"    - {name}")
                    print("\n  ⚠️ Self-signed certificate - Android clients will need to")
                    print("     add a security exception or install this certificate")
                
    # Add the language parameter
    cmd.extend(["--language", args.language])
    
    # Add translation if disabled
    if args.disable_translation:
        cmd.extend(["--disable-translation"])
    
    # Add debug mode if enabled
    if args.debug:
        cmd.extend(["--debug"])
        cmd.extend(["--log-level", "DEBUG"])
    
    # Print the command being run
    cmd_str = " ".join(cmd)
    print(f"Starting server with command:\n{cmd_str}\n")
    
    # Generate QR code with connection string if requested
    if args.qr or args.qr_file:
        try:
            # Get local IP address
            local_ip = get_local_ip()
            
            # Create API URL
            protocol = "https" if use_ssl else "http"
            port_str = f":{args.port}" if args.port != 80 else ""
            api_url = f"{protocol}://{local_ip}{port_str}/api/info"
            
            print("\n==== CONNECTION INFORMATION ====")
            print(f"API Info URL: {api_url}")
            print("Use this URL in your Android client app to configure connection")
            
            # Generate and display QR code
            qr_path = args.qr_file if args.qr_file else None
            qr_file = generate_qr_code(api_url, qr_path)
            
            print(f"\nQR Code generated: {qr_file}")
            print("Scan this QR code with your Android client app to connect")
            
            # Try to open the QR code in the default image viewer
            if args.qr:
                try:
                    webbrowser.open(f"file://{qr_file}")
                except Exception as e:
                    print(f"Could not open QR code: {str(e)}")
            
            print("===========================\n")
        except Exception as e:
            print(f"Error generating QR code: {str(e)}")
    
    # Run the command
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Error running server: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 