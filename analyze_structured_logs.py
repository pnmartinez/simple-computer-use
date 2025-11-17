#!/usr/bin/env python3
"""
Script para analizar logs estructurados del servicio LLM Control.
Extrae y analiza eventos JSON de los logs para identificar patrones de uso.
"""

import json
import re
import sys
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

def extract_json_logs(log_file):
    """Extrae todas las líneas JSON de los logs."""
    json_logs = []
    json_pattern = re.compile(r'\{.*"event".*\}')
    
    try:
        # Check if it's a JSONL file (structured log file)
        if log_file.endswith('.jsonl'):
            with open(log_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        log_entry = json.loads(line)
                        # Extract event from data field or directly
                        event_data = log_entry.get('data') or log_entry
                        if 'event' in event_data:
                            json_logs.append({
                                'line': line_num,
                                'raw': line,
                                'event': event_data
                            })
                    except json.JSONDecodeError:
                        pass
        else:
            # Regular log file - extract JSON from log messages
            with open(log_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    # Buscar JSON en el mensaje
                    if '"event"' in line:
                        # Intentar extraer el JSON del mensaje
                        if '"message":' in line:
                            # El JSON puede estar en el campo message
                            try:
                                # Buscar el JSON dentro del mensaje
                                json_match = json_pattern.search(line)
                                if json_match:
                                    try:
                                        event_data = json.loads(json_match.group())
                                        json_logs.append({
                                            'line': line_num,
                                            'raw': line.strip(),
                                            'event': event_data
                                        })
                                    except json.JSONDecodeError:
                                        # Intentar extraer del campo message
                                        if '"message": "' in line:
                                            msg_start = line.find('"message": "') + 12
                                            msg_end = line.find('"', msg_start)
                                            if msg_end > msg_start:
                                                msg_content = line[msg_start:msg_end]
                                                try:
                                                    event_data = json.loads(msg_content)
                                                    json_logs.append({
                                                        'line': line_num,
                                                        'raw': line.strip(),
                                                        'event': event_data
                                                    })
                                                except json.JSONDecodeError:
                                                    pass
                            except Exception as e:
                                pass
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo {log_file}")
        return []
    except Exception as e:
        print(f"Error leyendo archivo: {e}")
        return []
    
    return json_logs

def analyze_events(json_logs):
    """Analiza los eventos extraídos y genera estadísticas."""
    stats = {
        'total_events': len(json_logs),
        'event_types': Counter(),
        'command_steps': [],
        'ui_searches': [],
        'ui_detections': [],
        'action_types': Counter(),
        'errors': []
    }
    
    for log_entry in json_logs:
        event = log_entry.get('event', {})
        event_type = event.get('event', 'unknown')
        stats['event_types'][event_type] += 1
        
        # Analizar eventos de comandos
        if event_type.startswith('command.'):
            if event_type == 'command.step.start':
                step_data = event.get('data', {})
                stats['command_steps'].append({
                    'step': step_data.get('step_original', ''),
                    'normalized': step_data.get('step_normalized', ''),
                    'handler': None  # Se llenará con el resultado
                })
            elif event_type == 'command.step.result':
                step_data = event.get('data', {})
                handler = step_data.get('handler', 'unknown')
                stats['action_types'][handler] += 1
                if stats['command_steps']:
                    stats['command_steps'][-1]['handler'] = handler
                    stats['command_steps'][-1]['success'] = step_data.get('success', False)
            elif event_type == 'command.keyboard_action':
                action_data = event.get('data', {})
                keys = action_data.get('keys', [])
                for key_combo in keys:
                    key_str = '+'.join(key_combo) if isinstance(key_combo, list) else str(key_combo)
                    stats['action_types'][f'keyboard:{key_str}'] += 1
            elif event_type == 'command.typing_action':
                action_data = event.get('data', {})
                text_len = action_data.get('text_length', 0)
                stats['action_types'][f'typing:{text_len}chars'] += 1
        
        # Analizar eventos de UI
        elif event_type.startswith('ui_element_search'):
            if event_type == 'ui_element_search_success':
                search_data = event.get('selected_match', {})
                stats['ui_searches'].append({
                    'query': event.get('query', ''),
                    'type': search_data.get('type', 'unknown'),
                    'score': search_data.get('score', 0),
                    'coordinates': search_data.get('coordinates', {}),
                    'total_matches': event.get('total_matches', 0)
                })
            elif event_type == 'ui_element_search_no_match':
                stats['ui_searches'].append({
                    'query': event.get('query', ''),
                    'success': False,
                    'elements_analyzed': event.get('elements_analyzed', 0)
                })
        
        elif event_type.startswith('ui_detection'):
            if event_type == 'ui_detection_complete':
                stats['ui_detections'].append({
                    'total_elements': event.get('total_elements', 0),
                    'element_types': event.get('element_types', {}),
                    'method': event.get('detection_method', 'unknown')
                })
    
    return stats

def print_report(stats):
    """Imprime un reporte de análisis."""
    print("=" * 80)
    print("REPORTE DE ANÁLISIS DE LOGS ESTRUCTURADOS")
    print("=" * 80)
    print()
    
    print(f"Total de eventos estructurados encontrados: {stats['total_events']}")
    print()
    
    print("TIPOS DE EVENTOS:")
    print("-" * 80)
    for event_type, count in stats['event_types'].most_common():
        print(f"  {event_type:40} {count:>5} veces")
    print()
    
    if stats['command_steps']:
        print("ANÁLISIS DE COMANDOS:")
        print("-" * 80)
        print(f"  Total de pasos procesados: {len(stats['command_steps'])}")
        
        handlers = Counter([s.get('handler', 'unknown') for s in stats['command_steps'] if s.get('handler')])
        print(f"\n  Handlers utilizados:")
        for handler, count in handlers.most_common():
            print(f"    {handler:30} {count:>5} veces")
        
        successful = sum(1 for s in stats['command_steps'] if s.get('success', False))
        print(f"\n  Pasos exitosos: {successful}/{len(stats['command_steps'])} ({successful*100/len(stats['command_steps']):.1f}%)")
        print()
    
    if stats['ui_searches']:
        print("ANÁLISIS DE BÚSQUEDAS DE ELEMENTOS UI:")
        print("-" * 80)
        successful_searches = [s for s in stats['ui_searches'] if s.get('success') is not False and 'score' in s]
        failed_searches = [s for s in stats['ui_searches'] if s.get('success') is False]
        
        print(f"  Búsquedas exitosas: {len(successful_searches)}")
        print(f"  Búsquedas fallidas: {len(failed_searches)}")
        
        if successful_searches:
            avg_score = sum(s.get('score', 0) for s in successful_searches) / len(successful_searches)
            print(f"  Puntuación promedio: {avg_score:.2f}")
            
            element_types = Counter([s.get('type', 'unknown') for s in successful_searches])
            print(f"\n  Tipos de elementos encontrados:")
            for elem_type, count in element_types.most_common():
                print(f"    {elem_type:30} {count:>5} veces")
        print()
    
    if stats['ui_detections']:
        print("ANÁLISIS DE DETECCIÓN DE UI:")
        print("-" * 80)
        total_detections = len(stats['ui_detections'])
        if total_detections > 0:
            avg_elements = sum(d.get('total_elements', 0) for d in stats['ui_detections']) / total_detections
            print(f"  Detecciones realizadas: {total_detections}")
            print(f"  Elementos promedio por detección: {avg_elements:.1f}")
            
            methods = Counter([d.get('method', 'unknown') for d in stats['ui_detections']])
            print(f"\n  Métodos de detección utilizados:")
            for method, count in methods.most_common():
                print(f"    {method:30} {count:>5} veces")
        print()
    
    if stats['action_types']:
        print("TIPOS DE ACCIONES EJECUTADAS:")
        print("-" * 80)
        for action, count in stats['action_types'].most_common():
            print(f"  {action:40} {count:>5} veces")
        print()
    
    print("=" * 80)

def main():
    """Función principal."""
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    else:
        # Try to find structured log file automatically
        structured_logs_dir = Path('structured_logs')
        if structured_logs_dir.exists():
            # Get today's log file
            today_file = structured_logs_dir / f"structured_events_{datetime.now().strftime('%Y%m%d')}.jsonl"
            if today_file.exists():
                log_file = str(today_file)
                print(f"Usando archivo de logs estructurados de hoy: {log_file}")
            else:
                # Try to find any JSONL file
                jsonl_files = list(structured_logs_dir.glob('structured_events_*.jsonl'))
                if jsonl_files:
                    log_file = str(sorted(jsonl_files)[-1])  # Most recent
                    print(f"Usando archivo de logs estructurados más reciente: {log_file}")
                else:
                    log_file = 'new_logs.log'
        else:
            log_file = 'new_logs.log'
    
    if not Path(log_file).exists():
        print(f"Error: El archivo {log_file} no existe")
        print(f"Uso: {sys.argv[0]} [archivo_log]")
        print(f"\nBuscando archivos en structured_logs/...")
        structured_logs_dir = Path('structured_logs')
        if structured_logs_dir.exists():
            jsonl_files = list(structured_logs_dir.glob('structured_events_*.jsonl'))
            if jsonl_files:
                print("Archivos disponibles:")
                for f in sorted(jsonl_files):
                    print(f"  - {f}")
        sys.exit(1)
    
    print(f"Analizando archivo: {log_file}")
    print()
    
    json_logs = extract_json_logs(log_file)
    print(f"Extraídos {len(json_logs)} eventos estructurados")
    print()
    
    if not json_logs:
        print("No se encontraron eventos estructurados en el archivo")
        sys.exit(0)
    
    stats = analyze_events(json_logs)
    print_report(stats)

if __name__ == '__main__':
    main()

