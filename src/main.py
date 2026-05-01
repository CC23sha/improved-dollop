import os
import sys
import logging
import platform
import subprocess
from datetime import datetime, timedelta

# Configuracion basica de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from src.utils.config_manager import ConfigManager
from src.processing.data_manager import DataManager
from src.storage import json_handler

# --- FUNCIONES DE INTERFAZ ---
def limpiar_pantalla():
    """
    Limpia la consola dependiendo del sistema operativo.
    """
    try:
        print("\033[H\033[2J", end="", flush=True)

        # En caso de que el código ANSII no funcione
        # Definir el comando según el sistema operativo
        es_windows = platform.system() == "Windows"
        comando = "cls" if es_windows else "clear"
        subprocess.run(comando, shell=es_windows, check=True)
        
    except Exception as e:
        #log_warning(f"No se pudo limpiar la pantalla: {e}")
        print("\033[H\033[2J", end="")

def menu_principal():
    print("\n" + "="*50)
    print("NIMBUS DATA")
    print("="*50)
    print("[1] Ingesta Automática (AEMET)")
    print("[2] Ver Historico de Datos")
    print("[3] Comparativa de fuentes")
    print("[4] Configurar Scheduler")
    print("[5] Gestion de Estaciones (Activas/Catálogo/Sync)")
    print("[X] Salir")
    print("\n(Ctrl+C para Salir del programa)")
    return input("Selecciona una opción: ").strip()

import os

def seleccionar_estaciones(data_manager, active=True):
    """
    Selecciona estaciones comprobando primero la existencia de los archivos físicos.
    Si no existen, fuerza la descarga desde la API.
    Retorna una lista de tuplas [(id, nombre)] o None.
    """
    # 1. DETERMINAR RUTA Y VALIDAR EXISTENCIA
    path = data_manager.active_path if active else data_manager.catalog_path
    
    if not os.path.exists(path):
        tipo = "activas" if active else "catálogo completo"
        print(f"\n[!] Archivo de estaciones {tipo} no encontrado.")
        print(f"[*] Sincronizando con la API de AEMET automáticamente...")
        
        exito = data_manager.sync_stations()
        if not exito:
            print("[ERROR] No se pudo generar el archivo de estaciones. Abortando.")
            return None

    # 2. CARGAR DATOS
    data = json_handler.load_from_path(path) or {}
    stations_dict = data.get("stations", {})
    
    if not stations_dict:
        print("\n[!] El archivo existe pero no contiene estaciones válidas.")
        return None

    # 3. PREPARAR LISTA Y MOSTRAR MENÚ
    ids_list = list(stations_dict.keys())
    processed_stations = []

    print("\nEstaciones disponibles:")
    print("-" * 55)

    for i, s_id in enumerate(ids_list, 1):
        info = stations_dict[s_id]
        full_name = info.get('name', 'Sin nombre')
        
        # Lógica de Limpieza Flexible
        if ", " in full_name:
            station_name = full_name.split(", ", 1)[1]
        else:
            parts = full_name.split(" ", 1)
            station_name = parts[1] if len(parts) > 1 else parts[0]
        
        processed_stations.append((s_id, station_name))
        print(f"[{i}] {station_name:<30} (ID: {s_id})")

    print("-" * 55)
    print("Tip: Pulsa [Enter] para seleccionar TODAS las estaciones.")

    # 4. BUCLE DE SELECCIÓN
    while True:
        try:
            selection = input("\nSelecciona una estación: ").strip()
            
            if selection == "":
                print("[INFO] Todas las estaciones seleccionadas.")
                return processed_stations 
                
            idx = int(selection) - 1
            if 0 <= idx < len(processed_stations):
                return [processed_stations[idx]]
            else:
                print(f"[!] Error: El número debe estar entre 1 y {len(processed_stations)}.")
        
        except ValueError:
            print("[!] Error: Introduce un número válido o pulsa [Enter] para todas.")
        except KeyboardInterrupt:
            print("\n[INFO] Selección cancelada.")
            return None

# --- LOGICA DE LAS OPCIONES ---

