import os
import logging
from dotenv import load_dotenv
from typing import Dict, Optional
from src.storage import json_handler

load_dotenv()

class ConfigManager:
    """
    Gestiona la configuración global de la aplicación.
    Se encarga de leer el archivo config.json y fusionarlo con variables de entorno.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._config: Optional[Dict] = None

    def get_config(self) -> Dict:
        """
        Carga la configuración base y prioriza la API Key del entorno (.env).
        Evita tener que leer el disco en cada llamada.
        """
        if self._config:
            return self._config

        try:
            # Intentar cargar el archivo físico
            config = json_handler.load_config()
            if config is None:
                self.logger.warning("Archivo config.json no encontrado. Usando valores vacíos.")
                config = {}

            # Priorizar la API Key del entorno 
            env_api_key = os.getenv("AEMET_API_KEY")
            if env_api_key:
                config["api_key"] = env_api_key
                self.logger.info("API Key cargada exitosamente desde el entorno (.env).")
            elif "api_key" not in config:
                self.logger.error("No se encontró API_KEY ni en .env ni en config.json")
            
            # Guardar en caché de instancia
            self._config = config
            return self._config

        except Exception as e:
            self.logger.error(f"Error crítico al inicializar la configuración: {e}")
            # Los servicios fallarán al no tener API Key.
            return {}

    def get(self, key: str, default: any = None) -> any:
        """Método de conveniencia para acceder a valores anidados."""
        return self.get_config().get(key, default)