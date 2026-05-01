from dataclasses import dataclass, asdict, field
from typing import Optional
from datetime import datetime

@dataclass
class Station:
    station_id: str
    name: str
    province: str
    latitude: str
    longitude: str
    altitude: str
    # state: str = "active"
    # registration_date: Optional[str] = None

    @property
    def geo_id(self) -> str:
        """
        Genera un ID único combinando fecha completa y estación.
        Ejemplo: "3126Y_403341N_034243W_740"
        """
        return f"{self.station_id}_{self.latitude}_{self.longitude}_{self.altitude}"
    
    def to_dict(self):
        """
        Serializa la estación a un diccionario para guardarla en el JSON.
        """
        return asdict(self)

@dataclass
class WeatherRecord:
    date: str
    station_id: str
    name: str
    #province: str
    temp_avg: Optional[float] = None
    temp_min: Optional[float] = None
    #time_temp_min: Optional[str] = None
    temp_max: Optional[float] = None
    #time_temp_max: Optional[str] = None
    humidity_avg: Optional[int] = None
    #humidity_min: Optional[int] = None
    #humidity_max: Optional[int] = None
    #time_humidity_min: Optional[str] = None
    #time_humidity_max: Optional[str] = None
    precipitation: Optional[float] = None
    #wind_gust: Optional[float] = None
    #time_wind_gust: Optional[str] = None
    wind_direction: Optional[int] = None
    wind_speed_avg: Optional[float] = None
    # Para caché (TTL): permite saber si el dato debe volver a descargarse
    last_update: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def record_id(self) -> str:
        """
        Genera un ID único combinando fecha completa y estación.
        Ejemplo: "2026-04-01T00:00:00UTC_3195"
        """
        return f"{self.date}_{self.station_id}"
    
    def to_dict(self):
        """
        Serializa el registro a un diccionario para guardarlo en el JSON.
        """
        return asdict(self)