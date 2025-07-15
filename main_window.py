from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QComboBox,
    QTableWidget, QTableWidgetItem, QPushButton, QTextEdit,
    QLabel, QMessageBox, QLineEdit, QHBoxLayout
)
from PySide6.QtGui import QIcon, QColor, QPalette
from engine_exporter import export_app_objects, import_app_objects

import configparser
import requests
import os
import logging
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)


class MainWindow(QMainWindow):
    def __init__(self, config_path="config.ini"):
        super().__init__()
        self.setWindowTitle("Qlik Version Control")
        self.config_path = config_path
        self.config = configparser.ConfigParser()
        self.config.read(self.config_path)

        # Main layout
        central_widget = QWidget()
        layout = QVBoxLayout()

        # Server selector
        self.server_selector = QComboBox()
        self.server_selector.addItems(self.config.sections())
        layout.addWidget(QLabel("Servidor Qlik"))
        layout.addWidget(self.server_selector)

        # Botón para cargar apps
        self.load_apps_button = QPushButton("Cargar aplicaciones")
        self.load_apps_button.clicked.connect(self.load_apps)
        layout.addWidget(self.load_apps_button)

        # Filtro
        filter_layout = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("🔍 Filtrar por nombre o stream...")
        filter_layout.addWidget(self.filter_input)
        layout.addLayout(filter_layout)

        # Tabla de apps
        self.app_table = QTableWidget()
        self.app_table.setColumnCount(5)
        self.app_table.setHorizontalHeaderLabels(["Nombre", "ID", "Stream / Área", "Publicado", "Último Refresco"])
        self.app_table.setSortingEnabled(True)
        layout.addWidget(QLabel("Aplicaciones disponibles"))
        layout.addWidget(self.app_table)

        # Export/import buttons
        self.export_button = QPushButton("Exportar App")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_selected_app)

        layout.addWidget(self.export_button)

        self.import_button = QPushButton("Importar App")
        self.import_button.clicked.connect(self.import_selected_app)
        layout.addWidget(self.import_button)


        # Config editor
        layout.addWidget(QLabel("Editor de configuración"))
        self.config_editor = QTextEdit()
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config_editor.setPlainText(f.read())
        layout.addWidget(self.config_editor)

        self.save_config_button = QPushButton("Guardar configuración")
        self.save_config_button.clicked.connect(self.save_config)
        layout.addWidget(self.save_config_button)

        # Events





        self.apps_data = []

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        self.filter_input.textChanged.connect(self.filter_table)
        self.app_table.itemDoubleClicked.connect(self.show_app_details)
        self.app_table.horizontalHeader().setSectionsMovable(True)
        self.env_label = QLabel("Entorno no conectado")
        self.env_label.setStyleSheet(
            "font-weight: bold; font-size: 16px; padding: 6px; background-color: #cccccc; color: white;")
        layout.addWidget(self.env_label)

        self.app_table.itemSelectionChanged.connect(self.on_app_selected)

        self.settings_file = "settings.json"
        self.load_ui_settings()


    def on_app_selected(self):
        selected = self.app_table.selectedItems()
        self.export_button.setEnabled(bool(selected))


    def get_connection_details(self):
        section = self.server_selector.currentText()
        host = self.config.get(section, "host")
        cert_file = self.config.get(section, "cert_file")
        key_file = self.config.get(section, "key_file")
        user_id = self.config.get(section, "user_id")
        user_directory = self.config.get(section, "user_directory")
        header_user = f"UserDirectory={user_directory};UserId={user_id}"
        color = self.config.get(section, "color", fallback="#333333")
        icon = self.config.get(section, "icon", fallback=None)

        return {
            "host": host,
            "cert_file": cert_file,
            "key_file": key_file,
            "user_id": user_id,
            "user_directory": user_directory,
            "header_user": header_user,
            "color": color,
            "icon": icon
        }


    def save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                f.write(self.config_editor.toPlainText())
            QMessageBox.information(self, "Guardado", "Configuración guardada correctamente.")
            self.config.read(self.config_path)
            self.server_selector.clear()
            self.server_selector.addItems(self.config.sections())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar: {e}")

    def export_selected_app(self):
        selected = self.app_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Exportar", "Selecciona una aplicación primero.")
            return

        row = selected[0].row()
        app = self.apps_data[row]
        app_id = app.get("id")
        app_name = app.get("name").replace(" ", "_")
        output_folder = os.path.join("exported", app_name)
        os.makedirs(output_folder, exist_ok=True)

        try:
            # Guardar metadata QRS
            with open(os.path.join(output_folder, "metadata.json"), "w", encoding="utf-8") as f:
                json.dump(app, f, indent=2)

            # Conexión
            conn = self.get_connection_details()
            export_app_objects(app_id, output_folder, conn)

            QMessageBox.information(self, "Exportación completada",
                                    f"Aplicación '{app_name}' exportada correctamente en:\n{output_folder}")
            logging.info(f"Exportación completa para {app_name} ({app_id})")
        except Exception as e:
            logging.exception("Error al exportar la app:")
            QMessageBox.critical(self, "Error", f"No se pudo exportar la app:\n{e}")

    def import_selected_app(self):
        selected = self.app_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Importar", "Selecciona una aplicación primero.")
            return

        row = selected[0].row()
        app = self.apps_data[row]
        app_id = app.get("id")
        app_name = app.get("name").replace(" ", "_")
        input_folder = os.path.join("exported", app_name)

        if not os.path.isdir(input_folder):
            QMessageBox.warning(self, "Error",
                                f"No se encontró el directorio de exportación para '{app_name}' en:\n{input_folder}")
            return

        try:
            conn = self.get_connection_details()
            import_app_objects(app_id, input_folder, conn)
            QMessageBox.information(self, "Importación completada",
                                    f"Aplicación '{app_name}' importada correctamente desde:\n{input_folder}")
            logging.info(f"Importación completa para {app_name} ({app_id})")
        except Exception as e:
            logging.exception("Error al importar la app:")
            QMessageBox.critical(self, "Error", f"No se pudo importar la app:\n{e}")

    def load_apps(self):

        logging.info("Cargando lista de aplicaciones desde Qlik Sense")
        try:
            conn = self.get_connection_details()
            logging.debug(f"Datos de conexión: {conn}")

            xrfkey = "123456789ABCDEFG"
            url = f"{conn['host']}/qrs/app/full?xrfkey={xrfkey}"
            headers = {
                "X-Qlik-User": conn["header_user"],
                "X-Qlik-Xrfkey": xrfkey,
                "Content-Type": "application/json"
            }
            logging.debug(f"Haciendo GET a: {url}")
            logging.debug(f"Cabeceras: {headers}")

            response = requests.get(
                url,
                cert=(conn["cert_file"], conn["key_file"]),
                verify=False,
                headers=headers,
                timeout=10
            )

            logging.info(f"Respuesta HTTP: {response.status_code}")

            if response.status_code == 200:
                try:
                    self.apps_data = response.json()
                    self.app_table.setRowCount(len(self.apps_data))
                    logging.info(f"Se recibieron {len(self.apps_data)} aplicaciones")
                    for row, app in enumerate(self.apps_data):
                        nombre = app.get("name", "")
                        stream_data = app.get("stream")
                        stream = stream_data.get("name") if stream_data else "Personal"
                        publicado = app.get("publishTime", "") or "-"
                        refresco = app.get("lastReloadTime", "") or "-"

                        self.app_table.setItem(row, 0, QTableWidgetItem(nombre))
                        self.app_table.setItem(row, 1, QTableWidgetItem(app.get("id", "")))
                        self.app_table.setItem(row, 2, QTableWidgetItem(stream))
                        self.app_table.setItem(row, 3, QTableWidgetItem(publicado))
                        self.app_table.setItem(row, 4, QTableWidgetItem(refresco))

                    self.update_theme_for_server()
                except Exception as e:
                    logging.exception("Error al parsear JSON:")
                    QMessageBox.critical(self, "Error JSON", f"No se pudo decodificar el JSON:\n{response.text}")
            else:
                logging.warning(f"Respuesta no exitosa: {response.status_code}")
                logging.debug(response.text)
                QMessageBox.warning(self, "Error", f"HTTP {response.status_code}:\n{response.text}")

        except Exception as e:
            logging.exception("Excepción durante la carga de apps")
            QMessageBox.critical(self, "Error", f"No se pudieron cargar las aplicaciones:\n{e}")


    def show_app_details(self, item):
        row = item.row()
        app = self.apps_data[row]

        nombre = app.get("name", "")
        app_id = app.get("id", "")
        stream = app.get("stream", {}).get("name", "Personal")
        owner = app.get("owner", {}).get("userId", "Desconocido")
        published = app.get("publishTime", "") or "-"
        last_reload = app.get("lastReloadTime", "") or "-"
        created = app.get("createdDate", "") or "-"
        modified = app.get("modifiedDate", "") or "-"
        description = app.get("description", "") or "-"

        details = (
            f"<b>Nombre:</b> {nombre}<br>"
            f"<b>ID:</b> {app_id}<br>"
            f"<b>Área / Stream:</b> {stream}<br>"
            f"<b>Propietario:</b> {owner}<br>"
            f"<b>Creado:</b> {created}<br>"
            f"<b>Modificado:</b> {modified}<br>"
            f"<b>Publicado:</b> {published}<br>"
            f"<b>Último refresco:</b> {last_reload}<br>"
            f"<b>Descripción:</b> {description}"
        )

        QMessageBox.information(self, "Detalles de la App", details)

    def filter_table(self):
        filtro = self.filter_input.text().lower()
        for row in range(self.app_table.rowCount()):
            nombre = self.app_table.item(row, 0).text().lower()
            stream = self.app_table.item(row, 1).text().lower()
            mostrar = filtro in nombre or filtro in stream
            self.app_table.setRowHidden(row, not mostrar)

    def closeEvent(self, event):
        self.save_ui_settings()
        super().closeEvent(event)

    def save_ui_settings(self):
        settings = {
            "window_geometry": [
                self.geometry().x(),
                self.geometry().y(),
                self.geometry().width(),
                self.geometry().height()
            ],
            "column_widths": [self.app_table.columnWidth(i) for i in range(self.app_table.columnCount())],
            "last_server": self.server_selector.currentText(),
            "column_order": [
                self.app_table.horizontalHeader().visualIndex(i)
                for i in range(self.app_table.columnCount())
            ]
        }
        try:
            with open(self.settings_file, "w") as f:
                json.dump(settings, f, indent=2)
            logging.info("Ajustes de interfaz guardados")
        except Exception as e:
            logging.error(f"No se pudo guardar settings.json: {e}")

    def load_ui_settings(self):
        try:
            with open(self.settings_file, "r") as f:
                settings = json.load(f)
            geom = settings.get("window_geometry")
            if geom and len(geom) == 4:
                self.setGeometry(*geom)

            column_widths = settings.get("column_widths", [])
            for i, width in enumerate(column_widths):
                self.app_table.setColumnWidth(i, width)

            last_server = settings.get("last_server")
            if last_server in self.config.sections():
                self.server_selector.setCurrentText(last_server)

            order = settings.get("column_order")
            if order and len(order) == self.app_table.columnCount():
                for logical_index, visual_index in enumerate(order):
                    self.app_table.horizontalHeader().moveSection(
                        self.app_table.horizontalHeader().visualIndex(logical_index),
                        visual_index
                    )

            logging.info("Ajustes de interfaz cargados")
        except Exception as e:
            logging.warning(f"No se pudieron cargar ajustes de UI: {e}")

    def update_theme_for_server(self):
        conn = self.get_connection_details()

        # Cambiar ícono
        if conn["icon"]:
            icon_path = os.path.join("ui", "icons", conn["icon"])
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))

        # Cambiar color de fondo
        color = QColor(conn["color"])
        palette = self.palette()
        palette.setColor(QPalette.Window, color)
        self.setPalette(palette)

        # (Opcional) Actualizar título con nombre del servidor
        self.setWindowTitle(f"Qlik Version Control – {self.server_selector.currentText()}")

        # Mostrar el entorno (nombre de la sección actual)
        entorno = self.server_selector.currentText()
        self.env_label.setText(f"Entorno: {entorno.upper()}")
        self.env_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: 16px;
            padding: 6px;
            background-color: {conn['color']};
            color: white;
        """)




