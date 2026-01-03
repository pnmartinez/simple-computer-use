# Resumen de Servicios LLM Control

## Servicios del Sistema Encontrados

### 1. Servicio a Nivel de Usuario: llm-control.service

**Ubicación del Archivo de Configuración:**
- `/home/nava/.config/systemd/user/llm-control.service`

**Estado:**
- Activo y en ejecución
- Habilitado para inicio automático

**Configuración del Servicio:**
```
[Unit]
Description=LLM Control Voice Server Service
After=network.target

[Service]
Type=simple
ExecStart=/home/nava/start-llm-control.sh
Restart=always
StandardOutput=journal
StandardError=journal
SyslogIdentifier=llm-control

[Install]
WantedBy=default.target
```

**Script de Inicio:**
El servicio ejecuta el script `/home/nava/start-llm-control.sh` que:
- Activa el entorno de Conda "autogui"
- Inicia el servidor de voz con el comando: `python -m llm_control voice-server --whisper-model large --ssl --ollama-model gemma3:12b`

**Funcionalidad:**
- Proporciona un servidor de control por voz
- Gestiona capturas de pantalla
- Procesa comandos del cliente web
- Mantiene un historial de comandos y favoritos

**Uso de Recursos:**
- Memoria: Aproximadamente 35.6 GB
- CPU: Uso moderado (alrededor de 10 minutos de CPU en tiempo de ejecución)

### 2. Servicio a Nivel de Sistema: ollama.service

**Ubicación del Archivo de Configuración:**
- `/etc/systemd/system/ollama.service`

**Estado:**
- Activo y en ejecución
- Habilitado para inicio automático

**Configuración del Servicio:**
```
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart=/usr/local/bin/ollama serve
User=ollama
Group=ollama
Restart=always
RestartSec=3
Environment="PATH=/home/nava/miniconda3/bin:[...]"

[Install]
WantedBy=default.target
```

**Funcionalidad:**
- Ejecuta el servicio Ollama para inferencia de modelos LLM
- Expone una API REST en localhost:11434
- Es utilizado por el servicio llm-control para procesar comandos de lenguaje natural

**Uso de Recursos:**
- Memoria: Aproximadamente 7.9 GB
- Posibles advertencias de uso de VRAM de GPU

## Interacción entre Servicios

Los dos servicios funcionan juntos:
1. `llm-control.service` proporciona la interfaz de usuario y el procesamiento de voz
2. `ollama.service` ofrece la capacidad de inferencia del modelo LLM (principalmente usando gemma3:12b)

## Administración de los Servicios

### Para el servicio llm-control:
```bash
# Verificar estado
systemctl --user status llm-control.service

# Reiniciar servicio
systemctl --user restart llm-control.service

# Ver logs
journalctl --user -u llm-control.service
```

### Para el servicio ollama:
```bash
# Verificar estado
sudo systemctl status ollama.service

# Reiniciar servicio
sudo systemctl restart ollama.service

# Ver logs
sudo journalctl -u ollama.service
``` 