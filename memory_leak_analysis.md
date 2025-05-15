# Análisis de Fuga de Memoria y Plan de Solución

## Problema Identificado
Cada nuevo comando de voz añade aproximadamente 7GB al uso de RAM, haciendo que la aplicación sea insostenible para uso prolongado.

## Modelos que Ocupan Memoria

1. **Whisper (OpenAI)** 
   - Tamaño: Variable según modelo (large = ~1.5GB)
   - Ubicación: `llm_control/voice/audio.py` en la función `transcribe_audio()`
   - Uso: Transcripción de audio a texto

2. **YOLO (YOLOv8)** 
   - Tamaño: ~150-250MB
   - Ubicación: `llm_control/ui_detection/element_finder.py` en `get_ui_detector()`
   - Uso: Detección de elementos UI en capturas de pantalla

3. **PHI-3 Vision** 
   - Tamaño: ~4-5GB
   - Ubicación: `llm_control/ui_detection/element_finder.py` en `get_phi3_vision()`
   - Uso: Análisis y descripción de imágenes con visión multimodal

4. **BLIP2** 
   - Tamaño: ~2-3GB
   - Ubicación: `llm_control/ui_detection/element_finder.py` en `get_caption_model_processor()`
   - Uso: Generación de descripciones (captions) para imágenes

5. **Ollama (Gemma 3 o Llama 3)** 
   - Tamaño: Variable (12B = ~6-7GB)
   - Ubicación: `llm_control/voice/commands.py` 
   - Uso: Procesamiento de comandos y generación de acciones

6. **Modelos OCR** 
   - Tamaño: ~200-500MB
   - Ubicación: `llm_control/ui_detection/ocr.py`
   - Uso: Detección y reconocimiento de texto en imágenes

## Causas del Problema

1. **Modelos cargados pero no liberados**:
   - Los modelos son almacenados en variables globales (`_ui_detector`, `_phi3_vision`, `_blip2_model`) pero nunca se limpian explícitamente.

2. **Sin limpieza de memoria CUDA**:
   - Aunque existe `torch.cuda.empty_cache()`, no se llama consistentemente después del uso de modelos.

3. **Capturas de pantalla acumuladas**:
   - La limpieza de capturas de pantalla ocurre en hilos separados que pueden no completarse antes de la siguiente solicitud.

4. **Estructuras de datos grandes en memoria**:
   - Los resultados de procesamiento incluyen datos grandes como imágenes, resultados de OCR y debugging que pueden persistir.

5. **Singleton Pattern sin destrucción adecuada**:
   - Los modelos son implementados como singletons para reutilización, pero no hay mecanismos para liberar estos singletons.

## Plan de Solución Incremental

### Fase 1: Liberación Explícita de Modelos

1. **Modificar `audio.py` para liberar modelo Whisper**:
   ```python
   def transcribe_audio(audio_data, model_size=WHISPER_MODEL_SIZE, language=DEFAULT_LANGUAGE):
       # Código existente...
       try:
           # Cargar modelo y transcribir
           model = whisper.load_model(model_size)
           result = model.transcribe(...)
           
           # Extraer datos necesarios
           text = result.get("text", "").strip()
           language_detected = result.get("language", language)
           segments = result.get("segments", [])
           
           # Limpiar memoria
           del model
           if torch.cuda.is_available():
               torch.cuda.empty_cache()
               logger.debug("CUDA cache cleared after transcription")
           
           # Forzar recolección de basura
           import gc
           gc.collect()
           
           return {
               "text": text,
               "language": language_detected,
               "segments": segments
           }
       # Resto del código...
   ```

2. **Añadir funciones de liberación para modelos de UI Detection**:
   ```python
   # En element_finder.py
   def release_ui_models():
       """Liberar modelos de detección de UI para limpiar memoria"""
       global _ui_detector, _phi3_vision, _blip2_model
       
       if _ui_detector is not None:
           del _ui_detector
           _ui_detector = None
           
       if _phi3_vision is not None:
           del _phi3_vision
           _phi3_vision = None
           
       if _blip2_model is not None:
           del _blip2_model
           _blip2_model = None
           
       # Limpiar CUDA cache
       if torch.cuda.is_available():
           torch.cuda.empty_cache()
   ```

3. **Modificar `voice_command_endpoint` para limpiar después de cada solicitud**:
   ```python
   @app.route('/voice-command', methods=['POST'])
   @cors_preflight
   def voice_command_endpoint():
       # Código existente...
       try:
           # Procesar comando...
           return jsonify(sanitized_result)
       except Exception as e:
           # Manejar error...
       finally:
           # Limpiar modelos y memoria
           try:
               from llm_control.ui_detection.element_finder import release_ui_models
               release_ui_models()
               
               from llm_control.utils.gpu_utils import clear_gpu_memory
               clear_gpu_memory()
               
               import gc
               gc.collect()
               logger.debug("Performed memory cleanup after voice command")
           except Exception as cleanup_err:
               logger.warning(f"Error during memory cleanup: {cleanup_err}")
   ```

