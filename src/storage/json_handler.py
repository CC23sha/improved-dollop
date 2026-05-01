import json
import os
import logging

logger = logging.getLogger(__name__)

# Funciones privadas

def _read_json(path):
    """Lee cualquier archivo JSON desde una ruta específica."""
    if not os.path.exists(path):
        logger.debug(f"El archivo no existe (esperado en primer inicio): {path}")
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error crítico leyendo {path}: {e}")
        return None

def _write_json(path, data):
    """Escribe datos en un JSON asegurando que los directorios existan."""
    try:
        # Crear toda la estructura de carpetas necesaria
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Estructura de directorios creada: {directory}")
            
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error crítico escribiendo en {path}: {e}")
        return False

# Funciones públicas

def load_config(filename="config.json"):
    """Carga el archivo de configuración inicial de la raíz."""
    return _read_json(filename)

def load_from_path(path):
    """
    Carga un JSON desde cualquier ruta dinámica proporcionada por los Managers.
    Se usa para: catalog.json, active.json, history.json.
    """
    return _read_json(path)

def save_to_path(data, path):
    """
    Guarda datos en cualquier ruta dinámica proporcionada por los Managers.
    Se encarga de crear las carpetas /data/stations/ o /data/weather/ si no existen.
    """
    return _write_json(path, data)