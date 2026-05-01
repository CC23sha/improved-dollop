import sys
import qtawesome as qta
from PySide6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, 
                             QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, 
                             QTableWidget, QTableWidgetItem, QLabel, QHeaderView, 
                             QFrame, QMessageBox)
from PySide6.QtCore import Qt, QSize, QThread, Signal
from qt_material import apply_stylesheet

# Importaciones de tu proyecto
from src.utils.config_manager import ConfigManager
from src.processing.data_manager import DataManager
from src.storage import json_handler

class AemetWorker(QThread):
    """Hilo para evitar que la UI se congele al conectar con AEMET"""
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, dm, station_id):
        super().__init__()
        self.dm = dm
        self.station_id = station_id

    def run(self):
        try:
            # CORRECCIÓN: En tu data_manager.py el método es fetch_and_update_all()
            # que internamente recorre las estaciones configuradas.
            success = self.dm.fetch_and_update_all() 
            
            if success:
                # CORRECCIÓN: Para leer el histórico usamos el json_handler sobre la ruta del DM
                data = json_handler.load_from_path(self.dm.history_path) or []
                # Filtramos los datos de la estación seleccionada
                filtered = [r for r in data if r.get('station_id') == self.station_id]
                self.finished.emit(filtered)
            else:
                self.error.emit("No se pudieron sincronizar los datos de AEMET.")
        except Exception as e:
            self.error.emit(str(e))

class NimbusMinimal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.dm = DataManager(self.config)
        
        self.setWindowTitle("NIMBUS")
        self.resize(950, 600)
        
        # Layout Principal
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.layout = QHBoxLayout(self.main_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Barra Lateral (Sidebar)
        self.setup_sidebar()
        
        # Contenido
        self.tabs = QTabWidget()
        self.tabs.tabBar().hide() # Look minimalista sin pestañas visibles
        self.layout.addWidget(self.tabs)

        self.init_pages()

    def setup_sidebar(self):
        sidebar = QFrame()
        sidebar.setFixedWidth(60)
        sidebar.setStyleSheet("background-color: #1a1a1a; border-right: 1px solid #333;")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(5, 20, 5, 20)
        layout.setSpacing(15)

        icons = [
            ('mdi6.view-dashboard', 0),
            ('mdi6.history', 1),
            ('mdi6.alert-decagram', 2),
            ('mdi6.cog', 3)
        ]

        for icon, idx in icons:
            btn = QPushButton(qta.icon(icon, color='#888'), "")
            btn.setFixedSize(50, 50)
            btn.setFlat(True)
            btn.clicked.connect(lambda _, i=idx: self.tabs.setCurrentIndex(i))
            layout.addWidget(btn)
        
        layout.addStretch()
        self.layout.addWidget(sidebar)

    def init_pages(self):
        # PAGINA 1: DASHBOARD
        self.page_dash = QWidget()
        ly_dash = QVBoxLayout(self.page_dash)
        ly_dash.setContentsMargins(30,30,30,30)
        
        header = QLabel("Monitor de Estaciones")
        header.setStyleSheet("font-size: 22px; font-weight: 200; color: #00d4ff;")
        ly_dash.addWidget(header)

        ctrls = QHBoxLayout()
        self.combo = QComboBox()
        # Cargamos estaciones del config.json
        for s in self.config.get_config().get('stations', []):
            self.combo.addItem(s['nombre'], s['id'])
        
        self.btn_upd = QPushButton("Sincronizar AEMET")
        self.btn_upd.clicked.connect(self.start_sync)
        
        ctrls.addWidget(self.combo)
        ctrls.addWidget(self.btn_upd)
        ctrls.addStretch()
        ly_dash.addLayout(ctrls)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Fecha/Hora", "Temp", "Humedad", "Viento"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setShowGrid(False)
        ly_dash.addWidget(self.table)
        
        self.tabs.addTab(self.page_dash, "")

        # PAGINA 2: HISTORIAL (Placeholder)
        self.page_hist = QWidget()
        ly_hist = QVBoxLayout(self.page_hist)
        ly_hist.addWidget(QLabel("Historial Completo (history.json)"))
        self.table_hist = QTableWidget(0, 3)
        self.table_hist.setHorizontalHeaderLabels(["Estación", "Fecha", "Temp Avg"])
        self.table_hist.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        ly_hist.addWidget(self.table_hist)
        
        btn_load = QPushButton("Cargar desde Disco")
        btn_load.clicked.connect(self.load_history_disk)
        ly_hist.addWidget(btn_load)
        self.tabs.addTab(self.page_hist, "")

        # PAGINA 3: ALERTAS (Placeholder)
        self.tabs.addTab(QLabel("Módulo de Alertas y Discrepancias"), "")
        # PAGINA 4: CONFIG
        self.tabs.addTab(QLabel(f"Nimbus v1.0\nAPI: {self.config.get_config().get('source_config', {}).get('name')}"), "")

    def start_sync(self):
        sid = self.combo.currentData()
        self.btn_upd.setEnabled(False)
        self.btn_upd.setText("Conectando...")
        
        self.worker = AemetWorker(self.dm, sid)
        self.worker.finished.connect(self.update_table)
        self.worker.error.connect(lambda e: QMessageBox.critical(self, "Error API", e))
        self.worker.start()

    def update_table(self, data):
        self.btn_upd.setEnabled(True)
        self.btn_upd.setText("Sincronizar AEMET")
        self.table.setRowCount(0)
        # Mostrar los últimos 24 registros
        for i, r in enumerate(reversed(data[-24:])):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(r.get('date', '')[-8:]))
            self.table.setItem(i, 1, QTableWidgetItem(f"{r.get('temp_avg')}°C"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{r.get('humidity_avg')}%"))
            self.table.setItem(i, 3, QTableWidgetItem(f"{r.get('wind_speed_avg')} km/h"))

    def load_history_disk(self):
        data = json_handler.load_from_path(self.dm.history_path) or []
        self.table_hist.setRowCount(0)
        for i, r in enumerate(data[-50:]):
            self.table_hist.insertRow(i)
            self.table_hist.setItem(i, 0, QTableWidgetItem(r.get('station_id')))
            self.table_hist.setItem(i, 1, QTableWidgetItem(r.get('date')[:10]))
            self.table_hist.setItem(i, 2, QTableWidgetItem(str(r.get('temp_avg'))))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_stylesheet(app, theme='dark_cyan.xml')
    window = NimbusMinimal()
    window.show()
    sys.exit(app.exec())