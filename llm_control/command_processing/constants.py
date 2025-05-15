"""
Constants for command processing.

This module contains the constants used for command processing to avoid circular imports.
"""

# Common constants for command processing
KEY_MAPPING = {
    # English keys
    'enter': 'enter', 'return': 'enter',
    'tab': 'tab',
    'esc': 'escape', 'escape': 'escape',
    'space': 'space', 'spacebar': 'space',
    'up': 'up', 'down': 'down', 'left': 'left', 'right': 'right',
    'backspace': 'backspace', 'delete': 'delete',
    'home': 'home', 'end': 'end',
    'pageup': 'pageup', 'pagedown': 'pagedown',
    'ctrl': 'ctrl', 'control': 'ctrl',
    'alt': 'alt', 'option': 'alt',
    'shift': 'shift',
    'win': 'win', 'command': 'command', 'cmd': 'command',
    
    # Spanish key mappings
    'intro': 'enter', 'entrar': 'enter', 'ingresar': 'enter',
    'tabulador': 'tab', 'tabulación': 'tab',
    'escape': 'escape', 'salir': 'escape',
    'espacio': 'space', 'barra': 'space', 'barra espaciadora': 'space',
    'arriba': 'up', 'subir': 'up',
    'abajo': 'down', 'bajar': 'down',
    'izquierda': 'left',
    'derecha': 'right',
    'retroceso': 'backspace', 'borrar': 'backspace',
    'suprimir': 'delete', 'eliminar': 'delete',
    'inicio': 'home',
    'fin': 'end',
    'página arriba': 'pageup', 'subir página': 'pageup',
    'página abajo': 'pagedown', 'bajar página': 'pagedown',
    'control': 'ctrl',
    'alternativa': 'alt', 'alt': 'alt',
    'mayúscula': 'shift', 'mayúsculas': 'shift', 'shift': 'shift',
    'windows': 'win', 'ventana': 'win', 'cmd': 'command'
}

# Regular expression patterns for command parsing
# Updated to include Spanish verbs
KEY_COMMAND_PATTERN = r'(press|hit|push|stroke|pulsa|presiona|oprime|teclea|presionar|oprimir|teclear)\s+(?:\"([^\"]+)\"|\'([^\']+)\'|(\w+(?:[-+\s]\w+)*))'
TYPING_COMMAND_PATTERNS = ['type ', 'typing ', 'write ', 'enter ', 'escribe ', 'escribir ', 'teclea ', 'teclear ', 'ingresa ', 'ingresar ']
REFERENCE_WORDS = ["it", "that", "this", "lo", "la", "le", "eso", "esto", "éste", "ésta", "aquel", "aquella"]
ACTION_VERBS = [
    # English verbs
    'click', 'type', 'move', 'press', 'hit', 'right', 'double', 'drag', 'scroll', 'wait',
    # Spanish verbs
    'clic', 'hacer clic', 'pulsa', 'presiona', 'escribe', 'escribir', 'teclea', 'teclear', 
    'mover', 'mueve', 'presionar', 'doble', 'doble clic', 'arrastrar', 'arrastra', 
    'desplazar', 'desplazamiento', 'esperar', 'espera'
]
STEP_SEPARATORS = [
    # English separators
    ', then ', ', and ', '; then ', '; and ',  # Complex separators
    ', ', '; ',  # Simple separators
    # Spanish separators
    ', luego ', ', después ', ', y ', '; luego ', '; después ', '; y ',
    ', entonces ', '; entonces '
] 