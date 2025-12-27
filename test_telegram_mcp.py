#!/usr/bin/env python3
"""
Script de prueba para el servidor MCP de Telegram
"""
import asyncio
import os
import sys
import pathlib
import json
from typing import Optional

# Añadir el directorio actual al path
sys.path.insert(0, '/home/nava/Descargas/llm-control')

# Importar las funciones del servidor MCP
from telegram_mcp_server import _telegram_send_document_sync

async def test_telegram_send():
    """Prueba el envío de archivos a Telegram"""
    
    # Cargar variables de entorno
    env_file = '/home/nava/Descargas/llm-control/.env.telegram'
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    
    # Configurar variables desde archivo
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    allowed_root = os.getenv('TELEGRAM_ALLOWED_ROOT', '/home/nava/Descargas/llm-control')
    
    if not token:
        print("❌ Error: No se encontró TELEGRAM_BOT_TOKEN")
        return False
        
    if not chat_id:
        print("❌ Error: No se encontró TELEGRAM_CHAT_ID")
        return False
    
    print(f"✅ Configuración cargada:")
    print(f"   - Bot Token: {token[:10]}...")
    print(f"   - Chat ID: {chat_id}")
    print(f"   - Allowed Root: {allowed_root}")
    
    # Verificar que el archivo de prueba existe
    test_file = '/home/nava/Descargas/llm-control/test_telegram.txt'
    if not os.path.exists(test_file):
        print(f"❌ Error: No existe el archivo de prueba: {test_file}")
        return False
    
    print(f"✅ Archivo de prueba encontrado: {test_file}")
    
    try:
        # Probar el envío del archivo
        print("📤 Enviando archivo a Telegram...")
        result = await asyncio.to_thread(
            _telegram_send_document_sync,
            token=token,
            chat_id=chat_id,
            file_path=test_file,
            caption="Prueba del servidor MCP de Telegram - 2025-12-26"
        )
        
        print("✅ ¡Archivo enviado exitosamente!")
        print(f"📄 Respuesta de Telegram:")
        
        if 'result' in result:
            msg = result['result']
            print(f"   - Message ID: {msg.get('message_id')}")
            if 'document' in msg:
                doc = msg['document']
                print(f"   - File Name: {doc.get('file_name')}")
                print(f"   - File Size: {doc.get('file_size')} bytes")
                print(f"   - MIME Type: {doc.get('mime_type')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error al enviar archivo: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Iniciando prueba del servidor MCP de Telegram")
    print("=" * 60)
    
    success = asyncio.run(test_telegram_send())
    
    print("=" * 60)
    if success:
        print("🎉 ¡Prueba completada exitosamente!")
    else:
        print("💥 La prueba falló")
    
    sys.exit(0 if success else 1)
