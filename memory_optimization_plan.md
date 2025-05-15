# Plan de Optimización de Memoria para LLM Control

## Problemas Identificados

1. **Error de memoria CUDA**: 
   - Se han detectado errores "CUDA out of memory" durante la transcripción de audio
   - El proceso consume aproximadamente 7.93 GiB de memoria en uso
   - La GPU tiene 15.70 GiB de capacidad total con muy poca memoria libre disponible

2. **Errores de procesamiento de imágenes**:
   - Múltiples errores "[Errno 36] File name too long" al generar subtítulos para imágenes
   - Problemas al manejar datos codificados en base64 como nombres de archivo

3. **Fallos en el inicio del servicio**:
   - Numerosos registros muestran "Failed with result 'exit-code'"
   - Errores relacionados con la variable "DISPLAY" ausente

## Plan de Acción Recomendado

### Fase 1: Corrección Inmediata de Memoria

1. **Implementar liberación explícita en `audio.py`**:
   ```python
   # Después de la transcripción
   del model
   torch.cuda.empty_cache()  # Limpiar caché CUDA
   ```

2. **Corregir manejo de capturas de pantalla**:
   - Verificar funcionamiento de `cleanup_old_screenshots`
   - Reducir valores para `SCREENSHOT_MAX_COUNT` y `SCREENSHOT_MAX_AGE_DAYS`

3. **Implementar recolección de basura**:
   ```python
   # Al final de voice_command_endpoint en server.py
   import gc
   gc.collect()
   ```

### Fase 2: Mejoras Estructurales

4. **Patrón Singleton para modelo Whisper**:
   - Crear clase gestora que reutilice el modelo en lugar de cargarlo cada vez
   - Implementar métodos de limpieza adecuados

5. **Optimizar objetos de gran tamaño**:
   - Limitar tamaño de información de depuración almacenada
   - Reducir tamaño del historial almacenado
   - Recortar objetos grandes antes de almacenarlos

6. **Monitoreo de memoria**:
   - Agregar registro de uso de memoria antes/después del procesamiento
   - Crear endpoint para verificar uso actual de memoria

### Fase 3: Soluciones a Largo Plazo

7. **Aislamiento de procesos**:
   - Ejecutar transcripción Whisper en proceso separado que pueda terminarse
   - Considerar arquitectura de microservicios para operaciones intensivas

8. **Implementar agrupación de recursos**:
   - Crear pool de trabajadores para procesar comandos
   - Implementar tiempos de espera y límites de recursos

9. **Métodos alternativos de transcripción**:
   - Evaluar opciones de transcripción más ligeras
   - Agregar opción para usar servicios de transcripción en la nube

## Configuración de CUDA Recomendada

Añadir la siguiente variable de entorno al script de inicio:
```
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
```

Esta configuración ayudará a evitar la fragmentación de memoria en CUDA.

## Monitoreo y Diagnóstico

### Comandos útiles para diagnóstico:

```bash
# Ver uso de memoria en tiempo real
journalctl --user -u llm-control.service --follow | grep -i "memory\|ram\|leak"

# Buscar errores específicos
journalctl --user -u llm-control.service | grep -i "error\|exception\|fail"

# Monitorear uso de GPU
nvidia-smi -l 1

# Verificar memoria del sistema
free -h
```

Estas recomendaciones deberían reducir significativamente los problemas de memoria y estabilizar el servicio mientras se implementan las soluciones más estructurales. 