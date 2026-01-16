# Tests para LLM Control

Este directorio contiene los tests automatizados para el proyecto LLM Control.

## Estructura

```
tests/
├── __init__.py
├── README.md
└── llm_control/
    ├── __init__.py
    └── command_processing/
        ├── __init__.py
        └── test_executor_typing_keyboard.py
```

## Ejecutar Tests

### Ejecutar todos los tests

```bash
# Desde la raíz del proyecto
python -m pytest tests/ -v

# O usando unittest
python -m unittest discover tests/ -v
```

### Ejecutar un archivo de tests específico

```bash
python -m pytest tests/llm_control/command_processing/test_executor_typing_keyboard.py -v

# O con unittest
python -m unittest tests.llm_control.command_processing.test_executor_typing_keyboard -v
```

### Ejecutar un test específico

```bash
python -m pytest tests/llm_control/command_processing/test_executor_typing_keyboard.py::TestTypingKeyboardDetection::test_is_typing_command_pure_typing -v
```

## Tests Disponibles

### test_executor_typing_keyboard.py

Tests para la detección y priorización de comandos de typing vs keyboard:

- **TestTypingKeyboardDetection**: Tests unitarios para las funciones de detección
  - `test_is_typing_command_pure_typing`: Verifica detección de comandos de typing puros
  - `test_is_typing_command_keyboard_false_positive`: Verifica que no haya falsos positivos
  - `test_is_keyboard_command_pure_keyboard`: Verifica detección de comandos de keyboard puros
  - `test_is_keyboard_command_combinations`: Verifica detección de combinaciones de teclas
  - `test_is_keyboard_command_typing_false_positive`: Verifica que no haya falsos positivos

- **TestCommandPrioritization**: Tests de integración para la lógica de priorización
  - `test_pure_keyboard_command`: Escenario 1 - Comando puro de keyboard
  - `test_pure_typing_command`: Escenario 2 - Comando puro de typing
  - `test_typing_with_keyboard_sequence`: Escenario 3 - Secuencia typing + keyboard
  - `test_keyboard_after_typing_separate_steps`: Escenario 4 - Steps separados
  - `test_enter_as_verb_typing`: Escenario 5 - "Enter" como verbo de typing
  - `test_multiple_keyboard_commands`: Múltiples comandos de keyboard en secuencia

- **TestEdgeCases**: Tests de casos límite
  - `test_ambiguous_enter_command`: Comandos ambiguos
  - `test_case_insensitive_detection`: Detección case-insensitive
  - `test_spanish_and_english_mixed`: Mezcla de español e inglés

## Requisitos

Los tests usan `unittest` que viene incluido en Python, no se requieren dependencias adicionales.

Para ejecutar los tests, asegúrate de estar en el directorio raíz del proyecto y que el entorno virtual esté activado (si usas uno).

## Agregar Nuevos Tests

Para agregar nuevos tests:

1. Crea un archivo `test_*.py` en el directorio apropiado
2. Importa `unittest` y las funciones a testear
3. Crea clases que hereden de `unittest.TestCase`
4. Usa métodos que empiecen con `test_` para cada caso de prueba
5. Usa `unittest.mock` para mockear dependencias externas (LLM, UI detection, etc.)

Ejemplo:

```python
import unittest
from unittest.mock import patch, Mock
from llm_control.command_processing.executor import process_single_step

class TestMyFeature(unittest.TestCase):
    @patch('llm_control.command_processing.executor.some_dependency')
    def test_my_feature(self, mock_dependency):
        mock_dependency.return_value = Mock()
        result = process_single_step("test command", {})
        self.assertIn('code', result)

if __name__ == '__main__':
    unittest.main()
```
