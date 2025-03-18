#!/usr/bin/env python3
"""
Command-line interface for the LLM PC Control server.
This module provides a command-line interface to start the server
with various configuration options.
"""

import os
import sys
import argparse
import logging
import ssl
import socket
import platform
import ipaddress
import click

from llm_control.server import run_server
from llm_control.main import setup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="LLM PC Control Server - Control your PC with voice commands"
    )
    
    parser.add_argument(
        "--host", 
        type=str, 
        default="0.0.0.0",
        help="Host address to bind the server to (default: 0.0.0.0 - all interfaces)"
    )
    
    parser.add_argument(
        "--port", 
        type=int, 
        default=5000,
        help="Port to bind the server to (default: 5000)"
    )
    
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="Run the server in debug mode"
    )
    
    parser.add_argument(
        "--whisper-model", 
        type=str, 
        choices=["tiny", "base", "small", "medium", "large"],
        default="base",
        help="Whisper model size to use for transcription (default: base)"
    )
    
    parser.add_argument(
        "--log-level", 
        type=str, 
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level (default: INFO)"
    )
    
    # Add translation options
    parser.add_argument(
        "--enable-translation", 
        action="store_true",
        help="Enable automatic Spanish to English translation"
    )
    
    parser.add_argument(
        "--ollama-model", 
        type=str, 
        default="llama3",
        help="Ollama model to use for translation (default: llama3)"
    )
    
    parser.add_argument(
        "--ollama-host", 
        type=str, 
        default="http://localhost:11434",
        help="Ollama API host (default: http://localhost:11434)"
    )
    
    # Add SSL/TLS options for secure WebSocket
    parser.add_argument(
        "--ssl", 
        action="store_true",
        help="Enable SSL/TLS for secure WebSocket (WSS)"
    )
    
    parser.add_argument(
        "--ssl-cert", 
        type=str, 
        help="Path to SSL certificate file (.crt or .pem)"
    )
    
    parser.add_argument(
        "--ssl-key", 
        type=str, 
        help="Path to SSL private key file (.key)"
    )
    
    parser.add_argument(
        "--android-compat", 
        action="store_true",
        help="Enable compatibility mode for Android clients using WebSockets"
    )
    
    parser.add_argument(
        "--android-wss-path", 
        type=str, 
        default="/ws",
        help="Path suffix for Android WSS connection (default: /ws)"
    )
    
    parser.add_argument(
        "--self-signed-ssl",
        action="store_true",
        help="Generate a self-signed SSL certificate automatically if none provided"
    )
    
    parser.add_argument(
        "--use-rest-api",
        action="store_true",
        help="Use REST API instead of WebSockets for Android clients"
    )
    
    return parser.parse_args()

def generate_self_signed_cert(output_dir=None):
    """Generate a self-signed SSL certificate for testing"""
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        import datetime
        
        # Create output directory if it doesn't exist
        if output_dir is None:
            output_dir = os.path.expanduser("~/.llm-pc-control/ssl")
        os.makedirs(output_dir, exist_ok=True)
        
        # Define certificate and key paths
        cert_path = os.path.join(output_dir, "server.crt")
        key_path = os.path.join(output_dir, "server.key")
        
        # Check if files already exist
        if os.path.exists(cert_path) and os.path.exists(key_path):
            logger.info(f"Self-signed certificates already exist at {output_dir}")
            return cert_path, key_path
        
        logger.info("Generating self-signed SSL certificate for testing...")
        
        # Generate a private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Get hostname for the certificate
        hostname = socket.gethostname()
        ip_addresses = []
        try:
            # Get all IP addresses
            hostname_info = socket.getaddrinfo(hostname, None)
            ip_addresses = set(addr[4][0] for addr in hostname_info)
            
            # Add localhost/127.0.0.1
            ip_addresses.add("127.0.0.1")
            
            # Try to get external IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_addresses.add(s.getsockname()[0])
            s.close()
        except Exception as e:
            logger.warning(f"Error getting IP addresses: {str(e)}")
        
        # Create a subject name
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, hostname),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "LLM PC Control Self-Signed"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Development"),
        ])
        
        # Create alternative names
        alt_names = [x509.DNSName(hostname), x509.DNSName("localhost")]
        for ip in ip_addresses:
            try:
                # Use the ipaddress module for proper IP address handling
                ip_obj = ipaddress.ip_address(ip)
                alt_names.append(x509.IPAddress(ip_obj))
            except ValueError:
                # Not a valid IP address
                logger.debug(f"Skipping invalid IP address: {ip}")
                pass
        
        # Create a certificate
        now = datetime.datetime.utcnow()
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName(alt_names),
                critical=False,
            )
            .sign(private_key, hashes.SHA256())
        )
        
        # Write the certificate and key to files
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        with open(key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ))
        
        # Set appropriate permissions
        if platform.system() != "Windows":
            os.chmod(key_path, 0o600)  # Only owner can read/write
            os.chmod(cert_path, 0o644)  # Owner can read/write, others can read
        
        logger.info(f"Generated self-signed SSL certificate at {cert_path}")
        logger.info(f"Generated private key at {key_path}")
        
        return cert_path, key_path
    
    except ImportError:
        logger.error("Missing required packages for SSL certificate generation")
        logger.error("Please install: pip install cryptography")
        return None, None
    except Exception as e:
        logger.error(f"Error generating self-signed certificate: {str(e)}")
        return None, None

