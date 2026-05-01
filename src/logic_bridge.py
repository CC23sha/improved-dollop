import os
import logging
from typing import List, Tuple, Dict, Any, Optional
from src.storage import json_handler

class LogicBridge:
    def __init__(self, data_manager):
        self.dm = data_manager
        self.logger = logging.getLogger("Nimbus.LogicBridge")

    def obtener_lista_estaciones(self, activas: bool = True) -> List[Tuple[str, str]]:
        """
        Obtiene y limpia nombres de estaciones: 'MADRID, RETIRO' -> 'RETIRO'.
        """
        path = self.dm.active_path if activas else self.dm.catalog_path
        
        # Sincronización automática si el archivo no existe
        if not os.path.exists(path):
            self.logger.info("Archivo de estaciones no encontrado. Sincronizando...")
            self.dm.sync_stations()

        data = json_handler.load_from_path(path) or {}
        stations_dict = data.get("stations", {})
        
        processed = []
        for s_id, info in stations_dict.items():
            full_name = info.get('name', 'Sin nombre')
            # Lógica de limpieza mejorada
            if ", " in full_name:
                name = full_name.split(", ", 1)[1]
            else:
                parts = full_name.split(" ", 1)
                name = parts[1] if len(parts) > 1 else parts[0]
            processed.append((s_id, name))
        
        # Devolvemos la lista ordenada alfabéticamente por nombre
        return sorted(processed, key=lambda x: x[1])
    
    def obtener_estaciones_con_coords(self):
        """Devuelve una lista de diccionarios con id, nombre, lat y lon."""
        path = self.dm.active_path
        data = json_handler.load_from_path(path) or {}
        stations_dict = data.get("stations", {})
        
        lista_coords = []
        for s_id, info in stations_dict.items():
            lista_coords.append({
                "id": s_id,
                "name": info.get('name', 'Estación'),
                "lat": float(info.get('lat', 0)),
                "lon": float(info.get('lon', 0))
            })
        return lista_coords

    def ejecutar_ingesta_forzada(self, start: str, end: str, station_id: str):
        """Descarga directa desde AEMET ignorando el caché local."""
        try:
            return self.dm.force_api_ingest(start, end, station_id)
        except Exception as e:
            self.logger.error(f"Error en ingesta forzada: {e}")
            return []

    def consultar_historico(self, start: str, end: str, station_id: str):
        """Consulta inteligente: busca en JSON y si no hay, va a la API."""
        return self.dm.get_weather(start, end, station_id)

    def realizar_comparativa(self, fecha: str, station_id: str) -> Dict[str, Any]:
        """
        Obtiene datos locales y de la API para detectar discrepancias.
        """
        # 1. Obtener de JSON local
        history_local = self.dm.get_records_from_json(fecha, fecha, station_id)
        local_data = history_local[0] if history_local else None

        # 2. Obtener fresco de la API
        api_records = self.dm.force_api_ingest(fecha, fecha, station_id)
        api_data = api_records[0] if api_records else None

        return {
            "local": local_data,
            "api": api_data
        }

    def sincronizar_catalogos(self) -> bool:
        """Actualiza manualmente la lista de estaciones desde AEMET."""
        return self.dm.sync_stations()