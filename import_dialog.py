from PySide6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox, QTreeWidget, QTreeWidgetItem
from PySide6.QtCore import Qt
import os
import json
import re

class ImportDialog(QDialog):
    def __init__(self, input_folder):
        super().__init__()
        self.setWindowTitle("Importación de aplicación")
        layout = QVBoxLayout(self)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Resumen de componentes encontrados")
        self.tree.setColumnCount(1)

        # Script
        script_path = os.path.join(input_folder, "script.qvs")
        script_item = QTreeWidgetItem(["Script"])
        if os.path.exists(script_path):
            with open(script_path, "r", encoding="utf-8") as f:
                content = f.read()
                tab_names = re.findall(r"^///\$tab (.+)$", content, flags=re.MULTILINE)
                if tab_names:
                    for name in tab_names:
                        tab_item = QTreeWidgetItem([name.strip() or "Sin nombre"])
                        script_item.addChild(tab_item)
                else:
                    script_item.addChild(QTreeWidgetItem(["Sin pestañas detectadas"]))
        self.tree.addTopLevelItem(script_item)

        # Componentes JSON
        for fname, label in [
            ("measures.json", "Medidas"),
            ("dimensions.json", "Dimensiones"),
            ("sheets.json", "Hojas"),
            ("other_objects.json", "Otros objetos"),
            ("variables.json", "Variables")
        ]:
            self.add_json_section(input_folder, fname, label)

        layout.addWidget(self.tree)

        # Botón único
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def add_json_section(self, folder, filename, section_name):
        full_path = os.path.join(folder, filename)
        section_item = QTreeWidgetItem([section_name])
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    items = json.load(f)
                    for i in range(min(5, len(items))):
                        label = f"{section_name} {i+1}"
                        section_item.addChild(QTreeWidgetItem([label]))
                    if len(items) > 5:
                        section_item.addChild(QTreeWidgetItem([f"... y {len(items) - 5} más"]))
            except:
                section_item.addChild(QTreeWidgetItem(["No se pudo leer el contenido"]))
        else:
            section_item.addChild(QTreeWidgetItem(["Archivo no encontrado"]))
        self.tree.addTopLevelItem(section_item)