def opcion_ingesta_automatica(data_manager):
    """
    Gestiona la ingesta forzada: Solicita datos directamente a la API de AEMET
    y actualiza el almacenamiento local (JSON) ignorando la caché.
    """
    while True:
        try:
            print("\n" + "="*55)
            print("--- [1] INGESTA FORZADA (Sincronización API) ---")
            print("="*55)
            print("(Presiona Ctrl+C para volver al menú principal)")

            # 1. VALIDACIÓN DEL CATÁLOGO
            if not os.path.exists(data_manager.active_path) or not data_manager.get_active_station_ids():
                print("\n[!] Catálogo no detectado. Sincronizando con AEMET...")
                if not data_manager.sync_stations():
                    print("[ERROR] No se pudo obtener el catálogo. Verifique su API Key.")
                    input("\nPresione Enter para salir...")
                    break

            # 2. SELECCIÓN DE ESTACIONES
            # Ahora target_stations es una lista de tuplas: [(id, nombre), ...]
            target_stations = seleccionar_estaciones(data_manager)
            if target_stations is None:
                break

            # 3. GESTIÓN DE FECHAS (Default: Hoy)
            today = datetime.now().strftime("%Y-%m-%d")
            print(f"\nIntroduzca el rango a sincronizar ([Enter] para hoy: {today})")
            start = input("Fecha Inicio: ").strip() or today
            end = input("Fecha Fin:    ").strip() or today

            print(f"\n[INFO] Conectando con AEMET...")

            # 5. BUCLE DE INGESTA FORZADA
            for s_id, s_name in target_stations:
                # Ya no necesitamos limpiar el nombre ni cargar el JSON aquí, 
                # usamos s_name que viene de la tupla.
                print(f"\n[API] Descargando: {s_name} ({s_id})...")
                
                # LLAMADA AL MÉTODO PÚBLICO DEL DATA_MANAGER
                nuevos_registros = data_manager.force_api_ingest(start, end, s_id)

                if nuevos_registros:
                    print(f"[OK] {len(nuevos_registros)} registros guardados en el histórico.")
                    
                    # Mostrar tabla de resumen de lo descargado
                    print(f"{'FECHA':^12} | {'TEMP (C)':^10} | {'HUM (%)':^10} | {'VIENTO':^12}")
                    print("-" * 55)
                    for r in nuevos_registros:
                        f_clean = r.date.split('T')[0]
                        t = f"{r.temp_avg:.1f}" if r.temp_avg is not None else "--"
                        h = f"{int(r.humidity_avg)}" if r.humidity_avg is not None else "--"
                        v = f"{r.wind_speed_avg:.1f}" if r.wind_speed_avg is not None else "--"
                        
                        print(f"{f_clean:^12} | {t:^10} | {h:^10} | {v:^12}")
                else:
                    print(f"[!] No se recibieron datos nuevos para {s_name} en este rango.")

            # 6. FINALIZACIÓN
            print("\n" + "="*55)
            print("Sincronización finalizada correctamente.")
            if input("\n¿Desea realizar otra sincronización forzada? (s/n): ").lower() != 's':
                break
            else:
                # Si tu app tiene una función para limpiar consola, úsala aquí
                if 'limpiar_pantalla' in globals(): limpiar_pantalla()
                continue

        except KeyboardInterrupt:
            print("\n\n[INFO] Operación cancelada. Regresando al menú principal...")
            break
        except Exception as e:
            print(f"\n[ERROR] Ocurrió un fallo en el proceso: {e}")
            input("Presione Enter para continuar...")
            break

def opcion_ver_historico(data_manager):
    print("\n" + "="*55)
    print("--- [2] CONSULTA DE HISTÓRICO Y CACHÉ ---")
    print("="*55)
    
    # 1. Gestión de Fechas
    default_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"Introduzca rango (YYYY-MM-DD).")
    start = input(f"Fecha Inicio ([Enter] para {default_start}): ").strip() or default_start
    end = input(f"Fecha Fin    ([Enter] para hoy: {today}): ").strip() or today

    # 2. Selección de Estación
    target_stations = seleccionar_estaciones(data_manager, active=True)
    
    if not target_stations:
        return 

    # 3. PROCESAMIENTO
    for s_id, s_name in target_stations:
        # Usamos s_name para un feedback más humano
        print(f"\n[INFO] Recuperando datos de: {s_name} ({s_id})...")
        
        # El DataManager sigue requiriendo el s_id para la lógica de búsqueda
        records = data_manager.get_weather(start, end, s_id)

        if not records:
            print(f"No se encontraron registros para {s_name} en el rango {start} a {end}.")
            continue

        # 4. Visualización de Resultados
        print(f"\nREPORTE: {s_name.upper()} ({s_id})")
        print(f"{'FECHA':^12} | {'T.MED (C)':^10} | {'T.MAX':^7} | {'T.MIN':^7} | {'PREC (mm)':^10}")
        print("-" * 65)

        for r in records:
            fecha = r.get('date', '--').split('T')[0]
            t_med = r.get('temp_avg', '--')
            t_max = r.get('temp_max', '--')
            t_min = r.get('temp_min', '--')
            prec = r.get('precipitation', '--')

            print(f"{fecha:^12} | {str(t_med):^10} | {str(t_max):^7} | {str(t_min):^7} | {str(prec):^10}")
    
    print("\n" + "="*55)
    input("Presione Enter para volver al menú principal...")

