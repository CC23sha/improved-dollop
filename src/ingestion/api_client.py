import os
import time
import logging
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

class AemetClient:
    def __init__(self):
        self.api_key = os.getenv("AEMET_API_KEY")
        self.base_url = "https://opendata.aemet.es/opendata/api"
        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": "NimbusData/1.0",
            "api_key": self.api_key
        })
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)

    @staticmethod
    def _check_status(response, context):
        """
        Gestiona los códigos de estado obligatorios.
        """
        code = response.status_code
        if code == 200:
            return True

        messages = {
            401: "No autorizado: API Key inválida.",
            403: "Prohibido: Acceso denegado al recurso.",
            404: "No encontrado: El endpoint o los datos no existen.",
            429: "Rate Limit: Demasiadas peticiones.",
            503: "Servicio no disponible: AEMET está en mantenimiento."
        }
        
        msg = messages.get(code, f"Error inesperado ({code})")
        logging.error(f"[{context}] {msg}")
        return False
    
    def _execute_request(self, endpoint):
        """
        Gestiona el flujo completo de AEMET: 
        Petición de URL -> Validación de estados -> Descarga de JSON final.
        """
        url = f"{self.base_url}/{endpoint}"
        
        try:
            # PASO 1: Obtener el enlace temporal de datos
            start_t = time.time()
            response = self.session.get(url, timeout=10)
            latency = time.time() - start_t

            logging.info(f"STEP1 {url} - {response.status_code} - {latency:.2f}s")

            if not self._check_status(response, f"STEP1: {endpoint}"):
                return None

            res_json = response.json()
            
            # Validación del estado interno de AEMET
            if res_json.get("estado") != 200:
                logging.warning(f"AEMET (Interno {res_json.get('estado')}): "
                                f"{res_json.get('descripcion')}")
                return None

            data_url = res_json.get("datos")
            if not data_url:
                logging.error(f"No se encontró 'datos_url' en la respuesta de {endpoint}")
                return None

            # PASO 2: Descargar el contenido real
            response_data = self.session.get(data_url, timeout=15)
            
            if self._check_status(response_data, "STEP2: Descarga Final"):
                return response_data.json()
            
            return None

        except requests.exceptions.RequestException as e:
            logging.error(f"Error de red: {e}")
            return None


    def get_today_weather(self, station_id):
        endpoint = f"observacion/convencional/datos/estacion/{station_id}"
        return self._execute_request(endpoint)

    def get_daily_weather(self, station_id, start_date, end_date):
        endpoint = f"valores/climatologicos/diarios/datos/fechaini/{start_date}/fechafin/{end_date}/estacion/{station_id}"
        return self._execute_request(endpoint)
        
    def get_stations(self): 
        endpoint = "valores/climatologicos/inventarioestaciones/todasestaciones"
        return self._execute_request(endpoint)