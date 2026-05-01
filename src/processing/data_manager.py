import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional

from src.storage import json_handler
from src.processing.models import WeatherRecord, Station
from src.ingestion.api_client import AemetClient
from src.processing.parser import DataParser

class DataManager:
    """
    Capa de persistencia y gestión de datos de Nimbus.
    Controla la caché inteligente, la sincronización con AEMET y la jerarquía del JSON.
    """

    def __init__(self, config_manager):
        self.logger = logging.getLogger(__name__)
        self.config = config_manager
        
        # Inicialización de servicios dependientes
        self.client = AemetClient()
        self.parser = DataParser()
        
        # Cargar rutas desde el ConfigManager
        storage_cfg = self.config.get_config().get("storage", {})
        self.active_path = storage_cfg.get("active_stations_path", "data/stations/active_stations.json")
        self.catalog_path = storage_cfg.get("stations_catalog_path", "data/stations/stations_catalog.json")
        self.history_path = storage_cfg.get("weather_history_path", "data/weather/history.json")

    @staticmethod
    def _to_api_format(date_str: str) -> str:
        """Formatea fechas ISO a formato aceptado por los endpoints de AEMET."""
        return f"{date_str.split('T')[0]}T00:00:00UTC"

    def _is_today_record_stale(self, last_update_str: str) -> bool:
        """
        Determina si el dato de hoy debe refrescarse basándose en el cambio
        de hora del sistema (TTL por ventana horaria).
        """
        now = datetime.now()
        last_upd = datetime.fromisoformat(last_update_str)

        # Si la hora actual es distinta a la de la última actualización, el dato es viejo.
        return now.hour != last_upd.hour or now.day != last_upd.day

    # --- 1. MÉTODOS DE CONSULTA A LA API ---

    def _fetch_today_from_api(self, station_id: str) -> List[WeatherRecord]:
        """Consulta datos de observación horaria (tiempo real) a la API."""
        raw_data = self.client.get_today_weather(station_id)
        # El parser devolverá solo el registro más reciente en una lista de 1 elemento.
        return self.parser.parse_hourly_weather(raw_data) if raw_data else []

    def _fetch_history_from_api(self, station_id: str, start: str, end: str) -> List[WeatherRecord]:
        """Consulta datos climatológicos diarios históricos a la API."""
        api_start = self._to_api_format(start)
        api_end = self._to_api_format(end)
        raw_data = self.client.get_daily_weather(station_id, api_start, api_end)
        return self.parser.parse_daily_weather(raw_data) if raw_data else []

    # --- 2. MÉTODOS DE CONSULTA AL JSON (CACHÉ) ---

    def _get_today_from_json(self, station_id: str) -> Optional[dict]:
        """Acceso O(1) al registro de hoy en la caché local."""
        hoy = date.today().isoformat()
        history = json_handler.load_from_path(self.history_path) or {}
        return history.get(station_id, {}).get("data", {}).get(hoy)

    def _get_history_from_json(self, station_id: str, start: str, end: str) -> List[dict]:
        """Recupera registros pasados de la caché local."""
        history = json_handler.load_from_path(self.history_path) or {}
        results = []
        hoy_str = date.today().isoformat()
        
        station_node = history.get(station_id, {}).get("data", {})
        for d_str, val in station_node.items():
            # Solo registros dentro del rango que NO sean los volátiles de hoy
            if start <= d_str <= end and d_str < hoy_str:
                results.append(val)
        
        return sorted(results, key=lambda x: x['date'])

    def get_records_from_json(self, start: str, end: str, station_id: str) -> List[dict]:
        """
        Método público que unifica la búsqueda en el JSON local tanto 
        para el registro de hoy como para el histórico.
        """
        results = []
        hoy_str = date.today().isoformat()

        # 1. Obtener datos históricos (anteriores a hoy)
        # Este método ya filtra por rango y excluye hoy
        history_records = self._get_history_from_json(station_id, start, end)
        results.extend(history_records)

        # 2. Si el rango incluye el día de hoy, lo añadimos específicamente
        if start <= hoy_str <= end:
            today_record = self._get_today_from_json(station_id)
            if today_record:
                results.append(today_record)

        # Ordenamos por fecha para que la comparativa o el reporte sea legible
        results.sort(key=lambda x: x.get('date', ''))
        
        return results

    # --- 3. ORQUESTADOR DE CLIMA ---

    def get_weather(self, start_date: str, end_date: str, station_id: str) -> List[dict]:
        """
        Punto de entrada principal. Coordina qué datos vienen de JSON y cuáles de API.
        """
        hoy_str = date.today().isoformat()
        final_results = []

        # FASE 1: Datos Históricos (Ayer y atrás)
        hist_start = start_date
        hist_end = end_date if end_date < hoy_str else (date.today() - timedelta(days=1)).isoformat()

        if hist_start < hoy_str:
            local_hist = self._get_history_from_json(station_id, hist_start, hist_end)
            
            # Verificación de integridad de la caché
            dias_solicitados = (date.fromisoformat(hist_end) - date.fromisoformat(hist_start)).days + 1
            if len(local_hist) < dias_solicitados:
                self.logger.info(f"Faltan datos históricos para {station_id}. Llamando a API...")
                new_api_data = self._fetch_history_from_api(station_id, hist_start, hist_end)
                self.update_weather_history(new_api_data)
                local_hist = self._get_history_from_json(station_id, hist_start, hist_end)
            
            final_results.extend(local_hist)

        # FASE 2: Datos de Hoy (Tiempo real con TTL dinámico)
        if end_date >= hoy_str:
            dato_hoy = self._get_today_from_json(station_id)
            
            necesita_refrescar = False
            if not dato_hoy:
                necesita_refrescar = True
            elif self._is_today_record_stale(dato_hoy["last_update"]):
                necesita_refrescar = True

            if necesita_refrescar:
                self.logger.info(f"Refrescando ventana horaria de hoy para {station_id}...")
                api_data_hoy = self._fetch_today_from_api(station_id)
                if api_data_hoy:
                    self.update_weather_history(api_data_hoy)
                    dato_hoy = self._get_today_from_json(station_id)

            if dato_hoy:
                final_results.append(dato_hoy)

        return final_results

    def force_api_ingest(self, start_date: str, end_date: str, station_id: str) -> List[WeatherRecord]:
        """
        Método público para forzar la descarga desde la API e ignorar la caché.
        Actualiza el histórico local automáticamente.
        """
        hoy_str = date.today().isoformat()
        all_new_records = []

        # 1. Si el rango incluye días pasados
        if start_date < hoy_str:
            # Calculamos el fin del rango histórico (sin incluir hoy)
            hist_end = end_date if end_date < hoy_str else (date.today() - timedelta(days=1)).isoformat()
            hist_records = self._fetch_history_from_api(station_id, start_date, hist_end)
            all_new_records.extend(hist_records)

        # 2. Si el rango incluye hoy
        if end_date >= hoy_str:
            today_records = self._fetch_today_from_api(station_id)
            all_new_records.extend(today_records)

        # 3. Persistencia
        if all_new_records:
            self.update_weather_history(all_new_records)
            self.logger.info(f"Ingesta forzada completada: {len(all_new_records)} registros actualizados.")

        return all_new_records

    # --- 4. PERSISTENCIA ---

    def update_weather_history(self, new_records: List[WeatherRecord]) -> bool:
        """Guarda registros en el JSON bajo la estructura Estación > Fecha."""
        if not new_records: return False

        try:
            history = json_handler.load_from_path(self.history_path) or {}
            
            for record in new_records:
                sid = record.station_id
                if sid not in history:
                    history[sid] = {"metadata": {"name": record.name}, "data": {}}
                
                # Se usa la fecha corta (YYYY-MM-DD) como clave única diaria
                short_date = record.date.split('T')[0]
                history[sid]["data"][short_date] = record.to_dict()

            return json_handler.save_to_path(history, self.history_path)
        except Exception as e:
            self.logger.error(f"Error crítico al actualizar histórico JSON: {e}")
            return False

    # --- 5. GESTIÓN DE ESTACIONES ---

    def sync_stations(self) -> bool:
        """Actualiza el catálogo de estaciones y aplica filtros de configuración."""
        self.logger.info("Sincronizando estaciones con AEMET...")
        try:
            raw_data = self.client.get_stations()
            if not raw_data: return False

            # Obtener filtro de ciudad (ej. MADRID)
            filter_city = self.config.get_config().get("source_config", {}).get("filter_nombre", "MADRID")
            api_stations = self.parser.parse_stations(raw_data, filter_city=filter_city)
            
            # Persistir estaciones activas
            ahora = datetime.now().isoformat()
            json_handler.save_to_path({
                "metadata": {"last_update": ahora, "count": len(api_stations)},
                "stations": {sid: s.to_dict() for sid, s in api_stations.items()}
            }, self.active_path)

            return True
        except Exception as e:
            self.logger.error(f"Error en sincronización de estaciones: {e}")
            return False

    def get_active_station_ids(self) -> List[str]:
        """Retorna los indicativos de las estaciones cargadas actualmente."""
        data = json_handler.load_from_path(self.active_path) or {}
        return list(data.get("stations", {}).keys())