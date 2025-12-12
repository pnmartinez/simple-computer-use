# Fix: Memory Monitor Scripts Not Found

## Problema

Los logs muestran errores relacionados con scripts de monitorización de memoria que no existen:

```
python: can't open file '/home/nava/Descargas/llm-control/scripts/memory_monitor.py': [Errno 2] No such file or directory
python: can't open file '/home/nava/Descargas/llm-control/scripts/analyze_memory_logs.py': [Errno 2] No such file or directory
```

## Causa

El script `/home/nava/start-llm-control.sh` que está siendo ejecutado por systemd tenía código (comentado o activo) que intentaba ejecutar scripts de monitorización de memoria que no existen en el repositorio.

## Solución Aplicada

1. **Actualizado el script de inicio**: Se ha limpiado `/home/nava/Descargas/llm-control/start-llm-control.sh` para eliminar todas las referencias a monitorización de memoria.

2. **Copiado al sistema**: El script actualizado se ha copiado a `/home/nava/start-llm-control.sh` (la ubicación que usa systemd).

3. **Monitorización desactivada**: La monitorización de memoria ha sido completamente desactivada ya que:
   - Los scripts `scripts/memory_monitor.py` y `scripts/analyze_memory_logs.py` no existen
   - No son necesarios para el funcionamiento del servidor
   - Causan errores en los logs sin proporcionar valor

## Verificación

Para verificar que el fix funciona:

```bash
# Verificar que el script está actualizado
cat /home/nava/start-llm-control.sh

# Reiniciar el servicio
systemctl --user restart llm-control.service

# Verificar los logs (no deberían aparecer errores de memory_monitor)
journalctl --user -u llm-control.service -f
```

## Nota

Si en el futuro se necesita monitorización de memoria, será necesario:
1. Crear los scripts `scripts/memory_monitor.py` y `scripts/analyze_memory_logs.py`
2. Descomentar y activar el código correspondiente en el script de inicio
3. Asegurarse de que las dependencias necesarias estén instaladas