### Fase 2: Optimización de Capturas de Pantalla

1. **Mejorar limpieza de capturas de pantalla**:
   ```python
   # En utils.py
   def cleanup_old_screenshots(max_age_days=1, max_count=5):
       # Reducir valores predeterminados para ser más agresivo con la limpieza
       # Resto de la función sin cambios
   ```

2. **Añadir limpieza sincrónica en puntos críticos**:
   ```python
   # En get_ui_snapshot
   def get_ui_snapshot(steps_with_targets):
       # Código existente...
       
       # Limpiar capturas viejas inmediatamente (no en hilo separado)
       cleanup_old_screenshots(0.25, 3)  # Mantener solo las últimas 3 capturas de las últimas 6 horas
       
       # Resto del código...
   ```

### Fase 3: Monitoreo y Limitación de Memoria

1. **Añadir monitoreo de uso de memoria**:
   ```python
   # Nuevo archivo: memory_monitor.py
   import os
   import psutil
   import gc
   import torch
   import logging
   
   logger = logging.getLogger("memory-monitor")
   
   def log_memory_usage(tag=""):
       """Registrar uso actual de memoria"""
       process = psutil.Process(os.getpid())
       memory_info = process.memory_info()
       
       memory_usage = {
           "rss_gb": memory_info.rss / (1024 ** 3),
           "vms_gb": memory_info.vms / (1024 ** 3),
       }
       
       # Añadir info CUDA si disponible
       if hasattr(torch, 'cuda') and torch.cuda.is_available():
           memory_usage["cuda_allocated_gb"] = torch.cuda.memory_allocated() / (1024 ** 3)
           memory_usage["cuda_reserved_gb"] = torch.cuda.memory_reserved() / (1024 ** 3)
       
       logger.info(f"Memory usage {tag}: RSS={memory_usage['rss_gb']:.2f}GB, VMS={memory_usage['vms_gb']:.2f}GB")
       return memory_usage
   
   def force_memory_cleanup(threshold_gb=10.0):
       """Forzar limpieza de memoria si se supera el umbral"""
       process = psutil.Process(os.getpid())
       memory_info = process.memory_info()
       rss_gb = memory_info.rss / (1024 ** 3)
       
       if rss_gb > threshold_gb:
           logger.warning(f"Memory usage ({rss_gb:.2f}GB) exceeded threshold ({threshold_gb:.2f}GB). Forcing cleanup...")
           
           # Liberar modelos
           from llm_control.ui_detection.element_finder import release_ui_models
           release_ui_models()
           
           # Limpiar CUDA
           if hasattr(torch, 'cuda') and torch.cuda.is_available():
               torch.cuda.empty_cache()
           
           # Forzar GC
           gc.collect()
           
           # Verificar resultado
           new_memory_info = process.memory_info()
           new_rss_gb = new_memory_info.rss / (1024 ** 3)
           logger.info(f"Memory after cleanup: {new_rss_gb:.2f}GB (freed {rss_gb - new_rss_gb:.2f}GB)")
   ```

2. **Integrar monitoreo en puntos críticos**:
   ```python
   # En voice_command_endpoint
   from llm_control.utils.memory_monitor import log_memory_usage, force_memory_cleanup
   
   @app.route('/voice-command', methods=['POST'])
   @cors_preflight
   def voice_command_endpoint():
       log_memory_usage("before_processing")
       # Código existente...
       
       # Al final antes de retornar
       log_memory_usage("after_processing")
       force_memory_cleanup(threshold_gb=8.0)
       return jsonify(sanitized_result)
   ```

### Fase 4: Soluciones Arquitectónicas a Largo Plazo

1. **Aislar modelos grandes en procesos separados**:
   - Crear microservicios dedicados para transcripción y detección de UI
   - Implementar comunicación mediante API REST o gRPC
   - Los procesos aislados terminan después de cada uso, liberando memoria

2. **Implementar descarga inteligente de modelos**:
   - Añadir sistema de caché con tiempo de vida (TTL) para modelos grandes
   - Cargar modelos bajo demanda y descargarlos cuando no se usen
   - Utilizar versiones más pequeñas de modelos cuando sea posible

3. **Optimizar estructuras de datos**:
   - Limitar tamaño de historial y datos de depuración
   - Comprimir o descartar datos innecesarios
   - Implementar serialización para datos que no necesitan estar en memoria

## Conclusión

La fuga de memoria principal proviene de modelos grandes de IA que permanecen en memoria y no se liberan adecuadamente, especialmente PHI-3 Vision (~5GB) y Ollama (~7GB). Implementando las soluciones propuestas, especialmente la limpieza explícita de modelos y memoria CUDA después de cada uso, debería reducirse significativamente el consumo de memoria por cada comando de voz, haciendo la aplicación sostenible para uso prolongado. 