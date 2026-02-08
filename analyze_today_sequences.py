#!/usr/bin/env python3
"""
Análisis específico de secuencias de pasos que no se tradujeron satisfactoriamente a código
en los Structured Events del día de hoy, últimas horas.
"""

import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple

def _event_payload(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract event type and payload from a log line (data or message-as-JSON)."""
    data = event.get('data')
    if data and isinstance(data, dict) and 'event' in data:
        return data
    message = event.get('message', '')
    if isinstance(message, str) and message.strip().startswith('{') and message.strip().endswith('}'):
        try:
            parsed = json.loads(message)
            if isinstance(parsed, dict) and 'event' in parsed:
                return parsed
        except json.JSONDecodeError:
            pass
    return None


class SequenceAnalyzer:
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.events = []
        self.step_starts = {}  # step_original -> event
        self.step_results = {}  # step_original -> event
        self.step_skipped = {}  # step_original -> event
        self.command_sequences = []  # Secuencias de comandos completos
        
    def load_events(self, hours_back: int = 6):
        """Carga eventos de las últimas N horas"""
        if not os.path.exists(self.log_file):
            print(f"❌ Archivo no encontrado: {self.log_file}")
            return
        
        now = datetime.now()
        events_loaded = 0
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    event = json.loads(line.strip())
                    self.events.append(event)
                    
                    # Filtrar por tiempo (últimas N horas)
                    ts_str = event.get('timestamp', '')
                    if ts_str:
                        try:
                            ts = datetime.strptime(ts_str.split(',')[0], '%Y-%m-%d %H:%M:%S')
                            if (now - ts).total_seconds() <= hours_back * 3600:
                                events_loaded += 1
                                
                                # Extraer data del evento
                                data = event.get('data', {})
                                message = event.get('message', '')
                                
                                # Si message es JSON, parsearlo
                                if message.startswith('{') and message.endswith('}'):
                                    try:
                                        message_data = json.loads(message)
                                        if 'event' in message_data:
                                            data = message_data
                                    except:
                                        pass
                                
                                if data and isinstance(data, dict) and 'event' in data:
                                    event_type = data['event']
                                    step_original = data.get('step_original', '')
                                    
                                    if event_type == 'command.step.start':
                                        self.step_starts[step_original] = {
                                            'event': event,
                                            'data': data,
                                            'timestamp': ts_str
                                        }
                                    
                                    elif event_type == 'command.step.result':
                                        self.step_results[step_original] = {
                                            'event': event,
                                            'data': data,
                                            'timestamp': ts_str
                                        }
                                    
                                    elif event_type == 'command.step.skipped':
                                        self.step_skipped[step_original] = {
                                            'event': event,
                                            'data': data,
                                            'timestamp': ts_str
                                        }
                        except Exception as e:
                            pass
                except json.JSONDecodeError:
                    continue
        
        print(f"📊 Eventos cargados: {len(self.events)}")
        print(f"📊 Eventos en últimas {hours_back} horas: {events_loaded}")
        print(f"📊 Step starts encontrados: {len(self.step_starts)}")
        print(f"📊 Step results encontrados: {len(self.step_results)}")
        print(f"📊 Step skipped encontrados: {len(self.step_skipped)}")
    
    def find_incomplete_sequences(self) -> List[Dict[str, Any]]:
        """Encuentra secuencias donde un step.start no tiene step.result ni step.skipped"""
        incomplete = []
        
        for step_original, start_info in self.step_starts.items():
            has_result = step_original in self.step_results
            has_skipped = step_original in self.step_skipped
            
            if not has_result and not has_skipped:
                incomplete.append({
                    'step_original': step_original,
                    'start_timestamp': start_info['timestamp'],
                    'start_data': start_info['data'],
                    'issue': 'step_started_but_no_result'
                })
        
        return incomplete
    
    def find_steps_without_code(self) -> List[Dict[str, Any]]:
        """Encuentra steps que tienen result pero sin código generado"""
        no_code = []
        
        for step_original, result_info in self.step_results.items():
            data = result_info['data']
            code = data.get('code', '')
            success = data.get('success', False)
            
            # Verificar si no hay código o el código es inválido
            if not code or not code.strip() or code.strip().startswith('#'):
                no_code.append({
                    'step_original': step_original,
                    'timestamp': result_info['timestamp'],
                    'handler': data.get('handler', 'unknown'),
                    'description': data.get('description', ''),
                    'success': success,
                    'code': code,
                    'issue': 'result_without_code'
                })
            elif not success:
                no_code.append({
                    'step_original': step_original,
                    'timestamp': result_info['timestamp'],
                    'handler': data.get('handler', 'unknown'),
                    'description': data.get('description', ''),
                    'success': success,
                    'code': code,
                    'issue': 'result_with_failure'
                })
        
        return no_code
    
    def find_multi_step_incomplete(self) -> List[Dict[str, Any]]:
        """Encuentra comandos con múltiples pasos donde algunos no se ejecutaron"""
        # Agrupar steps por timestamp cercano (mismo comando)
        step_groups = []
        current_group = []
        last_timestamp = None
        
        # Ordenar todos los steps por timestamp
        all_steps = []
        for step_original, start_info in self.step_starts.items():
            all_steps.append({
                'step_original': step_original,
                'timestamp': start_info['timestamp'],
                'type': 'start',
                'data': start_info['data']
            })
        
        for step_original, result_info in self.step_results.items():
            all_steps.append({
                'step_original': step_original,
                'timestamp': result_info['timestamp'],
                'type': 'result',
                'data': result_info['data']
            })
        
        for step_original, skipped_info in self.step_skipped.items():
            all_steps.append({
                'step_original': step_original,
                'timestamp': skipped_info['timestamp'],
                'type': 'skipped',
                'data': skipped_info['data']
            })
        
        # Ordenar por timestamp
        all_steps.sort(key=lambda x: x['timestamp'])
        
        # Agrupar por comandos (steps dentro de 30 segundos)
        for step in all_steps:
            try:
                ts = datetime.strptime(step['timestamp'].split(',')[0], '%Y-%m-%d %H:%M:%S')
                
                if last_timestamp and (ts - last_timestamp).total_seconds() > 30:
                    if current_group:
                        step_groups.append(current_group)
                    current_group = []
                
                current_group.append(step)
                last_timestamp = ts
            except:
                continue
        
        if current_group:
            step_groups.append(current_group)
        
        # Analizar grupos para encontrar incompletos
        incomplete_groups = []
        
        for group in step_groups:
            # Contar starts, results y skipped
            starts = {}
            results = {}
            skipped = {}
            
            for step in group:
                step_original = step['step_original']
                if step['type'] == 'start':
                    starts[step_original] = step
                elif step['type'] == 'result':
                    results[step_original] = step
                elif step['type'] == 'skipped':
                    skipped[step_original] = step
            
            # Verificar si hay pasos sin completar
            incomplete_steps = []
            for step_original in starts:
                if step_original not in results and step_original not in skipped:
                    incomplete_steps.append(step_original)
            
            # Si hay múltiples pasos y algunos están incompletos
            if len(starts) > 1 and incomplete_steps:
                incomplete_groups.append({
                    'timestamp': group[0]['timestamp'] if group else None,
                    'total_steps': len(starts),
                    'completed_steps': len(results),
                    'skipped_steps': len(skipped),
                    'incomplete_steps': incomplete_steps,
                    'steps': [s['step_original'] for s in group if s['type'] == 'start'],
                    'issue': 'multi_step_incomplete'
                })
        
        return incomplete_groups
    
    def find_failed_click_diagnostics(
        self,
        keywords: Optional[List[str]] = None,
        hours_back: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find failed command.ui_element_action events and correlate with preceding
        ui_element_search_* to diagnose OCR vs matching (e.g. 'focus'/'plot' in sample_elements).
        """
        if keywords is None:
            keywords = ["focus", "plot"]
        failed = []
        # Events are in chronological order; get optional time filter
        now = datetime.now()
        
        for i, event in enumerate(self.events):
            payload = _event_payload(event)
            if not payload or payload.get('event') != 'command.ui_element_action':
                continue
            if payload.get('success', True):
                continue
            
            # Optional filter by time
            if hours_back is not None:
                ts_str = event.get('timestamp', '')
                if ts_str:
                    try:
                        ts = datetime.strptime(ts_str.split(',')[0], '%Y-%m-%d %H:%M:%S')
                        if (now - ts).total_seconds() > hours_back * 3600:
                            continue
                    except Exception:
                        pass
            
            reason = payload.get('reason', '')
            description = payload.get('description', '')
            step = payload.get('step', '') or description
            available_elements = payload.get('available_elements', 0)
            
            # Look backward for the most recent ui_element_search_* event
            preceding_search = None
            for j in range(i - 1, -1, -1):
                p = _event_payload(self.events[j])
                if not p:
                    continue
                ev = p.get('event', '')
                if ev in (
                    'ui_element_search_no_matches',
                    'ui_element_search_no_match',
                    'ui_element_search_failed',
                ):
                    preceding_search = {
                        'event': ev,
                        'query_original': p.get('query_original') or p.get('query', ''),
                        'sample_elements': p.get('sample_elements', []),
                        'top_candidate': p.get('top_candidate'),
                        'available_elements_count': p.get('available_elements_count'),
                        'elements_analyzed': p.get('elements_analyzed'),
                        'top_match_score': p.get('top_match_score'),
                        'reason': p.get('reason'),
                    }
                    break
                if ev == 'ui_element_search_success':
                    break
            
            # Check if any keyword appears in sample_elements or top_candidate
            text_found_in_sample = False
            if preceding_search:
                texts_to_check = []
                for elem in preceding_search.get('sample_elements') or []:
                    t = elem.get('text', '') if isinstance(elem, dict) else ''
                    if t:
                        texts_to_check.append(t.lower())
                tc = preceding_search.get('top_candidate')
                if isinstance(tc, dict) and tc.get('text'):
                    texts_to_check.append(tc['text'].lower())
                for kw in keywords:
                    if any(kw.lower() in t for t in texts_to_check):
                        text_found_in_sample = True
                        break
            
            failed.append({
                'timestamp': event.get('timestamp', ''),
                'step': step,
                'reason': reason,
                'description': description,
                'available_elements': available_elements,
                'preceding_search': preceding_search,
                'text_found_in_sample': text_found_in_sample,
                'keywords_checked': keywords,
            })
        
        return failed
    
    def analyze_sequences(self):
        """Ejecuta todos los análisis y genera reporte"""
        print("\n" + "="*80)
        print("🔍 ANÁLISIS: Secuencias no traducidas a código")
        print("="*80)
        
        # 1. Steps que empezaron pero no tienen result ni skipped
        incomplete = self.find_incomplete_sequences()
        print(f"\n1️⃣  Steps que empezaron pero no completaron:")
        print(f"   Total: {len(incomplete)}")
        if incomplete:
            print(f"\n   Ejemplos (últimos 10):")
            for i, item in enumerate(incomplete[-10:], 1):
                print(f"   {i}. '{item['step_original'][:60]}...'")
                print(f"      Timestamp: {item['start_timestamp'][:19]}")
                print(f"      Issue: {item['issue']}")
        
        # 2. Steps con result pero sin código
        no_code = self.find_steps_without_code()
        print(f"\n2️⃣  Steps con result pero sin código válido:")
        print(f"   Total: {len(no_code)}")
        if no_code:
            print(f"\n   Ejemplos (últimos 10):")
            for i, item in enumerate(no_code[-10:], 1):
                print(f"   {i}. '{item['step_original'][:60]}...'")
                print(f"      Handler: {item['handler']}")
                print(f"      Success: {item['success']}")
                print(f"      Code: '{item['code'][:50] if item['code'] else 'N/A'}...'")
                print(f"      Issue: {item['issue']}")
        
        # 3. Comandos multi-paso incompletos
        multi_incomplete = self.find_multi_step_incomplete()
        print(f"\n3️⃣  Comandos multi-paso con pasos incompletos:")
        print(f"   Total: {len(multi_incomplete)}")
        if multi_incomplete:
            print(f"\n   Ejemplos (últimos 10):")
            for i, group in enumerate(multi_incomplete[-10:], 1):
                print(f"   {i}. Timestamp: {group['timestamp'][:19] if group['timestamp'] else 'N/A'}")
                print(f"      Pasos totales: {group['total_steps']}")
                print(f"      Completados: {group['completed_steps']}")
                print(f"      Saltados: {group['skipped_steps']}")
                print(f"      Incompletos: {len(group['incomplete_steps'])}")
                print(f"      Steps: {', '.join([s[:30] for s in group['steps'][:3]])}...")
        
        # 4. Steps skipped
        print(f"\n4️⃣  Steps explícitamente saltados:")
        print(f"   Total: {len(self.step_skipped)}")
        if self.step_skipped:
            print(f"\n   Ejemplos (últimos 10):")
            for i, (step_original, skipped_info) in enumerate(list(self.step_skipped.items())[-10:], 1):
                data = skipped_info['data']
                print(f"   {i}. '{step_original[:60]}...'")
                print(f"      Razón: {data.get('reason', 'N/A')}")
                print(f"      Timestamp: {skipped_info['timestamp'][:19]}")
        
        # 5. Failed UI element actions (clicks) with OCR vs matching diagnosis
        failed_clicks = self.find_failed_click_diagnostics(keywords=["focus", "plot"])
        print(f"\n5️⃣  Clicks fallidos (command.ui_element_action success=false):")
        print(f"   Total: {len(failed_clicks)}")
        if failed_clicks:
            focus_plot = [f for f in failed_clicks if any(k in (f.get('step') or '').lower() or k in (f.get('description') or '').lower() for k in ('focus', 'plot'))]
            print(f"   Con 'focus'/'plot' en step/description: {len(focus_plot)}")
            print(f"\n   Ejemplos (últimos 10):")
            for i, item in enumerate(failed_clicks[-10:], 1):
                step = (item.get('step') or item.get('description') or '')[:60]
                print(f"   {i}. step: '{step}...'")
                print(f"      reason: {item.get('reason')}, available_elements: {item.get('available_elements')}")
                pre = item.get('preceding_search')
                if pre:
                    print(f"      search_event: {pre.get('event')}, query: '{pre.get('query_original', '')[:40]}'")
                    if pre.get('top_candidate'):
                        tc = pre['top_candidate']
                        print(f"      top_candidate: type={tc.get('type')}, text='{tc.get('text', '')[:40]}', score={tc.get('score')}")
                    sample = pre.get('sample_elements') or []
                    if sample:
                        texts = [s.get('text', '')[:30] for s in sample if isinstance(s, dict)]
                        print(f"      sample_elements (texts): {texts}")
                print(f"      text_found_in_sample (focus/plot): {item.get('text_found_in_sample')}")
        
        return {
            'incomplete_sequences': incomplete,
            'steps_without_code': no_code,
            'multi_step_incomplete': multi_incomplete,
            'skipped_steps': list(self.step_skipped.items()),
            'failed_click_diagnostics': failed_clicks,
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Analiza secuencias no traducidas a código")
    parser.add_argument("--log-file",
                       default=None,
                       help="Archivo de log estructurado (default: structured_logs/structured_events_YYYYMMDD.jsonl)")
    parser.add_argument("--hours", type=int, default=6,
                       help="Horas hacia atrás para analizar")
    
    args = parser.parse_args()
    log_file = args.log_file
    if not log_file:
        log_file = f"structured_logs/structured_events_{datetime.now().strftime('%Y%m%d')}.jsonl"
    
    analyzer = SequenceAnalyzer(log_file)
    analyzer.load_events(hours_back=args.hours)
    results = analyzer.analyze_sequences()
    
    print("\n" + "="*80)
    print("✅ Análisis completado")
    print("="*80)


if __name__ == "__main__":
    main()