def check_ssl_config(args):
    """Check SSL configuration and provide helpful messages"""
    if args.ssl:
        # If self-signed option is enabled and no certs provided, generate them
        if args.self_signed_ssl and (not args.ssl_cert or not args.ssl_key):
            cert_path, key_path = generate_self_signed_cert()
            if cert_path and key_path:
                args.ssl_cert = cert_path
                args.ssl_key = key_path
            else:
                logger.error("Failed to generate self-signed certificates")
                sys.exit(1)
        
        # Check if certificates are provided
        if not args.ssl_cert or not args.ssl_key:
            logger.error("SSL is enabled but certificate or key path is missing")
            logger.error("Please provide both --ssl-cert and --ssl-key arguments")
            logger.error("Or use --self-signed-ssl to generate them automatically")
            sys.exit(1)
        
        if not os.path.exists(args.ssl_cert):
            logger.error(f"SSL certificate file not found: {args.ssl_cert}")
            sys.exit(1)
        
        if not os.path.exists(args.ssl_key):
            logger.error(f"SSL key file not found: {args.ssl_key}")
            sys.exit(1)
        
        logger.info(f"Using SSL certificate: {args.ssl_cert}")
        logger.info(f"Using SSL key: {args.ssl_key}")
        
        return True
    
    # If Android compatibility mode is enabled, but SSL is not
    if args.android_compat and not args.ssl:
        logger.warning("Android compatibility mode is enabled, but SSL is not")
        logger.warning("The Android client uses WSS (secure WebSockets), which requires SSL")
        logger.warning("Consider enabling SSL with --ssl or --self-signed-ssl")
    
    return False

def get_network_interfaces():
    """Get all network interfaces and their IP addresses"""
    interfaces = []
    
    try:
        if platform.system() == "Windows":
            # On Windows, use a different approach
            import socket
            hostname = socket.gethostname()
            ip_addresses = socket.gethostbyname_ex(hostname)[2]
            interfaces.append(("Default", ip_addresses))
        else:
            # On Unix-like systems
            import netifaces
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addrs:
                    ip_info = addrs[netifaces.AF_INET]
                    # Get IPv4 addresses
                    ip_addresses = [addr['addr'] for addr in ip_info if 'addr' in addr]
                    if ip_addresses:
                        interfaces.append((interface, ip_addresses))
    except ImportError:
        # If netifaces is not available, use socket
        interfaces.append(("localhost", ["127.0.0.1"]))
        
        # Try to get the local IP address
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            interfaces.append(("Default", [s.getsockname()[0]]))
            s.close()
        except:
            pass
    except Exception as e:
        logger.warning(f"Error getting network interfaces: {str(e)}")
    
    # Always add localhost
    local_found = False
    for name, ips in interfaces:
        if "127.0.0.1" in ips:
            local_found = True
    
    if not local_found:
        interfaces.append(("localhost", ["127.0.0.1"]))
    
    return interfaces

