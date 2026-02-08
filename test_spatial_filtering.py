#!/usr/bin/env python3
"""
Tests exhaustivos para el sistema de filtrado espacial.
Verifica que la separación entre target y especificación espacial funcione correctamente
en diferentes ordenamientos y casos edge.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm_control.command_processing.spatial_filter import (
    extract_spatial_specs,
    normalize_spatial_spec,
    remove_spatial_specs_from_command,
    get_grid_zones_for_spec,
    filter_elements_by_spatial_spec
)

def test_spatial_extraction():
    """Test 1: Extracción de specs espaciales en diferentes posiciones"""
    print("=" * 80)
    print("TEST 1: Extracción de specs espaciales en diferentes posiciones")
    print("=" * 80)
    
    test_cases = [
        # (comando, specs_esperadas, descripción)
        ("click arriba", ["arriba"], "Spec al final"),
        ("arriba click", ["arriba"], "Spec al inicio"),
        ("click en el botón arriba", ["arriba"], "Spec después del target"),
        ("click arriba en el botón", ["arriba"], "Spec antes del target"),
        ("arriba click en el botón", ["arriba"], "Spec al inicio con target"),
        ("click arriba izquierda", ["arriba", "izquierda"], "Dos specs juntas"),
        ("click izquierda arriba", ["arriba", "izquierda"], "Dos specs orden inverso"),
        ("click centro en Guardar", ["centro"], "Spec centro con target"),
        ("click derecha arriba", ["arriba", "derecha"], "Dos specs diferentes"),
        ("click top right", ["arriba", "derecha"], "Specs en inglés"),
        ("click superior izquierda", ["arriba", "izquierda"], "Sinónimos"),
        ("click abajo en 'Enviar'", ["abajo"], "Spec con target entre comillas"),
        ("arriba click en 'Guardar' arriba", ["arriba"], "Spec duplicada (debe normalizarse)"),
    ]
    
    passed = 0
    failed = 0
    
    for cmd, expected_specs, desc in test_cases:
        specs = extract_spatial_specs(cmd)
        normalized = normalize_spatial_spec(specs) if specs else None
        
        # Verificar que se encontraron las specs esperadas (orden no importa)
        expected_set = set(expected_specs)
        found_set = set(specs)
        
        if expected_set == found_set:
            print(f"✓ {desc}: '{cmd}' → {specs} (normalized: {normalized})")
            passed += 1
        else:
            print(f"✗ {desc}: '{cmd}'")
            print(f"  Esperado: {expected_specs}, Encontrado: {specs}")
            failed += 1
    
    print(f"\nResultado: {passed} pasados, {failed} fallidos\n")
    return failed == 0


def test_target_separation():
    """Test 2: Separación correcta de target y specs espaciales"""
    print("=" * 80)
    print("TEST 2: Separación correcta de target y specs espaciales")
    print("=" * 80)
    
    test_cases = [
        # (comando, target_esperado_en_cleaned, descripción)
        ("click arriba en Guardar", "click en Guardar", "Target después de spec"),
        ("click en Guardar arriba", "click en Guardar", "Target antes de spec"),
        ("arriba click en Guardar", "click en Guardar", "Spec al inicio"),
        ("click arriba en 'Guardar'", "click en 'Guardar'", "Target con comillas después"),
        ("click en 'Guardar' arriba", "click en 'Guardar'", "Target con comillas antes"),
        ("click izquierda en el botón Enviar", "click en el botón Enviar", "Target largo"),
        ("click en el botón Enviar izquierda", "click en el botón Enviar", "Target largo antes"),
        ("click centro en Submit", "click en Submit", "Target en inglés"),
        ("click derecha arriba en Botón", "click en Botón", "Múltiples specs"),
        ("arriba click izquierda en 'Save'", "click en 'Save'", "Múltiples specs al inicio"),
        ("click en 'Save' arriba izquierda", "click en 'Save'", "Múltiples specs al final"),
        ("click arriba en botón Guardar", "click en botón Guardar", "Target con tipo"),
        ("click en botón Guardar arriba", "click en botón Guardar", "Target con tipo antes"),
    ]
    
    passed = 0
    failed = 0
    
    for cmd, expected_cleaned, desc in test_cases:
        cleaned = remove_spatial_specs_from_command(cmd)
        cleaned_normalized = " ".join(cleaned.split())  # Normalizar espacios
        
        if expected_cleaned.lower() in cleaned_normalized.lower() or cleaned_normalized.lower() in expected_cleaned.lower():
            print(f"✓ {desc}: '{cmd}' → '{cleaned}'")
            passed += 1
        else:
            print(f"✗ {desc}: '{cmd}'")
            print(f"  Esperado contiene: '{expected_cleaned}'")
            print(f"  Obtenido: '{cleaned}'")
            failed += 1
    
    print(f"\nResultado: {passed} pasados, {failed} fallidos\n")
    return failed == 0


def test_edge_cases():
    """Test 3: Casos edge y confusos"""
    print("=" * 80)
    print("TEST 3: Casos edge y confusos")
    print("=" * 80)
    
    test_cases = [
        # (comando, descripción, verificación)
        ("click arriba", "Solo spec, sin target", lambda c, s, cl: len(s) > 0 and len(cl.split()) <= 2),
        ("click en arriba", "Target que parece spec", lambda c, s, cl: len(s) == 0 or "arriba" in cl.lower()),
        ("click en 'arriba'", "Target entre comillas que es spec", lambda c, s, cl: "'arriba'" in cl or '"arriba"' in cl),
        ("click arriba en arriba", "Target igual a spec", lambda c, s, cl: len(s) > 0 and "arriba" in cl.lower()),
        ("click centro en centro", "Target igual a spec", lambda c, s, cl: len(s) > 0 and "centro" in cl.lower()),
        ("click derecha en botón Derecha", "Target contiene palabra spec", lambda c, s, cl: len(s) > 0 and "Derecha" in cl),
        ("click izquierda en Izquierda", "Target igual a spec capitalizado", lambda c, s, cl: len(s) > 0 and "Izquierda" in cl),
        ("arriba arriba click", "Specs duplicadas", lambda c, s, cl: len(set(s)) == 1),  # Debe normalizarse a una
        ("click arriba izquierda derecha", "Tres specs", lambda c, s, cl: len(s) >= 2),
        ("click en botón", "Sin spec", lambda c, s, cl: len(s) == 0 and "botón" in cl.lower()),
        ("", "Comando vacío", lambda c, s, cl: len(s) == 0),
        ("click", "Solo acción", lambda c, s, cl: len(s) == 0),
    ]
    
    passed = 0
    failed = 0
    
    for cmd, desc, check in test_cases:
        specs = extract_spatial_specs(cmd)
        normalized = normalize_spatial_spec(specs) if specs else None
        cleaned = remove_spatial_specs_from_command(cmd)
        
        if check(cmd, specs, cleaned):
            print(f"✓ {desc}: '{cmd}' → specs: {specs}, cleaned: '{cleaned}'")
            passed += 1
        else:
            print(f"✗ {desc}: '{cmd}'")
            print(f"  Specs: {specs}, Cleaned: '{cleaned}'")
            failed += 1
    
    print(f"\nResultado: {passed} pasados, {failed} fallidos\n")
    return failed == 0


def test_grid_zones():
    """Test 4: Cálculo correcto de zonas del grid"""
    print("=" * 80)
    print("TEST 4: Cálculo correcto de zonas del grid")
    print("=" * 80)
    
    screen_size = (1920, 1080)
    width, height = screen_size
    third_w = width / 3
    third_h = height / 3
    
    test_cases = [
        # (spec, expected_zones_count, expected_total_area_ratio, descripción)
        ("arriba", 3, 1.0/3, "Fila superior completa (1/3 del área)"),
        ("abajo", 3, 1.0/3, "Fila inferior completa (1/3 del área)"),
        ("izquierda", 3, 1.0/3, "Columna izquierda completa (1/3 del área)"),
        ("derecha", 3, 1.0/3, "Columna derecha completa (1/3 del área)"),
        ("centro", 1, 1.0/9, "Celda central"),
        ("arriba-izquierda", 1, 1.0/9, "Celda arriba-izquierda"),
        ("arriba-centro", 1, 1.0/9, "Celda arriba-centro"),
        ("arriba-derecha", 1, 1.0/9, "Celda arriba-derecha"),
        ("centro-izquierda", 1, 1.0/9, "Celda centro-izquierda"),
        ("centro-derecha", 1, 1.0/9, "Celda centro-derecha"),
        ("abajo-izquierda", 1, 1.0/9, "Celda abajo-izquierda"),
        ("abajo-centro", 1, 1.0/9, "Celda abajo-centro"),
        ("abajo-derecha", 1, 1.0/9, "Celda abajo-derecha"),
    ]
    
    passed = 0
    failed = 0
    
    for spec, expected_count, expected_area_ratio, desc in test_cases:
        zones = get_grid_zones_for_spec(spec, screen_size)
        
        if len(zones) != expected_count:
            print(f"✗ {desc}: '{spec}'")
            print(f"  Esperado {expected_count} zonas, obtenido {len(zones)}")
            failed += 1
            continue
        
        # Calcular área total cubierta
        total_area = sum((right - left) * (bottom - top) for left, top, right, bottom in zones)
        screen_area = width * height
        area_ratio = total_area / screen_area
        
        # Verificar que el área es aproximadamente correcta (con tolerancia)
        if abs(area_ratio - expected_area_ratio) < 0.01:
            print(f"✓ {desc}: '{spec}' → {len(zones)} zona(s), área: {area_ratio:.3f}")
            passed += 1
        else:
            print(f"✗ {desc}: '{spec}'")
            print(f"  Esperado área ratio: {expected_area_ratio:.3f}, obtenido: {area_ratio:.3f}")
            failed += 1
    
    print(f"\nResultado: {passed} pasados, {failed} fallidos\n")
    return failed == 0


def test_element_filtering():
    """Test 5: Filtrado de elementos según zona espacial"""
    print("=" * 80)
    print("TEST 5: Filtrado de elementos según zona espacial")
    print("=" * 80)
    
    screen_size = (1920, 1080)
    width, height = screen_size
    third_w = width / 3
    third_h = height / 3
    
    # Crear elementos en cada zona del grid
    elements = []
    zone_names = []
    
    # Fila superior
    for col in range(3):
        x = int(col * third_w + third_w / 2)
        y = int(third_h / 2)
        elements.append({
            'bbox': [x - 50, y - 25, x + 50, y + 25],
            'text': f'Top-{["Left", "Center", "Right"][col]}'
        })
        zone_names.append(f'arriba-{["izquierda", "centro", "derecha"][col]}')
    
    # Fila central
    for col in range(3):
        x = int(col * third_w + third_w / 2)
        y = int(third_h + third_h / 2)
        elements.append({
            'bbox': [x - 50, y - 25, x + 50, y + 25],
            'text': f'Center-{["Left", "Center", "Right"][col]}'
        })
        zone_names.append(f'centro-{["izquierda", "centro", "derecha"][col]}')
    
    # Fila inferior
    for col in range(3):
        x = int(col * third_w + third_w / 2)
        y = int(2 * third_h + third_h / 2)
        elements.append({
            'bbox': [x - 50, y - 25, x + 50, y + 25],
            'text': f'Bottom-{["Left", "Center", "Right"][col]}'
        })
        zone_names.append(f'abajo-{["izquierda", "centro", "derecha"][col]}')
    
    test_cases = [
        # (spec, expected_count, expected_texts, descripción)
        ("arriba", 3, ["Top-Left", "Top-Center", "Top-Right"], "Fila superior"),
        ("abajo", 3, ["Bottom-Left", "Bottom-Center", "Bottom-Right"], "Fila inferior"),
        ("izquierda", 3, ["Top-Left", "Center-Left", "Bottom-Left"], "Columna izquierda"),
        ("derecha", 3, ["Top-Right", "Center-Right", "Bottom-Right"], "Columna derecha"),
        ("centro", 1, ["Center-Center"], "Celda central"),
        ("arriba-izquierda", 1, ["Top-Left"], "Celda específica"),
        ("arriba-derecha", 1, ["Top-Right"], "Celda específica"),
        ("abajo-centro", 1, ["Bottom-Center"], "Celda específica"),
    ]
    
    passed = 0
    failed = 0
    
    for spec, expected_count, expected_texts, desc in test_cases:
        filtered = filter_elements_by_spatial_spec(elements, spec, screen_size)
        filtered_texts = [e['text'] for e in filtered]
        
        if len(filtered) != expected_count:
            print(f"✗ {desc}: '{spec}'")
            print(f"  Esperado {expected_count} elementos, obtenido {len(filtered)}")
            print(f"  Elementos: {filtered_texts}")
            failed += 1
            continue
        
        # Verificar que todos los textos esperados están presentes
        if all(text in filtered_texts for text in expected_texts):
            print(f"✓ {desc}: '{spec}' → {len(filtered)} elemento(s): {filtered_texts}")
            passed += 1
        else:
            print(f"✗ {desc}: '{spec}'")
            print(f"  Esperado: {expected_texts}")
            print(f"  Obtenido: {filtered_texts}")
            failed += 1
    
    print(f"\nResultado: {passed} pasados, {failed} fallidos\n")
    return failed == 0


def test_complex_commands():
    """Test 6: Comandos complejos con múltiples componentes"""
    print("=" * 80)
    print("TEST 6: Comandos complejos con múltiples componentes")
    print("=" * 80)
    
    test_cases = [
        # (comando, descripción, verificaciones)
        (
            "click arriba en el botón 'Guardar' y luego presiona Enter",
            "Comando con múltiples acciones",
            lambda s, cl: len(s) == 1 and "Guardar" in cl and "Enter" in cl
        ),
        (
            "arriba click izquierda en 'Enviar' arriba",
            "Specs duplicadas y en diferentes posiciones",
            lambda s, cl: len(set(s)) == 2 and "Enviar" in cl
        ),
        (
            "click en el botón Guardar que está arriba a la derecha",
            "Descripción espacial en el target",
            lambda s, cl: len(s) >= 1 and "Guardar" in cl
        ),
        (
            "arriba izquierda click en botón",
            "Múltiples specs al inicio",
            lambda s, cl: len(s) == 2 and "botón" in cl.lower()
        ),
        (
            "click centro en el campo de texto 'Nombre' y escribe 'Juan'",
            "Comando con typing",
            lambda s, cl: len(s) == 1 and "Nombre" in cl and "Juan" in cl
        ),
        (
            "click derecha arriba en icono",
            "Dos specs, orden inverso",
            lambda s, cl: len(s) == 2 and "icono" in cl.lower()
        ),
    ]
    
    passed = 0
    failed = 0
    
    for cmd, desc, check in test_cases:
        specs = extract_spatial_specs(cmd)
        normalized = normalize_spatial_spec(specs) if specs else None
        cleaned = remove_spatial_specs_from_command(cmd)
        
        if check(specs, cleaned):
            print(f"✓ {desc}: '{cmd}'")
            print(f"    Specs: {specs} (normalized: {normalized})")
            print(f"    Cleaned: '{cleaned}'")
            passed += 1
        else:
            print(f"✗ {desc}: '{cmd}'")
            print(f"    Specs: {specs}, Cleaned: '{cleaned}'")
            failed += 1
    
    print(f"\nResultado: {passed} pasados, {failed} fallidos\n")
    return failed == 0


def test_spanish_english_mixing():
    """Test 7: Mezcla de español e inglés"""
    print("=" * 80)
    print("TEST 7: Mezcla de español e inglés")
    print("=" * 80)
    
    test_cases = [
        ("click top en Guardar", ["arriba"], "Inglés top"),
        ("click arriba en Save", ["arriba"], "Español arriba, inglés target"),
        ("click left right en botón", ["izquierda", "derecha"], "Dos specs inglés"),
        ("click superior en Button", ["arriba"], "Sinónimo español"),
        ("click bottom center en 'Submit'", ["abajo", "centro"], "Inglés specs"),
        ("arriba click right en 'Enviar'", ["arriba", "derecha"], "Mezcla español-inglés"),
    ]
    
    passed = 0
    failed = 0
    
    for cmd, expected_specs, desc in test_cases:
        specs = extract_spatial_specs(cmd)
        normalized = normalize_spatial_spec(specs) if specs else None
        cleaned = remove_spatial_specs_from_command(cmd)
        
        expected_set = set(expected_specs)
        found_set = set(specs)
        
        if expected_set == found_set:
            print(f"✓ {desc}: '{cmd}' → {specs} (normalized: {normalized})")
            print(f"    Cleaned: '{cleaned}'")
            passed += 1
        else:
            print(f"✗ {desc}: '{cmd}'")
            print(f"    Esperado: {expected_specs}, Obtenido: {specs}")
            failed += 1
    
    print(f"\nResultado: {passed} pasados, {failed} fallidos\n")
    return failed == 0


def main():
    """Ejecutar todos los tests"""
    print("\n" + "=" * 80)
    print("TESTS EXHAUSTIVOS DEL SISTEMA DE FILTRADO ESPACIAL")
    print("=" * 80 + "\n")
    
    results = []
    
    results.append(("Extracción de specs", test_spatial_extraction()))
    results.append(("Separación de target", test_target_separation()))
    results.append(("Casos edge", test_edge_cases()))
    results.append(("Cálculo de zonas", test_grid_zones()))
    results.append(("Filtrado de elementos", test_element_filtering()))
    results.append(("Comandos complejos", test_complex_commands()))
    results.append(("Mezcla español-inglés", test_spanish_english_mixing()))
    
    print("=" * 80)
    print("RESUMEN FINAL")
    print("=" * 80)
    
    total_passed = sum(1 for _, result in results if result)
    total_failed = len(results) - total_passed
    
    for test_name, result in results:
        status = "✓ PASÓ" if result else "✗ FALLÓ"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {total_passed} tests pasaron, {total_failed} tests fallaron")
    
    if total_failed == 0:
        print("\n🎉 ¡Todos los tests pasaron!")
        return 0
    else:
        print(f"\n⚠️  {total_failed} test(s) fallaron. Revisar implementación.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