def opcion_comparativa_discrepancias(data_manager):
    if 'limpiar_pantalla' in globals(): limpiar_pantalla()
    print("\n" + "="*65)
    print("--- [SISTEMA DE RESILIENCIA] COMPARATIVA Y DISCREPANCIAS ---")
    print("="*65)

    # 1. Selección de estación (Recibe lista de tuplas [(id, nombre)])
    resultado = seleccionar_estaciones(data_manager)
    if not resultado: return
    
    # Usamos la primera estación seleccionada para la comparativa
    s_id, s_name = resultado[0]
    
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"\nAnalizando: {s_name} ({s_id})")
    fecha_target = input(f"Fecha a comparar (YYYY-MM-DD) [[Enter] ayer: {yesterday}]: ").strip() or yesterday

    # 2. Obtener datos locales ANTES de la sincronización
    # Buscamos en el JSON lo que tenemos actualmente guardado
    history_local = data_manager.get_records_from_json(fecha_target, fecha_target, s_id)
    local_data = history_local[0] if history_local else None

    print(f"[*] Consultando fuente oficial AEMET...")

    # 3. Obtener datos frescos de la API
    # force_api_ingest nos devuelve los objetos WeatherRecord recién bajados
    api_records = data_manager.force_api_ingest(fecha_target, fecha_target, s_id)
    api_data = api_records[0] if api_records else None

    if not api_data:
        print(f"\n[!] Error: No se pudo obtener respuesta de la API para {s_name}.")
        input("\nPresione Enter para volver...")
        return

    # 4. Renderizado de la tabla comparativa
    print(f"\n{'MÉTRICA':<15} | {'HISTÓRICO (JSON)':>18} | {'ACTUAL (API)':>15} | {'ESTADO'}")
    print("-" * 78)

    # Definimos qué comparar: (Atributo_Objeto_API, Key_Diccionario_Local, Etiqueta)
    metricas = [
        ('temp_avg', 'temp_avg', 'Temp. Media'),
        ('humidity_avg', 'humidity_avg', 'Humedad'),
        ('wind_speed_avg', 'wind_speed_avg', 'Viento'),
        ('precipitation', 'precipitation', 'Precipitación')
    ]

    discrepancias_detectadas = 0

    for api_attr, local_key, label in metricas:
        # Valor local (viene de un diccionario del JSON)
        v_local = local_data.get(local_key) if local_data else None
        # Valor API (viene de un objeto WeatherRecord)
        v_api = getattr(api_data, api_attr)
        
        # Lógica de detección de discrepancia (diferencia > 0.01)
        diff = False
        if v_local is not None and v_api is not None:
            try:
                if abs(float(v_local) - float(v_api)) > 0.01:
                    diff = True
            except (ValueError, TypeError):
                pass

        # Formateo de texto para la tabla
        txt_local = f"{str(v_local):>18}" if v_local is not None else f"{'---':>18}"
        txt_api = f"{str(v_api):>15}" if v_api is not None else f"{'---':>15}"
        
        if v_local is None:
            status = "[ NUEVO REGISTRO ]"
        elif diff:
            status = "[ DISCREPANCIA ]"
            discrepancias_detectadas += 1
        else:
            status = "[ OK ]"

        print(f"{label:<15} | {txt_local} | {txt_api} | {status}")

    # 5. Resumen final
    print("-" * 78)
    if discrepancias_detectadas > 0:
        print(f"ALERTA: Se han detectado {discrepancias_detectadas} divergencias en {s_name}.")
        print("El histórico local ha sido actualizado con los nuevos valores de la API.")
    elif local_data is None:
        print("Sincronización inicial: Los datos no existían y han sido creados.")
    else:
        print("Sincronización perfecta. Los datos locales coinciden con la fuente oficial.")
    
    input("\nPresione Enter para continuar...")

def opcion_gestion_estaciones(data_manager):
    while True:
        print("\n--- [4] GESTION DE ESTACIONES ---")
        print("[1] Ver activas | [2] Catalogo | [3] Sync | [4] Volver")
        sub = input("Selecciona una opcion: ").strip()
        if sub == "1":
            for s in data_manager.get_active_station_ids(): print(f"- {s}")
        elif sub == "2":
            catalog = json_handler.load_from_path(data_manager.catalog_path)
            if catalog:
                for uid, info in catalog.get("stations", {}).items():
                    print(f"{info.get('station_id'):<10} | {info.get('name')[:30]:<30}")
        elif sub == "3":
            data_manager.sync_stations()
        elif sub == "4": break

# --- FLUJO PRINCIPAL ---

def main():
    config = ConfigManager()
    data_manager = DataManager(config)
    
    while True:
        try:
            limpiar_pantalla()
            choice = menu_principal()
            if choice in ["1", "2", "3", "4", "5", "X"]:
                limpiar_pantalla()

            if choice == "1": 
                opcion_ingesta_automatica(data_manager)
            elif choice == "2": 
                opcion_ver_historico(data_manager)
            elif choice == "3":
                opcion_comparativa_discrepancias(data_manager)
            elif choice == "4":
                print("\nMódulo Scheduler pendiente.")
            elif choice == "5": 
                opcion_gestion_estaciones(data_manager)
            elif choice == "X": 
                print("\nCerrando sesión..."); sys.exit(0)
            else: print("Opcion no reconocida.")
        except KeyboardInterrupt:
            print("\n\n[INFO] Accion cancelada. Cerrando sesión")
            sys.exit(0)
        
if __name__ == "__main__":
    main()