@click.command()
@click.option(
    "--host",
    type=str,
    default="0.0.0.0",
    help="Host address to bind the server to (default: 0.0.0.0 - all interfaces)"
)
@click.option(
    "--port",
    type=int,
    default=5000,
    help="Port to bind the server to (default: 5000)"
)
@click.option(
    "--debug",
    is_flag=True,
    help="Run the server in debug mode"
)
@click.option(
    "--whisper-model",
    type=click.Choice(["tiny", "base", "small", "medium", "large"]),
    default="base",
    help="Whisper model size to use for transcription (default: base)"
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    help="Set the logging level (default: INFO)"
)
@click.option(
    "--enable-translation",
    is_flag=True,
    help="Enable automatic Spanish to English translation"
)
@click.option(
    "--ollama-model",
    type=str,
    default="llama3",
    help="Ollama model to use for translation (default: llama3)"
)
@click.option(
    "--ollama-host",
    type=str,
    default="http://localhost:11434",
    help="Ollama API host (default: http://localhost:11434)"
)
@click.option(
    "--ssl",
    is_flag=True,
    help="Enable SSL/TLS for secure WebSocket (WSS)"
)
@click.option(
    "--ssl-cert",
    type=str,
    help="Path to SSL certificate file (.crt or .pem)"
)
@click.option(
    "--ssl-key",
    type=str,
    help="Path to SSL private key file (.key)"
)
@click.option(
    "--self-signed-ssl",
    is_flag=True,
    help="Generate a self-signed SSL certificate automatically if none provided"
)
@click.option(
    "--android-compat",
    is_flag=True,
    help="Enable Android compatibility mode"
)
@click.option(
    "--android-wss-path",
    type=str,
    default="/ws",
    help="WebSocket path for Android clients"
)
@click.option(
    "--use-rest-api",
    is_flag=True,
    help="Use REST API instead of WebSockets for Android clients"
)
def cli_server(
    host, port, whisper_model, log_level, debug, 
    enable_translation, ollama_model, 
    ollama_host, ssl, ssl_cert, ssl_key, self_signed_ssl,
    android_compat, android_wss_path, use_rest_api
):
    """Run the LLM PC Control server"""
    # Configure logging
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')
    logging.basicConfig(level=numeric_level)
    
    # Set up SSL context if enabled
    ssl_context = None
    if ssl:
        if ssl_cert and ssl_key:
            # Use provided certificate files
            ssl_context = (ssl_cert, ssl_key)
            logger.info(f"Using SSL certificate: {ssl_cert}")
            logger.info(f"Using SSL key: {ssl_key}")
        elif self_signed_ssl:
            # Generate self-signed certificate
            from llm_control.server import create_self_signed_cert
            cert_path, key_path = create_self_signed_cert()
            if cert_path and key_path:
                ssl_context = (cert_path, key_path)
                logger.info(f"Using self-signed SSL certificate: {cert_path}")
            else:
                logger.error("Failed to generate self-signed SSL certificate")
                return
        else:
            # Use default SSL context (not recommended)
            import ssl as ssl_module
            ssl_context = ssl_module.create_default_context(
                ssl_module.Purpose.CLIENT_AUTH
            )
            logger.warning("Using default SSL context - not recommended for production")
    
    # Initialize whisper model
    import os
    from llm_control.server import get_whisper_model
    os.environ["WHISPER_MODEL_SIZE"] = whisper_model
    get_whisper_model()
    
    # Print platform information
    import platform
    logger.info(f"Platform: {platform.system()} {platform.release()} ({platform.machine()})")
    
    # Android compatibility notice
    if android_compat:
        logger.info("Android compatibility mode enabled")
        if use_rest_api:
            logger.info("Using REST API for Android clients (preferred)")
        else:
            logger.info(f"WebSocket path for Android clients: {android_wss_path}")
    
    # Run the server
    try:
        from llm_control.server import run_server
        run_server(
            host=host,
            port=port,
            debug=debug,
            translation_enabled=enable_translation,
            ollama_model=ollama_model,
            ollama_host=ollama_host,
            ssl_context=ssl_context,
            android_compat=android_compat,
            android_wss_path=android_wss_path,
            use_rest_api=use_rest_api
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception(f"Error running server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    cli_server() 