# Scripts de Migración a Python 3.11/3.12

Este directorio contiene scripts y herramientas para ayudar en la migración del proyecto a Python 3.11 o 3.12.

## 📁 Archivos

### Scripts de Shell

- **`verify_python_compatibility.sh`**: Verifica la compatibilidad de dependencias críticas con una versión específica de Python
- **`migrate_venv.sh`**: Migra un entorno virtual existente a Python 3.11/3.12

### Scripts de Python

- **`test_imports.py`**: Prueba todos los imports críticos del proyecto después de la migración

## 🚀 Uso

### 1. Verificar Compatibilidad

Antes de migrar, verifica que las dependencias críticas sean compatibles:

```bash
# Verificar Python 3.11
./scripts/migration/verify_python_compatibility.sh 3.11

# Verificar Python 3.12
./scripts/migration/verify_python_compatibility.sh 3.12
```

### 2. Migrar Entorno Virtual

Migra tu entorno virtual actual a Python 3.11:

```bash
./scripts/migration/migrate_venv.sh 3.11 venv venv-py311 requirements-py311.txt
```

Parámetros:
- `3.11`: Versión de Python objetivo
- `venv`: Directorio del entorno virtual antiguo
- `venv-py311`: Directorio del nuevo entorno virtual
- `requirements-py311.txt`: Archivo de dependencias actualizado

### 3. Probar Imports

Después de la migración, verifica que todos los imports funcionen:

```bash
source venv-py311/bin/activate
python scripts/migration/test_imports.py
```

## ⚠️ Notas Importantes

- Los scripts crean entornos temporales para pruebas
- Algunas dependencias (PyTorch, PaddlePaddle) pueden tardar mucho en instalarse
- PyAudio puede requerir instalación manual de dependencias del sistema
- PaddlePaddle puede no ser compatible con Python 3.12

## 🔧 Solución de Problemas

### PyAudio no se instala

```bash
# Instalar dependencias del sistema
sudo apt-get install portaudio19-dev python3-pyaudio

# O usar pipwin
pip install pipwin
pipwin install pyaudio
```

### PaddlePaddle falla

```bash
# Instalar desde fuente alternativa
pip install paddlepaddle==2.6.1 -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### NumPy version conflict

```bash
# Forzar reinstalación de NumPy
pip install --force-reinstall "numpy>=1.26.0,<2.0.0"
```

## 📚 Documentación Completa

Ver `PLAN_MIGRACION_PYTHON_3.11_3.12.md` en la raíz del proyecto para el plan completo de migración.


