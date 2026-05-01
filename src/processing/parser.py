import re
from src.processing.models import Station, WeatherRecord
#from src.utils.logger import config_logger

# Inicializamos el logger para registrar el proceso de limpieza
#logger = config_logger(__name__)
import logging
logger = logging.getLogger(__name__)

class DataParser:
    def __init__(self):#, allowed_stations):
        """
        Allowed stations: [{'nombre': 'Retiro', 'id': '3195'}, ...]
        """
        #self.station_mapping = {s['id']: s['nombre'] for s in allowed_stations}
    
    @staticmethod
    def _to_iso8601_date(fecha_str):
        fecha_str = fecha_str.split('+')[0]

        # Si es una fecha simple (sin 'T'), completamos el formato
        if 'T' not in fecha_str:
            return f"{fecha_str}T00:00:00UTC"
        
        # Si tiene 'T' pero no termina en 'UTC', se lo añadimos
        if not fecha_str.endswith("UTC"):
            return f"{fecha_str}UTC"
            
        return fecha_str

    @staticmethod
    def _clean_float(value):
        if value is None: return None
        try:
            return float(str(value).replace(',', '.'))
        except (ValueError, TypeError):
            return None

    def parse_daily_weather(self, raw_data):
        """
        Recibe la lista de la API y devuelve una lista de objetos WeatherRecord.
        """
        processed_data = [] 
        for register in raw_data:
            indicator = register.get("indicativo")
            
            # Filtro de estaciones permitidas y control de duplicados
            #if indicator in self.station_mapping and indicator not in seen_indicators:
            try:
                # Creamos el objeto WeatherRecord con los datos mapeados
                record = WeatherRecord(
                    date=self._to_iso8601_date(register.get("fecha")),
                    station_id=indicator,
                    name=register.get("nombre"),
                    #province=register.get("provincia"),
                    temp_avg=self._clean_float(register.get("tmed")),
                    temp_min=self._clean_float(register.get("tmin")),
                    #time_temp_min=register.get("horatmin"),
                    temp_max=self._clean_float(register.get("tmax")),
                    #time_temp_max=register.get("horatmax"),
                    humidity_avg=self._clean_float(register.get("hrMedia")),
                    #humidity_min=self.clean_float(register.get("hrMin")),
                    #humidity_max=self.clean_float(register.get("hrMax")),
                    #time_humidity_min=register.get("horahrmin"),
                    #time_humidity_max=register.get("horahrmax"),
                    precipitation=self._clean_float(register.get("prec")),
                    #wind_gust=self.clean_float(register.get("racha")),
                    #time_wind_gust=register.get("horaracha"),
                    wind_direction=self._clean_float(register.get("dir")),
                    wind_speed_avg=self._clean_float(register.get("velmedia"))
                )
                
                # Validación mínima para alertas
                #if record.temp_max is not None and record.wind_gust is not None:
                processed_data.append(record)
                    # seen_indicators.add(indicator)
                #else:
                #    logger.warning(f"Datos esenciales (temp/viento) ausentes en {record.name} - Omitido.")
                    
            except Exception as e:
                logger.error(f"Error inesperado procesando la estación {indicator}: {e}")
        
        logger.info(f"Procesados {len(processed_data)} objetos WeatherRecord de Madrid.")
        return processed_data
    
    def parse_hourly_weather(self, raw_data: list[dict]) -> list[WeatherRecord]:
        """
        Selecciona únicamente el registro más reciente de la lista horaria.
        Como los datos son acumulados, el último registro contiene el estado actual del día.
        """
        if not raw_data:
            return []

        # Ordenamos por 'fint' (fecha-hora de fin de observación) para asegurar el más reciente
        # AEMET suele enviarlos ordenados, pero esto garantiza que el último es el más actual.
        try:
            raw_data.sort(key=lambda x: x.get("fint", ""))
            latest_record = raw_data[-1]
            
            record_obj = WeatherRecord(
                date=self._to_iso8601_date(latest_record.get("fint")),
                station_id=latest_record.get("idema"),
                name=latest_record.get("ubi"),
                temp_avg=self._clean_float(latest_record.get("ta")),
                temp_min=self._clean_float(latest_record.get("tmin")),
                temp_max=self._clean_float(latest_record.get("tmax")),
                humidity_avg=self._clean_float(latest_record.get("hr")),
                precipitation=self._clean_float(latest_record.get("prec")),
                wind_direction=self._clean_float(latest_record.get("dv")),
                wind_speed_avg=self._clean_float(latest_record.get("vv"))
            )
            return [record_obj]

        except Exception as e:
            logger.error("Error al identificar el registro más reciente "
                         f"de hoy para la estacion : {e}")
            return []
    
    def parse_stations(self, raw_data, filter_city="MADRID"):
        """
        Convierte la respuesta de la API en un diccionario de objetos Station.
        Usa el filtrado por la primera palabra del nombre.
        """
        stations_map = {}
        
        for item in raw_data:
            name = item.get("nombre", "")
            station_id = item.get("indicativo")

            # Filtrado por primera palabra (Ej: "MADRID, RETIRO" -> "MADRID")
            if station_id and name and re.split(r'[,\s]+', name)[0].upper() == filter_city:
                try:
                    station_obj = Station(
                        station_id=station_id,
                        name=name,
                        province=item.get("provincia"),
                        latitude=item.get("latitud"),
                        longitude=item.get("longitud"),
                        altitude=item.get("altitud")
                    )
                    stations_map[station_id] = station_obj

                except Exception as e:
                    logger.error(f"Error al crear objeto Station para {station_id}: {e}")
                    
        return stations_map